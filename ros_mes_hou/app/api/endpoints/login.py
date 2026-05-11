from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db import models
from app.core import security

router = APIRouter()


@router.post("/login")
def login_for_access_token(
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
):
    user = db.query(models.User).filter(
        models.User.Username == form_data.username
    ).first()

    if not user or not security.verify_password(form_data.password, user.Password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.Islock:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="该账号已被锁定，请联系管理员",
        )

    user.Locktime = None
    db.commit()

    access_token_expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.Username},
        expires_delta=access_token_expires
    )

    headimage_url = f"/api/uploads/avatars/{user.Headimage}" if user.Headimage else ""

    return {
        "code": 200,
        "message": "登录成功",
        "data": {
            "account": user.Username,
            "name": user.Name or user.Username,
            "typeId": user.Type_ID,
            "token": access_token,
            "tokenType": "bearer",
            "headImage": headimage_url,
            "updateTime": datetime.now().isoformat()
        }
    }
