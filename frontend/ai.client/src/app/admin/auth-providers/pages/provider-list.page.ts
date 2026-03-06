import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  computed,
  effect,
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { NgIcon, provideIcons } from '@ng-icons/core';
import {
  heroPlus,
  heroMagnifyingGlass,
  heroPencilSquare,
  heroTrash,
  heroXMark,
  heroArrowPath,
  heroArrowLeft,
  heroFingerPrint,
  heroCheckCircle,
  heroXCircle,
  heroExclamationTriangle,
  heroServerStack,
  heroLink,
} from '@ng-icons/heroicons/outline';
import { heroClockSolid } from '@ng-icons/heroicons/solid';
import { AuthProvidersService } from '../services/auth-providers.service';
import { AuthProvider } from '../models/auth-provider.model';

@Component({
  selector: 'app-auth-provider-list',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, FormsModule, NgIcon],
  providers: [
    provideIcons({
      heroPlus,
      heroMagnifyingGlass,
      heroPencilSquare,
      heroTrash,
      heroXMark,
      heroArrowPath,
      heroArrowLeft,
      heroFingerPrint,
      heroCheckCircle,
      heroXCircle,
      heroExclamationTriangle,
      heroClockSolid,
      heroServerStack,
      heroLink,
    }),
  ],
  host: {
    class: 'block p-6',
  },
  template: `
    <!-- Back Button -->
    <a
      routerLink="/admin"
      class="mb-6 inline-flex items-center gap-2 text-sm/6 font-medium text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white"
    >
      <ng-icon name="heroArrowLeft" class="size-4" />
      Back to Admin
    </a>

    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="text-3xl/9 font-bold">Authentication Providers</h1>
        <p class="text-gray-600 dark:text-gray-400">
          Configure OIDC authentication providers for user login.
        </p>
      </div>
      <a
        routerLink="/admin/auth-providers/new"
        class="inline-flex items-center gap-2 rounded-sm bg-blue-600 px-4 py-2 text-sm/6 font-medium text-white hover:bg-blue-700 focus:outline-hidden focus:ring-3 focus:ring-blue-500/50 dark:bg-blue-500 dark:hover:bg-blue-600"
      >
        <ng-icon name="heroPlus" class="size-5" />
        Add Provider
      </a>
    </div>

    <!-- Runtime Version Summary -->
    @if (currentImageTag() && hasAnyRuntimeInfo()) {
      <div class="mb-6 rounded-sm border border-blue-200 bg-blue-50 p-4 dark:border-blue-800 dark:bg-blue-900/20">
        <div class="flex items-start justify-between gap-4">
          <div class="flex items-start gap-3">
            <ng-icon name="heroServerStack" class="size-5 shrink-0 text-blue-600 dark:text-blue-400" />
            <div>
              <h3 class="text-sm font-medium text-blue-900 dark:text-blue-100">Runtime Version Status</h3>
              <div class="mt-1 flex flex-wrap items-center gap-3 text-sm">
                <div>
                  <span class="text-blue-700 dark:text-blue-300">Current Image Tag:</span>
                  <span class="ml-1 font-mono font-medium text-blue-900 dark:text-blue-100">{{ currentImageTag() }}</span>
                </div>
                <div class="h-4 w-px bg-blue-300 dark:bg-blue-700"></div>
                <div>
                  <span class="text-blue-700 dark:text-blue-300">Active Runtimes:</span>
                  <span class="ml-1 font-medium text-blue-900 dark:text-blue-100">{{ getProvidersWithRuntimes().length }}</span>
                </div>
                @if (getOutdatedRuntimesCount() > 0) {
                  <div class="h-4 w-px bg-blue-300 dark:bg-blue-700"></div>
                  <div class="flex items-center gap-1">
                    <ng-icon name="heroExclamationTriangle" class="size-4 text-yellow-600 dark:text-yellow-400" />
                    <span class="text-yellow-700 dark:text-yellow-300">Outdated:</span>
                    <span class="ml-1 font-medium text-yellow-900 dark:text-yellow-100">{{ getOutdatedRuntimesCount() }}</span>
                  </div>
                }
              </div>
            </div>
          </div>
        </div>
      </div>
    }

    <!-- Search and Filters -->
    <div class="mb-6 flex flex-wrap items-center gap-4">
      <div class="relative min-w-64 flex-1">
        <ng-icon
          name="heroMagnifyingGlass"
          class="absolute left-3 top-1/2 size-5 -translate-y-1/2 text-gray-400"
        />
        <input
          type="text"
          [(ngModel)]="searchQuery"
          placeholder="Search by name or ID..."
          class="w-full rounded-sm border border-gray-300 bg-white py-2 pl-10 pr-10 focus:border-blue-500 focus:ring-2 focus:ring-blue-500 dark:border-gray-500 dark:bg-gray-800 dark:text-white dark:placeholder-gray-400"
        />
        @if (searchQuery()) {
          <button
            (click)="searchQuery.set('')"
            class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
          >
            <ng-icon name="heroXMark" class="size-5" />
          </button>
        }
      </div>

      <select
        [ngModel]="enabledFilter()"
        (ngModelChange)="enabledFilter.set($event)"
        class="rounded-sm border border-gray-300 bg-white px-3 py-2 dark:border-gray-500 dark:bg-gray-800 dark:text-white"
      >
        <option value="">All Providers</option>
        <option value="enabled">Enabled Only</option>
        <option value="disabled">Disabled Only</option>
      </select>

      @if (hasActiveFilters()) {
        <button
          (click)="resetFilters()"
          class="text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
        >
          Clear Filters
        </button>
      }
    </div>

    <!-- Loading State -->
    @if (providersResource.isLoading() && providers().length === 0) {
      <div class="flex h-64 items-center justify-center">
        <div class="flex flex-col items-center gap-4">
          <div
            class="size-12 animate-spin rounded-full border-4 border-gray-300 border-t-blue-600 dark:border-gray-600"
          ></div>
          <p class="text-sm text-gray-500 dark:text-gray-400">
            Loading providers...
          </p>
        </div>
      </div>
    }

    <!-- Error State -->
    @if (providersResource.error()) {
      <div class="mb-6 rounded-sm border border-red-200 bg-red-50 p-4 text-red-800 dark:border-red-800 dark:bg-red-900/20 dark:text-red-200">
        <p>Failed to load authentication providers. Please try again.</p>
        <button
          (click)="authProvidersService.reload()"
          class="mt-2 text-sm underline hover:no-underline"
        >
          Retry
        </button>
      </div>
    }

    <!-- Providers List -->
    @if (!providersResource.isLoading() || providers().length > 0) {
      <div class="space-y-3">
        @for (provider of filteredProviders(); track provider.provider_id) {
          <div
            class="rounded-sm border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800"
          >
            <div class="p-4">
              <div class="flex items-start justify-between gap-4">
                <!-- Provider Info -->
                <div class="min-w-0 flex-1">
                  <div class="mb-1 flex items-center gap-2">
                    <span class="text-lg/7 font-medium">{{ provider.display_name }}</span>
                    @if (provider.enabled) {
                      <span class="inline-flex items-center gap-1 rounded-xs bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800 dark:bg-green-900/30 dark:text-green-300">
                        <ng-icon name="heroCheckCircle" class="size-3" />
                        Enabled
                      </span>
                    } @else {
                      <span class="inline-flex items-center gap-1 rounded-xs bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-700 dark:text-gray-400">
                        <ng-icon name="heroXCircle" class="size-3" />
                        Disabled
                      </span>
                    }
                    <span class="rounded-xs bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-800 dark:bg-blue-900/30 dark:text-blue-300">
                      {{ provider.provider_type.toUpperCase() }}
                    </span>
                  </div>
                  <p class="mb-2 text-sm text-gray-500 dark:text-gray-400">
                    {{ provider.provider_id }}
                  </p>

                  <!-- Provider Details Grid -->
                  <div class="grid grid-cols-1 gap-3 text-sm sm:grid-cols-3">
                    <!-- Issuer URL -->
                    <div>
                      <span class="font-medium text-gray-700 dark:text-gray-300">Issuer:</span>
                      <div class="mt-1 truncate text-gray-600 dark:text-gray-400" [title]="provider.issuer_url">
                        {{ provider.issuer_url }}
                      </div>
                    </div>

                    <!-- Client ID -->
                    <div>
                      <span class="font-medium text-gray-700 dark:text-gray-300">Client ID:</span>
                      <div class="mt-1 truncate text-gray-600 dark:text-gray-400" [title]="provider.client_id">
                        {{ provider.client_id }}
                      </div>
                    </div>

                    <!-- Scopes -->
                    <div>
                      <span class="font-medium text-gray-700 dark:text-gray-300">Scopes:</span>
                      <div class="mt-1 flex flex-wrap gap-1">
                        @for (scope of provider.scopes.split(' ').slice(0, 3); track scope) {
                          <span class="rounded-xs bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600 dark:bg-gray-700 dark:text-gray-400">
                            {{ scope }}
                          </span>
                        }
                        @if (provider.scopes.split(' ').length > 3) {
                          <span class="rounded-xs bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600 dark:bg-gray-700 dark:text-gray-400">
                            +{{ provider.scopes.split(' ').length - 3 }} more
                          </span>
                        }
                      </div>
                    </div>
                  </div>

                  <!-- Runtime Status Section -->
                  @if (hasRuntimeInfo(provider)) {
                    <div class="mt-4 rounded-sm border border-gray-200 bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-900/50">
                      <div class="mb-2 flex items-center justify-between">
                        <div class="flex items-center gap-2">
                          <ng-icon name="heroServerStack" class="size-4 text-gray-500 dark:text-gray-400" />
                          <span class="text-sm font-medium text-gray-700 dark:text-gray-300">AgentCore Runtime</span>
                          <span 
                            [class]="'inline-flex items-center gap-1 rounded-xs px-2 py-0.5 text-xs font-medium ' + getRuntimeStatusBadgeClass(provider.agentcore_runtime_status)"
                          >
                            <ng-icon 
                              [name]="getRuntimeStatusIcon(provider.agentcore_runtime_status)" 
                              class="size-3"
                              [class.animate-spin]="provider.agentcore_runtime_status === 'CREATING' || provider.agentcore_runtime_status === 'UPDATING'"
                            />
                            {{ getRuntimeStatusLabel(provider.agentcore_runtime_status) }}
                          </span>
                        </div>
                        
                        <!-- Manual Update Button -->
                        @if (provider.agentcore_runtime_status === 'READY' && hasVersionMismatch(provider)) {
                          <button
                            (click)="updateRuntime(provider)"
                            [disabled]="updatingRuntime() === provider.provider_id"
                            class="inline-flex items-center gap-1 rounded-xs bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50 dark:bg-blue-500 dark:hover:bg-blue-600"
                            title="Update runtime to latest image version"
                          >
                            <ng-icon 
                              name="heroArrowPath" 
                              class="size-3"
                              [class.animate-spin]="updatingRuntime() === provider.provider_id"
                            />
                            Update Runtime
                          </button>
                        }
                      </div>

                      <div class="grid grid-cols-1 gap-2 text-xs sm:grid-cols-2">
                        <!-- Runtime ID -->
                        @if (provider.agentcore_runtime_id) {
                          <div>
                            <span class="font-medium text-gray-600 dark:text-gray-400">Runtime ID:</span>
                            <div class="mt-0.5 truncate font-mono text-gray-700 dark:text-gray-300" [title]="provider.agentcore_runtime_id">
                              {{ provider.agentcore_runtime_id }}
                            </div>
                          </div>
                        }

                        <!-- Runtime ARN -->
                        @if (provider.agentcore_runtime_arn) {
                          <div>
                            <span class="font-medium text-gray-600 dark:text-gray-400">Runtime ARN:</span>
                            <div class="mt-0.5 truncate font-mono text-gray-700 dark:text-gray-300" [title]="provider.agentcore_runtime_arn">
                              {{ provider.agentcore_runtime_arn }}
                            </div>
                          </div>
                        }

                        <!-- Endpoint URL -->
                        @if (provider.agentcore_runtime_endpoint_url) {
                          <div class="sm:col-span-2">
                            <span class="font-medium text-gray-600 dark:text-gray-400">Endpoint URL:</span>
                            <div class="mt-0.5 flex items-center gap-1">
                              <ng-icon name="heroLink" class="size-3 shrink-0 text-gray-500" />
                              <span class="truncate font-mono text-gray-700 dark:text-gray-300" [title]="provider.agentcore_runtime_endpoint_url">
                                {{ provider.agentcore_runtime_endpoint_url }}
                              </span>
                            </div>
                          </div>
                        }

                        <!-- Image Tag -->
                        @if (provider.agentcore_runtime_image_tag) {
                          <div>
                            <span class="font-medium text-gray-600 dark:text-gray-400">Image Tag:</span>
                            <div class="mt-0.5 flex items-center gap-1">
                              <span class="font-mono text-gray-700 dark:text-gray-300">
                                {{ provider.agentcore_runtime_image_tag }}
                              </span>
                              @if (hasVersionMismatch(provider)) {
                                <span 
                                  class="inline-flex items-center gap-0.5 rounded-xs bg-yellow-100 px-1.5 py-0.5 text-xs font-medium text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300"
                                  title="Runtime is using an older image version"
                                >
                                  <ng-icon name="heroExclamationTriangle" class="size-3" />
                                  Outdated
                                </span>
                              }
                            </div>
                          </div>
                        }
                      </div>

                      <!-- Error Message -->
                      @if (provider.agentcore_runtime_error) {
                        <div class="mt-2 rounded-xs border border-red-200 bg-red-50 p-2 dark:border-red-800 dark:bg-red-900/20">
                          <div class="flex items-start gap-2">
                            <ng-icon name="heroExclamationTriangle" class="size-4 shrink-0 text-red-600 dark:text-red-400" />
                            <div class="min-w-0 flex-1">
                              <p class="text-xs font-medium text-red-800 dark:text-red-200">Error Details:</p>
                              <p class="mt-1 text-xs text-red-700 dark:text-red-300">
                                {{ provider.agentcore_runtime_error }}
                              </p>
                            </div>
                          </div>
                        </div>
                      }
                    </div>
                  }
                </div>

                <!-- Actions -->
                <div class="flex shrink-0 items-center gap-2">
                  <button
                    (click)="testProvider(provider)"
                    [disabled]="testing() === provider.provider_id"
                    class="rounded-sm p-2 text-gray-500 hover:bg-gray-100 hover:text-green-600 disabled:opacity-50 dark:hover:bg-gray-700 dark:hover:text-green-400"
                    title="Test connectivity"
                  >
                    <ng-icon
                      name="heroArrowPath"
                      class="size-5"
                      [class.animate-spin]="testing() === provider.provider_id"
                    />
                  </button>
                  <a
                    [routerLink]="['/admin/auth-providers/edit', provider.provider_id]"
                    class="rounded-sm p-2 text-gray-500 hover:bg-gray-100 hover:text-blue-600 dark:hover:bg-gray-700 dark:hover:text-blue-400"
                    title="Edit provider"
                  >
                    <ng-icon name="heroPencilSquare" class="size-5" />
                  </a>
                  <button
                    (click)="deleteProvider(provider)"
                    class="rounded-sm p-2 text-gray-500 hover:bg-gray-100 hover:text-red-600 dark:hover:bg-gray-700 dark:hover:text-red-400"
                    title="Delete provider"
                  >
                    <ng-icon name="heroTrash" class="size-5" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        }
      </div>

      <!-- Empty State -->
      @if (filteredProviders().length === 0 && !providersResource.isLoading()) {
        <div class="py-12 text-center text-gray-500">
          <ng-icon name="heroFingerPrint" class="mx-auto mb-4 size-12 text-gray-300" />
          @if (hasActiveFilters()) {
            <p class="text-lg/7">No providers match your filters</p>
            <p class="text-sm/6">Try adjusting your search or filter criteria</p>
          } @else {
            <p class="text-lg/7">No authentication providers configured</p>
            <p class="mb-4 text-sm/6">Add your first OIDC provider to enable user authentication</p>
            <a
              routerLink="/admin/auth-providers/new"
              class="inline-flex items-center gap-2 rounded-sm bg-blue-600 px-4 py-2 text-sm/6 font-medium text-white hover:bg-blue-700"
            >
              <ng-icon name="heroPlus" class="size-5" />
              Add Provider
            </a>
          }
        </div>
      }
    }
  `,
})
export class AuthProviderListPage {
  authProvidersService = inject(AuthProvidersService);
  private router = inject(Router);

