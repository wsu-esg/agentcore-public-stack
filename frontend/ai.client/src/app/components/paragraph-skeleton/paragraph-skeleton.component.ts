import { Component, ChangeDetectionStrategy, input } from '@angular/core';

/**
 * ParagraphSkeletonComponent
 *
 * An animated skeleton loading component that simulates paragraph text loading.
 * Features multiple lines with varying widths and a shimmer animation effect.
 *
 * @example
 * ```html
 * <app-paragraph-skeleton />
 * <app-paragraph-skeleton [lines]="5" />
 * ```
 */
@Component({
  selector: 'app-paragraph-skeleton',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div
      class="space-y-3"
      role="status"
      aria-busy="true"
      aria-label="Loading content">
      @for (line of lineWidths; track $index) {
        <div
          class="skeleton-line h-4 rounded"
          [style.width]="line"
          aria-hidden="true">
        </div>
      }
      <span class="sr-only">Loading...</span>
    </div>

    <style>
      :host {
        display: block;
      }

      .skeleton-line {
        background: linear-gradient(
          90deg,
          var(--color-gray-300) 0%,
          var(--color-gray-200) 50%,
          var(--color-gray-300) 100%
        );
        background-size: 200% 100%;
        animation: shimmer 1.5s ease-in-out infinite;
      }

      :host-context(.dark) .skeleton-line {
        background: linear-gradient(
          90deg,
          var(--color-gray-800) 0%,
          var(--color-gray-700) 50%,
          var(--color-gray-800) 100%
        );
        background-size: 200% 100%;
      }

      @keyframes shimmer {
        0% {
          background-position: 200% 0;
        }
        100% {
          background-position: -200% 0;
        }
      }

      /* Staggered animation delay for each line */
      .skeleton-line:nth-child(1) { animation-delay: 0s; }
      .skeleton-line:nth-child(2) { animation-delay: 0.1s; }
      .skeleton-line:nth-child(3) { animation-delay: 0.2s; }
      .skeleton-line:nth-child(4) { animation-delay: 0.3s; }
      .skeleton-line:nth-child(5) { animation-delay: 0.4s; }
      .skeleton-line:nth-child(6) { animation-delay: 0.5s; }
      .skeleton-line:nth-child(7) { animation-delay: 0.6s; }
    </style>
  `,
})
export class ParagraphSkeletonComponent {
  /**
   * Number of skeleton lines to display
   */
  lines = input<number>(4);

  /**
   * Pre-computed line widths for visual variety.
   * Uses a deterministic pattern for consistent appearance.
   */
  readonly lineWidths = [
    '100%',
    '92%',
    '85%',
    '78%',
    '88%',
    '70%',
    '95%',
  ];
}
