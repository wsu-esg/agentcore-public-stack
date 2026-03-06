# Tool RBAC Specification (v2 - AppRole Integration)

## Document Information

| Field | Value |
|-------|-------|
| Version | 2.0 |
| Status | Draft |
| Created | 2025-01-XX |
| Updated | 2025-01-XX |
| Depends On | APP_ROLES_RBAC_SPEC.md |

---

## Overview

This specification defines an RBAC-based tool access system that **integrates with the existing AppRole system** (see `APP_ROLES_RBAC_SPEC.md`). The Tool Catalog provides administrators with:

1. A centralized catalog of all available tools with metadata
2. Integration with AppRoles for role-based access control
3. Public tools available to all authenticated users
4. Default enabled/disabled states per tool
5. User-level preference overrides
6. Bidirectional sync between tool assignments and AppRole grants

### Key Design Decision

Tool access is managed through **AppRoles**, not direct JWT role mappings. This provides:
- Single point of role management
- Consistent permission resolution across tools and models
- Inheritance support (tools granted to parent roles flow to child roles)
- Pre-computed effective permissions for fast authorization

---

## Current State

### Backend
- Tools are defined in `backend/src/agentcore/local_tools/` and `backend/src/agentcore/builtin_tools/`
- `ToolFilter` class filters tools based on user-enabled preferences
- **AppRole system is implemented** with `grantedTools` and `effectivePermissions.tools`

### Frontend
- Tools are hardcoded in `frontend/ai.client/src/app/session/services/tool/tool-settings.service.ts`
- Users can enable/disable tools manually
- **AppRole management UI exists** at `/admin/roles`

### What This Spec Adds
- Tool Catalog: Centralized tool metadata (display names, categories, icons, status)
- Admin Tool Management UI
- Tool ↔ AppRole bidirectional sync
- User tool preferences stored in backend

---

## Integration with AppRole System

### How Tool Access Works

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Tool Access Flow                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. User requests tool list                                                  │
│                                                                              │
│  2. AppRoleService.resolve_user_permissions(user)                           │
│     └── Returns UserEffectivePermissions with tools: ["tool1", "tool2", *]  │
│                                                                              │
│  3. ToolCatalogService.get_accessible_tools(effective_permissions)          │
│     └── Filters catalog by:                                                 │
│         - tool.is_public = true, OR                                         │
│         - tool.tool_id in effective_permissions.tools, OR                   │
│         - "*" in effective_permissions.tools (wildcard = all)               │
│                                                                              │
│  4. Merge with user preferences                                             │
│     └── User can enable/disable tools they have access to                   │
│                                                                              │
│  5. Return UserToolAccess[] to frontend                                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Permission Sources

| Source | Description | Example |
|--------|-------------|---------|
| Public Tool | `is_public=true` on tool | Calculator, Weather |
| AppRole Grant | Tool in role's `grantedTools` | Code Interpreter for "power_user" role |
| Inherited Grant | Tool granted via `inheritsFrom` chain | "researcher" inherits "basic_user" tools |
| Wildcard | `"*"` in effective permissions | System Admin has all tools |

---

## Data Models

### Tool Definition (Catalog Entry)

