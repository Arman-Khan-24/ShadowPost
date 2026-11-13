"""Whole-message framing, encryption, error correction and DCT integration."""

from __future__ import annotations
import math
from pathlib import Path
import jpeglib
from PIL import Image
from .crypto import (
    NONCE_BYTES,
    TAG_BYTES,
    decrypt_container,
    derive_aes256_key,
    encrypt_message,
)
from .dct_codec import embed_native_dct, extract_native_dct, luminance_coefficients
from .ecc import CODEWORD_BITS, bits_to_bytes, decode_codewords, encode_codewords
from .profiles import PLATFORM_PROFILES, pre_condition_image

PAIR_INDICES = (0, 2)
LENGTH_PREFIX_BYTES = 2


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
    framed = len(message).to_bytes(LENGTH_PREFIX_BYTES, "big") + encrypt_message(
        key, message
    )
    bits = encode_codewords(framed, profile.rs_parity_bytes)

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

    key = derive_aes256_key(passphrase)
    first = bits_to_bytes(extract_native_dct(source, CODEWORD_BITS, PAIR_INDICES))
    first_chunk = decode_codewords(first)
    length = int.from_bytes(first_chunk[:LENGTH_PREFIX_BYTES], "big")

    if length > capacity["plaintext_bytes"]:
        raise ValueError("decoded length exceeds this image's capacity")

    count = math.ceil((length + LENGTH_PREFIX_BYTES + NONCE_BYTES + TAG_BYTES) / 32)
    bits = extract_native_dct(source, count * CODEWORD_BITS, PAIR_INDICES)
    recovered = decode_codewords(bits_to_bytes(bits))
    container = recovered[
        LENGTH_PREFIX_BYTES : LENGTH_PREFIX_BYTES + NONCE_BYTES + length + TAG_BYTES
    ]
    return decrypt_container(key, container).decode("utf-8")
