import {
  Component,
  ChangeDetectionStrategy,
  input,
  computed,
  output,
} from '@angular/core';

/**
 * Displays an assistant card with avatar, name, description, and conversation starters.
 * Used in the assistant preview and when an assistant is activated.
 */
@Component({
  selector: 'app-assistant-card',
  standalone: true,
  imports: [],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="assistant-card">
      <!-- Gradient hero banner -->
      <div class="banner" [style.background]="avatarGradient()">
        <div class="banner-noise"></div>
      </div>

      <!-- Avatar overlapping the banner edge -->
      <div class="avatar-wrapper">
        <div class="avatar" [style.background]="avatarGradient()">
          @if (emoji()) {
            <span class="text-4xl leading-none">{{ emoji() }}</span>
          } @else {
            <span class="text-2xl font-bold text-white leading-none">{{ firstLetter() }}</span>
          }
        </div>
      </div>

      <!-- Content below avatar -->
      <div class="card-body">
        <h2 class="text-xl font-bold text-gray-900 dark:text-white tracking-tight">
          {{ name() }}
        </h2>

        <p class="mt-1 text-xs font-medium text-gray-400 dark:text-gray-500 uppercase tracking-widest">
          By {{ ownerName() || 'You' }}
        </p>

        @if (description()) {
          <p class="mt-3 text-sm text-gray-500 dark:text-gray-400 max-w-sm leading-relaxed">
            {{ description() }}
          </p>
        }

        @if (starters().length > 0) {
          <div class="mt-6 w-full max-w-sm">
            <p class="text-[10px] font-semibold uppercase tracking-[0.15em] text-gray-400 dark:text-gray-500 mb-2.5">
              Try asking
            </p>
            <div class="flex flex-col gap-1.5">
              @for (starter of starters(); track $index) {
                <button
                  type="button"
                  (click)="onStarterClick(starter)"
                  class="starter-btn group"
                >
                  <span class="starter-accent" [style.background]="avatarGradient()"></span>
                  <span class="flex-1 text-left">{{ starter }}</span>
                  <svg class="size-4 shrink-0 text-gray-300 dark:text-gray-600 group-hover:text-gray-500 dark:group-hover:text-gray-300 transition-all group-hover:translate-x-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
                  </svg>
                </button>
              }
            </div>
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    :host {
      display: flex;
      justify-content: center;
    }

    .assistant-card {
      position: relative;
      border-radius: 1rem;
      overflow: hidden;
      background: var(--color-secondary-50);
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06), 0 8px 24px rgba(0, 0, 0, 0.06);
      width: 100%;
      max-width: 28rem;
    }

    :host-context(.dark) .assistant-card {
      background: var(--color-secondary-950);
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2), 0 8px 24px rgba(0, 0, 0, 0.15);
    }

    .banner {
      position: relative;
      height: 4rem;
      overflow: hidden;
    }

    .banner-noise {
      position: absolute;
      inset: 0;
      opacity: 0.08;
      background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
      background-size: 128px 128px;
      mix-blend-mode: overlay;
    }

    .avatar-wrapper {
      display: flex;
      justify-content: center;
      margin-top: -2rem;
      position: relative;
      z-index: 1;
    }

    .avatar {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 4rem;
      height: 4rem;
      border-radius: 1rem;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
      ring: 3px solid white;
      border: 3px solid white;
    }

    :host-context(.dark) .avatar {
      border-color: var(--color-secondary-950);
    }

    .card-body {
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
      padding: 0.75rem 1.5rem 1.5rem;
    }

    .starter-btn {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      width: 100%;
      padding: 0.625rem 0.875rem;
      border-radius: 0.625rem;
      font-size: 0.8125rem;
      line-height: 1.4;
      color: var(--color-secondary-700);
      background: white;
      border: 1px solid var(--color-secondary-200);
      transition: all 150ms ease;
      cursor: pointer;
      text-align: left;
    }

    .starter-btn:hover {
      background: var(--color-secondary-50);
      border-color: var(--color-secondary-300);
      box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
    }

    :host-context(.dark) .starter-btn {
      color: var(--color-secondary-200);
      background: color-mix(in oklch, var(--color-secondary-base) 20%, transparent);
      border-color: color-mix(in oklch, var(--color-secondary-base) 30%, transparent);
    }

    :host-context(.dark) .starter-btn:hover {
      background: color-mix(in oklch, var(--color-secondary-base) 30%, transparent);
      border-color: color-mix(in oklch, var(--color-secondary-base) 40%, transparent);
      box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
    }

    .starter-accent {
      width: 3px;
      height: 1.25rem;
      border-radius: 2px;
      flex-shrink: 0;
      opacity: 0.6;
      transition: opacity 150ms ease;
    }

    .starter-btn:hover .starter-accent {
      opacity: 1;
    }
  `],
})
export class AssistantCardComponent {
  // Inputs
  readonly name = input.required<string>();
  readonly description = input<string>('');
  readonly ownerName = input<string>('');
  readonly starters = input<string[]>([]);
  readonly emoji = input<string>('');
  readonly imageUrl = input<string | null>(null);

  // Outputs
  readonly starterSelected = output<string>();

  // Computed: Get first letter of name for avatar
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

  onStarterClick(starter: string): void {
    this.starterSelected.emit(starter);
  }
}
