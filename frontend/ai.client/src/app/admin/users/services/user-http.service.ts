import { Injectable, inject, computed } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ConfigService } from '../../../services/config.service';
import {
  UserListResponse,
  UserDetailResponse,
  UserListRequestOptions,
} from '../models';

/**
 * HTTP service for admin user management API.
 * Communicates with FastAPI backend admin/users endpoints.
 */
@Injectable({
  providedIn: 'root',
})
export class UserHttpService {
  private http = inject(HttpClient);
  private config = inject(ConfigService);
  private baseUrl = computed(() => `${this.config.appApiUrl()}/admin/users`);

  /**
   * List users with optional filters and pagination.
   *
   * @param options Filter and pagination options
   * @returns Observable of paginated user list
   */
  listUsers(options: UserListRequestOptions = {}): Observable<UserListResponse> {
    let params = new HttpParams();

    if (options.status) {
      params = params.set('status', options.status);
    }
    if (options.domain) {
      params = params.set('domain', options.domain);
    }
    if (options.limit !== undefined) {
      params = params.set('limit', options.limit.toString());
    }
    if (options.cursor) {
      params = params.set('cursor', options.cursor);
    }

    return this.http.get<UserListResponse>(this.baseUrl(), { params });
  }

  /**
   * Search for a user by exact email match.
   *
   * @param email Email address to search for
   * @returns Observable of matching users (0 or 1)
   */
  searchByEmail(email: string): Observable<UserListResponse> {
    const params = new HttpParams().set('email', email);
    return this.http.get<UserListResponse>(`${this.baseUrl()}/search`, { params });
  }

  /**
   * Get comprehensive user detail.
   * Includes profile, cost summary, quota status, and recent events.
   *
   * @param userId User identifier
   * @returns Observable of user detail
   */
  getUserDetail(userId: string): Observable<UserDetailResponse> {
    return this.http.get<UserDetailResponse>(`${this.baseUrl()}/${encodeURIComponent(userId)}`);
  }

  /**
   * List distinct email domains.
   * Currently returns empty list - requires backend implementation.
   *
   * @param limit Maximum number of domains to return
   * @returns Observable of domain strings
   */
  listDomains(limit: number = 50): Observable<string[]> {
    const params = new HttpParams().set('limit', limit.toString());
    return this.http.get<string[]>(`${this.baseUrl()}/domains/list`, { params });
  }
}
