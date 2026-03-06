# Frontend Authentication Strategy for Multi-Runtime Architecture

## Overview

The frontend authentication strategy has been updated to align with the backend's issuer-based provider resolution. The key insight is that **provider_id is never in the JWT token** - instead, the backend resolves the provider by matching the token's **issuer claim** against configured providers in the database.

## How It Works

### Backend Provider Resolution (Already Implemented)

```python
# In GenericOIDCJWTValidator.resolve_provider_from_token()

1. Decode JWT token (no signature verification)
2. Extract issuer claim: iss = "https://login.microsoftonline.com/{tenant}/v2.0"
3. Query enabled providers from DynamoDB
4. Match issuer to provider (handles variants like Entra ID v1/v2)
5. Return matched AuthProvider object
```

### Frontend Flow

```
User authenticates with provider
        ↓
Frontend receives JWT token (contains issuer claim, NOT provider_id)
        ↓
Frontend stores token in localStorage
        ↓
Frontend stores provider_id in sessionStorage (from login flow)
        ↓
When making inference request:
        ↓
Frontend calls GET /auth/runtime-endpoint (with JWT in Authorization header)
        ↓
Backend extracts issuer from JWT
        ↓
Backend matches issuer to provider in database
        ↓
Backend returns runtime endpoint URL + provider_id
        ↓
Frontend uses runtime endpoint URL for inference API calls
```

## Key Components

### 1. AuthApiService (`auth-api.service.ts`)

```typescript
/**
 * Get the AgentCore Runtime endpoint URL for the user's auth provider.
 * 
 * The backend resolves the provider by extracting the issuer claim from the
 * user's JWT token and matching it against configured providers in the database.
 */
getRuntimeEndpoint(): Observable<RuntimeEndpointResponse> {
  return this.http.get<RuntimeEndpointResponse>(`${this.baseUrl()}/auth/runtime-endpoint`);
}
```

**Response:**
```typescript
{
  runtime_endpoint_url: "https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/arn:aws:bedrock-agentcore:us-east-1:123456789012:agent/abc-123/invocations",
  provider_id: "entra-id"
}
```

### 2. AuthService (`auth.service.ts`)

**Simplified Approach:**
- No longer attempts to extract provider_id from JWT token
- Tracks provider_id in sessionStorage (set during login flow)
- Uses signal for reactive provider_id tracking
- Provider_id is used for:
  - Routing logout requests to correct provider
  - Routing refresh token requests to correct provider
  - Display purposes in UI

```typescript
// Signal for tracking current provider (from sessionStorage)
readonly currentProviderId = signal<string | null>(null);

// Get provider ID (for logout/refresh routing)
getProviderId(): string | null {
  return this.currentProviderId();
}
```

### 3. User Model (`user.model.ts`)

**No provider_id field:**
```typescript
export interface User {
  email: string;
  user_id: string;
  firstName: string;
  lastName: string;
  fullName: string;
  roles: string[];
  picture?: string;
  // NO provider_id - not in JWT token
}
```

## Backend API Endpoint (To Be Implemented)

### GET /auth/runtime-endpoint

**Purpose:** Return the runtime endpoint URL for the authenticated user's provider

**Authentication:** Required (JWT in Authorization header)

**Implementation:**
```python
@router.get("/auth/runtime-endpoint")
async def get_runtime_endpoint(current_user: User = Depends(get_current_user)):
    """
    Get the AgentCore Runtime endpoint URL for the user's auth provider.
    
    Resolves the provider from the user's JWT token issuer claim.
    """
    # Get the JWT token from the request
    token = request.headers.get("Authorization").replace("Bearer ", "")
    
    # Resolve provider from token's issuer claim
    generic_validator = _get_generic_validator()
    provider = await generic_validator.resolve_provider_from_token(token)
    
    if not provider:
        raise HTTPException(
            status_code=404,
            detail="Provider not found for token issuer"
        )
    
    if not provider.agentcore_runtime_endpoint_url:
        raise HTTPException(
            status_code=404,
            detail=f"Runtime not ready for provider {provider.provider_id}"
        )
    
    return {
        "runtime_endpoint_url": provider.agentcore_runtime_endpoint_url,
        "provider_id": provider.provider_id
    }
```

