import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import models
from app.db.database import get_db

work_router = APIRouter()
workflow_router = APIRouter()


def work_to_dict(work: models.Work):
    return {
        "Work_ID": work.Work_ID,
        "Workname": work.Workname,
        "WorkDescript": work.WorkDescript or "",
        "Drawing_ID": work.Drawing_ID,
        "Device_id": work.Device_id,
        "unit_id": work.unit_id,
        "sensor_id": work.sensor_id,
        "data": work.data or "",
        "creater_id": work.creater_id,
        "Createtime": str(work.Createtime) if work.Createtime else "",
        "Modifytime": str(work.Modifytime) if work.Modifytime else "",
        "del_flag": work.del_flag,
        "Notes": work.Notes or "",
    }


def workflow_to_dict(wf: models.Workflow):
    return {
        "Workflow_ID": wf.Workflow_ID,
        "Workflowname": wf.Workflowname,
        "WorkflowDescript": wf.WorkflowDescript or "",
        "creater_id": wf.creater_id,
        "Createtime": str(wf.Createtime) if wf.Createtime else "",
        "Modifytime": str(wf.Modifytime) if wf.Modifytime else "",
        "del_flag": wf.del_flag,
        "Notes": wf.Notes or "",
    }


def relation_to_dict(rel: models.WorkFlowRelation):
    return {
        "work_flow_relation_ID": rel.work_flow_relation_ID,
        "Workflow_ID": rel.Workflow_ID,
        "Work_ID": rel.Work_ID,
        "flow_seq": rel.flow_seq,
        "creater_id": rel.creater_id,
        "Createtime": str(rel.Createtime) if rel.Createtime else "",
        "Modifytime": str(rel.Modifytime) if rel.Modifytime else "",
        "del_flag": rel.del_flag,
        "Notes": rel.Notes or "",
    }


# ==================== 工作接口 ====================


