"""Knowledge layer: aggregate the reel corpus into a browsable research view."""

from .aggregate import Topic, build_knowledge, load_knowledge

__all__ = ["Topic", "build_knowledge", "load_knowledge"]
