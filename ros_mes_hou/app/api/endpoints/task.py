from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import models
from app.db.database import get_db

router = APIRouter()


class TaskCreate(BaseModel):
    Taskname: str
    Taskdescripte: Optional[str] = None
    Workflow_ID: Optional[int] = None
    Drawing_ID: Optional[int] = None
    TaskAssignment_id: Optional[int] = None
    Notes: Optional[str] = None


class TaskUpdate(BaseModel):
    Taskname: Optional[str] = None
    Taskdescripte: Optional[str] = None
    Workflow_ID: Optional[int] = None
    Drawing_ID: Optional[int] = None
    TaskAssignment_id: Optional[int] = None
    Notes: Optional[str] = None


class ProgressCreate(BaseModel):
    Notes: str


def task_to_dict(task: models.Task):
    return {
        "Task_ID": task.Task_ID,
        "Taskname": task.Taskname,
        "Taskdescripte": task.Taskdescripte or "",
        "Workflow_ID": task.Workflow_ID,
        "Drawing_ID": task.Drawing_ID,
        "creater_id": task.creater_id,
        "Createtime": str(task.Createtime) if task.Createtime else "",
        "TaskAssignment_id": task.TaskAssignment_id,
        "Status": task.Status,
        "Modifytime": str(task.Modifytime) if task.Modifytime else "",
        "del_flag": task.del_flag,
        "Notes": task.Notes or "",
    }


def tracing_to_dict(tracing: models.TasksTracing):
    return {
        "TasksTracing_ID": tracing.TasksTracing_ID,
        "Task_ID": tracing.Task_ID,
        "operate_type": tracing.operate_type,
        "Workflow_ID": tracing.Workflow_ID,
        "operater_ID": tracing.operater_ID,
        "operate_time": str(tracing.operate_time) if tracing.operate_time else "",
        "Notes": tracing.Notes or "",
    }


def get_work_subset(db: Session, workflow_id: Optional[int]):
    if not workflow_id:
        return []

    relations = db.query(models.WorkFlowRelation).filter(
        models.WorkFlowRelation.Workflow_ID == workflow_id,
        models.WorkFlowRelation.del_flag == False,
    ).order_by(models.WorkFlowRelation.flow_seq).all()

    result = []
    for rel in relations:
        work = db.query(models.Work).filter(
            models.Work.Work_ID == rel.Work_ID
        ).first()

        if work:
            result.append({
                "Work_ID": work.Work_ID,
                "Workname": work.Workname,
                "WorkDescript": work.WorkDescript or "",
                "flow_seq": rel.flow_seq,
            })

    return result


def enrich_task_response(db: Session, task: models.Task, d: dict):
    if task.Drawing_ID:
        drawing = db.query(models.Drawing).filter(
            models.Drawing.Drawing_ID == task.Drawing_ID
        ).first()
        d["DrawingName"] = drawing.Drawingname if drawing else ""
    else:
        d["DrawingName"] = ""

    if task.Workflow_ID:
        workflow = db.query(models.Workflow).filter(
            models.Workflow.Workflow_ID == task.Workflow_ID
        ).first()
        d["WorkflowName"] = workflow.Workflowname if workflow else ""
    else:
        d["WorkflowName"] = ""

    if task.TaskAssignment_id:
        assignee = db.query(models.User).filter(
            models.User.User_ID == task.TaskAssignment_id
        ).first()
        d["AssigneeName"] = assignee.Name if assignee and assignee.Name else (
            assignee.Username if assignee else ""
        )
    else:
        d["AssigneeName"] = ""

    d["WorksSubset"] = get_work_subset(db, task.Workflow_ID)
    return d


def create_tracing_record(
    db: Session,
    task_id: int,
    operate_type: int,
    workflow_id: int,
    operater_id: int,
    notes: str,
):
    record = models.TasksTracing(
        Task_ID=task_id,
        operate_type=operate_type,
        Workflow_ID=workflow_id,
        operater_ID=operater_id,
        operate_time=datetime.now(timezone.utc),
        Notes=notes,
    )
    db.add(record)
    return record