  readonly providersResource = this.authProvidersService.providersResource;

  searchQuery = signal('');
  enabledFilter = signal('');
  testing = signal<string | null>(null);
  currentImageTag = signal<string | null>(null);
  updatingRuntime = signal<string | null>(null);

  readonly providers = computed(() => this.authProvidersService.getProviders());

  constructor() {
    // Fetch current image tag when providers are loaded
    effect(() => {
      if (this.providers().length > 0 && !this.currentImageTag()) {
        this.fetchCurrentImageTag();
      }
    });
  }

  async fetchCurrentImageTag(): Promise<void> {
    try {
      const result = await this.authProvidersService.getCurrentImageTag();
      this.currentImageTag.set(result.image_tag);
    } catch (error) {
      console.error('Failed to fetch current image tag:', error);
    }
  }

  readonly filteredProviders = computed(() => {
    let providers = this.providers();
    const query = this.searchQuery().toLowerCase();
    const enabled = this.enabledFilter();

    if (query) {
      providers = providers.filter(
        p =>
          p.display_name.toLowerCase().includes(query) ||
          p.provider_id.toLowerCase().includes(query) ||
          p.issuer_url.toLowerCase().includes(query)
      );
    }

    if (enabled === 'enabled') {
      providers = providers.filter(p => p.enabled);
    } else if (enabled === 'disabled') {
      providers = providers.filter(p => !p.enabled);
    }

    return providers.sort((a, b) => {
      if (a.enabled !== b.enabled) return a.enabled ? -1 : 1;
      return a.display_name.localeCompare(b.display_name);
    });
  });

