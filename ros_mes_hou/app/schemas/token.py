# app/schemas/token.py
from pydantic import BaseModel
from typing import Optional

# 这是返回给前端的 JSON 格式
class Token(BaseModel):
    access_token: str  # 那个长长的手环字符串
    token_type: str    # 令牌类型，通常是 "bearer"

# 这是我们解析 Token 时用到的内部模型
class TokenData(BaseModel):
    username: Optional[str] = None