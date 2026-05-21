import {
  Component, ChangeDetectionStrategy, signal, inject, OnInit
} from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { NgIf } from '@angular/common';
import { firstValueFrom } from 'rxjs';
import { BrandingService, BrandingColors } from '../../services/branding/branding.service';

interface BrandingResponse {
  colors?: { primary: string; secondary: string; tertiary: string };
  logo_light_url?: string;
  logo_dark_url?: string;
  favicon_url?: string;
}

type AssetType = 'logo_light' | 'logo_dark' | 'favicon';

const API = '/api/admin/branding';

@Component({
  selector: 'app-branding-page',
  standalone: true,
  imports: [FormsModule, NgIf],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="max-w-3xl mx-auto px-4 py-8 space-y-10">
      <div>
        <h1 class="text-2xl font-bold text-gray-900 dark:text-white">Branding</h1>
        <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Customise the application colour palette and logo assets. Changes apply
          immediately to all users on next page load.
        </p>
      </div>

      <!-- Color Palette -->
      <section class="space-y-4">
        <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-100">Colour Palette</h2>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-6">
          @for (swatch of swatches(); track swatch.key) {
            <div class="flex flex-col gap-2">
              <label class="text-sm font-medium text-gray-700 dark:text-gray-300">{{ swatch.label }}</label>
              <div class="flex items-center gap-3">
                <input
                  type="color"
                  [value]="swatch.value"
                  (input)="onColorInput(swatch.key, $event)"
                  class="h-10 w-16 rounded border border-gray-300 dark:border-gray-600 cursor-pointer"
                />
                <span class="text-xs font-mono text-gray-500 dark:text-gray-400">{{ swatch.value }}</span>
              </div>
            </div>
          }
        </div>
        <div class="flex items-center gap-3 pt-2">
          <button
            (click)="saveColors()"
            [disabled]="savingColors()"
            class="px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
          >
            {{ savingColors() ? 'Saving…' : 'Save colours' }}
          </button>
          <button
            (click)="resetColors()"
            class="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white transition-colors"
          >
            Reset to defaults
          </button>
          @if (colorsSaved()) {
            <span class="text-sm text-green-600 dark:text-green-400">&#x2713; Saved</span>
          }
          @if (colorsError()) {
            <span class="text-sm text-red-600 dark:text-red-400">{{ colorsError() }}</span>
          }
        </div>
      </section>

      <!-- Logo Assets -->
      <section class="space-y-6">
        <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-100">Logo &amp; Favicon</h2>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-8">
          @for (asset of assetSlots(); track asset.type) {
            <div class="flex flex-col gap-3">
              <span class="text-sm font-medium text-gray-700 dark:text-gray-300">{{ asset.label }}</span>
              <div class="relative h-24 w-full rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-600 flex items-center justify-center overflow-hidden"
                [class.bg-gray-900]="asset.type === 'logo_dark'"
                [class.bg-gray-50]="asset.type !== 'logo_dark'">
                @if (asset.currentUrl) {
                  <img [src]="asset.currentUrl" alt="{{ asset.label }}" class="max-h-20 max-w-full object-contain p-2" />
                } @else {
                  <span class="text-xs text-gray-400">No image set</span>
                }
              </div>
              <label class="cursor-pointer">
                <span class="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors">
                  {{ uploadingAsset() === asset.type ? 'Uploading…' : 'Upload' }}
                </span>
                <input
                  type="file"
                  class="sr-only"
                  [accept]="asset.type === 'favicon' ? 'image/png,image/x-icon,image/webp' : 'image/png,image/jpeg,image/svg+xml,image/webp'"
                  (change)="onFileSelected(asset.type, $event)"
                />
              </label>
              @if (assetErrors()[asset.type]) {
                <span class="text-xs text-red-600 dark:text-red-400">{{ assetErrors()[asset.type] }}</span>
              }
              @if (assetSaved() === asset.type) {
                <span class="text-xs text-green-600 dark:text-green-400">&#x2713; Uploaded</span>
              }
            </div>
          }
        </div>
      </section>
    </div>
  `,
})
export class BrandingPage implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly brandingSvc = inject(BrandingService);

  readonly DEFAULT_PRIMARY = '#0033a0';
  readonly DEFAULT_SECONDARY = '#d64309';
  readonly DEFAULT_TERTIARY = '#0072ce';

  readonly primary = signal(this.DEFAULT_PRIMARY);
  readonly secondary = signal(this.DEFAULT_SECONDARY);
  readonly tertiary = signal(this.DEFAULT_TERTIARY);

  readonly savingColors = signal(false);
  readonly colorsSaved = signal(false);
  readonly colorsError = signal<string | null>(null);

  readonly uploadingAsset = signal<AssetType | null>(null);
  readonly assetSaved = signal<AssetType | null>(null);
  readonly assetErrors = signal<Partial<Record<AssetType, string>>>({});

  readonly logoLightUrl = signal<string | undefined>(undefined);
  readonly logoDarkUrl = signal<string | undefined>(undefined);
  readonly faviconUrl = signal<string | undefined>(undefined);

  readonly swatches = () => [
    { key: 'primary' as const, label: 'Primary', value: this.primary() },
    { key: 'secondary' as const, label: 'Secondary', value: this.secondary() },
    { key: 'tertiary' as const, label: 'Tertiary', value: this.tertiary() },
  ];

  readonly assetSlots = () => [
    { type: 'logo_light' as AssetType, label: 'Logo (light mode)', currentUrl: this.logoLightUrl() },
    { type: 'logo_dark' as AssetType, label: 'Logo (dark mode)', currentUrl: this.logoDarkUrl() },
    { type: 'favicon' as AssetType, label: 'Favicon', currentUrl: this.faviconUrl() },
  ];

  async ngOnInit(): Promise<void> {
    try {
      const cfg = await firstValueFrom(this.http.get<BrandingResponse>(API));
      if (cfg.colors) {
        this.primary.set(cfg.colors.primary);
        this.secondary.set(cfg.colors.secondary);
        this.tertiary.set(cfg.colors.tertiary);
      }
      this.logoLightUrl.set(cfg.logo_light_url);
      this.logoDarkUrl.set(cfg.logo_dark_url);
      this.faviconUrl.set(cfg.favicon_url);
    } catch { /* defaults remain */ }
  }

  onColorInput(key: 'primary' | 'secondary' | 'tertiary', event: Event): void {
    const value = (event.target as HTMLInputElement).value;
    if (key === 'primary') this.primary.set(value);
    else if (key === 'secondary') this.secondary.set(value);
    else this.tertiary.set(value);
    this.colorsSaved.set(false);
  }

  async saveColors(): Promise<void> {
    this.savingColors.set(true);
    this.colorsError.set(null);
    this.colorsSaved.set(false);
    const colors: BrandingColors = {
      primary: this.primary(),
      secondary: this.secondary(),
      tertiary: this.tertiary(),
    };
    try {
      await firstValueFrom(this.http.put(API, { colors }));
      this.brandingSvc.applyColors(colors);
      this.colorsSaved.set(true);
      setTimeout(() => this.colorsSaved.set(false), 3000);
    } catch {
      this.colorsError.set('Failed to save. Please try again.');
    } finally {
      this.savingColors.set(false);
    }
  }

  async resetColors(): Promise<void> {
    this.primary.set(this.DEFAULT_PRIMARY);
    this.secondary.set(this.DEFAULT_SECONDARY);
    this.tertiary.set(this.DEFAULT_TERTIARY);
    await this.saveColors();
  }

  async onFileSelected(assetType: AssetType, event: Event): Promise<void> {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (!file) return;
    this.uploadingAsset.set(assetType);
    this.assetSaved.set(null);
    this.assetErrors.update(e => ({ ...e, [assetType]: undefined }));
    try {
      // Step 1: get presigned PUT URL
      const presign = await firstValueFrom(this.http.post<{ presigned_url: string; s3_key: string }>(
        `${API}/presign-logo`,
        { asset_type: assetType, content_type: file.type, filename: file.name },
      ));
      // Step 2: upload directly to S3
      await firstValueFrom(
        this.http.put(presign.presigned_url, file, {
          headers: { 'Content-Type': file.type },
        })
      );
      // Step 3: save s3_key to branding config
      const field = assetType === 'logo_light' ? 'logo_light_s3_key'
        : assetType === 'logo_dark' ? 'logo_dark_s3_key' : 'favicon_s3_key';
      const updated = await firstValueFrom(
        this.http.put<BrandingResponse>(API, { [field]: presign.s3_key })
      );
      // Update preview
      if (assetType === 'logo_light') this.logoLightUrl.set(updated.logo_light_url);
      if (assetType === 'logo_dark') this.logoDarkUrl.set(updated.logo_dark_url);
      if (assetType === 'favicon') this.faviconUrl.set(updated.favicon_url);
      this.assetSaved.set(assetType);
      setTimeout(() => this.assetSaved.set(null), 3000);
    } catch {
      this.assetErrors.update(e => ({ ...e, [assetType]: 'Upload failed. Please try again.' }));
    } finally {
      this.uploadingAsset.set(null);
    }
  }
}