  readonly hasActiveFilters = computed(() => {
    return !!(this.searchQuery() || this.enabledFilter());
  });

  resetFilters(): void {
    this.searchQuery.set('');
    this.enabledFilter.set('');
  }

  async deleteProvider(provider: AuthProvider): Promise<void> {
    if (!confirm(`Are you sure you want to delete the provider "${provider.display_name}"? This action cannot be undone.`)) {
      return;
    }

    try {
      await this.authProvidersService.deleteProvider(provider.provider_id);
    } catch (error: any) {
      console.error('Error deleting provider:', error);
      const message = error?.error?.detail || error?.message || 'Failed to delete provider.';
      alert(message);
    }
  }

  async testProvider(provider: AuthProvider): Promise<void> {
    this.testing.set(provider.provider_id);
    try {
      const result = await this.authProvidersService.testProvider(provider.provider_id);
      if (result.status === 'ok') {
        alert(`Provider "${provider.display_name}" is working correctly.`);
      } else {
        alert(`Provider test returned: ${result.status}\n${JSON.stringify(result.details, null, 2)}`);
      }
    } catch (error: any) {
      console.error('Error testing provider:', error);
      const message = error?.error?.detail || error?.message || 'Failed to test provider.';
      alert(message);
    } finally {
      this.testing.set(null);
    }
  }

