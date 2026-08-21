"""Phase 5 platform delivery bench for Telegram, Discord, and Imgur.

Uses the local FastAPI endpoints through TestClient to create and decode each
trial's stego JPEG. Platform credentials are read only from environment
variables and are never logged.
"""
from __future__ import annotations

import csv
import io
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests
from fastapi.testclient import TestClient

from app import app
from phase1_native_dct_experiment import extract_native_dct

ROOT = Path(__file__).resolve().parent
COVER = Path(r"C:\Users\aakaa\Pictures\Wallpaper.Engine.v2.5.28\Wallpaper.Engine.v2.5.28\Wallpaper.Engine.v2.5.28\projects\defaultprojects\arsenal\preview.jpg")
MESSAGE = "bench"
PASSPHRASE = "ShadowPost Phase 5 test passphrase"
TRIALS_PER_PLATFORM = 3
CODEWORD_BITS = 48 * 8


class StructuralFailure(RuntimeError):
    """A platform configuration or delivery failure, rather than BER damage."""


def required_codeword_bits(message: str) -> int:
    # [2-byte length][12-byte nonce][ciphertext][16-byte tag], packed in 32-byte RS chunks.
    chunks = (2 + 12 + len(message.encode("utf-8")) + 16 + 31) // 32
    return chunks * CODEWORD_BITS


def telegram_round_trip(image: bytes, filename: str) -> bytes:
    token, chat_id = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise StructuralFailure("missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
    base = f"https://api.telegram.org/bot{token}"
    response = requests.post(f"{base}/sendPhoto", data={"chat_id": chat_id}, files={"photo": (filename, image, "image/jpeg")}, timeout=60)
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


def imgur_round_trip(image: bytes, filename: str) -> bytes:
    client_id = os.getenv("IMGUR_CLIENT_ID")
    if not client_id:
        raise StructuralFailure("missing IMGUR_CLIENT_ID")
    response = requests.post("https://api.imgur.com/3/image", headers={"Authorization": f"Client-ID {client_id}"},
                             files={"image": (filename, image, "image/jpeg")}, timeout=60)
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        raise StructuralFailure("Imgur upload rejected")
    download = requests.get(payload["data"]["link"], timeout=60)
    download.raise_for_status()
    return download.content


PLATFORMS = {"telegram": telegram_round_trip, "discord": discord_round_trip, "imgur": imgur_round_trip}


def main() -> None:
    out_dir = ROOT / "phase5_results"
    out_dir.mkdir(exist_ok=True)
    client = TestClient(app)
    original_bits_count = required_codeword_bits(MESSAGE)
    rows: list[dict[str, object]] = []
    for platform, deliver in PLATFORMS.items():
        for trial in range(1, TRIALS_PER_PLATFORM + 1):
            timestamp = datetime.now(timezone.utc).isoformat()
            row: dict[str, object] = {"platform": platform, "trial": trial, "cover_name": COVER.name,
                                      "payload_size_bytes": len(MESSAGE.encode("utf-8")), "success": False,
                                      "ber": "", "failure_reason": "", "timestamp": timestamp}
            try:
                with COVER.open("rb") as source:
                    encoded = client.post("/encode", files={"cover": (COVER.name, source, "image/jpeg")},
                                          data={"message": MESSAGE, "passphrase": PASSPHRASE})
                if encoded.status_code != 200:
                    raise StructuralFailure(f"local /encode failed: HTTP {encoded.status_code}: {encoded.text}")
                local_stego = encoded.content
                delivered = deliver(local_stego, "shadowpost_stego.jpg")
                with tempfile.TemporaryDirectory() as temp_dir:
                    local_path, delivered_path = Path(temp_dir) / "local.jpg", Path(temp_dir) / "delivered.jpg"
                    local_path.write_bytes(local_stego)
                    delivered_path.write_bytes(delivered)
                    original_bits = extract_native_dct(local_path, original_bits_count, (0, 2))
                    delivered_bits = extract_native_dct(delivered_path, original_bits_count, (0, 2))
                    row["ber"] = f"{np.count_nonzero(original_bits != delivered_bits) / original_bits_count:.8f}"
                decoded = client.post("/decode", files={"stego": ("delivered.jpg", delivered, "image/jpeg")},
                                      data={"passphrase": PASSPHRASE})
                if decoded.status_code != 200:
                    raise StructuralFailure(f"local /decode failed: HTTP {decoded.status_code}: {decoded.text}")
                if decoded.json().get("message") != MESSAGE:
                    raise StructuralFailure("decoded plaintext did not match the test message")
                row["success"] = True
            except Exception as exc:  # Persist every failure for later matrix analysis.
                row["failure_reason"] = f"{type(exc).__name__}: {exc}"
            rows.append(row)
            print(f"{platform} trial {trial}: success={row['success']} ber={row['ber']} {row['failure_reason']}")

    destination = out_dir / "platform_trials.csv"
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {destination}")


if __name__ == "__main__":
    main()
