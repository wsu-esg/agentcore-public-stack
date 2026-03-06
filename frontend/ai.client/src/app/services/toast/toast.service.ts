import { Injectable, signal } from '@angular/core';

/**
 * Types of toast notifications
 */
export type ToastType = 'success' | 'error' | 'warning' | 'info';

/**
 * Toast message interface
 */
export interface ToastMessage {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
  duration: number;
  dismissible: boolean;
  timestamp: Date;
}

/**
 * Options for showing a toast
 */
export interface ToastOptions {
  /** Duration in milliseconds (0 for no auto-dismiss) */
  duration?: number;
  /** Whether the toast can be manually dismissed */
  dismissible?: boolean;
}

const DEFAULT_DURATION = 5000;

/**
 * Service for displaying toast notifications throughout the application.
 *
 * Supports success, error, warning, and info toast types with configurable
 * duration and dismissibility.
 *
 * @example
 * ```typescript
 * // In a component
 * private toast = inject(ToastService);
 *
 * onSuccess() {
 *   this.toast.success('Saved!', 'Your changes have been saved successfully.');
 * }
 *
 * onError() {
 *   this.toast.error('Error', 'Failed to save changes.');
 * }
 * ```
 */
@Injectable({
  providedIn: 'root'
})
export class ToastService {
  private toastsSignal = signal<ToastMessage[]>([]);

  /** Readonly signal of current toast messages */
  readonly toasts = this.toastsSignal.asReadonly();

  /**
   * Show a success toast
   * @param title - Toast title
   * @param message - Optional description
   * @param options - Toast options
   */
  success(title: string, message?: string, options?: ToastOptions): void {
    this.show('success', title, message, options);
  }

  /**
   * Show an error toast
   * @param title - Toast title
   * @param message - Optional description
   * @param options - Toast options
   */
  error(title: string, message?: string, options?: ToastOptions): void {
    this.show('error', title, message, { duration: 8000, ...options });
  }

  /**
   * Show a warning toast
   * @param title - Toast title
   * @param message - Optional description
   * @param options - Toast options
   */
  warning(title: string, message?: string, options?: ToastOptions): void {
    this.show('warning', title, message, options);
  }

  /**
   * Show an info toast
   * @param title - Toast title
   * @param message - Optional description
   * @param options - Toast options
   */
  info(title: string, message?: string, options?: ToastOptions): void {
    this.show('info', title, message, options);
  }

  /**
   * Dismiss a toast by ID
   * @param id - Toast ID
   */
  dismiss(id: string): void {
    this.toastsSignal.update(toasts => toasts.filter(t => t.id !== id));
  }

  /**
   * Dismiss all toasts
   */
  dismissAll(): void {
    this.toastsSignal.set([]);
  }

  /**
   * Show a toast notification
   */
  private show(
    type: ToastType,
    title: string,
    message?: string,
    options?: ToastOptions
  ): void {
    const id = this.generateId();
    const duration = options?.duration ?? DEFAULT_DURATION;
    const dismissible = options?.dismissible ?? true;

    const toast: ToastMessage = {
      id,
      type,
      title,
      message,
      duration,
      dismissible,
      timestamp: new Date()
    };

    this.toastsSignal.update(toasts => [...toasts, toast]);

    // Auto-dismiss after duration (if duration > 0)
    if (duration > 0) {
      setTimeout(() => this.dismiss(id), duration);
    }
  }

  /**
   * Generate a unique toast ID
   */
  private generateId(): string {
    return `toast-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
  }
}
