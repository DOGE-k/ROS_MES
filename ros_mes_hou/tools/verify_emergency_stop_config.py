r"""急停地址配置验收脚本（本地自查，不需要真机、不需要启动后端）。

在任意目录运行，建议在 ros_mes_hou 下执行：
    python tools\verify_emergency_stop_config.py

逐项打印 PASS/FAIL：
  1. 不设 ROSBRIDGE_URL 时，急停发到默认地址 ws://localhost:9010
  2. 急停帧内容仍是 /control/softstop + module_id=0 + device_id=0 + position=[1]
  3. 设 ROSBRIDGE_URL=ws://127.0.0.1:9099 后，急停发到 9099，9010 收不到
  4. rosbridge 不在线时，trigger_emergency_stop() 返回 False（接口层据此报 500）

脚本会在本机 9010 / 9099 起临时 WebSocket 服务模拟 rosbridge，退出时自动关闭。
"""
import asyncio
import json
import os
import sys

from websockets.asyncio.server import serve

DEFAULT_PORT = 9010
ALT_PORT = 9099
DEAD_PORT = 9098

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
received = {DEFAULT_PORT: [], ALT_PORT: []}
results = []


def make_handler(port):
    async def handler(ws):
        async for message in ws:
            received[port].append(message)

    return handler


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))


async def start(port):
    return await serve(make_handler(port), "127.0.0.1", port)


async def main():
    sys.path.insert(0, BACKEND_DIR)
    from app.services import ros_control

    default_server = await start(DEFAULT_PORT)
    alt_server = await start(ALT_PORT)
    try:
        # 场景 1：未设环境变量 -> 默认地址
        os.environ.pop("ROSBRIDGE_URL", None)
        ok = await ros_control.trigger_emergency_stop()
        await asyncio.sleep(0.3)
        check(
            "未设 ROSBRIDGE_URL 时发往默认地址 9010",
            ok and len(received[DEFAULT_PORT]) == 1,
            f"ret={ok}, 9010 收到 {len(received[DEFAULT_PORT])} 帧",
        )
        if received[DEFAULT_PORT]:
            frame = json.loads(received[DEFAULT_PORT][0])
            check(
                "急停帧内容为 /control/softstop + module/device=0 + position=[1]",
                frame["topic"] == "/control/softstop"
                and frame["msg"]["module_id"] == 0
                and frame["msg"]["device_id"] == 0
                and frame["msg"]["position"] == [1],
                json.dumps(frame["msg"], ensure_ascii=False),
            )

        # 场景 2：指定新地址 -> 只发到新地址
        os.environ["ROSBRIDGE_URL"] = f"ws://127.0.0.1:{ALT_PORT}"
        before_9010 = len(received[DEFAULT_PORT])
        ok = await ros_control.trigger_emergency_stop()
        await asyncio.sleep(0.3)
        check(
            "设置 ROSBRIDGE_URL 后发往新地址 9099",
            ok and len(received[ALT_PORT]) == 1,
            f"ret={ok}, 9099 收到 {len(received[ALT_PORT])} 帧",
        )
        check(
            "新地址生效时 9010 不再收到",
            len(received[DEFAULT_PORT]) == before_9010,
            f"9010 新增 {len(received[DEFAULT_PORT]) - before_9010} 帧",
        )

        # 场景 3：rosbridge 不在线 -> 明确失败
        os.environ["ROSBRIDGE_URL"] = f"ws://127.0.0.1:{DEAD_PORT}"
        ok = await ros_control.trigger_emergency_stop()
        check("rosbridge 不在线时返回 False（不报发送成功）", ok is False, f"ret={ok}")
    finally:
        for server in (default_server, alt_server):
            server.close()
            await server.wait_closed()

    failed = [name for name, ok in results if not ok]
    print()
    print(f"{len(results) - len(failed)}/{len(results)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
