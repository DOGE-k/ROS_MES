# app/db/schema.py
"""把已存在的库对齐到 models.py 的定义（SQLite 轻量迁移）。

为什么需要：
    create_all() 只建缺失的表，不会修改已存在表的列。SQLite 又没有
    ALTER TABLE ... ALTER COLUMN，改可空性、加 NOT NULL 列、加带
    CURRENT_TIMESTAMP 默认值的列都只能重建整张表。

设计原则：
    1. models.py 是唯一真相源。这里不维护任何手抄的列清单/DDL 副本，
       所有目标结构都从 ORM 现算。改 models.py 后重启即自动对齐。
    2. 只做安全动作。放宽 NOT NULL 可以；收紧 NOT NULL 前先查有没有 NULL，
       有就跳过；库里有 ORM 未定义的列时绝不重建（否则等于静默删数据）。
    3. 重建走显式 BEGIN，失败整体 ROLLBACK。pysqlite 在默认隔离级别下
       会把 DDL 隐式提交，engine.begin() 挡不住，必须用原生连接。
    4. 幂等：已对齐时一条 SQL 都不执行。

不负责：跨库类型转换、外键/唯一约束的逐项比对（重建时会顺带按 ORM 重写）、
        数据搬迁。这些超出"启动自愈"的边界，用 Alembic 或人工处理。
"""

import logging

from sqlalchemy import MetaData, inspect
from sqlalchemy.schema import CreateIndex, CreateTable

from app.db import models  # noqa: F401  确保所有表已注册到 Base.metadata
from app.db.database import Base, engine

logger = logging.getLogger(__name__)

# 重建时用的临时表后缀。崩溃残留靠 recover_interrupted_rebuild() 收拾。
TMP_SUFFIX = "__rebuild"

# SQLite 里 ADD COLUMN 不能带非常量默认值，这类列必须走重建
_NON_CONSTANT_DEFAULT_MARKERS = ("CURRENT_TIMESTAMP", "CURRENT_DATE", "CURRENT_TIME", "(")


def _affinity(type_text):
    """把类型字符串归一化成 SQLite 存储类，避免 INTEGER/INT 之类的写法差异误报。"""
    t = str(type_text).upper().strip()
    if t.startswith(("VARCHAR", "NVARCHAR", "CHAR", "CLOB", "TEXT", "STRING")):
        return "TEXT"
    if t.startswith(("INTEGER", "INT", "BIGINT", "SMALLINT", "TINYINT")):
        return "INTEGER"
    if t.startswith(("FLOAT", "REAL", "DOUBLE", "NUMERIC", "DECIMAL")):
        return "FLOAT"
    if t.startswith(("BOOLEAN", "BOOL")):
        return "BOOLEAN"
    if t.startswith(("DATETIME", "TIMESTAMP", "DATE", "TIME")):
        return "DATETIME"
    return t


def _compiled_type(col, dialect):
    try:
        return col.type.compile(dialect=dialect)
    except Exception:
        return type(col.type).__name__.upper()


def _server_default_sql(col, dialect):
    """返回该列的 server_default SQL 文本；没有则 None。"""
    if col.server_default is None:
        return None
    arg = col.server_default.arg
    if isinstance(arg, str):
        return arg
    try:
        return str(arg.compile(dialect=dialect))
    except Exception:
        return str(arg)


def _is_non_constant(default_sql):
    if default_sql is None:
        return False
    up = default_sql.upper()
    return any(m in up for m in _NON_CONSTANT_DEFAULT_MARKERS)


def _column_fragment(col, dialect):
    """拼出 ADD COLUMN 用的列定义片段。"""
    parts = [col.name, _compiled_type(col, dialect)]
    if not col.nullable:
        parts.append("NOT NULL")
    default_sql = _server_default_sql(col, dialect)
    if default_sql is not None:
        parts.append("DEFAULT " + default_sql)
    return " ".join(parts)


def _can_add_directly(col, dialect):
    """判断该列能否用 ALTER TABLE ADD COLUMN 加，不必重建整表。"""
    default_sql = _server_default_sql(col, dialect)
    if _is_non_constant(default_sql):
        # SQLite: Cannot add a column with non-constant default
        return False
    if not col.nullable and default_sql is None:
        # SQLite: Cannot add a NOT NULL column with default value NULL
        return False
    if col.unique:
        # SQLite: Cannot add a UNIQUE column
        return False
    return True


