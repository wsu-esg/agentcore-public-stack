/**
 * Document status types matching backend DocumentStatus
 */
export type DocumentStatus = 'uploading' | 'chunking' | 'embedding' | 'complete' | 'failed';

/**
 * Statuses that indicate a document is still being processed.
 */
export const PROCESSING_STATUSES: readonly DocumentStatus[] = [
  'uploading',
  'chunking',
  'embedding',
] as const;

/**
 * Threshold (ms) after which a processing document is considered stale.
 * Must exceed the Lambda ingestion timeout (900s / 15 min) to avoid
 * killing in-flight jobs. Matches backend STALE_PROCESSING_TIMEOUT_MINUTES (20 min).
 */
export const STALE_DOCUMENT_THRESHOLD_MS = 20 * 60 * 1000;

/**
 * Request body for POST /assistants/{assistantId}/documents/upload-url
 */
export interface CreateDocumentRequest {
  filename: string;
  contentType: string;
  sizeBytes: number;
}

/**
 * Response from POST /assistants/{assistantId}/documents/upload-url
 */
export interface UploadUrlResponse {
  documentId: string;
  uploadUrl: string;
  expiresIn: number;
}

/**
 * Document response model matching backend DocumentResponse
 */
export interface Document {
  documentId: string;
  assistantId: string;
  filename: string;
  contentType: string;
  sizeBytes: number;
  status: DocumentStatus;
  errorMessage?: string;
  errorDetails?: string;
  chunkCount?: number;
  createdAt: string;
  updatedAt: string;
}

/**
 * Response from GET /assistants/{assistantId}/documents
 */
export interface DocumentsListResponse {
  documents: Document[];
  nextToken?: string;
}

/**
 * Response from GET /assistants/{assistantId}/documents/{documentId}/download
 */
export interface DownloadUrlResponse {
  downloadUrl: string;
  filename: string;
  expiresIn: number;
}

