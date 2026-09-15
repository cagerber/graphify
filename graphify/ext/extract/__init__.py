"""Consumer extractor registry (``[[tool.graphify.extractors]]``)."""

from graphify.ext.extract.registry import (
    resolve_consumer_extractor,
    resolve_consumer_extractors,
)

__all__ = [
    "resolve_consumer_extractor",
    "resolve_consumer_extractors",
]