def _plan(table, inspector):
    """对比 ORM 表定义与库里实际结构，产出一张表的对齐计划。"""
    name = table.name
    dialect = inspector.bind.dialect if hasattr(inspector, "bind") else None
    db_columns = {c["name"]: c for c in inspector.get_columns(name)}
    orm_columns = {c.name: c for c in table.columns}

    missing = [orm_columns[c] for c in orm_columns if c not in db_columns]
    extra = [c for c in db_columns if c not in orm_columns]

    # 可空性差异：只统计 ORM 有定义的列
    relax = []   # 库里 NOT NULL，ORM 允许空 → 放宽（安全）
    tighten = []  # 库里可空，ORM 要求 NOT NULL → 收紧（先查 NULL）
    type_diff = []
    default_diff = []
    for col_name, orm_col in orm_columns.items():
        db_col = db_columns.get(col_name)
        if db_col is None:
            continue
        if orm_col.primary_key:
            continue  # SQLite 对主键列的 nullable 报告不可靠，跳过
        db_not_null = not db_col["nullable"]
        if db_not_null and orm_col.nullable:
            relax.append(col_name)
        elif (not db_not_null) and (not orm_col.nullable):
            tighten.append(col_name)
        if dialect is not None and _affinity(_compiled_type(orm_col, dialect)) != _affinity(db_col["type"]):
            type_diff.append((col_name, _compiled_type(orm_col, dialect), db_col["type"]))

    # 判断是否需要重建
    rebuild_reasons = []
    for col in missing:
        if not _can_add_directly(col, dialect):
            rebuild_reasons.append(
                "新增列 %s 无法直接 ADD COLUMN（%s）"
                % (col.name, _column_fragment(col, dialect))
            )
    if relax:
        rebuild_reasons.append("放宽 NOT NULL：%s" % ", ".join(relax))
    if tighten:
        rebuild_reasons.append("收紧 NOT NULL：%s" % ", ".join(tighten))

    return {
        "table": table,
        "missing": missing,
        "extra": extra,
        "relax": relax,
        "tighten": tighten,
        "type_diff": type_diff,
        "default_diff": default_diff,
        "rebuild_reasons": rebuild_reasons,
        "db_columns": db_columns,
        "orm_columns": orm_columns,
    }


def _create_table_sql(table, new_name, dialect):
    """用 ORM 定义生成建表 DDL，表名换成 new_name。

    外键引用的表也要复制进临时 MetaData，否则 SQLAlchemy 解析不到目标表。
    """
    md = MetaData()
    pending, copied = [table], set()
    while pending:
        current = pending.pop()
        if current.name in copied:
            continue
        copied.add(current.name)
        target_name = new_name if current is table else current.name
        current.to_metadata(md, name=target_name)
        for fk in current.foreign_key_constraints:
            for element in fk.elements:
                ref = element.column.table
                if ref.name not in copied:
                    pending.append(ref)
    return str(CreateTable(md.tables[new_name]).compile(dialect=dialect))


def _rebuild(conn, plan, dialect, allow_drop_columns=False):
    """重建一张表：建临时表 → 拷交集列 → 删原表 → 改名 → 重建索引。

    conn 必须是已显式 BEGIN 的原生连接，失败由调用方 ROLLBACK。
    """
    table = plan["table"]
    name = table.name
    tmp = name + TMP_SUFFIX
    shared = [c for c in plan["db_columns"] if c in plan["orm_columns"]]

    if plan["extra"] and not allow_drop_columns:
        raise RuntimeError(
            "表 %s 存在 ORM 未定义的列 %s，重建会丢数据；"
            "确认可丢弃后传 allow_drop_columns=True" % (name, plan["extra"])
        )

    conn.execute("DROP TABLE IF EXISTS %s" % tmp)
    conn.execute(_create_table_sql(table, tmp, dialect))
    if shared:
        cols = ", ".join(shared)
        conn.execute("INSERT INTO %s (%s) SELECT %s FROM %s" % (tmp, cols, cols, name))
    else:
        logger.warning("表 %s 与原表无同名列，重建后数据为空", name)
    conn.execute("DROP TABLE %s" % name)
    conn.execute("ALTER TABLE %s RENAME TO %s" % (tmp, name))
    # DROP TABLE 会带走索引，按 ORM 定义补回
    for idx in sorted(table.indexes, key=lambda i: i.name or ""):
        conn.execute(str(CreateIndex(idx).compile(dialect=dialect)))
    logger.info(
        "表 %s 已重建（%s），保留 %d 列",
        name, "；".join(plan["rebuild_reasons"]), len(shared),
    )


