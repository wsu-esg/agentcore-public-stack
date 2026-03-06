import {
  Component,
  ChangeDetectionStrategy,
  input,
  computed,
  output,
} from '@angular/core';

/**
 * A subtle, frosted-glass indicator chip that shows which assistant
 * is powering the current conversation. Displays the assistant's
 * avatar (emoji or gradient letter) and name in a compact format.
 */
@Component({
  selector: 'app-assistant-indicator',
  standalone: true,
  imports: [],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <button
      type="button"
      (click)="onClick()"
      class="assistant-indicator group"
      [attr.aria-label]="'Chatting with ' + name()"
    >
      <!-- Avatar circle with gradient -->
      <div
        class="assistant-indicator__avatar"
        [style.background]="avatarGradient()"
      >
        @if (emoji()) {
          <span class="text-sm leading-none">{{ emoji() }}</span>
        } @else {
          <span class="text-xs font-semibold leading-none text-white">{{ firstLetter() }}</span>
        }
      </div>

      <!-- Assistant name -->
      <span class="assistant-indicator__name">
        {{ name() }}
      </span>

      <!-- Subtle chevron hint for interactivity -->
      <svg
        class="assistant-indicator__chevron"
        viewBox="0 0 16 16"
        fill="none"
        aria-hidden="true"
      >
        <path
          d="M4 6L8 10L12 6"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    </button>
  `,
  styles: [`
    @import "tailwindcss";
    @custom-variant dark (&:where(.dark, .dark *));

    .assistant-indicator {
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.375rem 0.75rem 0.375rem 0.375rem;
      border-radius: 9999px;

      /* Frosted glass effect */
      background: rgba(255, 255, 255, 0.72);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);

      /* Subtle border and shadow */
      border: 1px solid rgba(0, 0, 0, 0.06);
      box-shadow:
        0 1px 3px rgba(0, 0, 0, 0.04),
        0 4px 12px rgba(0, 0, 0, 0.03),
        inset 0 1px 0 rgba(255, 255, 255, 0.6);

      /* Animation */
      animation: indicator-enter 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards;
      opacity: 0;

      /* Interaction */
      cursor: pointer;
      transition:
        transform 0.2s cubic-bezier(0.16, 1, 0.3, 1),
        box-shadow 0.2s ease,
        background 0.2s ease;

      &:hover {
        transform: translateY(-1px);
        background: rgba(255, 255, 255, 0.85);
        box-shadow:
          0 2px 8px rgba(0, 0, 0, 0.06),
          0 8px 24px rgba(0, 0, 0, 0.06),
          inset 0 1px 0 rgba(255, 255, 255, 0.8);
      }

      &:active {
        transform: translateY(0);
      }

      &:focus-visible {
        outline: 2px solid var(--color-primary-500);
        outline-offset: 2px;
      }
    }

    /* Dark mode */
    :host-context(html.dark) .assistant-indicator {
      background: rgba(31, 41, 55, 0.75);
      border-color: rgba(255, 255, 255, 0.08);
      box-shadow:
        0 1px 3px rgba(0, 0, 0, 0.2),
        0 4px 12px rgba(0, 0, 0, 0.15),
        inset 0 1px 0 rgba(255, 255, 255, 0.05);

      &:hover {
        background: rgba(31, 41, 55, 0.88);
        box-shadow:
          0 2px 8px rgba(0, 0, 0, 0.25),
          0 8px 24px rgba(0, 0, 0, 0.2),
          inset 0 1px 0 rgba(255, 255, 255, 0.08);
      }
    }

    .assistant-indicator__avatar {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 1.625rem;
      height: 1.625rem;
      border-radius: 0.5rem;
      flex-shrink: 0;
      box-shadow:
        0 1px 2px rgba(0, 0, 0, 0.1),
        inset 0 1px 0 rgba(255, 255, 255, 0.2);
    }

    .assistant-indicator__name {
      font-size: 0.8125rem;
      font-weight: 500;
      color: var(--color-gray-700);
      letter-spacing: -0.01em;
      white-space: nowrap;
      max-width: 160px;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    :host-context(html.dark) .assistant-indicator__name {
      color: var(--color-gray-200);
    }

    .assistant-indicator__chevron {
      width: 0.875rem;
      height: 0.875rem;
      color: var(--color-gray-400);
      flex-shrink: 0;
      transition:
        transform 0.2s ease,
        color 0.2s ease;
    }

    .assistant-indicator:hover .assistant-indicator__chevron {
      color: var(--color-gray-500);
      transform: translateY(1px);
    }

    :host-context(html.dark) .assistant-indicator__chevron {
      color: var(--color-gray-500);
    }

    :host-context(html.dark) .assistant-indicator:hover .assistant-indicator__chevron {
      color: var(--color-gray-400);
    }

    @keyframes indicator-enter {
      0% {
        opacity: 0;
        transform: translateY(-8px) scale(0.96);
      }
      100% {
        opacity: 1;
        transform: translateY(0) scale(1);
      }
    }
  `],
})
export class AssistantIndicatorComponent {
  // Inputs
  readonly name = input.required<string>();
  readonly emoji = input<string>('');
  readonly imageUrl = input<string | null>(null);

  // Output for click interaction (can be used to show details)
  readonly indicatorClicked = output<void>();

  // Computed: Get first letter of name for avatar fallback
  readonly firstLetter = computed(() => {
    const name = this.name();
    return name ? name.charAt(0).toUpperCase() : '?';
  });

  // Computed: Generate a gradient based on the first letter
  readonly avatarGradient = computed(() => {
    const letter = this.firstLetter();
    const gradients: Record<string, string> = {
      'A': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      'B': 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
      'C': 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
      'D': 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
      'E': 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
      'F': 'linear-gradient(135deg, #30cfd0 0%, #330867 100%)',
      'G': 'linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)',
      'H': 'linear-gradient(135deg, #5ee7df 0%, #b490ca 100%)',
      'I': 'linear-gradient(135deg, #d299c2 0%, #fef9d7 100%)',
      'J': 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)',
      'K': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      'L': 'linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%)',
      'M': 'linear-gradient(135deg, #a1c4fd 0%, #c2e9fb 100%)',
      'N': 'linear-gradient(135deg, #d4fc79 0%, #96e6a1 100%)',
      'O': 'linear-gradient(135deg, #84fab0 0%, #8fd3f4 100%)',
      'P': 'linear-gradient(135deg, #cfd9df 0%, #e2ebf0 100%)',
      'Q': 'linear-gradient(135deg, #a6c0fe 0%, #f68084 100%)',
      'R': 'linear-gradient(135deg, #fccb90 0%, #d57eeb 100%)',
      'S': 'linear-gradient(135deg, #e0c3fc 0%, #8ec5fc 100%)',
      'T': 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
      'U': 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
      'V': 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
      'W': 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
      'X': 'linear-gradient(135deg, #30cfd0 0%, #330867 100%)',
      'Y': 'linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)',
      'Z': 'linear-gradient(135deg, #5ee7df 0%, #b490ca 100%)',
    };

    return gradients[letter] || 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
  });

  onClick(): void {
    this.indicatorClicked.emit();
  }
}
