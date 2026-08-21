"""Phase 4 FastAPI interface for the finalized ShadowPost pipeline."""
from __future__ import annotations

import math
import os
import tempfile
from pathlib import Path

import jpeglib
import numpy as np
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from reedsolo import RSCodec, ReedSolomonError

from phase1_native_dct_experiment import embed_native_dct, extract_native_dct, luminance_coefficients
from phase2_rs_roundtrip import bits_to_bytes, bytes_to_bits
from phase3_aes_gcm_roundtrip import NONCE_BYTES, TAG_BYTES, RS_PARITY_BYTES, derive_aes256_key

app = FastAPI(title="ShadowPost")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["null"],  # Allows opening frontend.html directly from disk.
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=False,
    allow_methods=["POST"],
    allow_headers=["*"],
)
PAIR_INDICES = (0, 2)
CODEWORD_BITS = 48 * 8
LENGTH_PREFIX_BYTES = 2


def capacity_for_jpeg(path: Path) -> dict[str, int]:
    coeffs = luminance_coefficients(jpeglib.read_dct(str(path)))
    luminance_blocks = int(coeffs.shape[0] * coeffs.shape[1])
    usable_bits = luminance_blocks * len(PAIR_INDICES)
    codewords = usable_bits // CODEWORD_BITS
    return {"luminance_blocks": luminance_blocks, "usable_bits": usable_bits,
            "codewords": codewords, "plaintext_bytes": max(0, codewords * 32 - LENGTH_PREFIX_BYTES - NONCE_BYTES - TAG_BYTES)}


def _decode_codeword(codec: RSCodec, codeword: bytes) -> bytes:
    chunk, _, _ = codec.decode(codeword)
    return bytes(chunk)


def encode_file(source: Path, destination: Path, message: bytes, passphrase: str) -> dict[str, int]:
    capacity = capacity_for_jpeg(source)
    if len(message) > capacity["plaintext_bytes"]:
        raise ValueError(f"message is {len(message)} bytes; max capacity for this image is {capacity['plaintext_bytes']} bytes")
    key = derive_aes256_key(passphrase)
    nonce = os.urandom(NONCE_BYTES)
    ciphertext_and_tag = AESGCM(key).encrypt(nonce, message, None)
    framed = len(message).to_bytes(LENGTH_PREFIX_BYTES, "big") + nonce + ciphertext_and_tag
    chunks = [framed[i:i + 32].ljust(32, b"\0") for i in range(0, len(framed), 32)]
    codec = RSCodec(RS_PARITY_BYTES)
    bits = np.concatenate([bytes_to_bits(bytes(codec.encode(chunk))) for chunk in chunks])
    embed_native_dct(source, destination, bits, 24, PAIR_INDICES)
    return capacity


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
    recovered = b"".join(_decode_codeword(codec, bits_to_bytes(bits[i:i + CODEWORD_BITS]))
                         for i in range(0, len(bits), CODEWORD_BITS))
    nonce = recovered[LENGTH_PREFIX_BYTES:LENGTH_PREFIX_BYTES + NONCE_BYTES]
    ciphertext_and_tag = recovered[LENGTH_PREFIX_BYTES + NONCE_BYTES:LENGTH_PREFIX_BYTES + NONCE_BYTES + length + TAG_BYTES]
    return AESGCM(key).decrypt(nonce, ciphertext_and_tag, None).decode("utf-8")


async def _save_upload(upload: UploadFile, directory: Path, name: str) -> Path:
    data = await upload.read()
    if not data:
        raise HTTPException(400, "uploaded image is empty")
    path = directory / name
    path.write_bytes(data)
    return path


@app.post("/encode")
async def encode(cover: UploadFile = File(...), message: str = Form(...), passphrase: str = Form(...)):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source, output = await _save_upload(cover, root, "cover.jpg"), root / "stego.jpg"
        try:
            capacity = encode_file(source, output, message.encode("utf-8"), passphrase)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(400, f"invalid JPEG or encode failure: {exc}") from exc
        return Response(output.read_bytes(), media_type="image/jpeg", headers={"X-ShadowPost-Max-Bytes": str(capacity["plaintext_bytes"])})


@app.post("/decode")
async def decode(stego: UploadFile = File(...), passphrase: str = Form(...)):
    with tempfile.TemporaryDirectory() as tmp:
        source = await _save_upload(stego, Path(tmp), "stego.jpg")
        try:
            return {"message": decode_file(source, passphrase)}
        except (ReedSolomonError, ValueError, UnicodeDecodeError) as exc:
            raise HTTPException(400, f"decode failed: {type(exc).__name__}: {exc}") from exc
        except Exception as exc:
            raise HTTPException(400, f"decode failed: {type(exc).__name__}") from exc
