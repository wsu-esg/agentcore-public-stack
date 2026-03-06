import { Component, ChangeDetectionStrategy, input, computed } from '@angular/core';
import { NgIcon, provideIcons } from '@ng-icons/core';
import {
  heroDocument,
  heroDocumentText,
  heroTableCells,
  heroCodeBracket,
  heroPhoto,
} from '@ng-icons/heroicons/outline';
import { formatBytes } from '../../../../../services/file-upload';
import { FileAttachmentData } from '../../../../services/models/message.model';

/**
 * Check if MIME type is an image
 */
function isImageMimeType(mimeType: string): boolean {
  return mimeType.startsWith('image/');
}

/**
 * File type to icon mapping
 */
const FILE_TYPE_ICONS: Record<string, string> = {
  'application/pdf': 'heroDocument',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'heroDocumentText',
  'text/plain': 'heroDocumentText',
  'text/html': 'heroCodeBracket',
  'text/csv': 'heroTableCells',
  'application/vnd.ms-excel': 'heroTableCells',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'heroTableCells',
  'text/markdown': 'heroDocumentText',
  'image/png': 'heroPhoto',
  'image/jpeg': 'heroPhoto',
  'image/gif': 'heroPhoto',
  'image/webp': 'heroPhoto',
};

/**
 * File type to color mapping for icon container
 */
const FILE_TYPE_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  'application/pdf': {
    bg: 'bg-rose-100 dark:bg-rose-900/60',
    text: 'text-rose-600 dark:text-rose-300',
    border: 'border-rose-300 dark:border-rose-700'
  },
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': {
    bg: 'bg-blue-100 dark:bg-blue-900/60',
    text: 'text-blue-600 dark:text-blue-300',
    border: 'border-blue-300 dark:border-blue-700'
  },
  'text/plain': {
    bg: 'bg-gray-100 dark:bg-gray-600',
    text: 'text-gray-600 dark:text-gray-200',
    border: 'border-gray-300 dark:border-gray-500'
  },
  'text/html': {
    bg: 'bg-orange-100 dark:bg-orange-900/60',
    text: 'text-orange-600 dark:text-orange-300',
    border: 'border-orange-300 dark:border-orange-700'
  },
  'text/csv': {
    bg: 'bg-green-100 dark:bg-green-900/60',
    text: 'text-green-600 dark:text-green-300',
    border: 'border-green-300 dark:border-green-700'
  },
  'application/vnd.ms-excel': {
    bg: 'bg-green-100 dark:bg-green-900/60',
    text: 'text-green-600 dark:text-green-300',
    border: 'border-green-300 dark:border-green-700'
  },
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': {
    bg: 'bg-green-100 dark:bg-green-900/60',
    text: 'text-green-600 dark:text-green-300',
    border: 'border-green-300 dark:border-green-700'
  },
  'text/markdown': {
    bg: 'bg-purple-100 dark:bg-purple-900/60',
    text: 'text-purple-600 dark:text-purple-300',
    border: 'border-purple-300 dark:border-purple-700'
  },
  'image/png': {
    bg: 'bg-indigo-100 dark:bg-indigo-900/60',
    text: 'text-indigo-600 dark:text-indigo-300',
    border: 'border-indigo-300 dark:border-indigo-700'
  },
  'image/jpeg': {
    bg: 'bg-indigo-100 dark:bg-indigo-900/60',
    text: 'text-indigo-600 dark:text-indigo-300',
    border: 'border-indigo-300 dark:border-indigo-700'
  },
  'image/gif': {
    bg: 'bg-indigo-100 dark:bg-indigo-900/60',
    text: 'text-indigo-600 dark:text-indigo-300',
    border: 'border-indigo-300 dark:border-indigo-700'
  },
  'image/webp': {
    bg: 'bg-indigo-100 dark:bg-indigo-900/60',
    text: 'text-indigo-600 dark:text-indigo-300',
    border: 'border-indigo-300 dark:border-indigo-700'
  },
};

const DEFAULT_COLORS = {
  bg: 'bg-gray-100 dark:bg-gray-600',
  text: 'text-gray-600 dark:text-gray-200',
  border: 'border-gray-300 dark:border-gray-500'
};

/**
 * Compact file attachment badge for displaying in user messages.
 *
 * This is a read-only display component (no remove/retry actions)
 * used for showing files that were attached to historical messages.
 * Styled consistently with the FileCardComponent.
 *
 * @example
 * ```html
 * <app-file-attachment-badge
 *   [attachment]="fileAttachment"
 * />
 * ```
 */
@Component({
  selector: 'app-file-attachment-badge',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgIcon],
  providers: [
    provideIcons({
      heroDocument,
      heroDocumentText,
      heroTableCells,
      heroCodeBracket,
      heroPhoto,
    })
  ],
  host: {
    'class': 'contents'
  },
  template: `
    <div
      class="flex w-48 shrink-0 items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 dark:border-gray-600 dark:bg-gray-800"
    >
      <!-- File icon -->
      <div
        class="flex size-8 shrink-0 items-center justify-center rounded-md border"
        [class]="iconContainerClass()"
      >
        <ng-icon [name]="iconName()" class="size-5" [class]="iconClass()" aria-hidden="true" />
      </div>

      <!-- File info -->
      <div class="min-w-0 flex-1">
        <p class="truncate text-sm font-medium text-gray-900 dark:text-white">
          {{ attachment().filename }}
        </p>
        <p class="text-xs text-gray-500 dark:text-gray-400">
          {{ formattedSize() }}
        </p>
      </div>
    </div>
  `,
})
export class FileAttachmentBadgeComponent {
  /** File attachment data */
  readonly attachment = input.required<FileAttachmentData>();

  protected readonly formattedSize = computed(() =>
    formatBytes(this.attachment().sizeBytes)
  );

  protected readonly isImage = computed(() =>
    isImageMimeType(this.attachment().mimeType)
  );

  protected readonly iconName = computed(() => {
    const mime = this.attachment().mimeType;
    return FILE_TYPE_ICONS[mime] ?? 'heroDocument';
  });

  protected readonly colors = computed(() => {
    const mime = this.attachment().mimeType;
    return FILE_TYPE_COLORS[mime] ?? DEFAULT_COLORS;
  });

  protected readonly iconContainerClass = computed(() => {
    const colors = this.colors();
    return `${colors.bg} ${colors.border}`;
  });

  protected readonly iconClass = computed(() => {
    return this.colors().text;
  });
}