def recover_interrupted_rebuild(conn, table_name):
    """收拾上次重建中途崩溃留下的临时表。

    正常情况下重建在事务里，不会留残骸；这里只处理极端情况（进程被 kill）。
    若原表已不在、只剩临时表，说明崩在 DROP 之后 RENAME 之前，补完改名。
    """
    tmp = table_name + TMP_SUFFIX
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN (?, ?)",
        (table_name, tmp),
    ).fetchall()
    present = {r[0] for r in rows}
    if tmp not in present:
        return False
    if table_name in present:
        conn.execute("DROP TABLE %s" % tmp)
        logger.warning("清理重建残留临时表 %s（原表完好）", tmp)
    else:
        conn.execute("ALTER TABLE %s RENAME TO %s" % (tmp, table_name))
        logger.warning("从残留临时表 %s 恢复表 %s", tmp, table_name)
    return True


def _all_tables():
    """按表名排序返回所有 ORM 表。

    不用 Base.metadata.sorted_tables：它会按外键依赖做拓扑排序，而 Drawings 与
    DrawingsVersion 互相引用，SQLAlchemy 会刷 "unresolvable cycles" 警告。
    这里只逐表对比/对齐已有表，不需要依赖顺序。
    """
    return [Base.metadata.tables[n] for n in sorted(Base.metadata.tables)]


def inspect_schema(bind=None):
    """只对比不改动，返回差异清单。给 check_schema_drift 和测试用。"""
    bind = engine if bind is None else bind
    inspector = inspect(bind)
    existing = set(inspector.get_table_names())
    report = {"missing_tables": [], "tables": []}
    for table in _all_tables():
        if table.name not in existing:
            report["missing_tables"].append(table.name)
            continue
        plan = _plan(table, inspector)
        if (plan["missing"] or plan["extra"] or plan["relax"] or plan["tighten"]
                or plan["type_diff"] or plan["rebuild_reasons"]):
            report["tables"].append(plan)
    return report


def format_report(report):
    """把 inspect_schema 的结果渲染成人读文本。"""
    lines = []
    if report["missing_tables"]:
        lines.append("缺失的表（create_all 会自动创建）：")
        for n in report["missing_tables"]:
            lines.append("  - %s" % n)
    if not report["tables"]:
        lines.append("所有已存在的表结构已与 models.py 一致。")
        return "\n".join(lines)
    for plan in report["tables"]:
        name = plan["table"].name
        lines.append("表 %s：" % name)
        for col in plan["missing"]:
            lines.append("  + 缺列 %s" % col.name)
        for col in plan["extra"]:
            lines.append("  - 库中多出列 %s（不自动删除）" % col)
        for col in plan["relax"]:
            lines.append("  ~ 放宽 NOT NULL %s" % col)
        for col in plan["tighten"]:
            lines.append("  ! 收紧 NOT NULL %s（有 NULL 时跳过）" % col)
        for col, orm_t, db_t in plan["type_diff"]:
            lines.append("  ! 类型差异 %s：ORM=%s 库=%s（SQLite 动态类型，不处理）"
                         % (col, orm_t, db_t))
        if plan["rebuild_reasons"]:
            lines.append("  → 需要重建表")
        else:
            lines.append("  → 仅需 ALTER TABLE ADD COLUMN")
    return "\n".join(lines)


