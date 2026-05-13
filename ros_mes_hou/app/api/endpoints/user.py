import csv
import io
import os
import uuid

from datetime import datetime, timezone
from typing import Dict, List, Optional

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
    avatar_url = f"/api/uploads/avatars/{user.Headimage}" if user.Headimage else ""
    return {
        "id": user.User_ID,
        "account": user.Username,
        "username": user.Username,
        "name": user.Name or user.Username,
        "typeId": user.Type_ID,
        "typeLabel": "管理员" if user.Type_ID == 1 else "操作员",
        "headImage": avatar_url,
        "isLock": user.Islock,
        "birthday": str(user.Birthday) if user.Birthday else "",
        "sex": user.Sex if user.Sex is not None else 0,
        "creatorId": user.Creator_ID,
        "createtime": str(user.Createtime),
        "locktime": str(user.Locktime) if user.Locktime else "",
        "modifytime": str(user.Modifytime) if user.Modifytime else "",
        "delFlag": user.del_flag if user.del_flag is not None else False,
        "notes": user.Notes or "",
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
    type_id: int = Query(0, description="按用户类型筛选"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.User)

    if keyword:
        kw = f"%{keyword.strip()}%"
        query = query.filter(models.User.Username.ilike(kw))

    if type_id:
        query = query.filter(models.User.Type_ID == type_id)

    users = query.order_by(models.User.User_ID.desc()).all()

    return {
        "code": 200,
        "message": "获取用户列表成功",
        "data": [user_to_dict(u) for u in users],
    }


@router.post("/")
def create_user(
    username: str = Body(...),
    password: str = Body(...),
    type_id: int = Body(2),
    name: Optional[str] = Body(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if len(username.strip()) < 3:
        raise HTTPException(status_code=400, detail="用户名至少需要 3 位")

    if len(password) < 6:
        raise HTTPException(status_code=400, detail="密码至少需要 6 位")

    existed = db.query(models.User).filter(models.User.Username == username).first()
    if existed:
        raise HTTPException(status_code=400, detail="该用户名已存在")

    user = models.User(
        Username=username.strip(),
        Password=security.get_password_hash(password),
        Type_ID=type_id,
        Creator_ID=current_user.User_ID,
        Name=name.strip() if name else None,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "code": 200,
        "message": "新增用户成功",
        "data": user_to_dict(user),
    }


@router.post("/password")
def change_password(
    old_password: str = Body(...),
    new_password: str = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not security.verify_password(old_password, current_user.Password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="原密码错误")

    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码至少需要 6 位")

    current_user.Password = security.get_password_hash(new_password)
    db.commit()

    return {
        "code": 200,
        "message": "密码修改成功",
        "data": None,
    }


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

    filename = f"user_{current_user.User_ID}_{uuid.uuid4().hex[:8]}{safe_ext}"
    filepath = os.path.join(AVATAR_DIR, filename)

    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    current_user.Headimage = filename
    db.commit()
    db.refresh(current_user)

    return {
        "code": 200,
        "message": "头像上传成功",
        "data": user_to_dict(current_user),
    }


@router.put("/profile/me")
def update_profile(
    name: Optional[str] = Body(None),
    birthday: Optional[str] = Body(None),
    sex: Optional[int] = Body(None),
    type_id: Optional[int] = Body(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if name is not None:
        current_user.Name = name.strip() if name.strip() else None

    if birthday is not None:
        from datetime import datetime as dt
        current_user.Birthday = dt.fromisoformat(birthday) if birthday else None

    if sex is not None:
        current_user.Sex = sex

    if type_id is not None:
        current_user.Type_ID = type_id

    current_user.Modifytime = datetime.now(timezone.utc)

    db.commit()
    db.refresh(current_user)

    return {
        "code": 200,
        "message": "个人资料保存成功",
        "data": user_to_dict(current_user),
    }


@router.put("/{user_id}")
def update_user(
    user_id: int,
    username: Optional[str] = Body(None),
    type_id: Optional[int] = Body(None),
    password: Optional[str] = Body(None),
    name: Optional[str] = Body(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    user = db.query(models.User).filter(models.User.User_ID == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if username and username != user.Username:
        existed = db.query(models.User).filter(models.User.Username == username).first()
        if existed:
            raise HTTPException(status_code=400, detail="该用户名已存在")

        user.Username = username.strip()

    if type_id is not None:
        user.Type_ID = type_id

    if password:
        if len(password) < 6:
            raise HTTPException(status_code=400, detail="密码至少需要 6 位")

        user.Password = security.get_password_hash(password)

    if name is not None:
        user.Name = name.strip() if name.strip() else None

    user.Modifytime = datetime.now(timezone.utc)

    db.commit()
    db.refresh(user)

    return {
        "code": 200,
        "message": "更新用户成功",
        "data": user_to_dict(user),
    }


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.User_ID == user_id:
        raise HTTPException(status_code=400, detail="不能删除当前登录用户")

    user = db.query(models.User).filter(models.User.User_ID == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if user.Username == "admin":
        raise HTTPException(status_code=400, detail="admin 账号不允许删除")

    user.del_flag = True
    db.commit()

    return {
        "code": 200,
        "message": "删除用户成功",
        "data": {"id": user_id},
    }


@router.put("/{user_id}/lock")
def lock_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    user = db.query(models.User).filter(models.User.User_ID == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if user.User_ID == current_user.User_ID:
        raise HTTPException(status_code=400, detail="不能锁定当前登录用户")

    if user.Type_ID == 1:
        raise HTTPException(status_code=400, detail="不能锁定管理员账号")

    user.Islock = True
    user.Locktime = datetime.now(timezone.utc)

    db.commit()
    db.refresh(user)

    return {
        "code": 200,
        "message": "锁定用户成功",
        "data": user_to_dict(user),
    }


@router.put("/{user_id}/unlock")
def unlock_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    user = db.query(models.User).filter(models.User.User_ID == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if user.Type_ID == 1:
        raise HTTPException(status_code=400, detail="不能解锁管理员账号")

    user.Islock = False
    user.Locktime = None

    db.commit()
    db.refresh(user)

    return {
        "code": 200,
        "message": "解锁用户成功",
        "data": user_to_dict(user),
    }


@router.put("/{user_id}/role")
def change_user_role(
    user_id: int,
    type_id: int = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if type_id not in (1, 2):
        raise HTTPException(status_code=400, detail="无效的用户类型值")

    user = db.query(models.User).filter(models.User.User_ID == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if user.User_ID == current_user.User_ID:
        raise HTTPException(status_code=400, detail="不能修改自己的权限")

    user.Type_ID = type_id

    db.commit()
    db.refresh(user)

    return {
        "code": 200,
        "message": "修改权限成功",
        "data": user_to_dict(user),
    }


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

    success_count = 0
    fail_list: List[Dict] = []
    created_users: List[Dict] = []

    for row_num, row in enumerate(reader, start=2):
        row = {k.lower().strip(): v.strip() if v else "" for k, v in row.items()}

        username_val = row.get("username", "")
        password_val = row.get("password", "")
        type_id_val = int(row["type_id"]) if row.get("type_id") and row["type_id"].isdigit() else 2

        if not username_val:
            fail_list.append({"row": row_num, "reason": "用户名为空"})
            continue

        if len(username_val) < 3:
            fail_list.append({"row": row_num, "reason": "用户名至少需要 3 位"})
            continue

        if len(password_val) < 6:
            fail_list.append({"row": row_num, "reason": "密码至少需要 6 位"})
            continue

        existed = db.query(models.User).filter(models.User.Username == username_val).first()

        if existed:
            fail_list.append({"row": row_num, "reason": f"用户名 {username_val} 已存在"})
            continue

        new_user = models.User(
            Username=username_val,
            Password=security.get_password_hash(password_val),
            Type_ID=type_id_val if type_id_val in (1, 2) else 2,
            Creator_ID=current_user.User_ID,
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
    users = db.query(models.User).order_by(models.User.User_ID.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["ID", "账号", "姓名", "用户类型", "是否锁定", "创建时间"])

    for u in users:
        type_text = "管理员" if u.Type_ID == 1 else "操作员"
        lock_text = "是" if u.Islock else "否"
        writer.writerow([
            u.User_ID,
            u.Username,
            u.Name or "",
            type_text,
            lock_text,
            str(u.Createtime),
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=users_export.csv"},
    )