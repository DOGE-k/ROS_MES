# -*- coding: utf-8 -*-
"""微调常驻链路 _AdjustCommandLink 单元测试。

用 FakeWS 模拟 rosbridge 服务端：advertise/subscribe 记录，publish 后按需回 adjust_ack。
验证两点：
  1) 收到回执 → confirmed=True，且 request_id 在 publish 与回执间一致；
  2) 超时未收到回执 → confirmed=False/unconfirmed，且**不自动重发**运动指令。
"""
import asyncio
import json

import pytest

import app.ros.rosbridge as rb
from app.ros.rosbridge import _AdjustCommandLink, build_fine_tuning_publish_payload
from app.ros.profile import get_active_profile

ACK_TOPIC = "/control/adjust_ack"


class FakeWS:
    """模拟 rosbridge：async context manager + async iterator + send。"""

    def __init__(self, auto_ack=True, ack_delay=0.05):
        self.sent = []
        self.published = []          # 微调 publish 帧
        self.auto_ack = auto_ack
        self.ack_delay = ack_delay
        self._queue = None  # 延迟到 __aenter__（常驻循环内）创建，避免跨事件循环

    async def __aenter__(self):
        self._queue = asyncio.Queue()
        return self

    async def __aexit__(self, *a):
        return False

    async def send(self, raw):
        self.sent.append(raw)
        ev = json.loads(raw)
        if ev.get("op") == "publish" and ev.get("topic") != ACK_TOPIC:
            self.published.append(ev)
            if self.auto_ack:
                rid = ev["msg"]["request_id"]
                ack = {"op": "publish", "topic": ACK_TOPIC,
                       "msg": {"request_id": rid, "result": 0,
                               "module_id": ev["msg"]["module_id"],
                               "device_id": ev["msg"]["device_id"], "message": "ok"}}
                asyncio.get_running_loop().call_later(
                    self.ack_delay, lambda: self._queue.put_nowait(json.dumps(ack)))

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await self._queue.get()


def _make_link(fake, monkeypatch):
    monkeypatch.setattr(rb.websockets, "connect", lambda *a, **k: fake)
    return _AdjustCommandLink(get_active_profile(), "ws://fake")


def test_send_confirmed(monkeypatch):
    fake = FakeWS(auto_ack=True)
    link = _make_link(fake, monkeypatch)
    payload = build_fine_tuning_publish_payload("rotation", 70.0, 17, 1)
    result = link.send(payload, timeout=2.0)
    assert result["confirmed"] is True, result
    assert result["confirmation_status"] == "confirmed"
    assert result["ack"]["request_id"] == result["request_id"]
    assert len(fake.published) == 1
    assert fake.published[0]["msg"]["request_id"] == result["request_id"]
    # advertise 三个微调话题 + 订阅回执话题，常驻只建一次
    ops = [json.loads(s).get("op") for s in fake.sent]
    assert ops.count("advertise") == 3
    assert ops.count("subscribe") == 1


def test_send_timeout_unconfirmed_no_retry(monkeypatch):
    fake = FakeWS(auto_ack=False)
    link = _make_link(fake, monkeypatch)
    payload = build_fine_tuning_publish_payload("telescopic", -10.0, 17, 3)
    result = link.send(payload, timeout=0.3)
    assert result["confirmed"] is False
    assert result["confirmation_status"] == "unconfirmed"
    assert "未收到控制节点" in result["error"]
    assert len(fake.published) == 1  # 关键：不自动重发运动指令