```python
# backend/src/api/tools/models.py

from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum
from datetime import datetime


class ToolCategory(str, Enum):
    """Categories for organizing tools in the UI."""
    SEARCH = "search"
    DATA = "data"
    VISUALIZATION = "visualization"
    DOCUMENT = "document"
    CODE = "code"
    BROWSER = "browser"
    COMMUNICATION = "communication"
    UTILITY = "utility"
    RESEARCH = "research"
    FINANCE = "finance"
    CUSTOM = "custom"


class ToolProtocol(str, Enum):
    """Protocol used to invoke the tool."""
    LOCAL = "local"           # Direct function call
    AWS_SDK = "aws_sdk"       # AWS Bedrock services
    MCP_GATEWAY = "mcp"       # MCP via AgentCore Gateway
    A2A = "a2a"               # Agent-to-Agent


class ToolStatus(str, Enum):
    """Availability status of the tool."""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    DISABLED = "disabled"
    COMING_SOON = "coming_soon"


class ToolDefinition(BaseModel):
    """
    Catalog entry for a tool.

    NOTE: Access control is managed via AppRoles, not stored directly on tools.
    The `allowed_app_roles` field is computed for display purposes only.
    """
    # Identity
    tool_id: str = Field(..., description="Unique identifier (e.g., 'get_current_weather')")

    # Display metadata
    display_name: str = Field(..., description="Human-readable name (e.g., 'Weather Lookup')")
    description: str = Field(..., description="Description of what the tool does")
    category: ToolCategory = Field(default=ToolCategory.UTILITY)
    icon: Optional[str] = Field(None, description="Icon identifier for UI (e.g., 'heroCloud')")

    # Technical metadata
    protocol: ToolProtocol = Field(..., description="How the tool is invoked")
    status: ToolStatus = Field(default=ToolStatus.ACTIVE)
    requires_api_key: bool = Field(default=False, description="Whether tool requires external API key")

    # Access control
    is_public: bool = Field(
        default=False,
        description="If true, tool is available to all authenticated users regardless of role"
    )

    # Computed field - which AppRoles grant this tool (for admin UI display)
    allowed_app_roles: List[str] = Field(
        default_factory=list,
        description="AppRole IDs that grant access to this tool (computed from AppRoles)"
    )

    # Default behavior
    enabled_by_default: bool = Field(
        default=False,
        description="If true, tool is enabled when user first accesses it"
    )

    # Audit
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = Field(None, description="User ID of admin who created this entry")
    updated_by: Optional[str] = Field(None, description="User ID of admin who last updated this")

    class Config:
        use_enum_values = True


class UserToolAccess(BaseModel):
    """
    Computed tool access for a specific user.
    Returned by the GET /tools endpoint.
    """
    tool_id: str
    display_name: str
    description: str
    category: ToolCategory
    icon: Optional[str]
    protocol: ToolProtocol
    status: ToolStatus

    # Access info
    granted_by: List[str] = Field(
        ...,
        description="List of sources that grant access (e.g., ['public', 'power_user', 'researcher'])"
    )
    enabled_by_default: bool

    # Current user state
    user_enabled: Optional[bool] = Field(
        None,
        description="User's explicit preference (None = use default)"
    )
    is_enabled: bool = Field(
        ...,
        description="Computed: user_enabled if set, else enabled_by_default"
    )


class UserToolPreference(BaseModel):
    """
    User's explicit tool preferences.
    Stored per-user, overrides default enabled state.
    """
    user_id: str
    tool_preferences: dict[str, bool] = Field(
        default_factory=dict,
        description="Map of tool_id -> enabled state"
    )
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

---

## DynamoDB Schema

### Table: `{env}-agentcore-tool-catalog`

Stores tool metadata only. Access control is managed in the AppRoles table.

| Attribute | Type | Description |
|-----------|------|-------------|
| PK | String | Partition key |
| SK | String | Sort key |
| GSI1PK | String | GSI for category queries |
| GSI1SK | String | GSI sort key |

#### Entity Patterns

**Tool Definition:**
```
PK: TOOL#{tool_id}
SK: METADATA
GSI1PK: CATEGORY#{category}
GSI1SK: TOOL#{tool_id}
data: { ...ToolDefinition fields }
```

**User Preferences:**
```
PK: USER#{user_id}
SK: TOOL_PREFERENCES
data: { ...UserToolPreference fields }
```

### Relationship to AppRoles Table

Tool grants are stored in the existing AppRoles table:

```
AppRole record:
  roleId: "power_user"
  grantedTools: ["code_interpreter", "browser_navigate", "deep_research"]
  effectivePermissions.tools: ["calculator", "web_search", "code_interpreter", ...]
```

The Tool Catalog stores only metadata. Authorization uses the AppRole effective permissions.

---

## API Endpoints

### Public Endpoints (Authenticated Users)

#### GET /api/tools

Returns tools available to the current user based on their AppRole permissions.

**Request:**
```http
GET /api/tools
Authorization: Bearer {jwt_token}
```

**Response:**
```json
{
  "tools": [
    {
      "toolId": "get_current_weather",
      "displayName": "Weather Lookup",
      "description": "Get current weather for a location",
      "category": "utility",
      "icon": "heroCloud",
      "protocol": "local",
      "status": "active",
      "grantedBy": ["public"],
      "enabledByDefault": false,
      "userEnabled": true,
      "isEnabled": true
    },
    {
      "toolId": "code_interpreter",
      "displayName": "Code Interpreter",
      "description": "Execute Python code in a sandbox",
      "category": "code",
      "icon": "heroCodeBracket",
      "protocol": "aws_sdk",
      "status": "active",
      "grantedBy": ["power_user"],
      "enabledByDefault": false,
      "userEnabled": null,
      "isEnabled": false
    }
  ],
  "categories": ["code", "utility"],
  "appRolesApplied": ["power_user", "basic_user"]
}
```

**Access Logic:**
```python
async def get_user_tools(user: User) -> List[UserToolAccess]:
    # 1. Get user's effective permissions from AppRoleService
    permissions = await app_role_service.resolve_user_permissions(user)

    # 2. Get all active tools from catalog
    all_tools = await tool_catalog_service.get_all_tools(status=ToolStatus.ACTIVE)

    # 3. Get user's preferences
    user_prefs = await tool_catalog_service.get_user_preferences(user.user_id)

    accessible_tools = []

    for tool in all_tools:
        granted_by = []

        # Check public access
        if tool.is_public:
            granted_by.append("public")

        # Check AppRole access (wildcard or specific)
        if "*" in permissions.tools or tool.tool_id in permissions.tools:
            # Add the AppRole IDs that grant this tool
            granted_by.extend(permissions.app_roles)

        # Skip if no access
        if not granted_by:
            continue

        # Determine enabled state
        user_enabled = user_prefs.tool_preferences.get(tool.tool_id)
        is_enabled = user_enabled if user_enabled is not None else tool.enabled_by_default

        accessible_tools.append(UserToolAccess(
            tool_id=tool.tool_id,
            display_name=tool.display_name,
            description=tool.description,
            category=tool.category,
            icon=tool.icon,
            protocol=tool.protocol,
            status=tool.status,
            granted_by=list(set(granted_by)),
            enabled_by_default=tool.enabled_by_default,
            user_enabled=user_enabled,
            is_enabled=is_enabled
        ))

    return sorted(accessible_tools, key=lambda t: (t.category, t.display_name))
