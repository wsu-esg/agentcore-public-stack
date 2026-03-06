import { inject, Injectable, computed, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { ConfigService } from '../services/config.service';

export interface TokenRefreshRequest {
  refresh_token: string;
}

export interface TokenRefreshResponse {
  access_token: string;
  refresh_token: string;
  id_token?: string;
  token_type: string;
  expires_in: number;
  scope: string;
}

export interface LoginResponse {
  authorization_url: string;
  state: string;
}

export interface LogoutResponse {
  logout_url: string;
}

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private http = inject(HttpClient);
  private config = inject(ConfigService);
  private readonly tokenKey = 'access_token';
  private readonly refreshTokenKey = 'refresh_token';
  private readonly tokenExpiryKey = 'token_expiry';
  private readonly stateKey = 'auth_state';
  private readonly returnUrlKey = 'auth_return_url';
  private readonly providerIdKey = 'auth_provider_id';

  // Computed signal for reactive base URL
  private readonly baseUrl = computed(() => this.config.appApiUrl());

  /**
   * Signal tracking the current authentication provider ID.
   * Resolved from the JWT token's issuer claim by the backend.
   * Used for display purposes and tracking which provider the user authenticated with.
   * 
   * Note: The backend resolves the provider by matching the token's issuer claim
   * against configured providers. The frontend doesn't need to extract the issuer
   * directly - it just tracks the provider_id returned from the backend.
   */
  readonly currentProviderId = signal<string | null>(null);

  constructor() {
    // Initialize provider ID from localStorage
    this.updateProviderIdFromStorage();
  }

  /**
   * Get the current access token from localStorage.
   * @returns The access token or null if not found
   */
  getAccessToken(): string | null {
    return localStorage.getItem(this.tokenKey);
  }

  /**
   * Get the refresh token from localStorage.
   * @returns The refresh token or null if not found
   */
  getRefreshToken(): string | null {
    return localStorage.getItem(this.refreshTokenKey);
  }

  /**
   * Check if the current access token is expired or will expire soon.
   * @param bufferSeconds Buffer time in seconds before expiry to consider token expired (default: 60)
   * @returns True if token is expired or will expire soon
   */
  isTokenExpired(bufferSeconds: number = 60): boolean {
    const expiryStr = localStorage.getItem(this.tokenExpiryKey);
    if (!expiryStr) {
      return true; // No expiry info means expired
    }

    const expiryTime = parseInt(expiryStr, 10);
    const currentTime = Date.now();
    const bufferTime = bufferSeconds * 1000;

    return currentTime >= (expiryTime - bufferTime);
  }

  /**
   * Check if user is authenticated (has a valid token).
   * @returns True if user has a token that is not expired
   */
  isAuthenticated(): boolean {
    const token = this.getAccessToken();
    if (!token) {
      return false;
    }
    return !this.isTokenExpired();
  }

  /**
   * Refresh the access token using the refresh token.
   * @returns Promise resolving to the new token response
   */
  async refreshAccessToken(): Promise<TokenRefreshResponse> {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    try {
      const request: TokenRefreshRequest = {
        refresh_token: refreshToken
      };

      const providerId = this.getStoredProviderId();
      const refreshParams = new URLSearchParams();
      if (providerId) {
        refreshParams.set('provider_id', providerId);
      }
      const refreshQuery = refreshParams.toString();
      const refreshUrl = `${this.baseUrl()}/auth/refresh${refreshQuery ? `?${refreshQuery}` : ''}`;

      const response = await firstValueFrom(
        this.http.post<TokenRefreshResponse>(refreshUrl, request)
      );

      if (!response || !response.access_token) {
        throw new Error('Invalid token refresh response');
      }

      // Store the new tokens
      this.storeTokens(response);

      return response;
    } catch (error) {
      // Clear tokens on refresh failure
      this.clearTokens();
      throw error;
    }
  }

  /**
   * Store tokens in localStorage.
   * @param response Token response containing access_token, refresh_token, and expires_in
   */
  storeTokens(response: { access_token: string; refresh_token?: string; expires_in: number }): void {
    localStorage.setItem(this.tokenKey, response.access_token);

    if (response.refresh_token) {
      localStorage.setItem(this.refreshTokenKey, response.refresh_token);
    }

    // Calculate and store token expiry timestamp
    const expiryTime = Date.now() + response.expires_in * 1000;
    localStorage.setItem(this.tokenExpiryKey, expiryTime.toString());

    // Update provider ID from localStorage (set during login)
    this.updateProviderIdFromStorage();

    // Dispatch custom event to notify UserService of token change in same tab
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('token-stored', {
        detail: { token: response.access_token }
      }));
    }
  }

  /**
   * Clear all authentication tokens from localStorage.
   */
  clearTokens(): void {
    localStorage.removeItem(this.tokenKey);
    localStorage.removeItem(this.refreshTokenKey);
    localStorage.removeItem(this.tokenExpiryKey);
    localStorage.removeItem(this.providerIdKey);

    // Clear provider ID signal
    this.currentProviderId.set(null);

    // Dispatch custom event to notify UserService of token removal in same tab
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('token-cleared'));
    }
  }

  /**
   * Get the Authorization header value.
   * @returns Bearer token string or null
   */
  getAuthorizationHeader(): string | null {
    const token = this.getAccessToken();
    return token ? `Bearer ${token}` : null;
  }

  /**
   * Update provider ID from localStorage or clear it.
   * The provider ID is set during login and used for routing logout/refresh requests.
   * Stored in localStorage (not sessionStorage) so it persists across tabs and
   * browser restarts, matching the lifetime of the tokens it's used with.
   */
  private updateProviderIdFromStorage(): void {
    const storedProviderId = this.getStoredProviderId();
    this.currentProviderId.set(storedProviderId);
  }

  /**
   * Initiates the OIDC login flow by calling the backend login endpoint
   * and redirecting the user to the IdP for authentication.
   *
   * Stores the state token in sessionStorage for CSRF protection and
   * the provider ID in localStorage for multi-provider routing.
   *
   * @param providerId Optional auth provider ID for multi-provider support
   * @param redirectUri Optional redirect URI override
   * @param prompt Optional prompt parameter (defaults to "select_account")
   * @throws Error if login initiation fails
   */
  async login(providerId?: string, redirectUri?: string, prompt: string = 'select_account'): Promise<void> {
    try {
      // Build query parameters
      const params = new URLSearchParams();
      if (providerId) {
        params.set('provider_id', providerId);
      }
      if (redirectUri) {
        params.set('redirect_uri', redirectUri);
      }
      params.set('prompt', prompt);

      const queryString = params.toString();
      const url = `${this.baseUrl()}/auth/login${queryString ? `?${queryString}` : ''}`;

      const response = await firstValueFrom(
        this.http.get<LoginResponse>(url)
      );

      if (!response || !response.authorization_url || !response.state) {
        throw new Error('Invalid login response');
      }

      // Store state token in sessionStorage for CSRF protection
      sessionStorage.setItem(this.stateKey, response.state);

      // Store provider ID in localStorage for refresh/logout routing
      // (must persist across tabs/restarts to match token lifetime)
      if (providerId) {
        localStorage.setItem(this.providerIdKey, providerId);
      }

      // Redirect to authorization URL
      window.location.href = response.authorization_url;
    } catch (error) {
      // Clear any stored state on error
      sessionStorage.removeItem(this.stateKey);

      if (error instanceof Error) {
        throw error;
      }
      throw new Error('Failed to initiate login');
    }
  }

  /**
   * Get the stored state token from sessionStorage.
   * @returns The state token or null if not found
   */
  getStoredState(): string | null {
    return sessionStorage.getItem(this.stateKey);
  }

  /**
   * Clear the stored state token from sessionStorage.
   */
  clearStoredState(): void {
    sessionStorage.removeItem(this.stateKey);
  }

  /**
   * Get the stored return URL from sessionStorage.
   * @returns The return URL or null if not found
   */
  getStoredReturnUrl(): string | null {
    return sessionStorage.getItem(this.returnUrlKey);
  }

  /**
   * Clear the stored return URL from sessionStorage.
   */
  clearStoredReturnUrl(): void {
    sessionStorage.removeItem(this.returnUrlKey);
  }

  /**
   * Get the stored provider ID from localStorage.
   * Used to route refresh and logout requests to the correct provider.
   */
  getStoredProviderId(): string | null {
    return localStorage.getItem(this.providerIdKey);
  }

  /**
   * Get the current provider ID from the signal.
   * This is extracted from the JWT token or retrieved from localStorage.
   * @returns The current provider ID or null if not available
   */
  getProviderId(): string | null {
    return this.currentProviderId();
  }

  /**
   * Ensures the user is authenticated before making an HTTP request.
   * Attempts to refresh the token if expired, throws an error if authentication fails.
   * 
   * This is a reusable utility for resource loaders and other async operations
   * that require authentication before proceeding.
   * 
   * @throws Error if user is not authenticated and token refresh fails
   * @returns Promise that resolves when user is authenticated
   * 
   * @example
   * ```typescript
   * // In a resource loader
   * readonly myResource = resource({
   *   loader: async () => {
   *     await this.authService.ensureAuthenticated();
   *     return this.http.get('/api/data').toPromise();
   *   }
   * });
   * ```
   */
  async ensureAuthenticated(): Promise<void> {
    // Check if user is authenticated
    if (this.isAuthenticated()) {
      return; // User is authenticated, proceed
    }

    // If not authenticated, try to refresh token if expired
    const token = this.getAccessToken();
    if (token && this.isTokenExpired()) {
      try {
        await this.refreshAccessToken();
        // Verify authentication after refresh
        if (this.isAuthenticated()) {
          return; // Refresh successful, proceed
        }
      } catch (error) {
        // Refresh failed, throw authentication error
        throw new Error('User is not authenticated. Please login again.');
      }
    }

    // No token or refresh failed, throw error
    throw new Error('User is not authenticated. Please login.');
  }

  /**
   * Logs the user out by clearing local tokens and redirecting to the
   * IdP's logout endpoint.
   *
   * This performs a complete logout:
   * 1. Clears all local tokens from localStorage
   * 2. Fetches the IdP logout URL from the backend
   * 3. Redirects the user to the IdP to end the session
   *
   * @param postLogoutRedirectUri Optional URL to redirect to after IdP logout
   * @throws Error if logout initiation fails
   */
  async logout(postLogoutRedirectUri?: string): Promise<void> {
    try {
      // Build query parameters
      const params = new URLSearchParams();
      const providerId = this.getStoredProviderId();
      if (providerId) {
        params.set('provider_id', providerId);
      }
      if (postLogoutRedirectUri) {
        params.set('post_logout_redirect_uri', postLogoutRedirectUri);
      }

      const queryString = params.toString();
      const url = `${this.baseUrl()}/auth/logout${queryString ? `?${queryString}` : ''}`;

      const response = await firstValueFrom(
        this.http.get<LogoutResponse>(url)
      );

      if (!response || !response.logout_url) {
        throw new Error('Invalid logout response');
      }

      // Clear local tokens first
      this.clearTokens();

      // Redirect to IdP logout
      window.location.href = response.logout_url;
    } catch (error) {
      // On error, still clear tokens and redirect to home
      this.clearTokens();

      if (error instanceof Error) {
        console.error('Logout error:', error.message);
      }

      // Redirect to home page as fallback
      window.location.href = '/';
    }
  }
}

