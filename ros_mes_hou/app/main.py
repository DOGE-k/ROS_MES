import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import engine, Base
import app.db.models

from app.api.endpoints import login, hardware, control, finetuning, ws_stream, register, user, module, coordination

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="ROS MES Backend",
    description="基于 FastAPI 与 SQLite 重构的机械臂 MES 系统",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"code": 200, "message": "ros_mes_hou FastAPI 启动成功！"}

app.include_router(login.router, prefix="/api", tags=["认证模块"])
app.include_router(register.router, prefix="/api", tags=["注册模块"])
app.include_router(user.router, prefix="/api/user", tags=["用户模块"])
app.include_router(hardware.router, prefix="/api/hardware", tags=["硬件管理模块"])
app.include_router(module.router, prefix="/api/module", tags=["模块管理模块"])
app.include_router(coordination.router, prefix="/api/coordination", tags=["坐标下发模块"])
app.include_router(control.router, prefix="/api/control", tags=["设备底层控制模块"])
app.include_router(finetuning.router, prefix="/api/finetuning", tags=["微调记录模块"])
app.include_router(ws_stream.router, prefix="/api/ws", tags=["实时数据流推送"])

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)