```

#### PUT /api/tools/preferences

Save user's tool preferences.

**Request:**
```http
PUT /api/tools/preferences
Authorization: Bearer {jwt_token}
Content-Type: application/json

{
  "preferences": {
    "get_current_weather": true,
    "ddg_web_search": false
  }
}
```

**Validation:**
- Only accept tool_ids the user has access to
- Reject unknown tool_ids with 400 error

---

### Admin Endpoints

All admin endpoints require `require_admin` dependency.

#### GET /api/admin/tools

List all tools in the catalog with their role assignments.

**Response:**
```json
{
  "tools": [
    {
      "toolId": "code_interpreter",
      "displayName": "Code Interpreter",
      "description": "Execute Python code",
      "category": "code",
      "protocol": "aws_sdk",
      "status": "active",
      "isPublic": false,
      "allowedAppRoles": ["power_user", "researcher"],
      "enabledByDefault": false,
      "createdAt": "2025-01-10T08:00:00Z",
      "updatedAt": "2025-01-10T08:00:00Z"
    }
  ],
  "total": 15
}
```

The `allowedAppRoles` field is computed by querying which AppRoles have this tool in their `grantedTools` or `effectivePermissions.tools`.

#### POST /api/admin/tools

Create a new tool catalog entry.

**Request:**
```http
POST /api/admin/tools
Content-Type: application/json

{
  "toolId": "custom_research_tool",
  "displayName": "Research Assistant",
  "description": "Advanced research capabilities",
  "category": "research",
  "icon": "heroAcademicCap",
  "protocol": "mcp",
  "status": "active",
  "isPublic": false,
  "enabledByDefault": true
}
```

**Note:** This only creates the catalog entry. To grant access to AppRoles, use the role management endpoints or the bidirectional sync endpoints below.

#### PUT /api/admin/tools/{tool_id}

Update tool metadata.

#### DELETE /api/admin/tools/{tool_id}

Soft delete (sets status to "disabled") by default.

---

### Bidirectional Sync Endpoints

These endpoints maintain consistency between tool grants and AppRole definitions.

#### GET /api/admin/tools/{tool_id}/roles

Get AppRoles that grant access to this tool.

**Response:**
```json
{
  "toolId": "code_interpreter",
  "roles": [
    {
      "roleId": "power_user",
      "displayName": "Power User",
      "grantType": "direct",
      "enabled": true
    },
    {
      "roleId": "researcher",
      "displayName": "Researcher",
      "grantType": "inherited",
      "inheritedFrom": "power_user",
      "enabled": true
    }
  ]
}
```

#### PUT /api/admin/tools/{tool_id}/roles

Set which AppRoles grant access to this tool.

**Request:**
```http
PUT /api/admin/tools/code_interpreter/roles
Content-Type: application/json

{
  "appRoleIds": ["power_user", "researcher", "developer"]
}
```

**Behavior:**
1. For each roleId in the request, add tool_id to that role's `grantedTools`
2. For roles NOT in the request, remove tool_id from their `grantedTools`
3. Trigger permission recomputation for affected roles
4. Invalidate caches

This is equivalent to editing each AppRole individually but provides a tool-centric view.

#### POST /api/admin/tools/{tool_id}/roles/add

Add AppRoles to tool access (preserves existing).

**Request:**
```http
POST /api/admin/tools/code_interpreter/roles/add
Content-Type: application/json

{
  "appRoleIds": ["new_role"]
}
```

#### POST /api/admin/tools/{tool_id}/roles/remove

Remove AppRoles from tool access.

**Request:**
```http
POST /api/admin/tools/code_interpreter/roles/remove
Content-Type: application/json

{
  "appRoleIds": ["old_role"]
}
```

---

## Service Implementation

### ToolCatalogService

```python
# backend/src/api/tools/service.py

from typing import List, Optional
from api.tools.models import ToolDefinition, UserToolAccess, UserToolPreference
from api.tools.repository import ToolCatalogRepository
from api.rbac.service import AppRoleService
from api.rbac.models import AppRole
from shared.auth.models import User