@router.post("/create")
def create_task(
    data: TaskCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not data.Taskname or not data.Taskname.strip():
        raise HTTPException(status_code=400, detail="任务名称不能为空")

    task = models.Task(
        Taskname=data.Taskname.strip(),
        Taskdescripte=data.Taskdescripte.strip() if data.Taskdescripte else None,
        Workflow_ID=data.Workflow_ID,
        Drawing_ID=data.Drawing_ID,
        creater_id=current_user.User_ID,
        TaskAssignment_id=data.TaskAssignment_id,
        Status="0",
        del_flag=False,
        Notes=data.Notes.strip() if data.Notes else None,
    )

    db.add(task)
    db.commit()
    db.refresh(task)

    return {
        "code": 200,
        "message": "创建任务成功",
        "data": task_to_dict(task),
    }


@router.get("/list")
def list_tasks(
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    drawing_id: Optional[int] = None,
    workflow_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.Task).filter(models.Task.del_flag == False)

    if keyword and keyword.strip():
        like_pattern = f"%{keyword.strip()}%"
        query = query.filter(models.Task.Taskname.ilike(like_pattern))

    if status is not None:
        query = query.filter(models.Task.Status == status)

    if drawing_id is not None:
        query = query.filter(models.Task.Drawing_ID == drawing_id)

    if workflow_id is not None:
        query = query.filter(models.Task.Workflow_ID == workflow_id)

    tasks = query.order_by(models.Task.Createtime.desc()).all()

    result = []
    for t in tasks:
        d = task_to_dict(t)
        enrich_task_response(db, t, d)
        result.append(d)

    return {
        "code": 200,
        "message": "获取任务列表成功",
        "data": result,
    }


@router.get("/{task_id}")
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = db.query(models.Task).filter(
        models.Task.Task_ID == task_id,
        models.Task.del_flag == False,
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    d = task_to_dict(task)
    enrich_task_response(db, task, d)

    return {
        "code": 200,
        "message": "获取任务详情成功",
        "data": d,
    }


@router.put("/{task_id}")
def update_task(
    task_id: int,
    data: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = db.query(models.Task).filter(
        models.Task.Task_ID == task_id,
        models.Task.del_flag == False,
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if data.Taskname is not None:
        if not data.Taskname.strip():
            raise HTTPException(status_code=400, detail="任务名称不能为空")
        task.Taskname = data.Taskname.strip()

    if data.Taskdescripte is not None:
        task.Taskdescripte = data.Taskdescripte.strip() if data.Taskdescripte else None

    if data.Workflow_ID is not None:
        task.Workflow_ID = data.Workflow_ID

    if data.Drawing_ID is not None:
        task.Drawing_ID = data.Drawing_ID

    if data.TaskAssignment_id is not None:
        task.TaskAssignment_id = data.TaskAssignment_id

    if data.Notes is not None:
        task.Notes = data.Notes.strip() if data.Notes else None

    task.Modifytime = datetime.now(timezone.utc)

    db.commit()
    db.refresh(task)

    return {
        "code": 200,
        "message": "更新任务成功",
        "data": task_to_dict(task),
    }


@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = db.query(models.Task).filter(
        models.Task.Task_ID == task_id,
        models.Task.del_flag == False,
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    task.del_flag = True
    task.Modifytime = datetime.now(timezone.utc)

    workflow_id = task.Workflow_ID if task.Workflow_ID else 0
    create_tracing_record(
        db,
        task_id,
        6,
        workflow_id,
        current_user.User_ID,
        "删除任务",
    )

    db.commit()

    return {
        "code": 200,
        "message": "删除任务成功",
        "data": {"Task_ID": task_id},
    }


@router.post("/{task_id}/start")
def start_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = db.query(models.Task).filter(
        models.Task.Task_ID == task_id,
        models.Task.del_flag == False,
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.Status not in ("0", "2"):
        raise HTTPException(status_code=400, detail="当前状态下不允许启动任务")

    task.Status = "1"
    task.Modifytime = datetime.now(timezone.utc)

    workflow_id = task.Workflow_ID if task.Workflow_ID else 0
    create_tracing_record(
        db,
        task_id,
        0,
        workflow_id,
        current_user.User_ID,
        "启动任务",
    )

    db.commit()
    db.refresh(task)

    return {
        "code": 200,
        "message": "任务已启动",
        "data": task_to_dict(task),
    }


@router.post("/{task_id}/pause")
def pause_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = db.query(models.Task).filter(
        models.Task.Task_ID == task_id,
        models.Task.del_flag == False,
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.Status != "1":
        raise HTTPException(status_code=400, detail="当前状态下不允许暂停任务")

    task.Status = "2"
    task.Modifytime = datetime.now(timezone.utc)

    workflow_id = task.Workflow_ID if task.Workflow_ID else 0
    create_tracing_record(
        db,
        task_id,
        1,
        workflow_id,
        current_user.User_ID,
        "暂停任务",
    )

    db.commit()
    db.refresh(task)

    return {
        "code": 200,
        "message": "任务已暂停",
        "data": task_to_dict(task),
    }


@router.post("/{task_id}/resume")
def resume_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = db.query(models.Task).filter(
        models.Task.Task_ID == task_id,
        models.Task.del_flag == False,
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.Status != "2":
        raise HTTPException(status_code=400, detail="当前状态下不允许唤醒任务")

    task.Status = "1"
    task.Modifytime = datetime.now(timezone.utc)

    workflow_id = task.Workflow_ID if task.Workflow_ID else 0
    create_tracing_record(
        db,
        task_id,
        2,
        workflow_id,
        current_user.User_ID,
        "唤醒任务",
    )

    db.commit()
    db.refresh(task)

    return {
        "code": 200,
        "message": "任务已唤醒",
        "data": task_to_dict(task),
    }


@router.post("/{task_id}/finish")
def finish_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = db.query(models.Task).filter(
        models.Task.Task_ID == task_id,
        models.Task.del_flag == False,
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.Status not in ("1", "2"):
        raise HTTPException(status_code=400, detail="当前状态下不允许结束任务")

    task.Status = "3"
    task.Modifytime = datetime.now(timezone.utc)

    workflow_id = task.Workflow_ID if task.Workflow_ID else 0
    create_tracing_record(
        db,
        task_id,
        3,
        workflow_id,
        current_user.User_ID,
        "结束任务",
    )

    db.commit()
    db.refresh(task)

    return {
        "code": 200,
        "message": "任务已结束",
        "data": task_to_dict(task),
    }


@router.post("/{task_id}/dispatch")
def dispatch_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    target_task = db.query(models.Task).filter(
        models.Task.Task_ID == task_id,
        models.Task.del_flag == False,
    ).first()

    if not target_task:
        raise HTTPException(status_code=404, detail="目标任务不存在")

    if target_task.Status != "0":
        raise HTTPException(status_code=400, detail="只有就绪状态的任务才能被调度")

    running_task = db.query(models.Task).filter(
        models.Task.Status == "1",
        models.Task.del_flag == False,
    ).first()

    if running_task:
        running_task.Status = "2"
        running_task.Modifytime = datetime.now(timezone.utc)

        r_workflow_id = running_task.Workflow_ID if running_task.Workflow_ID else 0
        create_tracing_record(
            db,
            running_task.Task_ID,
            1,
            r_workflow_id,
            current_user.User_ID,
            "因任务调度被暂停",
        )

    target_task.Status = "1"
    target_task.Modifytime = datetime.now(timezone.utc)

    t_workflow_id = target_task.Workflow_ID if target_task.Workflow_ID else 0
    create_tracing_record(
        db,
        task_id,
        5,
        t_workflow_id,
        current_user.User_ID,
        "任务被调度进入流水线",
    )

    db.commit()
    db.refresh(target_task)

    return {
        "code": 200,
        "message": "任务调度成功",
        "data": task_to_dict(target_task),
    }


@router.get("/{task_id}/tracing")
def get_task_tracing(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = db.query(models.Task).filter(
        models.Task.Task_ID == task_id,
        models.Task.del_flag == False,
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    tracings = db.query(models.TasksTracing).filter(
        models.TasksTracing.Task_ID == task_id,
    ).order_by(models.TasksTracing.operate_time.desc()).all()

    result = []
    for t in tracings:
        d = tracing_to_dict(t)

        if t.operater_ID:
            user = db.query(models.User).filter(
                models.User.User_ID == t.operater_ID
            ).first()
            d["OperatorName"] = user.Name if user and user.Name else (
                user.Username if user else ""
            )
        else:
            d["OperatorName"] = ""

        result.append(d)

    return {
        "code": 200,
        "message": "获取任务跟踪记录成功",
        "data": result,
    }


@router.get("/{task_id}/works")
def get_task_works(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = db.query(models.Task).filter(
        models.Task.Task_ID == task_id,
        models.Task.del_flag == False,
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    works = get_work_subset(db, task.Workflow_ID)

    return {
        "code": 200,
        "message": "获取工作子集成功",
        "data": works,
    }


@router.post("/{task_id}/progress")
def add_task_progress(
    task_id: int,
    data: ProgressCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = db.query(models.Task).filter(
        models.Task.Task_ID == task_id,
        models.Task.del_flag == False,
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    workflow_id = task.Workflow_ID if task.Workflow_ID else 0
    record = create_tracing_record(
        db,
        task_id,
        4,
        workflow_id,
        current_user.User_ID,
        data.Notes,
    )

    db.commit()
    db.refresh(record)

    return {
        "code": 200,
        "message": "添加进度记录成功",
        "data": tracing_to_dict(record),
    }
