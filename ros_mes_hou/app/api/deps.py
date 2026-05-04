#Dependencies，执行 Token 校验 和 用户对象提取
# app/api/deps.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core import security
from app.db import models
from app.schemas.token import TokenData

# 1. 初始化 OAuth2 认证方案
# auto_error=True 表示如果不带 Authorization Header，直接抛出 401 错误
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> models.User:
    """
    JWT 认证依赖函数：
    1. 从请求头 Authorization 中提取 Bearer Token
    2. 使用 SECRET_KEY 解码并验证签名
    3. 从 Payload 中提取 sub (username)
    4. 检索数据库确保用户存在
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # 解码 JWT Payload
        payload = jwt.decode(
            token, 
            security.SECRET_KEY, 
            algorithms=[security.ALGORITHM]
        )
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        # 签名不匹配或 Token 过期会触发此异常
        raise credentials_exception

    # 数据库验证
    user = db.query(models.User).filter(models.User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    
    return user