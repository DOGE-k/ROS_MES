import json
import os
import shutil
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import models
from app.db.database import get_db

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads", "drawings")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def drawing_to_dict(drawing: models.Drawing):
    return {
        "id": drawing.id,
        "name": drawing.name,
        "filePath": drawing.file_path,
        "jsonData": drawing.json_data,
        "createdAt": str(drawing.created_at) if drawing.created_at else None,
        "updatedAt": str(drawing.updated_at) if drawing.updated_at else None,
    }


@router.get("/")
def list_drawings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    drawings = db.query(models.Drawing).order_by(models.Drawing.id.desc()).all()
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
    drawing = db.query(models.Drawing).filter(models.Drawing.id == drawing_id).first()
    if not drawing:
        raise HTTPException(status_code=404, detail="图纸不存在")

    return {
        "code": 200,
        "message": "获取图纸详情成功",
        "data": drawing_to_dict(drawing),
    }


@router.post("/")
async def create_drawing(
    name: str = Form(...),
    json_data: str = Form("{}"),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if len(name.strip()) < 1:
        raise HTTPException(status_code=400, detail="图纸名称不能为空")

    parsed_json = {}
    if json_data and json_data.strip():
        try:
            parsed_json = json.loads(json_data)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="JSON 格式不正确")

    file_path = None
    if file and file.filename:
        ext = os.path.splitext(file.filename)[1] or ".bin"
        unique_name = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_name)
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

    drawing = models.Drawing(
        name=name.strip(),
        file_path=file_path,
        json_data=json.dumps(parsed_json, ensure_ascii=False),
    )
    db.add(drawing)
    db.commit()
    db.refresh(drawing)

    return {
        "code": 200,
        "message": "上传图纸成功",
        "data": drawing_to_dict(drawing),
    }


@router.put("/{drawing_id}")
async def update_drawing(
    drawing_id: int,
    name: str = Form(None),
    json_data: str = Form(None),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    drawing = db.query(models.Drawing).filter(models.Drawing.id == drawing_id).first()
    if not drawing:
        raise HTTPException(status_code=404, detail="图纸不存在")

    if name is not None:
        if len(name.strip()) < 1:
            raise HTTPException(status_code=400, detail="图纸名称不能为空")
        drawing.name = name.strip()

    if json_data is not None:
        try:
            parsed_json = json.loads(json_data)
            drawing.json_data = json.dumps(parsed_json, ensure_ascii=False)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="JSON 格式不正确")

    if file and file.filename:
        if drawing.file_path and os.path.exists(drawing.file_path):
            os.remove(drawing.file_path)
        ext = os.path.splitext(file.filename)[1] or ".bin"
        unique_name = f"{uuid.uuid4().hex}{ext}"
        new_path = os.path.join(UPLOAD_DIR, unique_name)
        with open(new_path, "wb") as f:
            content = await file.read()
            f.write(content)
        drawing.file_path = new_path

    db.commit()
    db.refresh(drawing)

    return {
        "code": 200,
        "message": "更新图纸成功",
        "data": drawing_to_dict(drawing),
    }


@router.delete("/{drawing_id}")
def delete_drawing(
    drawing_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    drawing = db.query(models.Drawing).filter(models.Drawing.id == drawing_id).first()
    if not drawing:
        raise HTTPException(status_code=404, detail="图纸不存在")

    if drawing.file_path and os.path.exists(drawing.file_path):
        os.remove(drawing.file_path)

    db.delete(drawing)
    db.commit()

    return {
        "code": 200,
        "message": "删除图纸成功",
        "data": {"id": drawing_id},
    }
