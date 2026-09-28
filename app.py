"""Phase 4 & Adaptive Multi-Platform FastAPI interface for ShadowPost."""
from __future__ import annotations

import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import jpeglib
import numpy as np
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from PIL import Image
from reedsolo import RSCodec, ReedSolomonError

from phase1_native_dct_experiment import embed_native_dct, extract_native_dct, luminance_coefficients
from phase2_rs_roundtrip import bits_to_bytes, bytes_to_bits
from phase3_aes_gcm_roundtrip import NONCE_BYTES, TAG_BYTES, RS_PARITY_BYTES, derive_aes256_key

ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://shadow-post-gules.vercel.app",
]

app = FastAPI(title="ShadowPost Adaptive Platform")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?|https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

PAIR_INDICES = (0, 2)
CODEWORD_BITS = 48 * 8
LENGTH_PREFIX_BYTES = 2


@dataclass(frozen=True)
class PlatformProfile:
    id: str
    name: str
    max_width: Optional[int]
    max_height: Optional[int]
    aspect_ratio: Optional[str]  # e.g., '1:1', '4:5', None
    pre_compress_quality: Optional[int]
    dct_gap: int
    rs_parity_bytes: int
    redundancy: int  # 1x or 3x block repetition


PLATFORM_PROFILES: dict[str, PlatformProfile] = {
    "default": PlatformProfile(
        id="default",
        name="General / Lossless (Discord & WhatsApp Doc)",
        max_width=None,
        max_height=None,
        aspect_ratio=None,
        pre_compress_quality=None,
        dct_gap=14,
        rs_parity_bytes=16,
        redundancy=1,
    ),
    "discord": PlatformProfile(
        id="discord",
        name="Discord Attachment",
        max_width=None,
        max_height=None,
        aspect_ratio=None,
        pre_compress_quality=None,
        dct_gap=14,
        rs_parity_bytes=16,
        redundancy=1,
    ),
    "whatsapp_doc": PlatformProfile(
        id="whatsapp_doc",
        name="WhatsApp Document Mode",
        max_width=None,
        max_height=None,
        aspect_ratio=None,
        pre_compress_quality=None,
        dct_gap=14,
        rs_parity_bytes=16,
        redundancy=1,
    ),
    "telegram": PlatformProfile(
        id="telegram",
        name="Telegram (sendPhoto)",
        max_width=1280,
        max_height=1280,
        aspect_ratio=None,
        pre_compress_quality=85,
        dct_gap=14,
        rs_parity_bytes=16,
        redundancy=1,
    ),
    "instagram": PlatformProfile(
        id="instagram",
        name="Instagram Feed (Square 1080x1080)",
        max_width=1080,
        max_height=1080,
        aspect_ratio="1:1",
        pre_compress_quality=80,
        dct_gap=14,
        rs_parity_bytes=16,
        redundancy=1,
    ),
    "twitter": PlatformProfile(
        id="twitter",
        name="Twitter / X (Feed Image)",
        max_width=1200,
        max_height=1200,
        aspect_ratio=None,
        pre_compress_quality=82,
        dct_gap=14,
        rs_parity_bytes=16,
        redundancy=1,
    ),
}


