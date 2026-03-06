import { Injectable, inject, computed } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { UserSearchResponse } from '../../assistants/models/assistant.model';
import { ConfigService } from '../../services/config.service';

@Injectable({
  providedIn: 'root'
})
export class UserApiService {
  private http = inject(HttpClient);
  private config = inject(ConfigService);
  
  // Use computed signal for reactive base URL
  private readonly baseUrl = computed(() => `${this.config.appApiUrl()}/users`);

  searchUsers(query: string, limit: number = 20): Observable<UserSearchResponse> {
    const params = new HttpParams()
      .set('q', query)
      .set('limit', limit.toString());
    
    return this.http.get<UserSearchResponse>(`${this.baseUrl()}/search`, { params });
  }
}
