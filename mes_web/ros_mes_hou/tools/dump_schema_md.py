#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 app/db/models.py 生成数据库表结构文档（字段级）。

用法（在 mes_web/ros_mes_hou/ 下）：
    python tools/dump_schema_md.py            # 打印到 stdout
    python tools/dump_schema_md.py --write    # 写回 docs/ROS_MES_数据库表结构.md

为什么要有这个脚本：
    xlsx/手写 md 都会和 models.py 漂移。本脚本把 models.py 当唯一真相源，
    字段说明取 models.py 里 Column 上方的注释，改代码时顺手改注释即可同步。
    tests/test_db_schema_doc_in_sync.py 会校验文档与代码一致。
"""
import argparse
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
sys.path.insert(0, BACKEND)

from app.db import models  # noqa: E402

MODELS_PY = os.path.join(BACKEND, "app", "db", "models.py")
OUT_MD = os.path.join(os.path.dirname(BACKEND), "docs", "ROS_MES_数据库表结构.md")

# 表名 → 中文名。新增表时在这里补一行，否则用表名自身。
TABLE_CN = {
    "Users": "用户表",
    "Drawings": "图纸表",
    "DrawingsVersion": "图纸版本表",
    "Tasks": "任务表",
    "TasksTracing": "任务跟踪表",
    "works": "工作表",
    "workflows": "工作流表",
    "work_flow_relations": "工作流关系表",
    "Type": "自适应工装型号表",
    "Module": "模块表",
    "Unit": "机械臂单元表",
    "sensors": "传感器表",
    "sensor_log": "传感器日志表",
    "Calculation": "计算解析数据日志表",
    "Point_data": "点云图解析数据表",
    "fine_tuning": "微调记录表",
    "fine_tuning_config": "微调配置表",
    "fine_tuning_batches": "微调批次表",
    "control_sessions": "模块握手会话表",
    "control_stop_holds": "局部停记录表",
    "control_safety": "全局安全状态表",
    "ros_debug_settings": "ROS 调试设置表",
}

# ROS 侧归档表：后端只保留 ORM 定义，不做读写；语义由 ROS 侧定义。
ROS_ARCHIVE = {
    "sensor_log": "ROS 侧写入的传感器归档表，后端不消费。`sensor_id` 实际是 AXIS 设备号"
                  "（1~15 轴 / 21~25 臂级），不是 `sensors.id` 行主键；"
                  "`sqlite_create.py` 里声明的外键为遗留项，SQLite 未启用 FK 校验。",
    "can_event_log": "ROS 侧写入的 CAN 事件归档表，后端不消费，`models.py` 中无 ORM 定义"
                     "（由 `sqlite_create.py` 与 `hardware_node.py` 建表写入）。",
    "Calculation": "ROS 侧写入的计算解析日志，后端不消费。",
    "Point_data": "ROS 侧写入的点云解析结果，后端不消费。",
}

# 表级说明。新增表时在这里补，缺省为空。
TABLE_NOTE = {
    "fine_tuning": "字段语义（初始值/应到值/到位实测/偏差/结论）见接口字段文档 §2.4.4。"
                   "`new_value` 允许为空：缺少初始值时无法算应到值。",
    "Tasks": "`Status` 取值 \"0\"就绪 / \"1\"运行中 / \"2\"已暂停 / \"3\"已结束，"
             "前端 `TaskManage.vue` 的 statusLabel() 只映射这四个值。",
    "TasksTracing": "`operate_type`：0启动 / 1暂停 / 2唤醒 / 3结束 / 4编辑 / "
                    "5调度入流水线 / 6删除。",
    "Unit": "`Unit_ID` 为业务臂号 32/64/96/128/160（调试数据允许 1~5）；"
            "21~25 是 AXIS 臂级设备号，不是本字段取值。",
    "fine_tuning_batches": "幂等请求 + 逐轴进度 + 目标锁；完成后人工关闭时 `target_key` 置空。",
    "control_safety": "固定单行。MES 急停/解除的发送状态与联锁代次，不是设备状态表。",
    "ros_debug_settings": "固定单行。当前服务连接模式与地址，逐项自动保存；`revision` 递增通知前端刷新。",
    "fine_tuning_config": "微调页面配置 JSON 快照。",
}


def _load_comments():
    """解析 models.py，取每个 Column 赋值上方紧邻的 # 注释作为字段说明。"""
    with open(MODELS_PY, encoding="utf-8") as f:
        src = f.read().splitlines()
    out, cur_class, buf = {}, None, []

    class_re = re.compile(r"^class\s+(\w+)\s*\(Base\)")
    tablename_re = re.compile(r'^\s*__tablename__\s*=\s*["\'](\w+)["\']')
    col_re = re.compile(r"^\s{4}(\w+)\s*=\s*Column\(")

    for line in src:
        m = class_re.match(line)
        if m:
            cur_class, buf = m.group(1), []
            continue
        m = tablename_re.match(line)
        if m and cur_class:
            out.setdefault(cur_class, {"table": m.group(1), "cols": {}})
            continue
        m = col_re.match(line)
        if m and cur_class:
            name = m.group(1)
            comment = " ".join(s.lstrip("# ").strip() for s in buf if s).strip()
            out.setdefault(cur_class, {"cols": {}})["cols"][name] = comment
            buf = []
            continue
        stripped = line.strip()
        if stripped.startswith("#"):
            buf.append(stripped)
        elif stripped:
            buf = []
    return out


