from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session

from app.db import models, database
from app.core import security

router = APIRouter()


@router.post("/register")
def register_user(
    username: str = Body(...),
    password: str = Body(...),
    db: Session = Depends(database.get_db)
):
    if len(username.strip()) < 3:
        raise HTTPException(status_code=400, detail="用户名至少需要 3 位")

    if len(password) < 6:
        raise HTTPException(status_code=400, detail="密码至少需要 6 位")

    db_user = db.query(models.User).filter(
        models.User.username == username
    ).first()

    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该用户名已被注册"
        )

    hashed_password = security.get_password_hash(password)
    new_user = models.User(username=username, password=hashed_password)

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return {
            "code": 200,
            "message": "注册成功",
            "data": {
                "account": username
            }
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"数据库写入失败: {str(e)}")