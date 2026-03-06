/**
 * Prefix for preview session IDs.
 * Sessions with this prefix are recognized by the backend and skip persistence.
 */
export const PREVIEW_SESSION_PREFIX = 'preview-';

/**
 * Check if a session ID is a preview session.
 * Preview sessions are used for assistant testing in the form builder.
 * They allow full agent functionality but don't save to user's conversation history.
 */
export function isPreviewSession(sessionId: string): boolean {
  return sessionId.startsWith(PREVIEW_SESSION_PREFIX);
}
