"""Manual upload/download bridge for the ShadowPost Phase 5 platform bench.

Prepare a stego image, upload it manually, download the delivered image, then
check it. The helper invokes the existing FastAPI endpoints via TestClient;
it does not implement or alter the locked embedding, RS, or encryption layers.
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from app import app
from phase1_native_dct_experiment import extract_native_dct

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "phase5_results"
UPLOADS = RESULTS / "manual_upload"
TRIAL_CSV = RESULTS / "platform_trials.csv"
CODEWORD_BITS = 48 * 8
CSV_FIELDS = ("platform", "trial", "cover_name", "payload_size_bytes", "success", "ber", "failure_reason", "timestamp")


def safe_platform_name(value: str) -> str:
    cleaned = "".join(char for char in value.lower() if char.isalnum() or char in "_-")
    if not cleaned:
        raise ValueError("platform name must contain letters or digits")
    return cleaned


def prepare(args: argparse.Namespace) -> None:
    platform = safe_platform_name(args.platform)
    cover = Path(args.cover).resolve()
    if not cover.is_file():
        raise ValueError(f"cover image not found: {cover}")
    UPLOADS.mkdir(parents=True, exist_ok=True)
    with cover.open("rb") as handle:
        response = TestClient(app).post("/encode", files={"cover": (cover.name, handle, "image/jpeg")},
                                        data={"message": args.message, "passphrase": args.passphrase})
    if response.status_code != 200:
        raise RuntimeError(f"/encode failed: HTTP {response.status_code}: {response.text}")
    destination = UPLOADS / f"{platform}.jpg"
    destination.write_bytes(response.content)
    # Record exactly how many DCT bits form this message and the original cover;
    # no passphrase or plaintext is persisted.
    plaintext_bytes = len(args.message.encode("utf-8"))
    codewords = (2 + 12 + plaintext_bytes + 16 + 31) // 32
    (UPLOADS / f"{platform}.json").write_text(json.dumps({"cover_name": cover.name, "payload_size_bytes": plaintext_bytes,
        "codeword_bits": codewords * CODEWORD_BITS}, indent=2) + "\n", encoding="utf-8")
    print(f"prepared {destination}")


def append_row(row: dict[str, object]) -> None:
    RESULTS.mkdir(exist_ok=True)
    write_header = not TRIAL_CSV.exists() or TRIAL_CSV.stat().st_size == 0
    with TRIAL_CSV.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def check(args: argparse.Namespace) -> None:
    platform = safe_platform_name(args.platform)
    downloaded = Path(args.downloaded_image).resolve()
    metadata_path, original_path = UPLOADS / f"{platform}.json", UPLOADS / f"{platform}.jpg"
    if not downloaded.is_file():
        raise ValueError(f"downloaded image not found: {downloaded}")
    if not metadata_path.is_file() or not original_path.is_file():
        raise ValueError(f"run /prepare for platform '{platform}' first")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    row: dict[str, object] = {"platform": platform, "trial": "manual", "cover_name": metadata["cover_name"],
        "payload_size_bytes": metadata["payload_size_bytes"], "success": False, "ber": "", "failure_reason": "",
        "timestamp": datetime.now(timezone.utc).isoformat()}
    try:
        bits = int(metadata["codeword_bits"])
        before = extract_native_dct(original_path, bits, (0, 2))
        after = extract_native_dct(downloaded, bits, (0, 2))
        row["ber"] = f"{np.count_nonzero(before != after) / bits:.8f}"
        with downloaded.open("rb") as handle:
            response = TestClient(app).post("/decode", files={"stego": (downloaded.name, handle, "image/jpeg")},
                                            data={"passphrase": args.passphrase})
        if response.status_code != 200:
            raise RuntimeError(f"/decode failed: HTTP {response.status_code}: {response.text}")
        row["success"] = True
    except Exception as exc:
        row["failure_reason"] = f"{type(exc).__name__}: {exc}"
    append_row(row)
    print(f"platform={platform} success={row['success']} ber={row['ber']} reason={row['failure_reason']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    prepare_parser = actions.add_parser("prepare", help="create a stego JPEG for manual upload")
    prepare_parser.add_argument("--platform", required=True)
    prepare_parser.add_argument("--cover", required=True)
    prepare_parser.add_argument("--message", required=True)
    prepare_parser.add_argument("--passphrase", required=True)
    prepare_parser.set_defaults(func=prepare)
    check_parser = actions.add_parser("check", help="decode a manually-downloaded image and append its result")
    check_parser.add_argument("--platform", required=True)
    check_parser.add_argument("--downloaded-image", required=True)
    check_parser.add_argument("--passphrase", required=True)
    check_parser.set_defaults(func=check)
    parsed = parser.parse_args()
    parsed.func(parsed)


if __name__ == "__main__":
    main()