def ensure_schema(bind=None, dry_run=False, allow_drop_columns=False):
    """把已存在的表对齐到 models.py。幂等，可重复调用。

    dry_run=True 时只返回报告不改库。
    allow_drop_columns=True 才允许为对齐结构而丢弃库中多出的列。
    """
    bind = engine if bind is None else bind

    if dry_run:
        return inspect_schema(bind)

    inspector = inspect(bind)
    existing = set(inspector.get_table_names())
    plans = []
    for table in _all_tables():
        if table.name not in existing:
            continue  # 缺失的表交给 create_all
        plans.append(_plan(table, inspector))

    is_sqlite = bind.dialect.name == "sqlite"
    dialect = bind.dialect

    # 索引名要在进入事务前采集：事务中另开连接 inspect 会撞 SQLite 写锁
    index_names = {}
    for plan in plans:
        try:
            index_names[plan["table"].name] = {
                i["name"] for i in inspector.get_indexes(plan["table"].name)
            }
        except Exception:
            index_names[plan["table"].name] = set()

    if not is_sqlite:
        # 非 SQLite 走普通事务；DDL 可回滚由后端保证
        with bind.begin() as conn:
            for plan in plans:
                _apply(conn, plan, dialect, bind, allow_drop_columns, raw=False,
                       index_names=index_names[plan["table"].name])
        return inspect_schema(bind)

    raw = bind.raw_connection()
    try:
        dbapi = raw.driver_connection
        # pysqlite 默认会把 DDL 隐式提交，必须自己控制事务
        dbapi.isolation_level = None
        dbapi.execute("BEGIN")
        try:
            for table in _all_tables():
                recover_interrupted_rebuild(dbapi, table.name)
            for plan in plans:
                _apply(dbapi, plan, dialect, bind, allow_drop_columns, raw=True,
                       index_names=index_names[plan["table"].name])
            dbapi.execute("COMMIT")
        except Exception:
            dbapi.execute("ROLLBACK")
            logger.exception("数据库结构对齐失败，已回滚，库保持原状")
            raise
    finally:
        raw.close()

    return inspect_schema(bind)


def _apply(conn, plan, dialect, bind, allow_drop_columns, raw, index_names):
    """执行单张表的对齐动作。conn 是原生连接(raw=True)或 SQLAlchemy 连接。

    index_names 是调用前采集的现有索引名集合——事务进行中不能再另开连接去
    inspect，否则会撞上 SQLite 写锁。
    """
    table = plan["table"]
    name = table.name

    def run(sql):
        if raw:
            conn.execute(sql)
        else:
            from sqlalchemy import text
            conn.execute(text(sql))

    def has_null(column_name):
        sql = 'SELECT 1 FROM "%s" WHERE "%s" IS NULL LIMIT 1' % (name, column_name)
        if raw:
            return conn.execute(sql).fetchone() is not None
        from sqlalchemy import text
        return conn.execute(text(sql)).first() is not None

    if plan["rebuild_reasons"]:
        # 重建会把目标结构按 ORM 重写。ORM 要求 NOT NULL 的列若在旧数据里存在
        # NULL，INSERT 到新表会触发约束错误（且整批回滚）。先探一遍，有就跳过。
        # 新加的列不在旧表里，不参与检查。
        at_risk = [
            col.name for col in table.columns
            if not col.nullable and not col.primary_key and col.name in plan["db_columns"]
        ]
        nulls = [c for c in at_risk if has_null(c)]
        if nulls:
            logger.warning(
                "表 %s 的列 %s 在现有数据中存在 NULL，但 models.py 要求 NOT NULL；"
                "重建会失败，跳过该表的结构对齐。请先清理这些 NULL 或放宽 ORM 定义",
                name, nulls,
            )
            return
        _rebuild(conn, plan, dialect, allow_drop_columns)
        return

    for col in plan["missing"]:
        run("ALTER TABLE %s ADD COLUMN %s" % (name, _column_fragment(col, dialect)))
        logger.info("表 %s 补充列 %s", name, col.name)

    # 索引补齐（重建路径已在 _rebuild 里处理）
    for idx in sorted(table.indexes, key=lambda i: i.name or ""):
        if idx.name in index_names:
            continue
        run(str(CreateIndex(idx).compile(dialect=dialect)))
        logger.info("表 %s 补充索引 %s", name, idx.name)
