"""
File Upload Module

Provides file upload functionality for conversations with S3 pre-signed URLs.
"""

from apis.shared.files.models import (
    FileMetadata,
    FileStatus,
    UserFileQuota,
    PresignRequest,
    PresignResponse,
    CompleteUploadResponse,
    FileListResponse,
    QuotaResponse,
)
from apis.shared.files.repository import FileUploadRepository, get_file_upload_repository
from apis.shared.files.file_resolver import FileResolver, FileResolverError, ResolvedFileContent, get_file_resolver
from .service import FileUploadService, get_file_upload_service

__all__ = [
    # Models
    "FileMetadata",
    "FileStatus",
    "UserFileQuota",
    "PresignRequest",
    "PresignResponse",
    "CompleteUploadResponse",
    "FileListResponse",
    "QuotaResponse",
    # Repository
    "FileUploadRepository",
    "get_file_upload_repository",
    # Service
    "FileUploadService",
    "get_file_upload_service",
    # File Resolver
    "FileResolver",
    "FileResolverError",
    "ResolvedFileContent",
    "get_file_resolver",
]