class ToolCatalogService:
    """
    Service for tool catalog operations.

    Tool access is determined by AppRoles. This service provides:
    - Catalog management (CRUD for tool metadata)
    - User preference management
    - Access computation using AppRoleService
    - Bidirectional sync between tools and AppRoles
    """

    def __init__(
        self,
        repository: ToolCatalogRepository,
        app_role_service: AppRoleService,
        app_role_admin_service: AppRoleAdminService
    ):
        self.repository = repository
        self.app_role_service = app_role_service
        self.app_role_admin_service = app_role_admin_service

    async def get_user_accessible_tools(self, user: User) -> List[UserToolAccess]:
        """
        Get tools accessible to a user based on their AppRole permissions.
        """
        # Get effective permissions from AppRoleService
        permissions = await self.app_role_service.resolve_user_permissions(user)

        # Get all active tools
        all_tools = await self.repository.list_tools(status="active")

        # Get user preferences
        prefs = await self.repository.get_user_preferences(user.user_id)

        accessible = []
        for tool in all_tools:
            granted_by = self._compute_granted_by(tool, permissions)

            if not granted_by:
                continue

            user_enabled = prefs.tool_preferences.get(tool.tool_id)
            is_enabled = user_enabled if user_enabled is not None else tool.enabled_by_default

            accessible.append(UserToolAccess(
                tool_id=tool.tool_id,
                display_name=tool.display_name,
                description=tool.description,
                category=tool.category,
                icon=tool.icon,
                protocol=tool.protocol,
                status=tool.status,
                granted_by=granted_by,
                enabled_by_default=tool.enabled_by_default,
                user_enabled=user_enabled,
                is_enabled=is_enabled
            ))

        return sorted(accessible, key=lambda t: (t.category.value, t.display_name))

    def _compute_granted_by(
        self,
        tool: ToolDefinition,
        permissions: UserEffectivePermissions
    ) -> List[str]:
        """Compute which sources grant access to this tool."""
        granted_by = []

        if tool.is_public:
            granted_by.append("public")

        if "*" in permissions.tools or tool.tool_id in permissions.tools:
            granted_by.extend(permissions.app_roles)

        return list(set(granted_by))

    async def get_roles_for_tool(self, tool_id: str) -> List[dict]:
        """
        Get all AppRoles that grant access to a tool.
        Uses the ToolRoleMappingIndex GSI on AppRoles table.
        """
        return await self.app_role_admin_service.get_roles_granting_tool(tool_id)

    async def set_roles_for_tool(
        self,
        tool_id: str,
        app_role_ids: List[str],
        admin: User
    ) -> None:
        """
        Set which AppRoles grant access to a tool (bidirectional sync).

        This updates the grantedTools field on each affected AppRole.
        """
        # Get current roles that grant this tool
        current_roles = await self.get_roles_for_tool(tool_id)
        current_role_ids = {r["roleId"] for r in current_roles if r["grantType"] == "direct"}

        new_role_ids = set(app_role_ids)

        # Roles to add tool to
        to_add = new_role_ids - current_role_ids

        # Roles to remove tool from
        to_remove = current_role_ids - new_role_ids

        # Update each role
        for role_id in to_add:
            await self.app_role_admin_service.add_tool_to_role(role_id, tool_id, admin)

        for role_id in to_remove:
            await self.app_role_admin_service.remove_tool_from_role(role_id, tool_id, admin)

    async def sync_catalog_from_registry(self, dry_run: bool = True) -> dict:
        """
        Discover tools from backend registry and sync to catalog.

        Returns summary of discovered, orphaned, and unchanged tools.
        """
        from agentcore.local_tools import get_all_local_tools
        from agentcore.builtin_tools import get_all_builtin_tools

        registered_tools = get_all_local_tools() + get_all_builtin_tools()
        registered_ids = {t.name for t in registered_tools}

        catalog_tools = await self.repository.list_tools()
        catalog_ids = {t.tool_id for t in catalog_tools}

        discovered = []
        for tool in registered_tools:
            if tool.name not in catalog_ids:
                discovered.append({
                    "tool_id": tool.name,
                    "display_name": tool.name.replace("_", " ").title(),
                    "description": tool.description or "",
                    "protocol": self._infer_protocol(tool),
                    "action": "create"
                })

        orphaned = []
        for tool in catalog_tools:
            if tool.tool_id not in registered_ids:
                orphaned.append({
                    "tool_id": tool.tool_id,
                    "action": "mark_deprecated"
                })

        unchanged = list(catalog_ids & registered_ids)

        if not dry_run:
            for item in discovered:
                await self.repository.create_tool(ToolDefinition(**item))
            for item in orphaned:
                await self.repository.update_tool(item["tool_id"], {"status": "deprecated"})

        return {
            "discovered": discovered,
            "orphaned": orphaned,
            "unchanged": unchanged,
            "dry_run": dry_run
        }
```

### AppRoleAdminService Extensions

Add these methods to the existing `AppRoleAdminService`:

```python
# backend/src/api/rbac/admin_service.py (additions)

class AppRoleAdminService:
    # ... existing methods ...

    async def get_roles_granting_tool(self, tool_id: str) -> List[dict]:
        """
        Query which AppRoles grant access to a specific tool.
        Uses GSI2 (ToolRoleMappingIndex) for efficient lookup.
        """
        # Query GSI2: GSI2PK=TOOL#{tool_id}
        results = await self.repository.query_roles_by_tool(tool_id)

        roles = []
        for item in results:
            role = await self.get_role(item["roleId"])
            if role:
                # Determine if grant is direct or inherited
                grant_type = "direct" if tool_id in role.granted_tools else "inherited"
                inherited_from = None

                if grant_type == "inherited":
                    # Find which parent role provides this tool
                    for parent_id in role.inherits_from:
                        parent = await self.get_role(parent_id)
                        if parent and tool_id in parent.effective_permissions.tools:
                            inherited_from = parent_id
                            break

                roles.append({
                    "roleId": role.role_id,
                    "displayName": role.display_name,
                    "grantType": grant_type,
                    "inheritedFrom": inherited_from,
                    "enabled": role.enabled
                })

        return roles

    async def add_tool_to_role(
        self,
        role_id: str,
        tool_id: str,
        admin: User
    ) -> AppRole:
        """
        Add a tool to a role's grantedTools.
        Triggers permission recomputation.
        """
        role = await self.get_role(role_id)
        if not role:
            raise ValueError(f"Role '{role_id}' not found")

        if tool_id not in role.granted_tools:
            new_tools = role.granted_tools + [tool_id]
            return await self.update_role(role_id, {"grantedTools": new_tools}, admin)

        return role

    async def remove_tool_from_role(
        self,
        role_id: str,
        tool_id: str,
        admin: User
    ) -> AppRole:
        """
        Remove a tool from a role's grantedTools.
        Triggers permission recomputation.
        """
        role = await self.get_role(role_id)
        if not role:
            raise ValueError(f"Role '{role_id}' not found")

        if tool_id in role.granted_tools:
            new_tools = [t for t in role.granted_tools if t != tool_id]
            return await self.update_role(role_id, {"grantedTools": new_tools}, admin)

        return role
