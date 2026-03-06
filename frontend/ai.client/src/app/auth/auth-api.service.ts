import { Injectable, inject, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ConfigService } from '../services/config.service';

/**
 * Response from the runtime endpoint API.
 */
export interface RuntimeEndpointResponse {
  runtime_endpoint_url: string;
  provider_id: string;
}

/**
 * Service for authentication-related API calls.
 * Handles runtime endpoint resolution for multi-provider authentication.
 */
@Injectable({
  providedIn: 'root'
})
export class AuthApiService {
  private http = inject(HttpClient);
  private config = inject(ConfigService);
  
  // Use computed signal for reactive base URL
  private readonly baseUrl = computed(() => `${this.config.appApiUrl()}/auth`);

  /**
   * Get the AgentCore Runtime endpoint URL for the user's auth provider.
   * 
   * The backend resolves the provider by extracting the issuer claim from the
   * user's JWT token and matching it against configured providers in the database.
   * Each provider has its own dedicated runtime with provider-specific JWT validation.
   * 
   * Flow:
   * 1. Frontend sends authenticated request (JWT in Authorization header)
   * 2. Backend extracts issuer from JWT (e.g., "https://login.microsoftonline.com/{tenant}/v2.0")
   * 3. Backend matches issuer to provider in database
   * 4. Backend returns runtime endpoint URL for that provider
   * 
   * @returns Observable of runtime endpoint response containing the endpoint URL and provider ID
   * @throws HTTP 404 if provider not found or runtime not ready
   * @throws HTTP 401 if user is not authenticated
   * 
   * @example
   * ```typescript
   * this.authApiService.getRuntimeEndpoint().subscribe({
   *   next: (response) => {
   *     console.log('Runtime endpoint:', response.runtime_endpoint_url);
   *     console.log('Provider:', response.provider_id);
   *     // Use this endpoint for inference API calls
   *   },
   *   error: (error) => {
   *     if (error.status === 404) {
   *       console.error('Runtime not found for provider');
   *     }
   *   }
   * });
   * ```
   */
  getRuntimeEndpoint(): Observable<RuntimeEndpointResponse> {
    return this.http.get<RuntimeEndpointResponse>(`${this.baseUrl()}/runtime-endpoint`);
  }
}
