from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core import security
from app.db import models
from app.db.database import get_db

router = APIRouter()


def user_to_dict(user: models.User):
    return {
        "id": user.id,
        "account": user.username,
        "username": user.username,
        "role": user.role,
        "createdAt": str(user.created_at),
    }


@router.get("/me")
def get_me(current_user: models.User = Depends(get_current_user)):
    return {
        "code": 200,
        "message": "获取用户信息成功",
        "data": user_to_dict(current_user),
    }


@router.get("/")
def list_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    users = db.query(models.User).order_by(models.User.id.desc()).all()
    return {"code": 200, "message": "获取用户列表成功", "data": [user_to_dict(u) for u in users]}


@router.post("/")
def create_user(
    username: str = Body(...),
    password: str = Body(...),
    role: str = Body("operator"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if len(username.strip()) < 3:
        raise HTTPException(status_code=400, detail="用户名至少需要 3 位")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="密码至少需要 6 位")

    existed = db.query(models.User).filter(models.User.username == username).first()
    if existed:
        raise HTTPException(status_code=400, detail="该用户名已存在")

    user = models.User(
        username=username.strip(),
        password=security.get_password_hash(password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"code": 200, "message": "新增用户成功", "data": user_to_dict(user)}


@router.post("/password")
def change_password(
    old_password: str = Body(...),
    new_password: str = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not security.verify_password(old_password, current_user.password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="原密码错误")
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码至少需要 6 位")

    current_user.password = security.get_password_hash(new_password)
    db.commit()
    return {"code": 200, "message": "密码修改成功", "data": None}


@router.put("/profile/me")
def update_profile(
    role: str | None = Body(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # 当前 User 表只有 username/role，先保存 role；头像/昵称建议下一步单独加 profile 表。
    if role:
        current_user.role = role
        db.commit()
        db.refresh(current_user)
    return {"code": 200, "message": "个人资料保存成功", "data": user_to_dict(current_user)}


@router.put("/{user_id}")
def update_user(
    user_id: int,
    username: str | None = Body(None),
    role: str | None = Body(None),
    password: str | None = Body(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if username and username != user.username:
        existed = db.query(models.User).filter(models.User.username == username).first()
        if existed:
            raise HTTPException(status_code=400, detail="该用户名已存在")
        user.username = username.strip()
    if role:
        user.role = role
    if password:
        if len(password) < 6:
            raise HTTPException(status_code=400, detail="密码至少需要 6 位")
        user.password = security.get_password_hash(password)

    db.commit()
    db.refresh(user)
    return {"code": 200, "message": "更新用户成功", "data": user_to_dict(user)}


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="不能删除当前登录用户")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    db.delete(user)
    db.commit()
    return {"code": 200, "message": "删除用户成功", "data": {"id": user_id}}
