"""FastAPI backend — thin HTTP layer over the reels_scrap modules."""

from .app import create_app

__all__ = ["create_app"]
