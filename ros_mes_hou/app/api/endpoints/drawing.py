import json
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import models
from app.db.database import get_db

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "drawings")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def drawing_to_dict(drawing: models.Drawing):
    return {
        "drawingId": drawing.drawing_id,
        "drawingName": drawing.drawing_name,
        "drawingDescription": drawing.drawing_description or "",
        "drawingFile": drawing.drawing_file or "",
        "creatorId": drawing.creator_id,
        "createTime": str(drawing.create_time) if drawing.create_time else "",
        "modifyTime": str(drawing.modify_time) if drawing.modify_time else "",
        "latestVersionId": drawing.latest_version_id,
        "delFlag": drawing.del_flag,
        "notes": drawing.notes or "",
    }


def version_to_dict(version: models.DrawingVersion):
    return {
        "versionId": version.version_id,
        "drawingId": version.drawing_id,
        "drawingFile": version.drawing_file or "",
        "creatorId": version.creator_id,
        "createTime": str(version.create_time) if version.create_time else "",
        "modifyId": version.modify_id,
        "modifyTime": str(version.modify_time) if version.modify_time else "",
        "delFlag": version.del_flag,
        "notes": version.notes or "",
    }


def extract_json_summary(json_data: dict) -> str:
    file_info = json_data.get("文件信息", {})
    if not file_info:
        return ""
    parts = []
    stp_path = file_info.get("STP文件路径", "")
    if stp_path:
        parts.append(f"STP文件路径: {stp_path}")
    cluster_threshold = file_info.get("聚类阈值(mm)", "")
    if cluster_threshold:
        parts.append(f"聚类阈值(mm): {cluster_threshold}")
    total_points = file_info.get("总坐标点数量", "")
    if total_points:
        parts.append(f"总坐标点数量: {total_points}")
    virtual_parts = file_info.get("虚拟部件数量", "")
    if virtual_parts:
        parts.append(f"虚拟部件数量: {virtual_parts}")
    return "; ".join(parts)


@router.get("/")
def list_drawings(
    keyword: str = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.Drawing).filter(models.Drawing.del_flag == False)
    if keyword and keyword.strip():
        like_pattern = f"%{keyword.strip()}%"
        query = query.filter(
            models.Drawing.drawing_name.ilike(like_pattern)
            | models.Drawing.drawing_description.ilike(like_pattern)
            | models.Drawing.notes.ilike(like_pattern)
        )
    drawings = query.order_by(models.Drawing.drawing_id.desc()).all()
    return {
        "code": 200,
        "message": "获取图纸列表成功",
        "data": [drawing_to_dict(d) for d in drawings],
    }


