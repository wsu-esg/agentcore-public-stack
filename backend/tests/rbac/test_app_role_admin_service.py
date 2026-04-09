"""Unit tests for AppRoleAdminService CRUD and inheritance.

Covers:
- create_role success (6.2)
- create_role non-existent parent ValueError (6.3)
- create_role duplicate ValueError (6.4)
- update system_admin protected fields ValueError (6.5)
- delete system role ValueError (6.6)
- delete non-system role success + cache invalidation (6.7)
- inheritance permission merge (6.8)
- update jwt_role_mappings cache invalidation (6.9)
- add_tool_to_role (6.10)
- remove_tool_from_role (6.11)

Validates: Requirements 6.1–6.11
"""

import pytest

from apis.shared.auth.models import User
from apis.shared.rbac.admin_service import AppRoleAdminService
from apis.shared.rbac.models import AppRoleCreate, AppRoleUpdate


@pytest.fixture
def admin():
    """Admin user performing operations."""
    return User(
        email="admin@example.com",
        user_id="admin-1",
        name="Admin User",
        roles=["Admin"],
    )


@pytest.fixture
def service(mock_app_role_repo, mock_app_role_cache):
    """AppRoleAdminService wired to mock repo and cache."""
    return AppRoleAdminService(repository=mock_app_role_repo, cache=mock_app_role_cache)


# ---------------------------------------------------------------------------
# 6.2 — create_role success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_role_success(service, mock_app_role_repo, mock_app_role_cache, admin):
    """Creating a role with valid data returns the created AppRole."""
    role_data = AppRoleCreate(
        role_id="editor",
        display_name="Editor",
        description="Can edit content",
        granted_tools=["tool_a", "tool_b"],
        granted_models=["model_a"],
        priority=10,
    )

    # No parent roles to validate, repo.get_role returns None (no existing role)
    mock_app_role_repo.get_role.return_value = None

    # repo.create_role returns the role it receives
    async def capture_create(role):
        return role
    mock_app_role_repo.create_role.side_effect = capture_create

    result = await service.create_role(role_data, admin)

    assert result.role_id == "editor"
    assert result.display_name == "Editor"
    assert result.is_system_role is False
    assert result.created_by == "admin-1"
    # Effective permissions should include granted tools
    assert set(result.effective_permissions.tools) == {"tool_a", "tool_b"}
    assert set(result.effective_permissions.models) == {"model_a"}
    # Cache invalidation should have been called
    mock_app_role_cache.invalidate_role.assert_called()


# ---------------------------------------------------------------------------
# 6.3 — create_role non-existent parent ValueError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_role_nonexistent_parent_raises(service, mock_app_role_repo, admin):
    """Creating a role that inherits from a non-existent parent raises ValueError."""
    role_data = AppRoleCreate(
        role_id="child_role",
        display_name="Child",
        inherits_from=["nonexistent_parent"],
    )

    # get_role returns None for the parent
    mock_app_role_repo.get_role.return_value = None

    with pytest.raises(ValueError, match="does not exist"):
        await service.create_role(role_data, admin)


# ---------------------------------------------------------------------------
# 6.4 — create_role duplicate ValueError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_role_duplicate_raises(service, mock_app_role_repo, admin):
    """Creating a role that already exists raises ValueError from the repository."""
    role_data = AppRoleCreate(
        role_id="existing_role",
        display_name="Existing",
    )

    # No inheritance to validate
    mock_app_role_repo.get_role.return_value = None
    # Repository raises ValueError on duplicate
    mock_app_role_repo.create_role.side_effect = ValueError("Role 'existing_role' already exists")

    with pytest.raises(ValueError, match="already exists"):
        await service.create_role(role_data, admin)


# ---------------------------------------------------------------------------
# 6.5 — update system_admin protected fields ValueError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_system_admin_protected_fields_stripped(
    service, mock_app_role_repo, make_app_role, admin
):
    """Updating protected fields on system_admin silently strips them."""
    system_admin_role = make_app_role(
        role_id="system_admin",
        display_name="System Admin",
        is_system_role=True,
    )
    mock_app_role_repo.get_role.return_value = system_admin_role
    mock_app_role_repo.update_role.return_value = system_admin_role

    # priority is a protected field — should be silently stripped
    updates = AppRoleUpdate(priority=999, display_name="Updated Admin")

    result = await service.update_role("system_admin", updates, admin)
    assert result is not None
    # display_name (allowed) should have been applied
    assert result.display_name == "Updated Admin"
    # priority (protected) should NOT have changed
    assert result.priority != 999


# ---------------------------------------------------------------------------
# 6.6 — delete system role ValueError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_system_role_raises(service, mock_app_role_repo, make_app_role, admin):
    """Deleting a system role raises ValueError."""
    system_role = make_app_role(
        role_id="system_admin",
        is_system_role=True,
    )
    mock_app_role_repo.get_role.return_value = system_role

    with pytest.raises(ValueError, match="Cannot delete system role"):
        await service.delete_role("system_admin", admin)


