import csv
import io
import os
import uuid

from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core import security
from app.db import models
from app.db.database import get_db

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AVATAR_DIR = os.path.join(BASE_DIR, "uploads", "avatars")
os.makedirs(AVATAR_DIR, exist_ok=True)


def user_to_dict(user: models.User):
    avatar_url = f"/api/uploads/avatars/{user.avatar}" if user.avatar else ""
    last_login_str = str(user.last_login) if user.last_login else ""
    return {
        "id": user.id,
        "account": user.username,
        "username": user.username,
        "role": user.role,
        "email": user.email or "",
        "phone": user.phone or "",
        "avatar": avatar_url,
        "status": user.status if user.status is not None else 0,
        "lastLogin": last_login_str,
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
    keyword: str = Query("", description="按账号/用户名模糊搜索"),
    role: str = Query("", description="按角色筛选"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.User)
    if keyword:
        kw = f"%{keyword.strip()}%"
        query = query.filter(models.User.username.ilike(kw))
    if role:
        query = query.filter(models.User.role == role)
    users = query.order_by(models.User.id.desc()).all()
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


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="只能上传图片格式文件")
    if file.size and file.size > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="头像图片大小不能超过 2MB")

    ext = os.path.splitext(file.filename or ".png")[1] or ".png"
    safe_ext = ext.lower()
    if safe_ext not in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        safe_ext = ".png"

    filename = f"user_{current_user.id}_{uuid.uuid4().hex[:8]}{safe_ext}"
    filepath = os.path.join(AVATAR_DIR, filename)

    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    current_user.avatar = filename
    db.commit()
    db.refresh(current_user)

    return {"code": 200, "message": "头像上传成功", "data": user_to_dict(current_user)}


@router.put("/profile/me")
def update_profile(
    username: str | None = Body(None),
    email: str | None = Body(None),
    phone: str | None = Body(None),
    role: str | None = Body(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if username is not None and username.strip():
        current_user.username = username.strip()
    if email is not None:
        current_user.email = email
    if phone is not None:
        current_user.phone = phone
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

    if user.username == "admin":
        raise HTTPException(status_code=400, detail="admin 账号不允许删除")

    db.delete(user)
    db.commit()
    return {"code": 200, "message": "删除用户成功", "data": {"id": user_id}}


@router.put("/{user_id}/lock")
def lock_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能锁定当前登录用户")
    user.status = 1
    db.commit()
    db.refresh(user)
    return {"code": 200, "message": "锁定用户成功", "data": user_to_dict(user)}


@router.put("/{user_id}/unlock")
def unlock_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.status = 0
    db.commit()
    db.refresh(user)
    return {"code": 200, "message": "解锁用户成功", "data": user_to_dict(user)}


@router.put("/{user_id}/role")
def change_user_role(
    user_id: int,
    role: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if role not in ("admin", "operator"):
        raise HTTPException(status_code=400, detail="无效的角色值")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能修改自己的权限")
    user.role = role
    db.commit()
    db.refresh(user)
    return {"code": 200, "message": "修改权限成功", "data": user_to_dict(user)}


@router.post("/import")
async def import_users(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="请上传 CSV 格式文件")

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("gbk", errors="replace")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV 文件为空或缺少表头")

    required = {"username", "password"}
    fieldnames_lower = {f.lower().strip() for f in reader.fieldnames}
    if not required.issubset(fieldnames_lower):
        raise HTTPException(status_code=400, detail="CSV 表头必须包含 username, password 列")

    name_map = {f.lower().strip(): f for f in reader.fieldnames}
    success_count = 0
    fail_list: list[dict] = []
    created_users: list[dict] = []

    for row_num, row in enumerate(reader, start=2):
        row = {k.lower().strip(): v.strip() if v else "" for k, v in row.items()}
        username_val = row.get("username", "")
        password_val = row.get("password", "")
        role_val = row.get("role", "operator")

        if not username_val:
            fail_list.append({"row": row_num, "reason": "用户名为空"})
            continue
        if len(username_val) < 3:
            fail_list.append({"row": row_num, "reason": "用户名至少需要 3 位"})
            continue
        if len(password_val) < 6:
            fail_list.append({"row": row_num, "reason": "密码至少需要 6 位"})
            continue

        existed = db.query(models.User).filter(models.User.username == username_val).first()
        if existed:
            fail_list.append({"row": row_num, "reason": f"用户名 {username_val} 已存在"})
            continue

        new_user = models.User(
            username=username_val,
            password=security.get_password_hash(password_val),
            role=role_val if role_val in ("admin", "operator") else "operator",
        )
        db.add(new_user)
        db.flush()
        created_users.append(user_to_dict(new_user))
        success_count += 1

    db.commit()
    return {
        "code": 200,
        "message": f"导入完成，成功 {success_count} 条，失败 {len(fail_list)} 条",
        "data": {
            "successCount": success_count,
            "failCount": len(fail_list),
            "failList": fail_list,
            "users": created_users,
        },
    }


@router.get("/export")
def export_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    users = db.query(models.User).order_by(models.User.id.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "账号", "角色", "状态", "邮箱", "电话", "最后登录", "创建时间"])
    for u in users:
        status_text = "正常" if u.status == 0 else "已锁定"
        last_login_text = str(u.last_login) if u.last_login else ""
        writer.writerow([u.id, u.username, u.role, status_text, u.email or "", u.phone or "", last_login_text, str(u.created_at)])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=users_export.csv"},
    )
