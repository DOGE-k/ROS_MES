import os
from datetime import datetime, timedelta
from typing import Optional

from jose import jwt
from passlib.context import CryptContext

# 安全修复：密钥改为优先从环境变量读取，避免硬编码泄露。
# 生产/比赛部署时请设置环境变量 MES_SECRET_KEY 为一段随机长字符串，例如：
#   Windows:  set MES_SECRET_KEY=xxxxxxxxxxxxxxxx
#   Linux:    export MES_SECRET_KEY=xxxxxxxxxxxxxxxx
SECRET_KEY = os.getenv("MES_SECRET_KEY", "your-secret-key-very-secure")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("MES_TOKEN_EXPIRE_MINUTES", "60"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()

    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt
