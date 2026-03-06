# Task 3.4: Update AuthService to Use ConfigService - Summary

## Overview

Task 3.4 updates the `AuthService` to use `ConfigService` for both the API base URL and the authentication enabled flag, replacing direct imports from `environment.ts`.

## Implementation

### Changes Made

1. **Added ConfigService injection**
   - Imported `ConfigService` and `computed` from Angular
   - Injected `ConfigService` using `inject(ConfigService)`

2. **Created reactive base URL**
   - Added computed signal: `private readonly baseUrl = computed(() => this.config.appApiUrl())`
   - Replaced all `environment.appApiUrl` references with `this.baseUrl()`

3. **Updated authentication flag**
   - Replaced `environment.enableAuthentication` with `this.config.enableAuthentication()`
   - Updated in 4 methods: `isAuthenticationEnabled()`, `isAuthenticated()`, `ensureAuthenticated()`, `logout()`

4. **Removed environment import**
   - Deleted unused `import { environment } from '../../environments/environment'`

### Code Changes

#### Before
```typescript
import { environment } from '../../environments/environment';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private http = inject(HttpClient);

  isAuthenticationEnabled(): boolean {
    return environment.enableAuthentication;
  }

  async refreshAccessToken(): Promise<TokenRefreshResponse> {
    const response = await firstValueFrom(
      this.http.post<TokenRefreshResponse>(
        `${environment.appApiUrl}/auth/refresh`,
        request
      )
    );
  }
}
```

#### After
```typescript
import { ConfigService } from '../services/config.service';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private http = inject(HttpClient);
  private config = inject(ConfigService);
  
  // Computed signal for reactive base URL
  private readonly baseUrl = computed(() => this.config.appApiUrl());

  isAuthenticationEnabled(): boolean {
    return this.config.enableAuthentication();
  }

  async refreshAccessToken(): Promise<TokenRefreshResponse> {
    const response = await firstValueFrom(
      this.http.post<TokenRefreshResponse>(
        `${this.baseUrl()}/auth/refresh`,
        request
      )
    );
  }
}
```

## Methods Updated

### 1. `isAuthenticationEnabled()`
- Changed from: `return environment.enableAuthentication`
- Changed to: `return this.config.enableAuthentication()`

### 2. `isAuthenticated()`
- Changed from: `if (!environment.enableAuthentication)`
- Changed to: `if (!this.config.enableAuthentication())`

### 3. `refreshAccessToken()`
- Changed from: `${environment.appApiUrl}/auth/refresh`
- Changed to: `${this.baseUrl()}/auth/refresh`

### 4. `login()`
- Changed from: `${environment.appApiUrl}/auth/login`
- Changed to: `${this.baseUrl()}/auth/login`

### 5. `ensureAuthenticated()`
- Changed from: `if (!environment.enableAuthentication)`
- Changed to: `if (!this.config.enableAuthentication())`

### 6. `logout()`
- Changed from: `if (!environment.enableAuthentication)`
- Changed to: `if (!this.config.enableAuthentication())`
- Changed from: `${environment.appApiUrl}/auth/logout`
- Changed to: `${this.baseUrl()}/auth/logout`

## Acceptance Criteria ✅

- [x] ConfigService injected in AuthService
- [x] `environment.enableAuthentication` replaced with `config.enableAuthentication()`
- [x] `environment.appApiUrl` replaced with computed signal `baseUrl()`
- [x] Authentication logic uses config correctly
- [x] No references to environment remain in AuthService
- [x] All HTTP requests use the reactive base URL

## Benefits

1. **Runtime Configuration**: Authentication behavior can be configured at deployment time
2. **Reactive Updates**: Base URL changes propagate automatically through computed signal
3. **Consistent Pattern**: Matches the pattern used in other services
4. **Type Safety**: TypeScript ensures correct usage of signals

## Testing Verification

The updated AuthService should be tested for:

1. **Authentication Enabled (Production)**
   - `config.enableAuthentication()` returns `true`
   - `isAuthenticated()` checks for valid token
   - `login()` redirects to OAuth provider
   - `logout()` clears tokens and redirects to logout URL

2. **Authentication Disabled (Local Dev)**
   - `config.enableAuthentication()` returns `false`
   - `isAuthenticated()` always returns `true`
   - `ensureAuthenticated()` returns immediately
   - `logout()` just clears tokens and redirects home

3. **API Calls**
   - Token refresh calls `${baseUrl()}/auth/refresh`
   - Login calls `${baseUrl()}/auth/login`
   - Logout calls `${baseUrl()}/auth/logout`
   - All URLs resolve correctly from ConfigService

## Files Modified

- `frontend/ai.client/src/app/auth/auth.service.ts` - Updated to use ConfigService

## Dependencies

This task depends on:
- Task 3.1: ConfigService implementation ✅
- Task 3.2: APP_INITIALIZER setup ✅

## Next Steps

Task 3.5 will update all remaining services that use `environment.appApiUrl` or `environment.inferenceApiUrl`.

## Notes

- The computed signal pattern ensures the base URL is always current
- Signal functions must be called with `()` - e.g., `this.baseUrl()` not `this.baseUrl`
- The service maintains backward compatibility - if config fails to load, it falls back to environment.ts
- Authentication flag is checked reactively, allowing runtime configuration changes
