# app/api/endpoints/ws_stream.py
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends, status
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from app.services.ros_control import stream_real_robot_data
from app.db.database import get_db
from app.core import security
from app.db import models

router = APIRouter()

@router.websocket("/ws/robot_status")
async def robot_status_stream(websocket: WebSocket, token: str = Query(None), db: Session = Depends(get_db)):
    """
    WebSocket 端点：与前端建立长连接，实时推送机械臂状态
    """
   
    
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        # 解码 Token (逻辑同 deps.py)
        payload = jwt.decode(
            token, 
            security.SECRET_KEY, 
            algorithms=[security.ALGORITHM]
        )
        username: str = payload.get("sub")
        if username is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        # 数据库验证用户是否存在
        user = db.query(models.User).filter(models.User.username == username).first()
        if user is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
            
    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
     # 接受前端的连接请求
    await websocket.accept()
    print(f"用户 {username} 已通过 WebSocket 连接大屏！开始推送实时数据...")
    
    # 3. 开始推送数据
    try:
        async for real_data_json_str in stream_real_robot_data():
            await websocket.send_text(real_data_json_str)
            
    except WebSocketDisconnect:
        print(f"用户 {username} 已断开连接。")