```

---

## Frontend Integration

### Updated ToolService

Replace hardcoded tool list with API-driven approach:

```typescript
// frontend/ai.client/src/app/services/tool/tool.service.ts

import { Injectable, inject, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface Tool {
  toolId: string;
  displayName: string;
  description: string;
  category: string;
  icon: string | null;
  protocol: string;
  status: string;
  grantedBy: string[];
  enabledByDefault: boolean;
  userEnabled: boolean | null;
  isEnabled: boolean;
}

export interface ToolsResponse {
  tools: Tool[];
  categories: string[];
  appRolesApplied: string[];
}

@Injectable({
  providedIn: 'root'
})
export class ToolService {
  private http = inject(HttpClient);
  private apiUrl = environment.apiUrl;

  // State
  private _tools = signal<Tool[]>([]);
  private _loading = signal(false);
  private _error = signal<string | null>(null);
  private _appRolesApplied = signal<string[]>([]);

  // Public readonly signals
  readonly tools = this._tools.asReadonly();
  readonly loading = this._loading.asReadonly();
  readonly error = this._error.asReadonly();
  readonly appRolesApplied = this._appRolesApplied.asReadonly();

  // Computed
  readonly enabledTools = computed(() =>
    this._tools().filter(t => t.isEnabled)
  );

  readonly enabledToolIds = computed(() =>
    this.enabledTools().map(t => t.toolId)
  );

  readonly toolsByCategory = computed(() => {
    const grouped = new Map<string, Tool[]>();
    for (const tool of this._tools()) {
      const list = grouped.get(tool.category) || [];
      list.push(tool);
      grouped.set(tool.category, list);
    }
    return grouped;
  });

  /**
   * Fetch available tools for the current user.
   * Should be called on app init or after login.
   */
  async loadTools(): Promise<void> {
    this._loading.set(true);
    this._error.set(null);

    try {
      const response = await firstValueFrom(
        this.http.get<ToolsResponse>(`${this.apiUrl}/tools`)
      );
      this._tools.set(response.tools);
      this._appRolesApplied.set(response.appRolesApplied);
    } catch (err) {
      this._error.set('Failed to load tools');
      console.error('Tool load error:', err);
    } finally {
      this._loading.set(false);
    }
  }

  /**
   * Toggle a tool's enabled state.
   */
  async toggleTool(toolId: string): Promise<void> {
    const tool = this._tools().find(t => t.toolId === toolId);
    if (!tool) return;

    const newState = !tool.isEnabled;

    // Optimistic update
    this._tools.update(tools =>
      tools.map(t =>
        t.toolId === toolId
          ? { ...t, isEnabled: newState, userEnabled: newState }
          : t
      )
    );

    try {
      await this.savePreferences({ [toolId]: newState });
    } catch (err) {
      // Revert on error
      this._tools.update(tools =>
        tools.map(t =>
          t.toolId === toolId
            ? { ...t, isEnabled: tool.isEnabled, userEnabled: tool.userEnabled }
            : t
        )
      );
      throw err;
    }
  }

  private async savePreferences(preferences: Record<string, boolean>): Promise<void> {
    await firstValueFrom(
      this.http.put(`${this.apiUrl}/tools/preferences`, { preferences })
    );
  }
}
```

### Admin Tool Management Component

```typescript
// frontend/ai.client/src/app/admin/tools/tool-management.page.ts

import {
  Component,
  inject,
  signal,
  computed,
  ChangeDetectionStrategy,
  OnInit
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule } from '@angular/forms';
import { NgIcon, provideIcons } from '@ng-icons/core';
import {
  heroPencil,
  heroTrash,
  heroPlus,
  heroUserGroup,
  heroArrowPath
} from '@ng-icons/heroicons/outline';
import { AdminToolService, ToolDefinition } from './admin-tool.service';
import { ToolRoleDialogComponent } from './tool-role-dialog.component';

@Component({
  selector: 'app-tool-management',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, ReactiveFormsModule, NgIcon, ToolRoleDialogComponent],
  providers: [provideIcons({ heroPencil, heroTrash, heroPlus, heroUserGroup, heroArrowPath })],
  template: `
    <div class="p-6">
      <div class="flex items-center justify-between mb-6">
        <h1 class="text-2xl/9 font-bold">Tool Catalog</h1>
        <div class="flex gap-2">
          <button
            (click)="syncFromRegistry()"
            [disabled]="syncing()"
            class="flex items-center gap-2 px-4 py-2 border rounded-sm hover:bg-gray-50">
            <ng-icon
              name="heroArrowPath"
              class="size-5"
              [class.animate-spin]="syncing()" />
            Sync from Registry
          </button>
          <button
            (click)="openCreateDialog()"
            class="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-sm hover:bg-blue-700">
            <ng-icon name="heroPlus" class="size-5" />
            Add Tool
          </button>
        </div>
      </div>

      <!-- Filters -->
      <div class="flex gap-4 mb-6">
        <select
          [value]="statusFilter()"
          (change)="statusFilter.set($any($event.target).value)"
          class="px-3 py-2 border rounded-sm">
          <option value="">All Statuses</option>
          <option value="active">Active</option>
          <option value="deprecated">Deprecated</option>
          <option value="disabled">Disabled</option>
        </select>

        <select
          [value]="categoryFilter()"
          (change)="categoryFilter.set($any($event.target).value)"
          class="px-3 py-2 border rounded-sm">
          <option value="">All Categories</option>
          @for (cat of categories(); track cat) {
            <option [value]="cat">{{ cat }}</option>
          }
        </select>
      </div>

      <!-- Tools Table -->
      <div class="bg-white dark:bg-gray-800 rounded-sm shadow-sm overflow-hidden">
        <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead class="bg-gray-50 dark:bg-gray-700">
            <tr>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Tool</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Category</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Access</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Default</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Status</th>
              <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-200 dark:divide-gray-700">
            @for (tool of filteredTools(); track tool.toolId) {
              <tr class="hover:bg-gray-50 dark:hover:bg-gray-700">
                <td class="px-6 py-4">
                  <div class="font-medium">{{ tool.displayName }}</div>
                  <div class="text-sm text-gray-500">{{ tool.toolId }}</div>
                </td>
                <td class="px-6 py-4">
                  <span class="px-2 py-1 text-xs rounded-full bg-gray-100 dark:bg-gray-600">
                    {{ tool.category }}
                  </span>
                </td>
                <td class="px-6 py-4">
                  @if (tool.isPublic) {
                    <span class="text-green-600 dark:text-green-400">Public</span>
                  } @else {
                    <span class="text-gray-600 dark:text-gray-400">
                      {{ tool.allowedAppRoles.length }} roles
                    </span>
                  }
                </td>
                <td class="px-6 py-4">
                  <span [class]="tool.enabledByDefault ? 'text-green-600 dark:text-green-400' : 'text-gray-400'">
                    {{ tool.enabledByDefault ? 'Enabled' : 'Disabled' }}
                  </span>
                </td>
                <td class="px-6 py-4">
                  <span [class]="getStatusClass(tool.status)">
                    {{ tool.status }}
                  </span>
                </td>
                <td class="px-6 py-4 text-right">
                  <button
                    (click)="openRoleDialog(tool)"
                    class="p-2 text-gray-500 hover:text-blue-600"
                    title="Manage Role Access">
                    <ng-icon name="heroUserGroup" class="size-5" />
                  </button>
                  <button
                    (click)="openEditDialog(tool)"
                    class="p-2 text-gray-500 hover:text-blue-600"
                    title="Edit Tool">
                    <ng-icon name="heroPencil" class="size-5" />
                  </button>
                  <button
                    (click)="deleteTool(tool)"
                    class="p-2 text-gray-500 hover:text-red-600"
                    title="Delete Tool">
                    <ng-icon name="heroTrash" class="size-5" />
                  </button>
                </td>
              </tr>
            }
          </tbody>
        </table>
      </div>

      <!-- Role Assignment Dialog -->
      @if (selectedToolForRoles()) {
        <app-tool-role-dialog
          [tool]="selectedToolForRoles()!"
          (closed)="selectedToolForRoles.set(null)"
          (saved)="onRolesSaved($event)" />
      }
    </div>
  `
})
export class ToolManagementPage implements OnInit {
  private adminToolService = inject(AdminToolService);