@router.get("/{drawing_id}")
def get_drawing(
    drawing_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    drawing = (
        db.query(models.Drawing)
        .filter(models.Drawing.drawing_id == drawing_id, models.Drawing.del_flag == False)
        .first()
    )
    if not drawing:
        raise HTTPException(status_code=404, detail="图纸不存在")

    return {
        "code": 200,
        "message": "获取图纸详情成功",
        "data": drawing_to_dict(drawing),
    }


@router.get("/{drawing_id}/versions")
def get_drawing_versions(
    drawing_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    drawing = (
        db.query(models.Drawing)
        .filter(models.Drawing.drawing_id == drawing_id, models.Drawing.del_flag == False)
        .first()
    )
    if not drawing:
        raise HTTPException(status_code=404, detail="图纸不存在")

    versions = (
        db.query(models.DrawingVersion)
        .filter(models.DrawingVersion.drawing_id == drawing_id)
        .order_by(models.DrawingVersion.version_id.desc())
        .all()
    )
    return {
        "code": 200,
        "message": "获取版本列表成功",
        "data": [version_to_dict(v) for v in versions],
    }


@router.get("/{drawing_id}/file")
def get_drawing_file_content(
    drawing_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    drawing = (
        db.query(models.Drawing)
        .filter(models.Drawing.drawing_id == drawing_id, models.Drawing.del_flag == False)
        .first()
    )
    if not drawing:
        raise HTTPException(status_code=404, detail="图纸不存在")

    file_path = drawing.drawing_file
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="图纸文件不存在")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        preview = content[:10000]
        return {
            "code": 200,
            "message": "获取文件内容成功",
            "data": {
                "content": preview,
                "fullLength": len(content),
                "truncated": len(content) > 10000,
            },
        }
    except Exception:
        raise HTTPException(status_code=500, detail="读取图纸文件失败")


@router.post("/import")
async def import_drawing(
    drawing_name: str = Form(...),
    drawing_description: str = Form(""),
    drawing_id: int = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not drawing_name or not drawing_name.strip():
        raise HTTPException(status_code=400, detail="图纸名称不能为空")

    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="请上传 JSON 图纸文件")

    if not file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="仅支持 JSON 格式文件")

    content = await file.read()
    try:
        json_data = json.loads(content.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="JSON 文件格式不正确")

    summary_notes = extract_json_summary(json_data)
    if drawing_description and drawing_description.strip():
        user_notes = drawing_description.strip()
        if summary_notes:
            summary_notes = user_notes + " | " + summary_notes
        else:
            summary_notes = user_notes

    ext = os.path.splitext(file.filename)[1] or ".json"
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    if drawing_id:
        drawing = (
            db.query(models.Drawing)
            .filter(models.Drawing.drawing_id == drawing_id, models.Drawing.del_flag == False)
            .first()
        )
        if not drawing:
            raise HTTPException(status_code=404, detail="图纸不存在")

        drawing.drawing_file = file_path
        drawing.modify_time = datetime.now(timezone.utc)
        if drawing_description is not None:
            drawing.drawing_description = drawing_description.strip()
        if summary_notes:
            drawing.notes = summary_notes

        version = models.DrawingVersion(
            drawing_id=drawing.drawing_id,
            drawing_file=file_path,
            creator_id=current_user.id,
            notes=summary_notes,
        )
        db.add(version)
        db.flush()

        drawing.latest_version_id = version.version_id
        db.commit()
        db.refresh(drawing)

        return {
            "code": 200,
            "message": f"图纸 [{drawing.drawing_name}] 新版本导入成功",
            "data": drawing_to_dict(drawing),
        }
    else:
        drawing = models.Drawing(
            drawing_name=drawing_name.strip(),
            drawing_description=drawing_description.strip() if drawing_description else "",
            drawing_file=file_path,
            creator_id=current_user.id,
            notes=summary_notes,
        )
        db.add(drawing)
        db.flush()

        version = models.DrawingVersion(
            drawing_id=drawing.drawing_id,
            drawing_file=file_path,
            creator_id=current_user.id,
            notes=summary_notes,
        )
        db.add(version)
        db.flush()

        drawing.latest_version_id = version.version_id
        db.commit()
        db.refresh(drawing)

        return {
            "code": 200,
            "message": "图纸导入成功",
            "data": drawing_to_dict(drawing),
        }


@router.put("/{drawing_id}")
def update_drawing(
    drawing_id: int,
    drawing_name: str = Form(None),
    drawing_description: str = Form(None),
    notes: str = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    drawing = (
        db.query(models.Drawing)
        .filter(models.Drawing.drawing_id == drawing_id, models.Drawing.del_flag == False)
        .first()
    )
    if not drawing:
        raise HTTPException(status_code=404, detail="图纸不存在")

    if drawing_name is not None:
        if not drawing_name.strip():
            raise HTTPException(status_code=400, detail="图纸名称不能为空")
        drawing.drawing_name = drawing_name.strip()

    if drawing_description is not None:
        drawing.drawing_description = drawing_description.strip()

    if notes is not None:
        drawing.notes = notes.strip()

    drawing.modify_time = datetime.now(timezone.utc)
    db.commit()
    db.refresh(drawing)

    return {
        "code": 200,
        "message": "更新图纸信息成功",
        "data": drawing_to_dict(drawing),
    }


@router.delete("/{drawing_id}")
def delete_drawing(
    drawing_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    drawing = (
        db.query(models.Drawing)
        .filter(models.Drawing.drawing_id == drawing_id, models.Drawing.del_flag == False)
        .first()
    )
    if not drawing:
        raise HTTPException(status_code=404, detail="图纸不存在")

    drawing.del_flag = True
    drawing.modify_time = datetime.now(timezone.utc)
    db.commit()

    return {
        "code": 200,
        "message": "删除图纸成功",
        "data": {"drawingId": drawing_id},
    }
