# app/api/endpoints/ws_stream.py
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.ros_control import stream_real_robot_data

router = APIRouter()

@router.websocket("/ws/robot_status")
async def robot_status_stream(websocket: WebSocket):
    """
    WebSocket 端点：与前端建立长连接，实时推送机械臂状态
    """
    # 1. 接受前端的连接请求
    await websocket.accept()
    print("前端大屏已连接！开始推送实时数据...")
    
    try:
        # 激活我们在 ros_control.py 里写的“抽水机”
        async for real_data_json_str in stream_real_robot_data():
            
            # 将从 web_data_node.py 读到的真实 JSON 字符串，直接推给 Vue 前端
            await websocket.send_text(real_data_json_str)
            
    except WebSocketDisconnect:
        # 5. 如果前端断开连接（比如关掉网页），优雅地结束循环
        print("前端已断开连接，停止数据推送。")