  // Filters
  statusFilter = signal('');
  categoryFilter = signal('');
  syncing = signal(false);

  // Dialogs
  selectedToolForRoles = signal<ToolDefinition | null>(null);

  // Data
  tools = this.adminToolService.tools;
  categories = computed(() =>
    [...new Set(this.tools().map(t => t.category))].sort()
  );

  filteredTools = computed(() => {
    let result = this.tools();

    const status = this.statusFilter();
    if (status) {
      result = result.filter(t => t.status === status);
    }

    const category = this.categoryFilter();
    if (category) {
      result = result.filter(t => t.category === category);
    }

    return result;
  });

  ngOnInit(): void {
    this.adminToolService.loadTools();
  }

  getStatusClass(status: string): string {
    switch (status) {
      case 'active': return 'text-green-600 dark:text-green-400';
      case 'deprecated': return 'text-yellow-600 dark:text-yellow-400';
      case 'disabled': return 'text-red-600 dark:text-red-400';
      default: return 'text-gray-600 dark:text-gray-400';
    }
  }

  openCreateDialog(): void {
    // Open dialog to create new tool
  }

  openEditDialog(tool: ToolDefinition): void {
    // Open dialog to edit tool
  }

  openRoleDialog(tool: ToolDefinition): void {
    this.selectedToolForRoles.set(tool);
  }

