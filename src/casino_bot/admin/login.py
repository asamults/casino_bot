from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from casino_bot.admin.models import AdminUser
from casino_bot.core.security import verify_password, create_access_token
from casino_bot.core.database import get_db

router = APIRouter(prefix="/admin")


@router.post("/login")
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(AdminUser).filter_by(email=form.username).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(user.email, user.role)
    return {"access_token": token, "token_type": "bearer"}
