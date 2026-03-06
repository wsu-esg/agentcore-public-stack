import { Component, ChangeDetectionStrategy, inject, input, output, signal, effect, ElementRef, HostListener } from '@angular/core';
import { NgIcon, provideIcons } from '@ng-icons/core';
import { heroXMark, heroCheck, heroChevronDown } from '@ng-icons/heroicons/outline';
import { ModelService } from '../../session/services/model/model.service';
import { ToolService } from '../../services/tool/tool.service';
import { ManagedModel } from '../../admin/manage-models/models/managed-model.model';

@Component({
  selector: 'app-model-settings',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgIcon],
  providers: [provideIcons({ heroXMark, heroCheck, heroChevronDown })],
  templateUrl: './model-settings.html',
  styleUrl: './model-settings.css',
})
export class ModelSettings {
  private elementRef = inject(ElementRef);
  protected modelService = inject(ModelService);
  protected toolService = inject(ToolService);

  // Input to control visibility
  isOpen = input<boolean>(false);

  // Track if panel has ever been opened to avoid initial animation
  protected hasBeenOpened = signal(false);

  // Model dropdown state
  protected isModelDropdownOpen = signal(false);
  protected focusedOptionIndex = signal(-1);

  // Output event when panel should close
  closed = output<void>();

  constructor() {
    // Track when panel is first opened and manage body scroll
    effect(() => {
      const isOpen = this.isOpen();

      if (isOpen && !this.hasBeenOpened()) {
        this.hasBeenOpened.set(true);
      }

      // Prevent background scrolling when panel is open
      if (isOpen) {
        document.body.style.overflow = 'hidden';
      } else {
        document.body.style.overflow = '';
      }
    });
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    // Close dropdown if clicking outside
    if (this.isModelDropdownOpen() && !this.elementRef.nativeElement.contains(event.target)) {
      this.isModelDropdownOpen.set(false);
    }
  }

  close(): void {
    this.closed.emit();
  }

  toggleModelDropdown(): void {
    this.isModelDropdownOpen.update(open => !open);
    if (this.isModelDropdownOpen()) {
      // Set focus to currently selected model
      const models = this.modelService.availableModels();
      const selectedModel = this.modelService.selectedModel();
      const selectedIndex = models.findIndex(m => m.modelId === selectedModel?.modelId);
      this.focusedOptionIndex.set(selectedIndex >= 0 ? selectedIndex : 0);
    }
  }

  selectModel(model: ManagedModel): void {
    this.modelService.setSelectedModel(model);
    this.isModelDropdownOpen.set(false);
  }

  isModelSelected(model: ManagedModel): boolean {
    return this.modelService.selectedModel()?.modelId === model.modelId;
  }

  onDropdownKeydown(event: KeyboardEvent): void {
    const models = this.modelService.availableModels();
    const currentIndex = this.focusedOptionIndex();

    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        if (!this.isModelDropdownOpen()) {
          this.isModelDropdownOpen.set(true);
          this.focusedOptionIndex.set(0);
        } else {
          this.focusedOptionIndex.set(Math.min(currentIndex + 1, models.length - 1));
        }
        break;
      case 'ArrowUp':
        event.preventDefault();
        if (this.isModelDropdownOpen()) {
          this.focusedOptionIndex.set(Math.max(currentIndex - 1, 0));
        }
        break;
      case 'Enter':
      case ' ':
        event.preventDefault();
        if (this.isModelDropdownOpen() && currentIndex >= 0 && currentIndex < models.length) {
          this.selectModel(models[currentIndex]);
        } else {
          this.toggleModelDropdown();
        }
        break;
      case 'Escape':
        event.preventDefault();
        this.isModelDropdownOpen.set(false);
        break;
      case 'Tab':
        this.isModelDropdownOpen.set(false);
        break;
    }
  }

  toggleTool(toolId: string): void {
    this.toolService.toggleTool(toolId);
  }
}
