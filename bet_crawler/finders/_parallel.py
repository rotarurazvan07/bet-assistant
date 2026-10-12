"""Small helpers for finder-level parallel work."""

from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")


def balanced_chunks(items: Sequence[T], max_chunks: int) -> list[list[T]]:
    """Split items into up to max_chunks chunks with sizes differing by at most one."""
    if max_chunks <= 0:
        return [list(items)] if items else []

    chunk_count = min(len(items), max_chunks)
    if chunk_count == 0:
        return []

    base_size, larger_chunks = divmod(len(items), chunk_count)
    chunks: list[list[T]] = []
    start = 0
    for idx in range(chunk_count):
        size = base_size + (1 if idx < larger_chunks else 0)
        end = start + size
        chunks.append(list(items[start:end]))
        start = end
    return chunks
