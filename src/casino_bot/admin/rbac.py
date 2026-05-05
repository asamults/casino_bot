"""RBAC role constants.

Supported JWT ``role`` values:
- ``admin``: standard admin operations (users, tokens, audit read, subscription read).
- ``superadmin``: full control including admin-user lifecycle and manual subscription activation.

Scopes are not used; authorization is role-based only (minimal surface).
"""

ROLE_ADMIN = "admin"
ROLE_SUPERADMIN = "superadmin"

ALL_ADMIN_ROLES = frozenset({ROLE_ADMIN, ROLE_SUPERADMIN})
