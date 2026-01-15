# src/casino_bot/admin/auth.py
from fastapi import Depends, HTTPException, status
from security.jwt import decode_admin_jwt

def get_current_admin(token: str = Depends()):
    payload = decode_admin_jwt(token)
    if not payload.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return payload
