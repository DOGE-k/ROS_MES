# app/db/schema.py
"""轻量表结构兼容：create_all 只建缺失的表，不会修改已存在表的列。

历史库的 fine_tuning 把 new_value 建成 NOT NULL，但按新语义它保存"应到值"，
缺少初始值时必须为空，SQLite 不支持改列的 NOT NULL 约束，只能重建表。
"""

import logging

from sqlalchemy import inspect, text

from app.db.database import engine

logger = logging.getLogger(__name__)

# 新语义下 fine_tuning 期望存在、但历史库可能缺失的列：列名 -> 列定义
FINE_TUNING_ADDED_COLUMNS = {
    "requested_delta": "FLOAT",
    "observed_position": "FLOAT",
    "observed_delta": "FLOAT",
    "deviation": "FLOAT",
    "position_error": "FLOAT",
    "outcome": "VARCHAR(20)",
    "outcome_by": "INTEGER",
    "outcome_at": "DATETIME",
}

# 重建表时使用：与 models.FineTuning 当前定义保持一致
_FINE_TUNING_REBUILD_DDL = """
CREATE TABLE fine_tuning__new (
    id INTEGER NOT NULL,
    module_id INTEGER NOT NULL,
    unit_id INTEGER NOT NULL,
    module_address INTEGER,
    module_descript TEXT,
    parameter_name VARCHAR(100) NOT NULL,
    old_value FLOAT,
    new_value FLOAT,
    requested_delta FLOAT,
    observed_position FLOAT,
    observed_delta FLOAT,
    deviation FLOAT,
    position_error FLOAT,
    outcome VARCHAR(20),
    outcome_by INTEGER,
    outcome_at DATETIME,
    creater_id INTEGER NOT NULL,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    notes TEXT,
    del_flag BOOLEAN,
    PRIMARY KEY (id),
    CONSTRAINT fk_fine_tuning_unit FOREIGN KEY (module_id, unit_id)
        REFERENCES "Unit" (Module_ID, Unit_ID),
    FOREIGN KEY(outcome_by) REFERENCES Users (User_ID),
    FOREIGN KEY(creater_id) REFERENCES Users (User_ID)
)
"""


def ensure_schema(bind=None):
    """补齐 fine_tuning 的新列；必要时按新定义重建该表。

    幂等：可重复调用，已符合新结构时不执行任何语句。
    """
    bind = engine if bind is None else bind
    inspector = inspect(bind)
    if "fine_tuning" not in inspector.get_table_names():
        return
    columns = {column["name"]: column for column in inspector.get_columns("fine_tuning")}
    with bind.begin() as connection:
        if columns.get("new_value", {}).get("nullable") is False:
            _rebuild_fine_tuning(connection, columns)
            columns = {column["name"]: column for column in inspect(connection).get_columns("fine_tuning")}
        for name, ddl in FINE_TUNING_ADDED_COLUMNS.items():
            if name in columns:
                continue
            connection.execute(text(f"ALTER TABLE fine_tuning ADD COLUMN {name} {ddl}"))
            logger.info("fine_tuning 补充列 %s", name)


def _rebuild_fine_tuning(connection, columns):
    """把 fine_tuning 重建成新定义，保留原有行。

    只拷贝两边都存在的列；新增列在历史行上保持 NULL。
    """
    connection.execute(text("DROP TABLE IF EXISTS fine_tuning__new"))
    connection.execute(text(_FINE_TUNING_REBUILD_DDL))
    kept = [name for name in columns if name != "id"]
    target_columns = ", ".join(["id"] + kept)
    connection.execute(text(
        f"INSERT INTO fine_tuning__new ({target_columns}) SELECT {target_columns} FROM fine_tuning"
    ))
    connection.execute(text("DROP TABLE fine_tuning"))
    connection.execute(text("ALTER TABLE fine_tuning__new RENAME TO fine_tuning"))
    logger.info("fine_tuning 已按新定义重建，保留 %d 列", len(kept) + 1)