def pre_condition_image(source: Path, destination: Path, profile: PlatformProfile) -> None:
    """Pre-condition cover image to comply with the platform's ingest canvas.

    Enforces multiples of 16 for DCT block alignment and pre-compresses to
    the platform's baseline quality so subsequent platform uploads avoid
    destructive spatial fractional downsampling.
    """
    with Image.open(source) as img:
        img = img.convert("RGB")
        w, h = img.size

        # Apply aspect ratio crop if required (e.g. Instagram 1:1)
        if profile.aspect_ratio == "1:1":
            min_side = min(w, h)
            left = (w - min_side) // 2
            top = (h - min_side) // 2
            img = img.crop((left, top, left + min_side, top + min_side))
            w, h = img.size

        # Apply max bounds preserving aspect ratio
        ratio = 1.0
        if profile.max_width and w > profile.max_width:
            ratio = min(ratio, profile.max_width / w)
        if profile.max_height and h > profile.max_height:
            ratio = min(ratio, profile.max_height / h)
        if ratio < 1.0:
            w = int(w * ratio)
            h = int(h * ratio)

        # Crucial for 8x8 DCT grid alignment: snap to nearest multiple of 16
        target_w = max(16, (w // 16) * 16)
        target_h = max(16, (h // 16) * 16)

        if (w, h) != (target_w, target_h):
            img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)

        quality = profile.pre_compress_quality or 95
        img.save(destination, "JPEG", quality=quality, subsampling=0, optimize=True)


def capacity_for_jpeg(path: Path) -> dict[str, int]:
    coeffs = luminance_coefficients(jpeglib.read_dct(str(path)))
    luminance_blocks = int(coeffs.shape[0] * coeffs.shape[1])
    usable_bits = luminance_blocks * len(PAIR_INDICES)
    codewords = usable_bits // CODEWORD_BITS
    return {
        "luminance_blocks": luminance_blocks,
        "usable_bits": usable_bits,
        "codewords": codewords,
        "plaintext_bytes": max(
            0, codewords * 32 - LENGTH_PREFIX_BYTES - NONCE_BYTES - TAG_BYTES
        ),
    }


def _decode_codeword(codec: RSCodec, codeword: bytes) -> bytes:
    chunk, _, _ = codec.decode(codeword)
    return bytes(chunk)


def encode_file(
    source: Path,
    destination: Path,
    message: bytes,
    passphrase: str,
    platform: str = "default",
) -> dict[str, object]:
    profile = PLATFORM_PROFILES.get(platform.lower(), PLATFORM_PROFILES["default"])

    # If the profile requires pre-conditioning, create the conditioned canvas first
    if profile.max_width or profile.aspect_ratio or profile.pre_compress_quality:
        conditioned_cover = source.parent / f"conditioned_{source.name}"
        pre_condition_image(source, conditioned_cover, profile)
        active_source = conditioned_cover
    else:
        active_source = source

    capacity = capacity_for_jpeg(active_source)
    if len(message) > capacity["plaintext_bytes"]:
        raise ValueError(
            f"message is {len(message)} bytes; max capacity for this image profile is {capacity['plaintext_bytes']} bytes"
        )

    key = derive_aes256_key(passphrase)
    nonce = os.urandom(NONCE_BYTES)
    ciphertext_and_tag = AESGCM(key).encrypt(nonce, message, None)
    framed = len(message).to_bytes(LENGTH_PREFIX_BYTES, "big") + nonce + ciphertext_and_tag
    chunks = [framed[i : i + 32].ljust(32, b"\0") for i in range(0, len(framed), 32)]
    codec = RSCodec(profile.rs_parity_bytes)
    bits = np.concatenate([bytes_to_bits(bytes(codec.encode(chunk))) for chunk in chunks])

    embed_native_dct(active_source, destination, bits, profile.dct_gap, PAIR_INDICES)

    with Image.open(destination) as final_img:
        dims = final_img.size

    return {
        **capacity,
        "platform": profile.id,
        "platform_name": profile.name,
        "dct_gap": profile.dct_gap,
        "dimensions": dims,
    }


def decode_file(source: Path, passphrase: str) -> str:
    capacity = capacity_for_jpeg(source)
    if capacity["codewords"] < 1:
        raise ValueError("image has no usable RS codeword capacity")

    key, codec = derive_aes256_key(passphrase), RSCodec(RS_PARITY_BYTES)
    first = bits_to_bytes(extract_native_dct(source, CODEWORD_BITS, PAIR_INDICES))
    first_chunk = _decode_codeword(codec, first)
    length = int.from_bytes(first_chunk[:LENGTH_PREFIX_BYTES], "big")

    if length > capacity["plaintext_bytes"]:
        raise ValueError("decoded length exceeds this image's capacity")

    count = math.ceil((length + LENGTH_PREFIX_BYTES + NONCE_BYTES + TAG_BYTES) / 32)
    bits = extract_native_dct(source, count * CODEWORD_BITS, PAIR_INDICES)
    recovered = b"".join(
        _decode_codeword(codec, bits_to_bytes(bits[i : i + CODEWORD_BITS]))
        for i in range(0, len(bits), CODEWORD_BITS)
    )
    nonce = recovered[LENGTH_PREFIX_BYTES : LENGTH_PREFIX_BYTES + NONCE_BYTES]
    ciphertext_and_tag = recovered[
        LENGTH_PREFIX_BYTES + NONCE_BYTES : LENGTH_PREFIX_BYTES + NONCE_BYTES + length + TAG_BYTES
    ]
    return AESGCM(key).decrypt(nonce, ciphertext_and_tag, None).decode("utf-8")


MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB


async def _save_upload(upload: UploadFile, directory: Path, name: str) -> Path:
    data = await upload.read()
    if not data:
        raise HTTPException(400, "Uploaded image is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, f"Image exceeds maximum allowed size ({MAX_UPLOAD_BYTES // (1024 * 1024)}MB)")
    if not data.startswith(b"\xff\xd8"):
        raise HTTPException(400, "Invalid image format: file must be a valid JPEG (missing SOI marker)")
    path = directory / name
    path.write_bytes(data)
    return path


@app.get("/")
async def index():
    """Serve the adaptive platform web UI."""
    index_path = Path(__file__).resolve().parent / "index.html"
    if index_path.is_file():
        return FileResponse(index_path)
    html_path = Path(__file__).resolve().parent / "frontend.html"
    if html_path.is_file():
        return FileResponse(html_path)
    return {"message": "ShadowPost Adaptive API is running."}


@app.get("/paper")
async def paper():
    """Serve the verified ShadowPost IEEE research paper PDF."""
    pdf_path = Path(__file__).resolve().parent / "ShadowPost_IEEE_Paper.pdf"
    if pdf_path.is_file():
        return FileResponse(pdf_path, media_type="application/pdf", filename="ShadowPost_IEEE_Paper.pdf")
    raise HTTPException(404, "Paper PDF not found")


@app.get("/logo.png")
async def get_logo():
    """Serve the ShadowPost logo image."""
    logo_path = Path(__file__).resolve().parent / "docs" / "logo.png"
    if not logo_path.is_file():
        logo_path = Path(__file__).resolve().parent / "logo.png"
    if logo_path.is_file():
        return FileResponse(logo_path, media_type="image/png")
    raise HTTPException(404, "Logo image not found")


@app.get("/platforms")
async def list_platforms():
    """Return available adaptive platform profiles and their specifications."""
    return [
        {
            "id": p.id,
            "name": p.name,
            "max_width": p.max_width,
            "max_height": p.max_height,
            "aspect_ratio": p.aspect_ratio,
            "pre_compress_quality": p.pre_compress_quality,
            "dct_gap": p.dct_gap,
            "rs_parity_bytes": p.rs_parity_bytes,
        }
        for p in PLATFORM_PROFILES.values()
    ]


@app.post("/encode")
async def encode(
    cover: UploadFile = File(...),
    message: str = Form(...),
    passphrase: str = Form(...),
    platform: str = Form("default"),
):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source, output = await _save_upload(cover, root, "cover.jpg"), root / "stego.jpg"
        try:
            capacity = encode_file(source, output, message.encode("utf-8"), passphrase, platform)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(400, f"invalid JPEG or encode failure: {exc}") from exc

        return Response(
            output.read_bytes(),
            media_type="image/jpeg",
            headers={
                "X-ShadowPost-Max-Bytes": str(capacity["plaintext_bytes"]),
                "X-ShadowPost-Platform": str(capacity["platform"]),
                "X-ShadowPost-Dimensions": f"{capacity['dimensions'][0]}x{capacity['dimensions'][1]}",
            },
        )


@app.post("/decode")
async def decode(stego: UploadFile = File(...), passphrase: str = Form(...)):
    with tempfile.TemporaryDirectory() as tmp:
        source = await _save_upload(stego, Path(tmp), "stego.jpg")
        try:
            return {"message": decode_file(source, passphrase)}
        except InvalidTag:
            raise HTTPException(
                400,
                "Authentication failed: Incorrect passphrase, or the hidden message was altered/corrupted.",
            )
        except ReedSolomonError:
            raise HTTPException(
                400,
                "Data desynchronized: Image was resized or re-encoded too heavily by the platform.",
            )
        except (ValueError, UnicodeDecodeError) as exc:
            raise HTTPException(400, f"Decode failed: {exc}")
        except Exception as exc:
            raise HTTPException(400, f"Decode failed: {exc}")
