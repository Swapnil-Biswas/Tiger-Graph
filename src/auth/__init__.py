"""
Authentication and Role-Based Access Control (RBAC) Module
"""
from src.auth.rbac import (
    Role,
    Permission,
    AuthUser,
    RBACManager,
    mask_pii_dict,
    get_current_user,
    require_permission,
)

__all__ = [
    "Role",
    "Permission",
    "AuthUser",
    "RBACManager",
    "mask_pii_dict",
    "get_current_user",
    "require_permission",
]