  async onRolesSaved(roleIds: string[]): Promise<void> {
    const tool = this.selectedToolForRoles();
    if (tool) {
      await this.adminToolService.setToolRoles(tool.toolId, roleIds);
      this.selectedToolForRoles.set(null);
    }
  }

  async deleteTool(tool: ToolDefinition): Promise<void> {
    if (confirm(`Delete tool "${tool.displayName}"?`)) {
      await this.adminToolService.deleteTool(tool.toolId);
    }
  }

  async syncFromRegistry(): Promise<void> {
    this.syncing.set(true);
    try {
      const result = await this.adminToolService.syncFromRegistry(false);
      alert(`Sync complete:\n- Created: ${result.discovered.length}\n- Deprecated: ${result.orphaned.length}`);
    } finally {
      this.syncing.set(false);
    }
  }
}
```

### Tool Role Assignment Dialog

```typescript
// frontend/ai.client/src/app/admin/tools/tool-role-dialog.component.ts

import {
  Component,
  ChangeDetectionStrategy,
  input,
  output,
  inject,
  signal,
  OnInit
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { NgIcon, provideIcons } from '@ng-icons/core';
import { heroXMark, heroCheck } from '@ng-icons/heroicons/outline';
import { AdminToolService, ToolDefinition, ToolRoleAssignment } from './admin-tool.service';
import { AppRolesService, AppRole } from '../roles/services/app-roles.service';

@Component({
  selector: 'app-tool-role-dialog',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, NgIcon],
  providers: [provideIcons({ heroXMark, heroCheck })],
  template: `
    <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div class="bg-white dark:bg-gray-800 rounded-sm shadow-lg w-full max-w-lg max-h-[80vh] overflow-hidden">
        <!-- Header -->
        <div class="flex items-center justify-between px-6 py-4 border-b dark:border-gray-700">
          <div>
            <h2 class="text-lg font-semibold">Manage Role Access</h2>
            <p class="text-sm text-gray-500">{{ tool().displayName }}</p>
          </div>
          <button (click)="closed.emit()" class="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-sm">
            <ng-icon name="heroXMark" class="size-5" />
          </button>
        </div>

        <!-- Content -->
        <div class="p-6 overflow-y-auto max-h-96">
          @if (loading()) {
            <p class="text-gray-500">Loading roles...</p>
          } @else {
            <p class="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Select which AppRoles should have access to this tool.
            </p>

            <div class="space-y-2">
              @for (role of allRoles(); track role.roleId) {
                <label
                  class="flex items-center gap-3 p-3 border rounded-sm hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer">
                  <input
                    type="checkbox"
                    [checked]="selectedRoleIds().has(role.roleId)"
                    (change)="toggleRole(role.roleId)"
                    class="size-4" />
                  <div class="flex-1">
                    <div class="font-medium">{{ role.displayName }}</div>
                    <div class="text-sm text-gray-500">{{ role.roleId }}</div>
                  </div>
                  @if (currentAssignments().has(role.roleId)) {
                    <span class="text-xs text-gray-400">
                      {{ getGrantType(role.roleId) }}
                    </span>
                  }
                </label>
              }
            </div>
          }
        </div>

        <!-- Footer -->
        <div class="flex items-center justify-between px-6 py-4 border-t dark:border-gray-700 bg-gray-50 dark:bg-gray-700">
          <p class="text-sm text-amber-600 dark:text-amber-400">
            Changes take effect within 5-10 minutes.
          </p>
          <div class="flex gap-2">
            <button
              (click)="closed.emit()"
              class="px-4 py-2 border rounded-sm hover:bg-gray-100 dark:hover:bg-gray-600">
              Cancel
            </button>
            <button
              (click)="save()"
              [disabled]="saving()"
              class="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-sm hover:bg-blue-700 disabled:opacity-50">
              <ng-icon name="heroCheck" class="size-4" />
              {{ saving() ? 'Saving...' : 'Save Changes' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  `
})
export class ToolRoleDialogComponent implements OnInit {
  tool = input.required<ToolDefinition>();
  closed = output<void>();
  saved = output<string[]>();

  private adminToolService = inject(AdminToolService);
  private appRolesService = inject(AppRolesService);

  loading = signal(true);
  saving = signal(false);
  allRoles = signal<AppRole[]>([]);
  currentAssignments = signal<Map<string, ToolRoleAssignment>>(new Map());
  selectedRoleIds = signal<Set<string>>(new Set());

  async ngOnInit(): Promise<void> {
    this.loading.set(true);
    try {
      // Load all roles and current assignments in parallel
      const [roles, assignments] = await Promise.all([
        this.appRolesService.listRoles(),
        this.adminToolService.getToolRoles(this.tool().toolId)
      ]);

      this.allRoles.set(roles.roles.filter(r => !r.isSystemRole || r.roleId !== 'system_admin'));

      const assignmentMap = new Map<string, ToolRoleAssignment>();
      for (const a of assignments) {
        assignmentMap.set(a.roleId, a);
      }
      this.currentAssignments.set(assignmentMap);

      // Initialize selected with direct grants only
      const directGrants = assignments.filter(a => a.grantType === 'direct').map(a => a.roleId);
      this.selectedRoleIds.set(new Set(directGrants));
    } finally {
      this.loading.set(false);
    }
  }