def _render_type(col):
    try:
        return str(col.type.compile()).upper()
    except Exception:
        return type(col.type).__name__.upper()


def _default_of(col):
    if col.server_default is not None:
        text = str(col.server_default.arg)
        if "now" in text.lower() or "CURRENT_TIMESTAMP" in text.upper():
            return "当前时间"
        return text
    if col.default is not None:
        val = getattr(col.default, "arg", None)
        if callable(val):
            return "程序生成"
        if isinstance(val, bool):
            return "TRUE" if val else "FALSE"
        return str(val)
    return ""


def build():
    comments = _load_comments()
    tables = [c for c in models.Base.__subclasses__() if hasattr(c, "__tablename__")]
    order = []
    for cls in tables:
        order.append((cls.__tablename__, cls))

    lines = []
    lines.append("# ROS_MES 数据库表结构")
    lines.append("")
    lines.append("> 本文件由 `ros_mes_hou/tools/dump_schema_md.py` 从 `app/db/models.py` "
                 "**自动生成**，不要手工编辑。")
    lines.append("> 改字段时改 `models.py`（含字段上方注释），再在 `ros_mes_hou/` 下执行")
    lines.append("> `python tools/dump_schema_md.py --write` 重新生成；")
    lines.append("> `tests/test_db_schema_doc_in_sync.py` 会校验两者是否一致，不一致即测试失败。")
    lines.append("")
    lines.append("## 总览")
    lines.append("")
    lines.append("| # | 表 | 中文名 | 字段数 | 归属 |")
    lines.append("|---|---|---|---|---|")
    for i, (name, cls) in enumerate(order, start=1):
        n = len(cls.__table__.columns)
        owner = "ROS 归档（后端不消费）" if name in ROS_ARCHIVE else "MES 前后端"
        lines.append("| %d | `%s` | %s | %d | %s |"
                     % (i, name, TABLE_CN.get(name, "-"), n, owner))
    lines.append("")
    lines.append("合计 **%d** 张 ORM 表。另有 `can_event_log` 由 ROS 侧建表写入，"
                 "`models.py` 无 ORM 定义，不在上表内。" % len(order))
    lines.append("")
    lines.append("---")
    lines.append("")

    for name, cls in order:
        tbl = cls.__table__
        cn = TABLE_CN.get(name, "")
        lines.append("## `%s`%s" % (name, ("　" + cn) if cn else ""))
        lines.append("")
        note = TABLE_NOTE.get(name)
        if note:
            lines.append(note)
            lines.append("")
        if name in ROS_ARCHIVE:
            lines.append("> **归属**：" + ROS_ARCHIVE[name])
            lines.append("")
        lines.append("| 字段名 | 数据类型 | 允许为空 | 键 | 默认值 | 说明 |")
        lines.append("|---|---|---|---|---|---|")
        col_comments = comments.get(cls.__name__, {}).get("cols", {})
        for col in tbl.columns:
            keys = []
            if col.primary_key:
                keys.append("主键")
            if col.unique:
                keys.append("唯一")
            for fk in sorted(col.foreign_keys,
                             key=lambda f: (f.column.table.name, f.column.name)):
                keys.append("外键→`%s.%s`" % (fk.column.table.name, fk.column.name))
            desc = col_comments.get(col.name, "")
            lines.append("| `%s` | %s | %s | %s | %s | %s |" % (
                col.name,
                _render_type(col),
                "是" if col.nullable else "否",
                "，".join(keys),
                _default_of(col),
                desc.replace("|", "\\|"),
            ))
        cons = []
        # 约束/索引在 SQLAlchemy 里是 set，迭代顺序不稳定；显式排序保证文档可复现
        for c in sorted(tbl.constraints, key=lambda x: (type(x).__name__, x.name or "")):
            kind = type(c).__name__
            if kind == "PrimaryKeyConstraint":
                continue
            if kind == "ForeignKeyConstraint":
                cons.append("外键 `%s`：`(%s)` → `%s(%s)`" % (
                    c.name or "-",
                    ", ".join(c.column_keys),
                    c.referred_table.name,
                    ", ".join(el.column.name for el in c.elements)))
            elif kind == "UniqueConstraint":
                cons.append("唯一约束 `%s`：`(%s)`" % (c.name or "-", ", ".join(c.columns.keys())))
        for idx in sorted(tbl.indexes, key=lambda x: x.name or ""):
            cons.append("索引 `%s`：`(%s)`" % (idx.name, ", ".join(c.name for c in idx.columns)))
        cons.sort()
        if cons:
            lines.append("")
            for c in cons:
                lines.append("- " + c)
        lines.append("")

    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="写回 %s" % OUT_MD)
    args = ap.parse_args()
    text = build()
    if args.write:
        with io.open(OUT_MD, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print("已写入:", OUT_MD)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
