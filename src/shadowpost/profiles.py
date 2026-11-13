"""Experimental image-conditioning profiles; no delivery guarantees."""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from PIL import Image


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
        dct_gap=6,
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
        dct_gap=6,
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
        dct_gap=6,
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
        dct_gap=6,
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
        dct_gap=6,
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
        dct_gap=6,
        rs_parity_bytes=16,
        redundancy=1,
    ),
}


def pre_condition_image(
    source: Path, destination: Path, profile: PlatformProfile
) -> None:
    """Pre-condition a cover using the configured experimental platform profile.

    Enforces multiples of 16 for DCT block alignment and pre-compresses to
    the profile's selected quality. These settings do not guarantee that a
    platform will preserve the resulting coefficient grid.
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
