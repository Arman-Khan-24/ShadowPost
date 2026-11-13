"""FastAPI boundary for the ShadowPost research library."""

from __future__ import annotations
import tempfile
from pathlib import Path
from cryptography.exceptions import InvalidTag
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from reedsolo import ReedSolomonError
from .pipeline import encode_file, decode_file
from .profiles import PLATFORM_PROFILES

REPO_ROOT = Path(__file__).resolve().parents[2]

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

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB


async def _save_upload(upload: UploadFile, directory: Path, name: str) -> Path:
    data = await upload.read()
    if not data:
        raise HTTPException(400, "Uploaded image is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            400,
            f"Image exceeds maximum allowed size ({MAX_UPLOAD_BYTES // (1024 * 1024)}MB)",
        )
    if not data.startswith(b"\xff\xd8"):
        raise HTTPException(
            400, "Invalid image format: file must be a valid JPEG (missing SOI marker)"
        )
    path = directory / name
    path.write_bytes(data)
    return path


@app.get("/")
async def index():
    """Serve the adaptive platform web UI."""
    index_path = REPO_ROOT / "web" / "index.html"
    if index_path.is_file():
        return FileResponse(index_path)
    return {"message": "ShadowPost Adaptive API is running."}


@app.get("/paper")
async def paper():
    """Serve the archived ShadowPost IEEE research paper PDF."""
    pdf_path = REPO_ROOT / "research" / "papers" / "ShadowPost_IEEE_Paper.pdf"
    if pdf_path.is_file():
        return FileResponse(
            pdf_path, media_type="application/pdf", filename="ShadowPost_IEEE_Paper.pdf"
        )
    raise HTTPException(404, "Paper PDF not found")


@app.get("/logo.png")
async def get_logo():
    """Serve the ShadowPost logo image."""
    logo_path = REPO_ROOT / "web" / "assets" / "logo.png"
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
        source, output = (
            await _save_upload(cover, root, "cover.jpg"),
            root / "stego.jpg",
        )
        try:
            capacity = encode_file(
                source, output, message.encode("utf-8"), passphrase, platform
            )
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
