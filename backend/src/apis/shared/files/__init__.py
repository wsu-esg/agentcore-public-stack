"""Shared files module for API projects.

This module provides file models, file resolver, and file repository operations
that are shared between the app API and inference API.
"""

from .models import (
    FileStatus,
    FileMetadata,
    UserFileQuota,
    PresignRequest,
    PresignResponse,
    CompleteUploadResponse,
    FileResponse,
    FileListResponse,
    QuotaResponse,
    QuotaExceededError,
    ALLOWED_MIME_TYPES,
    ALLOWED_EXTENSIONS,
    get_file_format,
    is_allowed_mime_type,
)

from .repository import (
    FileUploadRepository,
    get_file_upload_repository,
)

from .file_resolver import (
    ResolvedFileContent,
    FileResolverError,
    FileResolver,
    get_file_resolver,
)

__all__ = [
    # Models
    "FileStatus",
    "FileMetadata",
    "UserFileQuota",
    "PresignRequest",
    "PresignResponse",
    "CompleteUploadResponse",
    "FileResponse",
    "FileListResponse",
    "QuotaResponse",
    "QuotaExceededError",
    "ALLOWED_MIME_TYPES",
    "ALLOWED_EXTENSIONS",
    "get_file_format",
    "is_allowed_mime_type",
    # Repository
    "FileUploadRepository",
    "get_file_upload_repository",
    # File Resolver
    "ResolvedFileContent",
    "FileResolverError",
    "FileResolver",
    "get_file_resolver",
]
