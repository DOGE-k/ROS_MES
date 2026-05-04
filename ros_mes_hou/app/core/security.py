# app/core/security.py
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt
from passlib.context import CryptContext
from app.core.config import settings

# 1. 初始化加密上下文：告诉 Python 我们要用 bcrypt 算法来处理密码
# 这相当于 Java 中的 BCryptPasswordEncoder
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 配置 JWT 签名用到的核心参数（建议把这些存在 .env 里）
SECRET_KEY = "your-secret-key-very-secure" # 这是一个只有后端知道的秘密字符串，用于加盖公章
ALGORITHM = "HS256"                       # 加密算法的名称
ACCESS_TOKEN_EXPIRE_MINUTES = 60          # 令牌有效期（分钟）

# --- 密码处理部分 ---

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    逻辑：比对【明文密码】和【数据库里的乱码】是否匹配
    """
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """
    逻辑：把【明文密码】转化成【乱码】存入数据库
    """
    return pwd_context.hash(password)

# --- Token 签发部分 ---

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    逻辑：把用户信息（比如 id 和 账号名）塞进 Token 里，并盖章
    """
    to_encode = data.copy() # 拷贝一份数据
    
    # 设置过期时间：当前时间 + 有效时长
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # 将过期时间也塞进 Token 的内容里
    to_encode.update({"exp": expire})
    
    # 使用 SECRET_KEY 进行签名加密
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt