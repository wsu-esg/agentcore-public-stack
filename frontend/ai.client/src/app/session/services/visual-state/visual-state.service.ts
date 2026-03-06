import { Injectable, inject, signal, effect } from '@angular/core';
import { SessionService } from '../session/session.service';

/**
 * Display state for a single promoted visual.
 */
export interface VisualDisplayState {
  /** Whether the user has dismissed this visual */
  dismissed: boolean;
  /** Whether the visual is expanded (default: true) */
  expanded: boolean;
}

/**
 * Service for managing the display state of promoted visual tool results.
 *
 * State is persisted to the session preferences via the SessionService,
 * allowing visual states to persist across page refreshes and sessions.
 *
 * Uses optimistic updates with debounced persistence to provide
 * immediate UI feedback while minimizing API calls.
 */
@Injectable({
  providedIn: 'root'
})
export class VisualStateService {
  private sessionService = inject(SessionService);

  /** Local cache for immediate UI updates */
  private localState = signal<Record<string, VisualDisplayState>>({});

  /** Debounce timer for API saves */
  private saveTimeout: ReturnType<typeof setTimeout> | null = null;

  /** Track the current session ID to detect session changes */
  private currentSessionId: string | null = null;

  /** Flag to skip effect sync when we triggered the update ourselves */
  private skipNextSync = false;

  constructor() {
    // Load visual state when session changes (not on every metadata update)
    effect(() => {
      const metadata = this.sessionService.currentSession();
      const sessionId = metadata?.sessionId;

      // Skip if we triggered this update ourselves
      if (this.skipNextSync) {
        this.skipNextSync = false;
        return;
      }

      // Only reset state when switching to a different session
      if (sessionId !== this.currentSessionId) {
        this.currentSessionId = sessionId ?? null;

        const preferences = metadata?.preferences as Record<string, unknown> | undefined;
        const visualState = preferences?.['visualState'] as Record<string, VisualDisplayState> | undefined;

        if (visualState && typeof visualState === 'object') {
          this.localState.set(visualState);
        } else {
          this.localState.set({});
        }
      }
    });
  }

  /**
   * Check if a visual is dismissed.
   *
   * @param toolUseId - The tool use ID for the visual
   * @returns true if the visual has been dismissed
   */
  isDismissed(toolUseId: string): boolean {
    return this.localState()[toolUseId]?.dismissed ?? false;
  }

  /**
   * Check if a visual is expanded (default: true).
   *
   * @param toolUseId - The tool use ID for the visual
   * @returns true if the visual is expanded
   */
  isExpanded(toolUseId: string): boolean {
    return this.localState()[toolUseId]?.expanded ?? true;
  }

  /**
   * Dismiss a visual.
   *
   * @param toolUseId - The tool use ID for the visual to dismiss
   */
  dismiss(toolUseId: string): void {
    this.updateState(toolUseId, { dismissed: true });
  }

  /**
   * Toggle the expanded state of a visual.
   *
   * @param toolUseId - The tool use ID for the visual to toggle
   */
  toggleExpanded(toolUseId: string): void {
    const current = this.isExpanded(toolUseId);
    this.updateState(toolUseId, { expanded: !current });
  }

  /**
   * Update state locally and schedule save to backend.
   */
  private updateState(toolUseId: string, updates: Partial<VisualDisplayState>): void {
    // Update local state immediately (optimistic)
    this.localState.update(state => ({
      ...state,
      [toolUseId]: {
        dismissed: state[toolUseId]?.dismissed ?? false,
        expanded: state[toolUseId]?.expanded ?? true,
        ...updates
      }
    }));

    // Debounced save to backend
    this.scheduleSave();
  }

  /**
   * Debounced save to prevent API spam during rapid interactions.
   */
  private scheduleSave(): void {
    if (this.saveTimeout) {
      clearTimeout(this.saveTimeout);
    }

    this.saveTimeout = setTimeout(() => {
      this.saveToBackend();
    }, 500); // 500ms debounce
  }

  /**
   * Save visual state to backend via session preferences.
   */
  private async saveToBackend(): Promise<void> {
    const sessionId = this.sessionService.currentSession().sessionId;
    if (!sessionId) return;

    try {
      // Mark that we're saving so the effect doesn't overwrite our local state
      this.skipNextSync = true;

      // Note: The backend SessionPreferences model has extra="allow",
      // so this will be persisted even without explicit field definition
      await this.sessionService.updateSessionMetadata(sessionId, {
        visualState: this.localState()
      } as Record<string, unknown>);
    } catch (error) {
      console.error('Failed to save visual state:', error);
      // State is already in local cache, so UI remains correct
    }
  }
}
