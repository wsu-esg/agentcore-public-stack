# Task 3.3: Update ApiService to Use ConfigService - Summary

## Overview

Task 3.3 demonstrates the pattern for updating services to use `ConfigService` instead of directly importing `environment`. Since there is no centralized `api.service.ts` file in the codebase, this task serves as a pattern demonstration using `UserApiService` as an example.

## Pattern Implementation

### Before (Using environment.ts)

```typescript
import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class UserApiService {
  private http = inject(HttpClient);
  private readonly baseUrl = `${environment.appApiUrl}/users`;

  searchUsers(query: string) {
    return this.http.get(`${this.baseUrl}/search`);
  }
}
```

### After (Using ConfigService)

```typescript
import { Injectable, inject, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ConfigService } from '../../services/config.service';

@Injectable({
  providedIn: 'root'
})
export class UserApiService {
  private http = inject(HttpClient);
  private config = inject(ConfigService);
  
  // Use computed signal for reactive base URL
  private readonly baseUrl = computed(() => `${this.config.appApiUrl()}/users`);

  searchUsers(query: string) {
    // Call baseUrl as a function since it's a computed signal
    return this.http.get(`${this.baseUrl()}/search`);
  }
}
```

## Key Changes

1. **Import ConfigService**: Replace `environment` import with `ConfigService`
2. **Inject ConfigService**: Add `private config = inject(ConfigService)`
3. **Import computed**: Add `computed` to Angular core imports
4. **Create computed signal**: Use `computed(() => this.config.appApiUrl())` for reactive base URL
5. **Call as function**: Use `this.baseUrl()` instead of `this.baseUrl` (it's a signal)
6. **Remove environment import**: Delete the unused environment import

## Benefits

- **Reactive**: Base URL updates automatically if config changes
- **Runtime configuration**: No rebuild needed when backend URLs change
- **Type-safe**: TypeScript ensures correct usage
- **Consistent**: Same pattern across all services

## Example Implementation

The pattern has been demonstrated in:
- `frontend/ai.client/src/app/users/services/user-api.service.ts`

## Services Pattern Variations

### Pattern 1: Simple baseUrl (Most Common)

```typescript
private readonly baseUrl = computed(() => `${this.config.appApiUrl()}/endpoint`);

// Usage in methods
this.http.get(`${this.baseUrl()}/resource`);
```

### Pattern 2: Direct URL construction (For single-use URLs)

```typescript
// No baseUrl property needed
this.http.get(`${this.config.appApiUrl()}/sessions/${id}`);
```

### Pattern 3: Multiple endpoints

```typescript
private readonly apiUrl = computed(() => this.config.appApiUrl());

// Usage in methods
this.http.get(`${this.apiUrl()}/sessions`);
this.http.get(`${this.apiUrl()}/messages`);
```

## Acceptance Criteria ✅

- [x] Pattern demonstrated using UserApiService
- [x] ConfigService injected and used for base URL
- [x] Computed signal used for reactive base URL
- [x] HTTP requests use the computed signal correctly
- [x] No references to environment.appApiUrl remain in example
- [x] Documentation created for pattern replication

## Next Steps

Task 3.5 will apply this pattern to all remaining services that use `environment.appApiUrl` or `environment.inferenceApiUrl`.

## Files Modified

- `frontend/ai.client/src/app/users/services/user-api.service.ts` - Updated to use ConfigService pattern
- `.kiro/specs/runtime-config/task-3.3-summary.md` - Created this documentation

## Testing

The pattern can be tested by:
1. Ensuring the app builds without errors
2. Verifying HTTP requests go to the correct backend URL
3. Checking that the service works in both local dev and deployed environments

## Notes

- The task name "Update ApiService" is conceptual - there is no single ApiService file
- This pattern applies to all services making HTTP calls to the backend
- The computed signal ensures reactivity if config changes at runtime
- Services should call `baseUrl()` as a function, not access it as a property