  getRuntimeStatusBadgeClass(status?: string): string {
    switch (status) {
      case 'READY':
        return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300';
      case 'CREATING':
      case 'UPDATING':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300';
      case 'PENDING':
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300';
      case 'FAILED':
      case 'UPDATE_FAILED':
        return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300';
      default:
        return 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400';
    }
  }

  getRuntimeStatusIcon(status?: string): string {
    switch (status) {
      case 'READY':
        return 'heroCheckCircle';
      case 'CREATING':
      case 'UPDATING':
        return 'heroArrowPath';
      case 'PENDING':
        return 'heroClockSolid';
      case 'FAILED':
      case 'UPDATE_FAILED':
        return 'heroExclamationTriangle';
      default:
        return 'heroXCircle';
    }
  }

  getRuntimeStatusLabel(status?: string): string {
    if (!status) return 'No Runtime';
    return status.replace(/_/g, ' ');
  }

  hasRuntimeInfo(provider: AuthProvider): boolean {
    return !!(provider.agentcore_runtime_arn || provider.agentcore_runtime_status);
  }

  hasVersionMismatch(provider: AuthProvider): boolean {
    if (!provider.agentcore_runtime_image_tag || !this.currentImageTag()) {
      return false;
    }
    return provider.agentcore_runtime_image_tag !== this.currentImageTag();
  }

  getProvidersWithRuntimes(): AuthProvider[] {
    return this.providers().filter(p => p.agentcore_runtime_status === 'READY');
  }

  hasAnyRuntimeInfo(): boolean {
    return this.providers().some(p => this.hasRuntimeInfo(p));
  }

  getOutdatedRuntimesCount(): number {
    return this.getProvidersWithRuntimes().filter(p => this.hasVersionMismatch(p)).length;
  }

  async updateRuntime(provider: AuthProvider): Promise<void> {
    if (!confirm(`Trigger manual runtime update for "${provider.display_name}"?\n\nThis will update the runtime to use the latest container image.`)) {
      return;
    }

    this.updatingRuntime.set(provider.provider_id);
    try {
      const result = await this.authProvidersService.triggerRuntimeUpdate(provider.provider_id);
      alert(`Runtime update triggered successfully.\n\n${result.message}`);
      // Reload providers to get updated status
      this.authProvidersService.reload();
    } catch (error: any) {
      console.error('Error updating runtime:', error);
      const message = error?.error?.detail || error?.message || 'Failed to trigger runtime update.';
      alert(`Failed to update runtime:\n\n${message}`);
    } finally {
      this.updatingRuntime.set(null);
    }
  }
}
