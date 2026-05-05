from fastapi import APIRouter, Depends
from app.api.deps import get_current_user
from app.db import models

router = APIRouter()


@router.get("/me")
def get_me(current_user: models.User = Depends(get_current_user)):
    return {
        "code": 200,
        "message": "获取用户信息成功",
        "data": {
            "account": current_user.username,
            "role": current_user.role,
            "createdAt": str(current_user.created_at)
        }
    }