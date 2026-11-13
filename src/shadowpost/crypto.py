"""AES-256-GCM message containers and the existing versioned scrypt KDF."""

from __future__ import annotations
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

NONCE_BYTES = 12
TAG_BYTES = 16
# The specified compact container has no room for a per-message salt. This
# versioned protocol salt is public and fixed; deployment code must treat the
# passphrase as secret and can supply an installation-specific salt later.
SCRYPT_SALT = b"ShadowPost/v1 AES-256-GCM scrypt salt"


def derive_aes256_key(passphrase: str) -> bytes:
    """Derive a 32-byte AES-256 key; the passphrase is never used directly."""
    return Scrypt(salt=SCRYPT_SALT, length=32, n=2**14, r=8, p=1).derive(
        passphrase.encode("utf-8")
    )


def encrypt_message(key: bytes, plaintext: bytes) -> bytes:
    """Return a fresh nonce followed by authenticated ciphertext and its tag."""
    nonce = os.urandom(NONCE_BYTES)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, None)


def decrypt_container(key: bytes, container: bytes) -> bytes:
    if len(container) < NONCE_BYTES + TAG_BYTES:
        raise ValueError("AES-GCM container is truncated")
    return AESGCM(key).decrypt(container[:NONCE_BYTES], container[NONCE_BYTES:], None)
