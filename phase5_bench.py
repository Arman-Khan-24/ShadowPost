"""Phase 5 delivery bench for Telegram and Discord.

Credentials are obtained only from TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, and
DISCORD_WEBHOOK_URL in the process environment; they are never logged.
"""
from __future__ import annotations

import csv
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from app import app, capacity_for_jpeg
from phase1_native_dct_experiment import extract_native_dct

ROOT = Path(__file__).resolve().parent
COVERS_DIR = Path(os.getenv(
    "SHADOWPOST_COVERS_DIR",
    r"C:\Users\aakaa\Pictures\Wallpaper.Engine.v2.5.28\Wallpaper.Engine.v2.5.28\Wallpaper.Engine.v2.5.28\projects\defaultprojects",
))
RESULTS_FILE = ROOT / "phase5_results" / "platform_trials.csv"
PHASE1_TRIALS_FILE = ROOT / "phase1_results_positions_0_2_tie_fixed" / "phase1_trials.csv"
PASSPHRASE = "ShadowPost Phase 5 test passphrase"
CODEWORD_BITS = 48 * 8
CSV_FIELDS = ("platform", "trial", "cover_name", "payload_size_bytes", "success", "ber", "failure_reason", "timestamp")


class StructuralFailure(RuntimeError):
    """A platform configuration or delivery failure, rather than BER damage."""


def required_codeword_bits(message: str) -> int:
    """Number of embedded RS bits required by one whole-message container."""
    chunks = math.ceil((2 + 12 + len(message.encode("utf-8")) + 16) / 32)
    return chunks * CODEWORD_BITS


