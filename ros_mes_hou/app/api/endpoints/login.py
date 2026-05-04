# app/api/endpoints/login.py
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db import models
from app.core import security
from app.schemas.token import Token

router = APIRouter()

@router.post("/login", response_model=Token)
def login_for_access_token(
    db: Session = Depends(get_db), 
    form_data: OAuth2PasswordRequestForm = Depends() # 自动获取账号密码
):
    # 1. 去数据库找人 (类似原来的 Usermapper.selectOne)
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    
    # 2. 校验：人不存在 或者 密码对不上 (利用我们刚写的 security 工具)
    if not user or not security.verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. 如果通过校验，签发“VIP手环” (Token)
    access_token_expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.username}, # sub 是 JWT 的标准字段，存放用户唯一标识
        expires_delta=access_token_expires
    )

    # 4. 返回手环给前端
    return {"access_token": access_token, "token_type": "bearer"}