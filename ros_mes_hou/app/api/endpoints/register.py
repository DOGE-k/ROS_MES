# app/api/endpoints/register.py
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from app.db import models, database
from app.core import security # 确保你有这个加密工具

router = APIRouter()

@router.post("/register") # 最终路径会是 /api/register
def register_user(
    username: str = Body(...), 
    password: str = Body(...), 
    db: Session = Depends(database.get_db)
):
    # 1. 检查用户是否已存在
    db_user = db.query(models.User).filter(models.User.username == username).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该用户名已被注册"
        )
    
    # 2. 创建新用户并加密密码
    # 注意：绝对不能直接存 123456，要存哈希值
    hashed_password = security.get_password_hash(password) 
    new_user = models.User(username=username, password=hashed_password)
    
    # 3. 写入数据库
    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return {"code": 200, "message": "注册成功", "data": {"username": username}}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"数据库写入失败: {str(e)}")