from fastapi import APIRouter

from app.api.endpoints import (
    control,
    coordination,
    drawing,
    finetuning,
    hardware_web,
    login,
    module,
    register,
    ros,
    user,
    ws_stream,
)

api_router = APIRouter()

api_router.include_router(login.router, tags=["login"])
api_router.include_router(register.router, tags=["register"])
api_router.include_router(user.router, prefix="/user", tags=["user"])
api_router.include_router(hardware_web.router, prefix="/hardware", tags=["hardware"])
api_router.include_router(finetuning.router, prefix="/finetuning", tags=["finetuning"])
api_router.include_router(drawing.router, prefix="/drawing", tags=["drawing"])
api_router.include_router(module.router, prefix="/module", tags=["module"])
api_router.include_router(control.router, prefix="/control", tags=["control"])
api_router.include_router(coordination.router, prefix="/coordination", tags=["coordination"])
api_router.include_router(ros.router, prefix="/ros", tags=["ros"])
api_router.include_router(ws_stream.router, prefix="/ws", tags=["ws"])
