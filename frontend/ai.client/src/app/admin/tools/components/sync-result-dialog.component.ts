import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
} from '@angular/core';
import { DIALOG_DATA, DialogRef } from '@angular/cdk/dialog';
import { NgIcon, provideIcons } from '@ng-icons/core';
import { heroXMark, heroArrowPath } from '@ng-icons/heroicons/outline';

/**
 * Data passed to the sync result dialog.
 */
export interface SyncResultDialogData {
  discovered: { tool_id: string; display_name: string; action: string }[];
  orphaned: { tool_id: string; action: string }[];
  unchanged: string[];
  dryRun: boolean;
}

/**
 * Result returned when the dialog is closed.
 * Returns true if user wants to apply changes, false/undefined otherwise.
 */
export type SyncResultDialogResult = boolean | undefined;

@Component({
  selector: 'app-sync-result-dialog',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgIcon],
  providers: [provideIcons({ heroXMark, heroArrowPath })],
  host: {
    'class': 'block',
    '(keydown.escape)': 'onClose()'
  },
  template: `
    <!-- Backdrop -->
    <div
      class="dialog-backdrop fixed inset-0 bg-gray-500/75 dark:bg-gray-900/80"
      aria-hidden="true"
      (click)="onClose()"
    ></div>

    <!-- Dialog Panel -->
    <div class="fixed inset-0 z-10 flex min-h-full items-end justify-center p-4 text-center focus:outline-none sm:items-center sm:p-0">
      <div
        class="dialog-panel relative transform overflow-hidden rounded-lg bg-white px-4 pt-5 pb-4 text-left shadow-xl sm:my-8 sm:w-full sm:max-w-lg sm:p-6 dark:bg-gray-800 dark:outline dark:-outline-offset-1 dark:outline-white/10"
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        aria-describedby="dialog-description"
      >
        <!-- Close button (top-right) -->
        <div class="absolute top-0 right-0 hidden pt-4 pr-4 sm:block">
          <button
            type="button"
            (click)="onClose()"
            class="rounded-md bg-white text-gray-400 hover:text-gray-500 focus:outline-2 focus:outline-offset-2 focus:outline-indigo-600 dark:bg-gray-800 dark:hover:text-gray-300 dark:focus:outline-white"
            aria-label="Close dialog"
          >
            <span class="sr-only">Close</span>
            <ng-icon name="heroXMark" class="size-6" aria-hidden="true" />
          </button>
        </div>

        <!-- Header with Icon -->
        <div class="sm:flex sm:items-start">
          <div class="mx-auto flex size-12 shrink-0 items-center justify-center rounded-full bg-indigo-100 sm:mx-0 sm:size-10 dark:bg-indigo-500/10">
            <ng-icon name="heroArrowPath" class="size-6 text-indigo-600 dark:text-indigo-400" aria-hidden="true" />
          </div>
          <div class="mt-3 text-center sm:mt-0 sm:ml-4 sm:text-left">
            <h3 id="dialog-title" class="text-base font-semibold text-gray-900 dark:text-white">
              Sync Result
            </h3>
            <div class="mt-2">
              <p class="text-sm text-gray-500 dark:text-gray-400">
                @if (data.dryRun) {
                  Preview of changes that will be applied to the tool catalog.
                } @else {
                  Changes have been applied to the tool catalog.
                }
              </p>
            </div>
          </div>
        </div>

        <!-- Content -->
        <div id="dialog-description" class="mt-4 max-h-72 overflow-y-auto">
          @if (data.dryRun) {
            <div class="mb-4 p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-md">
              <p class="text-sm text-amber-800 dark:text-amber-200">
                Dry run - no changes have been made yet.
              </p>
            </div>
          }

          @if (data.discovered.length > 0) {
            <div class="mb-4">
              <h4 class="font-medium mb-2 text-green-600 dark:text-green-400">
                Discovered ({{ data.discovered.length }})
              </h4>
              <ul class="text-sm space-y-1">
                @for (item of data.discovered; track item.tool_id) {
                  <li class="text-gray-600 dark:text-gray-400">
                    {{ item.display_name }} <span class="text-gray-400 dark:text-gray-500">({{ item.tool_id }})</span>
                  </li>
                }
              </ul>
            </div>
          }

          @if (data.orphaned.length > 0) {
            <div class="mb-4">
              <h4 class="font-medium mb-2 text-amber-600 dark:text-amber-400">
                Orphaned ({{ data.orphaned.length }})
              </h4>
              <ul class="text-sm space-y-1">
                @for (item of data.orphaned; track item.tool_id) {
                  <li class="text-gray-600 dark:text-gray-400">
                    {{ item.tool_id }}
                  </li>
                }
              </ul>
            </div>
          }

          @if (data.unchanged.length > 0) {
            <div>
              <h4 class="font-medium mb-2 text-gray-600 dark:text-gray-400">
                Unchanged ({{ data.unchanged.length }})
              </h4>
            </div>
          }

          @if (data.discovered.length === 0 && data.orphaned.length === 0) {
            <p class="text-center text-gray-500 dark:text-gray-400 py-4">
              No changes detected.
            </p>
          }
        </div>

        <!-- Actions -->
        <div class="mt-5 sm:mt-4 sm:flex sm:flex-row-reverse">
          @if (data.dryRun && (data.discovered.length > 0 || data.orphaned.length > 0)) {
            <button
              type="button"
              (click)="onApply()"
              [disabled]="applying()"
              class="inline-flex w-full justify-center rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-xs hover:bg-indigo-500 sm:ml-3 sm:w-auto dark:bg-indigo-500 dark:shadow-none dark:hover:bg-indigo-400 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {{ applying() ? 'Applying...' : 'Apply Changes' }}
            </button>
            <button
              type="button"
              (click)="onClose()"
              class="mt-3 inline-flex w-full justify-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-xs inset-ring-1 inset-ring-gray-300 hover:bg-gray-50 sm:mt-0 sm:w-auto dark:bg-white/10 dark:text-white dark:shadow-none dark:inset-ring-white/5 dark:hover:bg-white/20"
            >
              Cancel
            </button>
          } @else {
            <button
              type="button"
              (click)="onClose()"
              class="inline-flex w-full justify-center rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-xs hover:bg-indigo-500 sm:w-auto dark:bg-indigo-500 dark:shadow-none dark:hover:bg-indigo-400"
            >
              Close
            </button>
          }
        </div>
      </div>
    </div>
  `,
  styles: `
    @import "tailwindcss";

    @custom-variant dark (&:where(.dark, .dark *));

    /* Backdrop fade-in animation */
    .dialog-backdrop {
      animation: backdrop-fade-in 200ms ease-out;
    }

    @keyframes backdrop-fade-in {
      from {
        opacity: 0;
      }
      to {
        opacity: 1;
      }
    }

    /* Dialog panel fade-in-up animation */
    .dialog-panel {
      animation: dialog-fade-in-up 200ms ease-out;
    }

    @keyframes dialog-fade-in-up {
      from {
        opacity: 0;
        transform: translateY(1rem) scale(0.95);
      }
      to {
        opacity: 1;
        transform: translateY(0) scale(1);
      }
    }
  `
})
export class SyncResultDialogComponent {
  protected readonly dialogRef = inject(DialogRef<SyncResultDialogResult>);
  protected readonly data = inject<SyncResultDialogData>(DIALOG_DATA);

  applying = signal(false);

  onApply(): void {
    this.applying.set(true);
    this.dialogRef.close(true);
  }

  onClose(): void {
    this.dialogRef.close(undefined);
  }
}
