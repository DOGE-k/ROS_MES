from fastapi import APIRouter, Body, HTTPException

router = APIRouter()


@router.post("/")
def lock_and_dispatch_module(payload: dict = Body(...)):
    print("收到模块下发数据：", payload)

    x = (
        payload.get("x")
        or payload.get("X")
        or payload.get("targetX")
        or payload.get("moduleX")
        or payload.get("col")
    )

    y = (
        payload.get("y")
        or payload.get("Y")
        or payload.get("targetY")
        or payload.get("moduleY")
        or payload.get("row")
    )

    position = payload.get("position")
    if isinstance(position, dict):
        x = x or position.get("x")
        y = y or position.get("y")

    if x is None or y is None:
        raise HTTPException(status_code=422, detail="缺少 x 或 y 坐标")

    try:
        x = int(x)
        y = int(y)
    except ValueError:
        raise HTTPException(status_code=422, detail="x 和 y 必须是数字")

    if not (1 <= x <= 8 and 1 <= y <= 8):
        raise HTTPException(status_code=400, detail="坐标范围必须是 1 到 8")

    print(f"模块锁定并下发：X={x}, Y={y}")

    return {
        "code": 200,
        "message": "模块锁定并下发成功",
        "data": {
            "x": x,
            "y": y
        }
    }