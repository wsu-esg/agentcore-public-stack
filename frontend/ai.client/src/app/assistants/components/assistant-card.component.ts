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
    <div class="flex flex-col items-center text-center">
      <!-- Avatar with emoji or first letter -->
      <div
        class="flex size-20 items-center justify-center rounded-xl text-3xl font-semibold text-white shadow-sm"
        [style.background]="avatarGradient()"
      >
        @if (emoji()) {
          <span class="text-5xl">{{ emoji() }}</span>
        } @else {
          {{ firstLetter() }}
        }
      </div>

      <!-- Name -->
      <h2 class="mt-4 text-xl font-bold text-gray-900 dark:text-white">
        {{ name() }}
      </h2>

      <!-- Owner -->
      <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
        By {{ ownerName() || 'You' }}
      </p>

      <!-- Description -->
      @if (description()) {
        <p class="mt-3 text-sm text-gray-600 dark:text-gray-300 max-w-md">
          {{ description() }}
        </p>
      }

      <!-- Conversation Starters -->
      @if (starters().length > 0) {
        <div class="mt-6 w-full max-w-md">
          <p class="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-3">
            Example Conversation Starters
          </p>
          <div class="flex flex-col gap-2">
            @for (starter of starters(); track $index) {
              <button
                type="button"
                (click)="onStarterClick(starter)"
                class="w-full rounded-xl bg-white dark:bg-slate-800 border border-gray-300 dark:border-white/10 px-4 py-3 text-left text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-slate-700 transition-colors"
              >
                {{ starter }}
              </button>
            }
          </div>
        </div>
      }
    </div>
  `,
  styles: [`
    :host {
      display: block;
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
