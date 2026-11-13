from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class LocalStopRequest(BaseModel):
    """局部停请求：按范围分级，不做“全停”。

    - scope=module：停整个模块（`[0x08, module_id]`）；
    - scope=arm：停整台机械臂（对该臂 3 根轴各发一帧 `[0x0C, 1]`），`device_id` 传臂号 1~5；
    - scope=axis：停单轴（`device_id` 轴号 1~15 + `[0x0C, 1]`）。
    全局急停仍走 `POST /control/emergency_stop`，不复用本接口。
    """

    model_config = ConfigDict(extra="forbid")
    scope: Literal["module", "arm", "axis"]
    module_id: int
    device_id: Optional[int] = None
    connection_revision: Optional[int] = None
