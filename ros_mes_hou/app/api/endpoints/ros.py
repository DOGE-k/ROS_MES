# app/api/endpoints/ros.py

from fastapi import APIRouter, HTTPException

from app.services.ros_service import (
    RosDispatchError,
    latest_status,
    publish_ros_command,
    ros_ready,
)

router = APIRouter()


@router.get("/send_ros")
def send_ros(msg: str):
    try:
        dispatch_result = publish_ros_command(
            "send_ros",
            {
                "msg": msg,
            },
        )
    except RosDispatchError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "code": 200,
        "message": f"已发送到 ROS：{msg}",
        "data": dispatch_result,
    }


@router.get("/get_ros_status")
def get_ros_status():
    return {
        "code": 200,
        "message": "获取 ROS 状态成功",
        "data": {
            **latest_status,
            "ros_ready": ros_ready,
        },
    }