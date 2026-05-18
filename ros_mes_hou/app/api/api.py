from fastapi import APIRouter

from app.api.endpoints import (
    control,
    coordination,
    dashboard,
    device_api,
    drawing,
    finetuning,
    login,
    model_api,
    module,
    register,
    ros,
    sensors_api,
    task,
    unit_api,
    user,
    workflow,
    ws_stream,
)

api_router = APIRouter()

api_router.include_router(login.router, tags=["login"])
api_router.include_router(register.router, tags=["register"])
api_router.include_router(user.router, prefix="/user", tags=["user"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(finetuning.router, prefix="/finetuning", tags=["finetuning"])
api_router.include_router(drawing.router, prefix="/drawing", tags=["drawing"])
api_router.include_router(module.router, prefix="/module", tags=["module"])
api_router.include_router(control.router, prefix="/control", tags=["control"])
api_router.include_router(coordination.router, prefix="/coordination", tags=["coordination"])
api_router.include_router(ros.router, prefix="/ros", tags=["ros"])
api_router.include_router(ws_stream.router, prefix="/ws", tags=["ws"])
api_router.include_router(workflow.work_router, prefix="/work", tags=["work"])
api_router.include_router(workflow.workflow_router, prefix="/workflow", tags=["workflow"])
api_router.include_router(task.router, prefix="/task", tags=["task"])
api_router.include_router(model_api.router, prefix="/model", tags=["model"])
api_router.include_router(device_api.router, prefix="/device", tags=["device"])
api_router.include_router(unit_api.router, prefix="/unit", tags=["unit"])
api_router.include_router(sensors_api.router, prefix="/sensors", tags=["sensors"])
