"""Integration and regression test suite for ShadowPost FastAPI application."""
from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

# Ensure repository root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import app, capacity_for_jpeg, PLATFORM_PROFILES


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def sample_jpeg_bytes() -> bytes:
    """Generate a reproducible, self-contained synthetic JPEG with varied DCT coefficients."""
    img = Image.new("RGB", (512, 512), color=(120, 140, 160))
    for x in range(0, 512, 8):
        for y in range(0, 512, 8):
            img.putpixel((x, y), ((x * 13) % 256, (y * 17) % 256, (x + y) % 256))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def test_platforms_listing(client: TestClient):
    """GET /platforms should list all configured platform profiles."""
    response = client.get("/platforms")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    profile_ids = {p["id"] for p in data}
    expected = {"default", "discord", "whatsapp_doc", "telegram", "instagram", "twitter"}
    assert expected.issubset(profile_ids)

    for item in data:
        assert "id" in item
        assert "name" in item
        assert "dct_gap" in item
        assert "rs_parity_bytes" in item


def test_root_serves_html(client: TestClient):
    """GET / should serve the primary HTML interface."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "ShadowPost" in response.text


def test_paper_endpoint(client: TestClient):
    """GET /paper should serve the paper PDF if available."""
    pdf_path = REPO_ROOT / "ShadowPost_IEEE_Paper.pdf"
    response = client.get("/paper")
    if pdf_path.is_file():
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/pdf"
    else:
        assert response.status_code == 404


def test_encode_decode_roundtrip_default(client: TestClient, sample_jpeg_bytes: bytes):
    """Encode secret payload and decode it with default profile."""
    passphrase = "correct-battery-horse-staple"
    message = "Classified operational dispatch #42."

    encode_resp = client.post(
        "/encode",
        files={"cover": ("cover.jpg", sample_jpeg_bytes, "image/jpeg")},
        data={"message": message, "passphrase": passphrase, "platform": "default"},
    )
    assert encode_resp.status_code == 200
    assert encode_resp.headers.get("X-ShadowPost-Platform") == "default"
    assert "image/jpeg" in encode_resp.headers.get("content-type", "")
    stego_bytes = encode_resp.content

    decode_resp = client.post(
        "/decode",
        files={"stego": ("stego.jpg", stego_bytes, "image/jpeg")},
        data={"passphrase": passphrase},
    )
    assert decode_resp.status_code == 200
    assert decode_resp.json() == {"message": message}


def test_encode_decode_roundtrip_adaptive_instagram(client: TestClient, sample_jpeg_bytes: bytes):
    """Test adaptive Instagram profile conditioning and round-trip."""
    passphrase = "instagram-key-secure"
    message = "Social media covert transmission"

    encode_resp = client.post(
        "/encode",
        files={"cover": ("cover.jpg", sample_jpeg_bytes, "image/jpeg")},
        data={"message": message, "passphrase": passphrase, "platform": "instagram"},
    )
    assert encode_resp.status_code == 200
    assert encode_resp.headers.get("X-ShadowPost-Platform") == "instagram"
    stego_bytes = encode_resp.content

    dims = encode_resp.headers.get("X-ShadowPost-Dimensions", "").split("x")
    assert len(dims) == 2
    # Verify square aspect ratio enforced for Instagram
    assert dims[0] == dims[1]

    decode_resp = client.post(
        "/decode",
        files={"stego": ("stego.jpg", stego_bytes, "image/jpeg")},
        data={"passphrase": passphrase},
    )
    assert decode_resp.status_code == 200
    assert decode_resp.json() == {"message": message}


def test_wrong_passphrase_fails(client: TestClient, sample_jpeg_bytes: bytes):
    """Decoding with an incorrect passphrase must fail with 400 and authentication error."""
    passphrase = "real-password-99"
    message = "Confidential telemetry"

    encode_resp = client.post(
        "/encode",
        files={"cover": ("cover.jpg", sample_jpeg_bytes, "image/jpeg")},
        data={"message": message, "passphrase": passphrase, "platform": "default"},
    )
    assert encode_resp.status_code == 200

    decode_resp = client.post(
        "/decode",
        files={"stego": ("stego.jpg", encode_resp.content, "image/jpeg")},
        data={"passphrase": "WRONG_PASSWORD_XYZ"},
    )
    assert decode_resp.status_code == 400
    assert "Authentication failed" in decode_resp.json().get("detail", "")


def test_corrupted_stego_fails(client: TestClient, sample_jpeg_bytes: bytes):
    """Decoding a corrupted stego file must cleanly return HTTP 400."""
    passphrase = "test-passphrase-robust"
    message = "Important payload"

    encode_resp = client.post(
        "/encode",
        files={"cover": ("cover.jpg", sample_jpeg_bytes, "image/jpeg")},
        data={"message": message, "passphrase": passphrase, "platform": "default"},
    )
    assert encode_resp.status_code == 200

    # Corrupt the JPEG headers / bitstream so decompression fails cleanly
    corrupted = bytearray(encode_resp.content)
    corrupted[200:800] = b"\xff" * 600

    decode_resp = client.post(
        "/decode",
        files={"stego": ("stego.jpg", bytes(corrupted), "image/jpeg")},
        data={"passphrase": passphrase},
    )
    assert decode_resp.status_code == 400


def test_payload_exceeding_capacity_fails(client: TestClient, sample_jpeg_bytes: bytes):
    """Encoding a payload exceeding cover capacity must fail with HTTP 400."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        temp_cover = Path(tmp_dir) / "temp_cover.jpg"
        temp_cover.write_bytes(sample_jpeg_bytes)
        capacity = capacity_for_jpeg(temp_cover)
        max_bytes = capacity["plaintext_bytes"]

    oversized_message = "A" * (max_bytes + 64)
    response = client.post(
        "/encode",
        files={"cover": ("cover.jpg", sample_jpeg_bytes, "image/jpeg")},
        data={"message": oversized_message, "passphrase": "sample-passphrase", "platform": "default"},
    )
    assert response.status_code == 400
    assert "max capacity" in response.json().get("detail", "").lower()


def test_empty_upload_fails(client: TestClient):
    """Uploading an empty file must return HTTP 400."""
    response = client.post(
        "/encode",
        files={"cover": ("empty.jpg", b"", "image/jpeg")},
        data={"message": "hello", "passphrase": "pass", "platform": "default"},
    )
    assert response.status_code == 400
    assert "empty" in response.json().get("detail", "").lower()


def test_non_jpeg_upload_fails(client: TestClient):
    """Uploading a non-JPEG payload must return HTTP 400."""
    response = client.post(
        "/encode",
        files={"cover": ("fake.jpg", b"NOT_A_JPEG_FILE_HEADER", "image/jpeg")},
        data={"message": "hello", "passphrase": "pass", "platform": "default"},
    )
    assert response.status_code == 400
    assert "soi marker" in response.json().get("detail", "").lower()