  toggleRole(roleId: string): void {
    this.selectedRoleIds.update(set => {
      const newSet = new Set(set);
      if (newSet.has(roleId)) {
        newSet.delete(roleId);
      } else {
        newSet.add(roleId);
      }
      return newSet;
    });
  }

  getGrantType(roleId: string): string {
    const assignment = this.currentAssignments().get(roleId);
    if (!assignment) return '';
    if (assignment.grantType === 'inherited') {
      return `inherited from ${assignment.inheritedFrom}`;
    }
    return 'direct';
  }

  async save(): Promise<void> {
    this.saving.set(true);
    try {
      const roleIds = Array.from(this.selectedRoleIds());
      this.saved.emit(roleIds);
    } finally {
      this.saving.set(false);
    }
  }
}
```

---

## Migration Strategy

### Phase 1: Tool Catalog Infrastructure

1. Create DynamoDB table for tool catalog (metadata only)
2. Implement `ToolCatalogRepository`
3. Create seed script to populate catalog from existing registry
4. Implement `/api/tools` and `/api/tools/preferences` endpoints

### Phase 2: AppRole Integration

1. Add `get_roles_granting_tool()` to AppRoleAdminService
2. Add `add_tool_to_role()` and `remove_tool_from_role()` methods
3. Implement bidirectional sync endpoints
4. Update ToolRoleMappingIndex (GSI2) queries

### Phase 3: Frontend Integration

1. Create `ToolService` to replace hardcoded list
2. Update tool settings UI to use dynamic data
3. Add tool loading to app initialization

### Phase 4: Admin UI

1. Create tool catalog management page
2. Create tool-role assignment dialog
3. Add sync from registry feature
4. Integrate with existing role management UI

### Phase 5: Cleanup

1. Remove hardcoded tool lists from frontend
2. Update documentation
3. Add monitoring/alerting

---

## Seed Data

Initial tool catalog entries (access controlled via AppRoles):

```json
{
  "tools": [
    {
      "toolId": "calculator",
      "displayName": "Calculator",
      "description": "Perform mathematical calculations",
      "category": "utility",
      "icon": "heroCalculator",
      "protocol": "local",
      "isPublic": true,
      "enabledByDefault": true
    },
    {
      "toolId": "get_current_weather",
      "displayName": "Weather Lookup",
      "description": "Get current weather conditions for a location",
      "category": "utility",
      "icon": "heroCloud",
      "protocol": "local",
      "isPublic": true,
      "enabledByDefault": false
    },
    {
      "toolId": "ddg_web_search",
      "displayName": "Web Search",
      "description": "Search the web using DuckDuckGo",
      "category": "search",
      "icon": "heroGlobeAlt",
      "protocol": "local",
      "isPublic": true,
      "enabledByDefault": false
    },
    {
      "toolId": "code_interpreter",
      "displayName": "Code Interpreter",
      "description": "Execute Python code and generate visualizations",
      "category": "code",
      "icon": "heroCodeBracket",
      "protocol": "aws_sdk",
      "isPublic": false,
      "enabledByDefault": false
    },
    {
      "toolId": "browser_navigate",
      "displayName": "Browser Navigation",
      "description": "Navigate to URLs in an automated browser",
      "category": "browser",
      "icon": "heroComputerDesktop",
      "protocol": "aws_sdk",
      "isPublic": false,
      "enabledByDefault": false
    }
  ]
}
```

**Note:** The `allowedAppRoles` field is computed at runtime by querying which AppRoles have each tool in their `grantedTools`.

---

## Security Considerations

### Authorization Enforcement

1. **AppRole-based Access**: Tool access derives from AppRole effective permissions
2. **Double Validation**: Tool access validated on both frontend (UI filtering) and backend (request validation)
3. **Audit Trail**: All admin actions logged with actor, timestamp, and changes
4. **Cache Consistency**: Tool access changes propagate via AppRole cache invalidation (5-10 min)

### Principle of Least Privilege

- Public tools explicitly marked with `isPublic: true`
- Non-public tools require explicit AppRole grant
- System admin has wildcard access (`"*"` in effective permissions)

---

## Open Questions (Resolved)

| Question | Resolution |
|----------|-----------|
| Role Discovery | Use AppRoles from existing RBAC system |
| Tool Dependencies | Future enhancement - not in initial scope |
| Usage Quotas | Handled by existing quota system |
| Tool Groups | AppRole inheritance provides grouping |

---

## Appendix: Comparison with v1 Spec

| Aspect | v1 (Original) | v2 (This Spec) |
|--------|---------------|----------------|
| Access Control | `allowed_roles: ["Faculty", "Staff"]` (JWT roles) | Via AppRoles (`grantedTools` field) |
| Role Assignments | `ToolRoleAssignment` entity | Stored on AppRole, computed for display |
| DynamoDB Schema | Separate tool-role mapping items | Uses AppRoles table GSI2 |
| Permission Resolution | Custom logic per tool | Reuses AppRoleService |
| Inheritance | None | Via AppRole `inheritsFrom` |
| Caching | Custom tool cache | Reuses AppRole cache layer |

---

*End of Specification*
