"""Document processors for different file types

All document formats are processed through Docling for unified handling.
Docling supports PDF, DOCX, PPTX, TXT, MD, RTF and other formats.
"""

from .docling_processor import DOCLING_SUPPORTED_EXTENSIONS, DOCLING_SUPPORTED_MIME_TYPES, is_docling_supported, process_with_docling

__all__ = ["process_with_docling", "is_docling_supported", "DOCLING_SUPPORTED_MIME_TYPES", "DOCLING_SUPPORTED_EXTENSIONS"]
