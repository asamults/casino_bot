from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from casino_bot.core.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/admin/login")


def admin_guard(required_role: str = "admin"):
    def dependency(token: str = Depends(oauth2_scheme)):
        try:
            payload = decode_token(token)
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")

        role = payload.get("role")
        if role not in ("superadmin", required_role):
            raise HTTPException(status_code=403, detail="Forbidden")

        return payload

    return dependency