@work_router.post("/create")
def create_work(
    Workname: str,
    WorkDescript: str = "",
    Drawing_ID: int = None,
    Device_id: int = None,
    unit_id: int = None,
    sensor_id: int = None,
    data: str = "",
    Notes: str = "",
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not Workname or not Workname.strip():
        raise HTTPException(status_code=400, detail="工作名称不能为空")

    if data and data.strip():
        try:
            json.loads(data)
        except (json.JSONDecodeError, ValueError):
            raise HTTPException(status_code=400, detail="data 字段不是合法的 JSON 格式")

    work = models.Work(
        Workname=Workname.strip(),
        WorkDescript=WorkDescript.strip() if WorkDescript else "",
        Drawing_ID=Drawing_ID,
        Device_id=Device_id,
        unit_id=unit_id,
        sensor_id=sensor_id,
        data=data,
        creater_id=current_user.User_ID,
        Notes=Notes.strip() if Notes else "",
    )
    db.add(work)
    db.commit()
    db.refresh(work)

    return {
        "code": 200,
        "message": "新建工作成功",
        "data": work_to_dict(work),
    }


@work_router.get("/list")
def list_works(
    keyword: str = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.Work).filter(models.Work.del_flag == False)
    if keyword and keyword.strip():
        like_pattern = f"%{keyword.strip()}%"
        query = query.filter(models.Work.Workname.ilike(like_pattern))
    works = query.order_by(models.Work.Work_ID.asc()).all()
    return {
        "code": 200,
        "message": "获取工作列表成功",
        "data": [work_to_dict(w) for w in works],
    }


@work_router.put("/{work_id}")
def update_work(
    work_id: int,
    Workname: str = None,
    WorkDescript: str = None,
    Drawing_ID: int = None,
    Device_id: int = None,
    unit_id: int = None,
    sensor_id: int = None,
    data: str = None,
    Notes: str = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    work = (
        db.query(models.Work)
        .filter(models.Work.Work_ID == work_id, models.Work.del_flag == False)
        .first()
    )
    if not work:
        raise HTTPException(status_code=404, detail="工作不存在")

    if Workname is not None:
        if not Workname.strip():
            raise HTTPException(status_code=400, detail="工作名称不能为空")
        work.Workname = Workname.strip()

    if WorkDescript is not None:
        work.WorkDescript = WorkDescript.strip()

    if Drawing_ID is not None:
        work.Drawing_ID = Drawing_ID

    if Device_id is not None:
        work.Device_id = Device_id

    if unit_id is not None:
        work.unit_id = unit_id

    if sensor_id is not None:
        work.sensor_id = sensor_id

    if data is not None:
        if data.strip():
            try:
                json.loads(data)
            except (json.JSONDecodeError, ValueError):
                raise HTTPException(status_code=400, detail="data 字段不是合法的 JSON 格式")
        work.data = data

    if Notes is not None:
        work.Notes = Notes.strip()

    work.Modifytime = datetime.now(timezone.utc)
    db.commit()
    db.refresh(work)

    return {
        "code": 200,
        "message": "更新工作成功",
        "data": work_to_dict(work),
    }


@work_router.delete("/{work_id}")
def delete_work(
    work_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    work = (
        db.query(models.Work)
        .filter(models.Work.Work_ID == work_id, models.Work.del_flag == False)
        .first()
    )
    if not work:
        raise HTTPException(status_code=404, detail="工作不存在")

    work.del_flag = True
    work.Modifytime = datetime.now(timezone.utc)
    db.commit()

    return {
        "code": 200,
        "message": "删除工作成功",
        "data": {"Work_ID": work_id},
    }


# ==================== 工作流接口 ====================


@workflow_router.post("/create")
def create_workflow(
    Workflowname: str,
    WorkflowDescript: str = "",
    Notes: str = "",
    work_ids: str = "[]",
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not Workflowname or not Workflowname.strip():
        raise HTTPException(status_code=400, detail="工作流名称不能为空")

    wf = models.Workflow(
        Workflowname=Workflowname.strip(),
        WorkflowDescript=WorkflowDescript.strip() if WorkflowDescript else "",
        creater_id=current_user.User_ID,
        Notes=Notes.strip() if Notes else "",
    )
    db.add(wf)
    db.flush()

    try:
        work_id_list = json.loads(work_ids)
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="work_ids 格式错误")

    if not isinstance(work_id_list, list):
        raise HTTPException(status_code=400, detail="work_ids 应为数组")

    for seq, wid in enumerate(work_id_list, start=1):
        relation = models.WorkFlowRelation(
            Workflow_ID=wf.Workflow_ID,
            Work_ID=wid,
            flow_seq=seq,
            creater_id=current_user.User_ID,
        )
        db.add(relation)

    db.commit()
    db.refresh(wf)

    return {
        "code": 200,
        "message": "创建工作流成功",
        "data": workflow_to_dict(wf),
    }


@workflow_router.get("/list")
def list_workflows(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.Workflow).filter(models.Workflow.del_flag == False)
    workflows = query.order_by(models.Workflow.Workflow_ID.asc()).all()

    result = []
    for wf in workflows:
        wf_dict = workflow_to_dict(wf)
        work_count = (
            db.query(models.WorkFlowRelation)
            .filter(
                models.WorkFlowRelation.Workflow_ID == wf.Workflow_ID,
                models.WorkFlowRelation.del_flag == False,
            )
            .count()
        )
        wf_dict["work_count"] = work_count
        result.append(wf_dict)

    return {
        "code": 200,
        "message": "获取工作流列表成功",
        "data": result,
    }


@workflow_router.get("/{workflow_id}")
def get_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    wf = (
        db.query(models.Workflow)
        .filter(
            models.Workflow.Workflow_ID == workflow_id,
            models.Workflow.del_flag == False,
        )
        .first()
    )
    if not wf:
        raise HTTPException(status_code=404, detail="工作流不存在")

    relations = (
        db.query(models.WorkFlowRelation)
        .filter(
            models.WorkFlowRelation.Workflow_ID == workflow_id,
            models.WorkFlowRelation.del_flag == False,
        )
        .order_by(models.WorkFlowRelation.flow_seq)
        .all()
    )

    work_list = []
    for rel in relations:
        work = db.query(models.Work).filter(models.Work.Work_ID == rel.Work_ID).first()
        if work:
            work_info = work_to_dict(work)
            work_info["flow_seq"] = rel.flow_seq
            work_list.append(work_info)
        else:
            work_list.append({
                "Work_ID": rel.Work_ID,
                "Workname": "(已删除)",
                "flow_seq": rel.flow_seq,
            })

    wf_dict = workflow_to_dict(wf)
    wf_dict["works"] = work_list

    return {
        "code": 200,
        "message": "获取工作流详情成功",
        "data": wf_dict,
    }


@workflow_router.put("/{workflow_id}")
def update_workflow(
    workflow_id: int,
    Workflowname: str = None,
    WorkflowDescript: str = None,
    Notes: str = None,
    work_ids: str = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    wf = (
        db.query(models.Workflow)
        .filter(
            models.Workflow.Workflow_ID == workflow_id,
            models.Workflow.del_flag == False,
        )
        .first()
    )
    if not wf:
        raise HTTPException(status_code=404, detail="工作流不存在")

    if Workflowname is not None:
        if not Workflowname.strip():
            raise HTTPException(status_code=400, detail="工作流名称不能为空")
        wf.Workflowname = Workflowname.strip()

    if WorkflowDescript is not None:
        wf.WorkflowDescript = WorkflowDescript.strip()

    if Notes is not None:
        wf.Notes = Notes.strip()

    wf.Modifytime = datetime.now(timezone.utc)

    if work_ids is not None:
        try:
            work_id_list = json.loads(work_ids)
        except (json.JSONDecodeError, ValueError):
            raise HTTPException(status_code=400, detail="work_ids 格式错误")

        if not isinstance(work_id_list, list):
            raise HTTPException(status_code=400, detail="work_ids 应为数组")

        old_relations = (
            db.query(models.WorkFlowRelation)
            .filter(models.WorkFlowRelation.Workflow_ID == workflow_id)
            .all()
        )
        for rel in old_relations:
            rel.del_flag = True
            rel.Modifytime = datetime.now(timezone.utc)

        for seq, wid in enumerate(work_id_list, start=1):
            relation = models.WorkFlowRelation(
                Workflow_ID=wf.Workflow_ID,
                Work_ID=wid,
                flow_seq=seq,
                creater_id=current_user.User_ID,
            )
            db.add(relation)

    db.commit()
    db.refresh(wf)

    return {
        "code": 200,
        "message": "更新工作流成功",
        "data": workflow_to_dict(wf),
    }


@workflow_router.delete("/{workflow_id}")
def delete_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    wf = (
        db.query(models.Workflow)
        .filter(
            models.Workflow.Workflow_ID == workflow_id,
            models.Workflow.del_flag == False,
        )
        .first()
    )
    if not wf:
        raise HTTPException(status_code=404, detail="工作流不存在")

    wf.del_flag = True
    wf.Modifytime = datetime.now(timezone.utc)

    relations = (
        db.query(models.WorkFlowRelation)
        .filter(models.WorkFlowRelation.Workflow_ID == workflow_id)
        .all()
    )
    for rel in relations:
        rel.del_flag = True
        rel.Modifytime = datetime.now(timezone.utc)

    db.commit()

    return {
        "code": 200,
        "message": "删除工作流成功",
        "data": {"Workflow_ID": workflow_id},
    }
