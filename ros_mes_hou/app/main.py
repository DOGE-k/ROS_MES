import sys
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# 引入数据库配置和模型
from app.db.database import engine, Base
import app.db.models  # 必须引入，这样 SQLAlchemy 才能发现模型
from app.api.endpoints import hardware
from app.api.endpoints import login, hardware, control, finetuning, ws_stream, register


# 自动创建数据库表（如果表不存在）
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="ROS MES Backend",
    description="基于 FastAPI 与 SQLite 重构的机械臂 MES 系统",
    version="2.0.0"
)

# 配置跨域中间件，允许 ros_mes_front (Vue) 访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"status": "success", "message": "ros_mes_hou FastAPI 启动成功！"}



if __name__ == "__main__":
    # 启动应用，reload=True 表示修改代码后自动重启
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


app.include_router(login.router, prefix="/api", tags=["认证模块"]) 
app.include_router(register.router, prefix="/api", tags=["注册模块"])
app.include_router(hardware.router, prefix="/api/hardware", tags=["硬件管理模块"])
app.include_router(control.router, prefix="/api/control", tags=["设备底层控制模块"])
app.include_router(finetuning.router, prefix="/api/finetuning", tags=["微调记录模块"])
app.include_router(ws_stream.router, prefix="/api/ws", tags=["实时数据流推送"])