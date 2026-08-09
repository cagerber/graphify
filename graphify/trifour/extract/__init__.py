"""Trifour consumer extractor registry (``[[tool.graphify.extractors]]``)."""

from graphify.trifour.extract.registry import (
    resolve_consumer_extractor,
    resolve_consumer_extractors,
)

__all__ = [
    "resolve_consumer_extractor",
    "resolve_consumer_extractors",
]