# ---------------------------------------------------------------------------
# 6.7 — delete non-system role success + cache invalidation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_non_system_role_success(
    service, mock_app_role_repo, mock_app_role_cache, make_app_role, admin
):
    """Deleting a non-system role succeeds and invalidates caches."""
    role = make_app_role(
        role_id="custom_role",
        is_system_role=False,
        jwt_role_mappings=["JWTEditor", "JWTViewer"],
    )
    mock_app_role_repo.get_role.return_value = role
    mock_app_role_repo.delete_role.return_value = True

    result = await service.delete_role("custom_role", admin)

    assert result is True
    mock_app_role_repo.delete_role.assert_called_once_with("custom_role")
    # Cache invalidation for the role itself
    mock_app_role_cache.invalidate_role.assert_called_with("custom_role")
    # Cache invalidation for each JWT mapping
    assert mock_app_role_cache.invalidate_jwt_mapping.call_count == 2
    mock_app_role_cache.invalidate_jwt_mapping.assert_any_call("JWTEditor")
    mock_app_role_cache.invalidate_jwt_mapping.assert_any_call("JWTViewer")


# ---------------------------------------------------------------------------
# 6.8 — inheritance permission merge
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_inheritance_permission_merge(
    service, mock_app_role_repo, mock_app_role_cache, make_app_role, admin
):
    """Creating a role that inherits from a parent merges granted_tools (union)."""
    parent_role = make_app_role(
        role_id="parent_role",
        granted_tools=["parent_tool_a", "parent_tool_b"],
        granted_models=["parent_model"],
        enabled=True,
    )

    role_data = AppRoleCreate(
        role_id="child_role",
        display_name="Child",
        inherits_from=["parent_role"],
        granted_tools=["child_tool"],
        granted_models=["child_model"],
    )

    # get_role returns the parent when validating inheritance and computing permissions
    mock_app_role_repo.get_role.return_value = parent_role

    async def capture_create(role):
        return role
    mock_app_role_repo.create_role.side_effect = capture_create

    result = await service.create_role(role_data, admin)

    # Effective tools should be the union of child + parent granted_tools
    assert set(result.effective_permissions.tools) == {
        "child_tool", "parent_tool_a", "parent_tool_b"
    }
    assert set(result.effective_permissions.models) == {
        "child_model", "parent_model"
    }


# ---------------------------------------------------------------------------
# 6.9 — update jwt_role_mappings cache invalidation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_jwt_role_mappings_invalidates_cache(
    service, mock_app_role_repo, mock_app_role_cache, make_app_role, admin
):
    """Updating jwt_role_mappings invalidates the JWT mapping cache."""
    existing_role = make_app_role(
        role_id="editor",
        jwt_role_mappings=["OldMapping"],
        granted_tools=["tool_a"],
    )
    mock_app_role_repo.get_role.return_value = existing_role

    async def capture_update(role):
        return role
    mock_app_role_repo.update_role.side_effect = capture_update

    updates = AppRoleUpdate(jwt_role_mappings=["NewMapping"])
    result = await service.update_role("editor", updates, admin)

    assert result is not None
    # The cache invalidation should fire for the role and its new JWT mappings
    mock_app_role_cache.invalidate_role.assert_called_with("editor")
    mock_app_role_cache.invalidate_jwt_mapping.assert_called_with("NewMapping")


# ---------------------------------------------------------------------------
# 6.10 — add_tool_to_role
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_tool_to_role(
    service, mock_app_role_repo, mock_app_role_cache, make_app_role, admin
):
    """Adding a tool to a role updates granted_tools and recomputes permissions."""
    role = make_app_role(
        role_id="editor",
        granted_tools=["tool_a"],
        tools=["tool_a"],
    )
    mock_app_role_repo.get_role.return_value = role

    async def capture_update(r):
        return r
    mock_app_role_repo.update_role.side_effect = capture_update

    result = await service.add_tool_to_role("editor", "tool_b", admin)

    assert "tool_b" in result.granted_tools
    assert "tool_a" in result.granted_tools


# ---------------------------------------------------------------------------
# 6.11 — remove_tool_from_role
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_remove_tool_from_role(
    service, mock_app_role_repo, mock_app_role_cache, make_app_role, admin
):
    """Removing a tool from a role updates granted_tools and recomputes permissions."""
    role = make_app_role(
        role_id="editor",
        granted_tools=["tool_a", "tool_b"],
        tools=["tool_a", "tool_b"],
    )
    mock_app_role_repo.get_role.return_value = role

    async def capture_update(r):
        return r
    mock_app_role_repo.update_role.side_effect = capture_update

    result = await service.remove_tool_from_role("editor", "tool_a", admin)

    assert "tool_a" not in result.granted_tools
    assert "tool_b" in result.granted_tools