**Response Codes:**
- 200: Success - returns runtime endpoint URL
- 401: Unauthorized - invalid or missing JWT token
- 404: Provider not found or runtime not ready

## Why This Approach Works

### 1. Issuer is Standard OIDC Claim
Every OIDC-compliant JWT token contains an `iss` (issuer) claim:
```json
{
  "iss": "https://login.microsoftonline.com/{tenant}/v2.0",
  "sub": "user-id",
  "email": "user@example.com",
  "aud": "client-id",
  "exp": 1234567890
}
```

### 2. Backend Already Has Provider Resolution Logic
The `GenericOIDCJWTValidator` already implements issuer-based provider resolution:
- Handles issuer variants (Entra ID v1 vs v2)
- Caches issuer → provider mappings
- Queries enabled providers from DynamoDB

### 3. No Frontend Token Parsing Required
- Frontend doesn't need to decode JWT tokens
- Frontend doesn't need to understand issuer formats
- Backend handles all provider resolution logic
- Frontend just calls the API and gets the runtime URL

### 4. Consistent with Existing Auth Flow
- Login flow already stores provider_id in sessionStorage
- Logout/refresh already use stored provider_id for routing
- Runtime endpoint resolution follows the same pattern

## Usage Example

### In Chat Service (Inference Requests)

```typescript
export class ChatService {
  private authApiService = inject(AuthApiService);
  private http = inject(HttpClient);
  
  async sendMessage(message: string): Promise<void> {
    // 1. Get runtime endpoint URL for user's provider
    const runtimeInfo = await firstValueFrom(
      this.authApiService.getRuntimeEndpoint()
    );
    
    // 2. Use provider-specific runtime endpoint
    const response = await firstValueFrom(
      this.http.post(runtimeInfo.runtime_endpoint_url, {
        message: message,
        // ... other payload
      })
    );
    
    // 3. Process response
    console.log('Response from runtime:', response);
  }
}
```

### Error Handling

```typescript
this.authApiService.getRuntimeEndpoint().subscribe({
  next: (response) => {
    // Use runtime endpoint URL
    this.runtimeEndpointUrl = response.runtime_endpoint_url;
  },
  error: (error) => {
    if (error.status === 404) {
      // Provider not found or runtime not ready
      this.showError('Your authentication provider is not configured. Please contact support.');
    } else if (error.status === 401) {
      // Token expired or invalid
      this.authService.logout();
    }
  }
});
```

## Benefits of This Approach

1. **Simpler Frontend**: No JWT parsing, no issuer extraction
2. **Backend Controls Resolution**: All provider matching logic in one place
3. **Consistent with Existing Patterns**: Uses same validator as authentication
4. **Handles Issuer Variants**: Backend already handles Entra ID v1/v2, etc.
5. **Cacheable**: Backend can cache issuer → provider mappings
6. **Secure**: Frontend never needs to parse or validate tokens

## Migration Notes

### What Changed
- Removed provider_id extraction from JWT tokens in frontend
- Simplified AuthService to only track provider_id from sessionStorage
- Removed provider_id field from User model
- Updated AuthApiService documentation to reflect issuer-based resolution

### What Stayed the Same
- Backend provider resolution logic (already implemented)
- Login flow (still stores provider_id in sessionStorage)
- Logout/refresh routing (still uses stored provider_id)
- Token storage and validation

### Next Steps
1. Implement GET /auth/runtime-endpoint backend endpoint (Task 15)
2. Update frontend chat service to fetch runtime endpoint (Task 13)
3. Test end-to-end flow with multiple providers
