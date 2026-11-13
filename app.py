"""Repository ASGI entry point: uvicorn app:app."""
from shadowpost.api import app

__all__ = ["app"]
