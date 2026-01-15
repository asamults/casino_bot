# src/casino_bot/admin/rbac.py
from fastapi import Depends, HTTPException, status
from .auth import get_current_admin

def require_scope(scope: str):
    def checker(admin=Depends(get_current_admin)):
        if scope not in admin.get("scopes", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing scope: {scope}"
            )
        return True
    return checker
