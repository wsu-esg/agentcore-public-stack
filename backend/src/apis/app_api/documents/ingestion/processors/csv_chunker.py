"""CSV-specific chunker for RAG ingestion.

Bypasses Docling for CSV files, using row-based chunking that preserves
the header row in every chunk. This prevents the token-limit overflow
that occurs when Docling treats the entire CSV as a single table structure.
"""

import csv
import io
import logging
from typing import List

import tiktoken

logger = logging.getLogger(__name__)

# Module-level encoder (lazy-loaded)
_encoder: tiktoken.Encoding | None = None


def _get_encoder() -> tiktoken.Encoding:
    global _encoder
    if _encoder is None:
        _encoder = tiktoken.get_encoding("cl100k_base")
    return _encoder


def _count_tokens(text: str) -> int:
    return len(_get_encoder().encode(text))


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to fit within max_tokens."""
    enc = _get_encoder()
    tokens = enc.encode(text)
    if len(tokens) <= max_tokens:
        return text
    return enc.decode(tokens[:max_tokens])


def _rows_to_csv_text(header_row: List[str], data_rows: List[List[str]]) -> str:
    """Serialize header + data rows back into CSV text."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header_row)
    writer.writerows(data_rows)
    return buf.getvalue().strip()


def chunk_csv(file_bytes: bytes, max_tokens: int = 900) -> List[str]:
    """
    Chunk a CSV file into token-bounded pieces, each starting with the header row.

    Args:
        file_bytes: Raw CSV file content.
        max_tokens: Maximum token count per chunk (default 900, well under
                    the Titan v2 8192 limit to leave room for embedding overhead).

    Returns:
        List of CSV text chunks, each containing the header + a subset of rows.
        Returns empty list for empty or header-only CSVs.
    """
    try:
        text = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = file_bytes.decode("utf-8", errors="replace")

    reader = csv.reader(io.StringIO(text))

    # Extract header
    try:
        header_row = next(reader)
    except StopIteration:
        logger.info("Empty CSV file, returning no chunks")
        return []

    header_text = _rows_to_csv_text(header_row, [])
    header_tokens = _count_tokens(header_text)

    if header_tokens >= max_tokens:
        # Header alone exceeds limit — truncate it and return as single chunk
        logger.warning(f"CSV header alone is {header_tokens} tokens (limit {max_tokens}), truncating")
        return [_truncate_to_tokens(header_text, max_tokens)]

    chunks: List[str] = []
    current_rows: List[List[str]] = []

    for row in reader:
        # Try adding this row and check the full assembled chunk token count.
        # This accounts for CSV delimiters (\r\n) that row-level estimates miss.
        candidate_rows = current_rows + [row]
        candidate_text = _rows_to_csv_text(header_row, candidate_rows)
        candidate_tokens = _count_tokens(candidate_text)

        if candidate_tokens <= max_tokens:
            # Fits — accumulate
            current_rows = candidate_rows
            continue

        # Doesn't fit. First, flush what we have so far.
        if current_rows:
            chunks.append(_rows_to_csv_text(header_row, current_rows))
            current_rows = []

        # Check if this single row + header fits
        single_text = _rows_to_csv_text(header_row, [row])
        single_tokens = _count_tokens(single_text)

        if single_tokens <= max_tokens:
            # Start a new chunk with this row
            current_rows = [row]
        else:
            # Oversized row — truncate to fit within max_tokens
            truncated_text = _truncate_to_tokens(single_text, max_tokens)
            chunks.append(truncated_text)
            logger.warning(f"Truncated oversized CSV row from {single_tokens} to {max_tokens} tokens")

    # Emit final chunk
    if current_rows:
        chunks.append(_rows_to_csv_text(header_row, current_rows))

    logger.info(f"CSV chunked into {len(chunks)} pieces (max_tokens={max_tokens})")
    return chunks
