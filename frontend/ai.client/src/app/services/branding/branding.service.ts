import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { ConfigService } from '../config.service';

export interface BrandingColors {
  primary: string;
  secondary: string;
  tertiary: string;
  sidebar_bg?: string;
  sidebar_bg_dark?: string;
  chat_bg?: string;
  chat_bg_dark?: string;
}

export interface BrandingConfig {
  colors?: BrandingColors;
  logoLightUrl?: string;
  logoDarkUrl?: string;
  faviconUrl?: string;
}

const BRANDING_STYLE_ID = 'dynamic-branding';

@Injectable({ providedIn: 'root' })
export class BrandingService {
  private readonly http = inject(HttpClient);
  private readonly configService = inject(ConfigService);
  private _config: BrandingConfig = {};

  /** Reactive logo URL signals — updated at bootstrap and after admin uploads. */
  readonly logoLightUrl = signal<string | undefined>(undefined);
  readonly logoDarkUrl = signal<string | undefined>(undefined);

  get config(): BrandingConfig { return this._config; }

  /** Called once at app startup via APP_INITIALIZER. Failures are swallowed
   *  so a misconfigured branding endpoint never blocks the app from loading. */
  async bootstrap(): Promise<void> {
    try {
      const raw = await firstValueFrom(
        this.http.get<any>(`${this.configService.appApiUrl()}/branding`)
      );
      this._config = {
        colors: raw.colors,
        logoLightUrl: raw.logo_light_url ?? undefined,
        logoDarkUrl: raw.logo_dark_url ?? undefined,
        faviconUrl: raw.favicon_url ?? undefined,
      };
      this._applyColors(this._config.colors);
      this._applyFavicon(this._config.faviconUrl);
      this.logoLightUrl.set(this._config.logoLightUrl);
      this.logoDarkUrl.set(this._config.logoDarkUrl);
    } catch {
      // Branding endpoint unavailable — fall back to defaults silently
    }
  }

  /** Re-apply colors without a page reload. Called after admin saves changes. */
  applyColors(colors: BrandingColors | undefined): void {
    this._applyColors(colors);
  }

  /** Update logo URL signals after an admin upload so the sidenav refreshes
   *  immediately without a page reload. Pass undefined to leave unchanged. */
  applyLogoUrls(logoLightUrl?: string, logoDarkUrl?: string): void {
    if (logoLightUrl !== undefined) this.logoLightUrl.set(logoLightUrl);
    if (logoDarkUrl !== undefined) this.logoDarkUrl.set(logoDarkUrl);
  }

  private _applyColors(colors: BrandingColors | undefined): void {
    let existing = document.getElementById(BRANDING_STYLE_ID);
    if (!colors) {
      existing?.remove();
      return;
    }
    if (!existing) {
      existing = document.createElement('style');
      existing.id = BRANDING_STYLE_ID;
      document.head.appendChild(existing);
    }
    // Override the base color variables; the @theme oklch() expressions
    // derive every shade from these three variables automatically.
    // Also override structural surface variables so sidenav/topbar background
    // colors update live without a page reload.
    existing.textContent = `
      :root {
        --color-primary-base: ${colors.primary};
        --color-secondary-base: ${colors.secondary};
        --color-tertiary-base: ${colors.tertiary};
        --app-sidebar-bg: ${colors.sidebar_bg ?? '#f3f4f6'};
        --app-topbar-bg: ${colors.sidebar_bg ?? '#f9fafb'};
        --app-chat-bg: ${colors.chat_bg ?? '#f9fafb'};
      }
      html.dark {
        --app-sidebar-bg: ${colors.sidebar_bg_dark ?? '#111827'};
        --app-topbar-bg: ${colors.sidebar_bg_dark ?? '#111827'};
        --app-chat-bg: ${colors.chat_bg_dark ?? '#111827'};
      }
    `;
  }

  private _applyFavicon(url: string | undefined): void {
    if (!url) return;
    const link: HTMLLinkElement =
      document.querySelector("link[rel~='icon']") ??
      (() => {
        const el = document.createElement('link');
        el.rel = 'icon';
        document.head.appendChild(el);
        return el;
      })();
    link.href = url;
  }
}