def message_of_size(size: int) -> str:
    """Return an ASCII message with exactly ``size`` UTF-8 bytes."""
    return ("ShadowPost-" * ((size // 11) + 1))[:size]


def payload_sizes(cover: Path) -> tuple[int, int, int]:
    """Return the requested 10-byte, 100-byte, and near-capacity payloads."""
    maximum = capacity_for_jpeg(cover)["plaintext_bytes"]
    if maximum < 100:
        raise StructuralFailure(f"cover capacity is only {maximum} bytes; cannot run 100-byte medium payload")
    # One byte below the computed limit exercises the largest practical message
    # while retaining the requested "near max" behavior.
    return 10, 100, max(100, maximum - 1)


def telegram_round_trip(image: bytes, filename: str) -> bytes:
    token, chat_id = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise StructuralFailure("missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
    base = f"https://api.telegram.org/bot{token}"
    response = requests.post(f"{base}/sendPhoto", data={"chat_id": chat_id},
                             files={"photo": (filename, image, "image/jpeg")}, timeout=60)
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise StructuralFailure(f"Telegram upload rejected: {payload.get('description', 'unknown error')}")
    file_id = payload["result"]["photo"][-1]["file_id"]
    metadata = requests.get(f"{base}/getFile", params={"file_id": file_id}, timeout=30)
    metadata.raise_for_status()
    file_path = metadata.json()["result"]["file_path"]
    download = requests.get(f"https://api.telegram.org/file/bot{token}/{file_path}", timeout=60)
    download.raise_for_status()
    return download.content


def discord_round_trip(image: bytes, filename: str) -> bytes:
    webhook = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook:
        raise StructuralFailure("missing DISCORD_WEBHOOK_URL")
    separator = "&" if "?" in webhook else "?"
    response = requests.post(f"{webhook}{separator}wait=true", files={"file": (filename, image, "image/jpeg")}, timeout=60)
    response.raise_for_status()
    attachments = response.json().get("attachments", [])
    if not attachments:
        raise StructuralFailure("Discord webhook response had no attachment")
    download = requests.get(attachments[0]["url"], timeout=60)
    download.raise_for_status()
    return download.content


PLATFORMS = {"telegram": telegram_round_trip, "discord": discord_round_trip}


def cover_images() -> list[Path]:
    """Return the exact 15 covers recorded in the finalized Phase 1 run."""
    if not PHASE1_TRIALS_FILE.is_file():
        raise StructuralFailure(f"final Phase 1 trial manifest not found: {PHASE1_TRIALS_FILE}")
    covers: list[Path] = []
    seen: set[str] = set()
    with PHASE1_TRIALS_FILE.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            relative = row["cover"]
            if relative in seen:
                continue
            seen.add(relative)
            cover = COVERS_DIR / Path(relative)
            if not cover.is_file():
                raise StructuralFailure(f"Phase 1 cover is missing: {cover}")
            covers.append(cover)
    if len(covers) != 15:
        raise StructuralFailure(f"expected 15 unique Phase 1 covers; found {len(covers)} in {PHASE1_TRIALS_FILE}")
    return covers


def run_trial(client: TestClient, platform: str, deliver, cover: Path, trial: int, payload_size: int) -> dict[str, object]:
    message = message_of_size(payload_size)
    row: dict[str, object] = {
        "platform": platform, "trial": trial, "cover_name": cover.relative_to(COVERS_DIR).as_posix(),
        "payload_size_bytes": payload_size, "success": False, "ber": "",
        "failure_reason": "", "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        with cover.open("rb") as source:
            encoded = client.post("/encode", files={"cover": (cover.name, source, "image/jpeg")},
                                  data={"message": message, "passphrase": PASSPHRASE})
        if encoded.status_code != 200:
            raise StructuralFailure(f"local /encode failed: HTTP {encoded.status_code}: {encoded.text}")
        local_stego = encoded.content
        delivered = deliver(local_stego, f"shadowpost_{cover.stem}_{payload_size}.jpg")
        bit_count = required_codeword_bits(message)
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            local_path, delivered_path = temporary / "local.jpg", temporary / "delivered.jpg"
            local_path.write_bytes(local_stego)
            delivered_path.write_bytes(delivered)
            source_bits = extract_native_dct(local_path, bit_count, (0, 2))
            recovered_bits = extract_native_dct(delivered_path, bit_count, (0, 2))
            row["ber"] = f"{np.count_nonzero(source_bits != recovered_bits) / bit_count:.8f}"
        decoded = client.post("/decode", files={"stego": ("delivered.jpg", delivered, "image/jpeg")},
                              data={"passphrase": PASSPHRASE})
        if decoded.status_code != 200:
            raise StructuralFailure(f"local /decode failed: HTTP {decoded.status_code}: {decoded.text}")
        if decoded.json().get("message") != message:
            raise StructuralFailure("decoded plaintext did not match the test message")
        row["success"] = True
    except Exception as exc:
        row["failure_reason"] = f"{type(exc).__name__}: {exc}"
    print(f"{platform} trial {trial} | {cover.name} | {payload_size} bytes | success={row['success']} | BER={row['ber']} {row['failure_reason']}")
    return row


def main() -> None:
    load_dotenv(ROOT / ".env")
    if not COVERS_DIR.is_dir():
        raise SystemExit(f"covers directory not found: {COVERS_DIR}")
    covers = cover_images()
    if not covers:
        raise SystemExit("no Phase 1 covers were listed in the trial manifest")

    RESULTS_FILE.parent.mkdir(exist_ok=True)
    rows: list[dict[str, object]] = []
    client = TestClient(app)
    for platform, deliver in PLATFORMS.items():
        trial = 0
        for cover in covers:
            try:
                sizes = payload_sizes(cover)
            except StructuralFailure as exc:
                trial += 1
                rows.append({"platform": platform, "trial": trial, "cover_name": cover.name,
                             "payload_size_bytes": "", "success": False, "ber": "",
                             "failure_reason": str(exc), "timestamp": datetime.now(timezone.utc).isoformat()})
                continue
            for size in sizes:
                trial += 1
                rows.append(run_trial(client, platform, deliver, cover, trial, size))

    with RESULTS_FILE.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {RESULTS_FILE}")


if __name__ == "__main__":
    main()
