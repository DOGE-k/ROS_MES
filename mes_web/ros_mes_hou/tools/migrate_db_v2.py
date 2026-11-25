#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把已有 SQLite 库中的 Calculation / Point_data 两张表原地升级到 V2.0 结构。

背景：
    V2.0 统一命名后，Calculation 与 Point_data 的主键从「Createtime」换成自增 ID，
    列名也随文档改名。SQLite 不支持给已有表追加自增主键，只能重建表再搬数据。
    `CREATE TABLE IF NOT EXISTS` 在旧库上不会补列，所以旧库必须走一次本脚本，
    否则 ROS 三节点启动自检会直接报「仍是旧结构」。

用法（在 mes_web/ros_mes_hou/ 下）：
    python tools/migrate_db_v2.py --db <库路径>            # 只打印计划，不写库
    python tools/migrate_db_v2.py --db <库路径> --apply    # 真正执行迁移

安全策略：
    1. 不删任何数据：旧表被改名为 <表名>__v1_<时间戳> 保留在原库中，需要时可回滚。
    2. 幂等：已经是 V2 结构的表直接跳过。
    3. 只动这两张表，其余 20 张表（Users / works / Module / Unit ...）不碰。
"""
import argparse
import datetime as _dt
import os
import sqlite3
import sys

# 目标结构：与 ros2 三节点建表语句、sqlite_create.py 保持同一条 DDL。
TARGETS = {
    "Calculation": {
        "pk": "calculation_id",
        "ddl": """
            CREATE TABLE IF NOT EXISTS Calculation (
                Calculation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                Create_time    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                Creator_id     INTEGER NOT NULL,
                Work_id        INTEGER NOT NULL,
                Module_id      INTEGER,
                Unit_id        INTEGER,
                Device_id      INTEGER,
                Is_read        INTEGER NOT NULL,
                Coordinates    TEXT,
                Axis_result    TEXT,
                Del_flag       BOOLEAN DEFAULT 0,
                Notes          TEXT
            )
        """,
        # 新列名 → 旧库里可能的列名（按顺序尝试，大小写不敏感）
        "map": {
            "Create_time": ("Createtime", "Create_time"),
            "Creator_id": ("creater_id", "Creator_id"),
            "Work_id": ("Work_ID", "Work_id"),
            "Module_id": ("Module_ID", "Module_id"),
            "Unit_id": ("Unit_ID", "Unit_id"),
            "Device_id": ("device_ID", "Device_id"),
            "Is_read": ("isread", "Is_read"),
            "Coordinates": ("coord", "Coordinates"),
            "Axis_result": ("position", "Axis_result"),
            "Del_flag": ("del_flag", "Del_flag"),
            "Notes": ("Notes",),
        },
    },
    "Point_data": {
        "pk": "point_data_id",
        "ddl": """
            CREATE TABLE IF NOT EXISTS Point_data (
                Point_data_id INTEGER PRIMARY KEY AUTOINCREMENT,
                Create_time   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                Creator_id    INTEGER NOT NULL,
                Module_id     INTEGER,
                Point         TEXT NOT NULL,
                Arms_address  TEXT NOT NULL,
                Del_flag      BOOLEAN DEFAULT 0,
                Notes         TEXT
            )
        """,
        "map": {
            "Create_time": ("Createtime", "Create_time"),
            "Creator_id": ("creater_id", "Creator_id"),
            "Module_id": ("Module_ID", "Module_id"),
            "Point": ("point", "Point"),
            "Arms_address": ("arms_address", "Arms_address"),
            "Del_flag": ("del_flag", "Del_flag"),
            "Notes": ("Notes",),
        },
    },
}


def _table_exists(cur, name):
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ? COLLATE NOCASE",
        (name,),
    )
    return cur.fetchone() is not None


def _columns(cur, name):
    cur.execute("PRAGMA table_info(%s)" % _quote(name))
    return {row[1].lower(): row[1] for row in cur.fetchall()}


def _quote(name):
    return '"%s"' % name.replace('"', '""')


def _plan_table(cur, name, spec):
    """返回 (状态, 明细)。状态取值：absent / aligned / migrate。"""
    if not _table_exists(cur, name):
        return "absent", "表不存在，跳过（新库由 sqlite_create.py 或后端 create_all 直接按 V2 建表）"

    cols = _columns(cur, name)
    if spec["pk"] in cols:
        return "aligned", "已是 V2 结构，跳过"

    src = {}
    for new_col, candidates in spec["map"].items():
        for cand in candidates:
            if cand.lower() in cols:
                src[new_col] = cols[cand.lower()]
                break
    missing = [c for c in spec["map"] if c not in src]
    cur.execute("SELECT COUNT(*) FROM %s" % _quote(name))
    rows = cur.fetchone()[0]
    detail = "旧结构，%d 行待搬迁；列映射 %s" % (rows, src)
    if missing:
        detail += "；旧库缺少列 %s（将留空/取默认值）" % missing
    return "migrate", detail


def _migrate_table(cur, name, spec, stamp):
    backup = "%s__v1_%s" % (name, stamp)
    cols = _columns(cur, name)

    src = {}
    for new_col, candidates in spec["map"].items():
        for cand in candidates:
            if cand.lower() in cols:
                src[new_col] = cols[cand.lower()]
                break

    cur.execute("ALTER TABLE %s RENAME TO %s" % (_quote(name), _quote(backup)))
    cur.execute(spec["ddl"])

    if src:
        target_cols = ", ".join(_quote(k) for k in src)
        source_cols = ", ".join(_quote(v) for v in src.values())
        cur.execute(
            "INSERT INTO %s (%s) SELECT %s FROM %s"
            % (_quote(name), target_cols, source_cols, _quote(backup))
        )
    cur.execute("SELECT COUNT(*) FROM %s" % _quote(name))
    copied = cur.fetchone()[0]
    return backup, copied


def main(argv=None):
    ap = argparse.ArgumentParser(description="把 Calculation / Point_data 迁移到 V2.0 结构")
    ap.add_argument("--db", required=True, help="SQLite 库文件路径")
    ap.add_argument("--apply", action="store_true", help="真正执行迁移（缺省只打印计划）")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.db):
        print("库文件不存在：%s" % args.db)
        return 2

    conn = sqlite3.connect(args.db)
    cur = conn.cursor()
    stamp = _dt.datetime.now().strftime("%Y%m%d%H%M%S")

    plans = []
    for name, spec in TARGETS.items():
        status, detail = _plan_table(cur, name, spec)
        plans.append((name, spec, status, detail))
        print("[%s] %s → %s" % (status, name, detail))

    if not args.apply:
        print("\n以上为计划，未写库。确认无误后加 --apply 执行。")
        return 0

    print("")
    for name, spec, status, _detail in plans:
        if status != "migrate":
            continue
        backup, copied = _migrate_table(cur, name, spec, stamp)
        print("[done] %s → 已迁移 %d 行；旧表保留为 %s" % (name, copied, backup))

    conn.commit()

    print("\n迁移后结构：")
    for name, spec in TARGETS.items():
        if not _table_exists(cur, name):
            print("  %s：不存在" % name)
            continue
        cols = _columns(cur, name)
        cur.execute("SELECT COUNT(*) FROM %s" % _quote(name))
        rows = cur.fetchone()[0]
        missing = [c for c in list(spec["map"]) + [spec["pk"]] if c.lower() not in cols]
        state = "OK" if not missing else "缺列 %s" % missing
        print("  %s：%d 列 / %d 行 / %s" % (name, len(cols), rows, state))

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
