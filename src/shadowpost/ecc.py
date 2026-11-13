"""RS(48,32) framing and big-endian byte/bit conversion."""

from __future__ import annotations
import numpy as np
from reedsolo import RSCodec

RS_DATA_BYTES = 32
RS_PARITY_BYTES = 16
RS_CODEWORD_BYTES = RS_DATA_BYTES + RS_PARITY_BYTES
CODEWORD_BITS = RS_CODEWORD_BYTES * 8


def bytes_to_bits(data: bytes) -> np.ndarray:
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8), bitorder="big")


def bits_to_bytes(bits: np.ndarray) -> bytes:
    if len(bits) % 8:
        raise ValueError("bit count must be byte-aligned")
    return np.packbits(bits, bitorder="big").tobytes()


def encode_codewords(data: bytes, parity_bytes: int = RS_PARITY_BYTES) -> np.ndarray:
    codec = RSCodec(parity_bytes)
    chunks = [
        data[i : i + RS_DATA_BYTES].ljust(RS_DATA_BYTES, b"\0")
        for i in range(0, len(data), RS_DATA_BYTES)
    ]
    return np.concatenate(
        [bytes_to_bits(bytes(codec.encode(chunk))) for chunk in chunks]
    )


def decode_codewords(data: bytes) -> bytes:
    codec = RSCodec(RS_PARITY_BYTES)
    recovered = []
    for i in range(0, len(data), RS_CODEWORD_BYTES):
        chunk, _, _ = codec.decode(data[i : i + RS_CODEWORD_BYTES])
        recovered.append(bytes(chunk))
    return b"".join(recovered)
