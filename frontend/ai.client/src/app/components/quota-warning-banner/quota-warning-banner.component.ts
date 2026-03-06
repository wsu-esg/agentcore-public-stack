import { Component, ChangeDetectionStrategy, inject, computed } from '@angular/core';
import { QuotaWarningService } from '../../services/quota/quota-warning.service';
import { NgIcon, provideIcons } from '@ng-icons/core';
import { heroExclamationTriangle, heroXMark } from '@ng-icons/heroicons/outline';

/**
 * Subtle quota warning indicator component
 *
 * Displays a compact warning message above the chat input when the user
 * approaches their usage quota. Shows at 80% (warning) and 90%+ (critical).
 *
 * Features:
 * - Compact tab-like design that sits on top of the chat input
 * - Dismissible with X button
 * - Accessible with proper ARIA attributes
 * - Light/dark mode support
 */
@Component({
  selector: 'app-quota-warning-banner',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgIcon],
  providers: [provideIcons({ heroExclamationTriangle, heroXMark })],
  template: `
    @if (quotaWarningService.hasVisibleWarning()) {
      <div class="flex justify-center">
        <div
          class="inline-flex items-center gap-1.5 px-3 py-1 text-xs rounded-t-lg border border-b-0 animate-fade-in bg-white dark:bg-slate-800"
          [class.border-amber-400]="quotaWarningService.severity() === 'warning'"
          [class.text-amber-700]="quotaWarningService.severity() === 'warning'"
          [class.dark:border-amber-500]="quotaWarningService.severity() === 'warning'"
          [class.dark:text-amber-300]="quotaWarningService.severity() === 'warning'"
          [class.border-red-400]="quotaWarningService.severity() === 'critical'"
          [class.text-red-700]="quotaWarningService.severity() === 'critical'"
          [class.dark:border-red-500]="quotaWarningService.severity() === 'critical'"
          [class.dark:text-red-300]="quotaWarningService.severity() === 'critical'"
          role="status"
          [attr.aria-live]="'polite'"
        >
          <ng-icon
            name="heroExclamationTriangle"
            class="size-3 shrink-0"
          />
          <span class="font-medium">{{ messageText() }}</span>
          <button
            type="button"
            (click)="dismiss($event)"
            class="p-0.5 -mr-1 rounded hover:bg-black/10 dark:hover:bg-white/10 transition-colors"
            aria-label="Dismiss warning"
          >
            <ng-icon name="heroXMark" class="size-3" />
          </button>
        </div>
      </div>
    }
  `,
  styles: [`
    @keyframes fadeIn {
      from {
        opacity: 0;
        transform: translateY(4px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    .animate-fade-in {
      animation: fadeIn 0.15s ease-out;
    }
  `]
})
export class QuotaWarningBannerComponent {
  protected quotaWarningService = inject(QuotaWarningService);

  /** Compact message text */
  messageText = computed(() => {
    const warning = this.quotaWarningService.activeWarning();
    if (!warning) return '';

    const remaining = this.quotaWarningService.formattedRemaining();

    if (warning.percentageUsed >= 90) {
      return `${warning.warningLevel} usage - ${remaining} remaining`;
    }
    return `${warning.warningLevel} of quota used - ${remaining} remaining`;
  });

  dismiss(event: Event): void {
    event.stopPropagation();
    this.quotaWarningService.dismissWarning();
  }
}
