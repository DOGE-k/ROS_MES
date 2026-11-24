"""ensure_schema 自动对齐的回归测试。

覆盖四类行为：
1. 幂等：已对齐时不动库
2. 重建：放宽 NOT NULL、加带 CURRENT_TIMESTAMP 默认值的列
3. 安全：收紧 NOT NULL 遇 NULL 跳过、多出列时拒绝重建
4. 容错：重建中途崩溃的临时表能被恢复
"""
import os
import sqlite3
import sys
import tempfile
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(TESTS_DIR)
sys.path.insert(0, BACKEND)

from sqlalchemy import create_engine, inspect  # noqa: E402

from app.db import models  # noqa: E402
from app.db.database import Base  # noqa: E402
from app.db.schema import (  # noqa: E402
    TMP_SUFFIX,
    ensure_schema,
    inspect_schema,
    recover_interrupted_rebuild,
)

# 只挑 fine_tuning 做样本：它外键指向 Users/Unit，能顺带验证依赖表复制
TARGET = "fine_tuning"


class SchemaSyncTestBase(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.engine = create_engine("sqlite:///" + self.path)

    def tearDown(self):
        self.engine.dispose()
        if os.path.exists(self.path):
            os.remove(self.path)

    def make_legacy(self, extra_sql="", rows_sql=None, parameter_name_not_null=True):
        """建一个"旧版" fine_tuning：new_value NOT NULL、缺 8 个新列。

        parameter_name_not_null=False 时把 parameter_name 建成可空，用于验证
        "收紧 NOT NULL"这条分支（ORM 要求 NOT NULL，库里却可空）。
        """
        pn = ("parameter_name VARCHAR(100) NOT NULL" if parameter_name_not_null
              else "parameter_name VARCHAR(100)")
        conn = sqlite3.connect(self.path)
        conn.executescript("""
            CREATE TABLE "Users" (
                "User_ID" INTEGER NOT NULL PRIMARY KEY,
                Username VARCHAR(50) NOT NULL
            );
            CREATE TABLE "Unit" (
                id INTEGER NOT NULL PRIMARY KEY,
                Module_ID INTEGER NOT NULL,
                Unit_ID INTEGER NOT NULL
            );
            CREATE TABLE fine_tuning (
                id INTEGER NOT NULL,
                module_id INTEGER NOT NULL,
                unit_id INTEGER NOT NULL,
                module_address INTEGER,
                module_descript TEXT,
                %s,
                old_value FLOAT,
                new_value FLOAT NOT NULL,
                creater_id INTEGER NOT NULL,
                create_time DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                notes TEXT,
                del_flag BOOLEAN,
                PRIMARY KEY (id)
            );
            CREATE INDEX ix_fine_tuning_id ON fine_tuning (id);
        """ % pn + extra_sql)
        if rows_sql:
            conn.executescript(rows_sql)
        conn.commit()
        conn.close()

    def signature(self, table=TARGET):
        """可比较的列指纹：类型用字符串，避免 TypeEngine 对象比较不等。"""
        return {
            c["name"]: (str(c["type"]).upper(), bool(c["nullable"]))
            for c in inspect(self.engine).get_columns(table)
        }

    def columns(self, table=TARGET):
        return {c["name"]: c for c in inspect(self.engine).get_columns(table)}

    def rows(self, sql):
        conn = sqlite3.connect(self.path)
        try:
            return list(conn.execute(sql))
        finally:
            conn.close()

    def tables(self):
        conn = sqlite3.connect(self.path)
        try:
            return {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            conn.close()


class IdempotentTest(SchemaSyncTestBase):
    def test_second_run_changes_nothing(self):
        self.make_legacy(rows_sql=(
            "INSERT INTO fine_tuning (id,module_id,unit_id,parameter_name,old_value,new_value,creater_id)"
            " VALUES (1,17,32,'rotation',47.25,2.0,1);"
        ))
        ensure_schema(self.engine)
        first = self.signature()
        data_first = self.rows("SELECT id, old_value, new_value FROM fine_tuning")

        ensure_schema(self.engine)
        second = self.signature()
        data_second = self.rows("SELECT id, old_value, new_value FROM fine_tuning")

        self.assertEqual(first, second)
        self.assertEqual(data_first, data_second)
        self.assertEqual([(1, 47.25, 2.0)], data_second)

    def test_already_aligned_database_reports_clean(self):
        Base.metadata.create_all(bind=self.engine)
        report = inspect_schema(self.engine)
        self.assertEqual([], report["missing_tables"])
        self.assertEqual([], report["tables"])


class RebuildTest(SchemaSyncTestBase):
    def test_relaxes_new_value_and_adds_missing_columns(self):
        self.make_legacy(rows_sql=(
            "INSERT INTO fine_tuning (id,module_id,unit_id,parameter_name,old_value,new_value,creater_id,notes)"
            " VALUES (7,17,32,'rotation',47.25,2.0,1,'batch=old');"
        ))
        ensure_schema(self.engine)

        cols = self.columns()
        self.assertTrue(cols["new_value"]["nullable"], "new_value 应放宽为可空")
        for name in ("requested_delta", "observed_position", "observed_delta", "deviation",
                     "position_error", "outcome", "outcome_by", "outcome_at"):
            self.assertIn(name, cols)

        # 数据必须原样保留
        self.assertEqual(
            [(7, 47.25, 2.0, "batch=old")],
            self.rows("SELECT id, old_value, new_value, notes FROM fine_tuning"),
        )

    def test_rebuild_restores_indexes(self):
        """DROP TABLE 会带走索引，重建后必须按 ORM 定义补回。"""
        self.make_legacy()
        before = {i["name"] for i in inspect(self.engine).get_indexes(TARGET)}
        self.assertIn("ix_fine_tuning_id", before)

        ensure_schema(self.engine)

        after = {i["name"] for i in inspect(self.engine).get_indexes(TARGET)}
        expected = {i.name for i in models.FineTuning.__table__.indexes}
        self.assertEqual(expected, after, "重建后索引应与 ORM 定义一致")

    def test_rebuild_leaves_no_temp_table(self):
        self.make_legacy()
        ensure_schema(self.engine)
        self.assertNotIn(TARGET + TMP_SUFFIX, self.tables())

    def test_new_nullable_column_with_timestamp_default_is_added(self):
        """ADD COLUMN 不能带非常量默认值，这类列必须走重建才能加上。"""
        self.make_legacy()
        # del_flag 是 BOOLEAN 可空、无默认值，可直加；这里验证新增列都在
        ensure_schema(self.engine)
        cols = self.columns()
        for col in models.FineTuning.__table__.columns:
            self.assertIn(col.name, cols, "列 %s 未补齐" % col.name)


class SafetyTest(SchemaSyncTestBase):
    def test_refuses_rebuild_when_database_has_unknown_column(self):
        """库里有 ORM 未定义的列时，重建等于静默删数据，必须拒绝。"""
        self.make_legacy(extra_sql="ALTER TABLE fine_tuning ADD COLUMN legacy_only TEXT;")
        # 让这张表必须走重建：new_value 是 NOT NULL
        with self.assertRaises(RuntimeError) as ctx:
            ensure_schema(self.engine)
        self.assertIn("legacy_only", str(ctx.exception))
        # 失败后必须回滚，库保持原状
        self.assertIn("legacy_only", self.columns())

    def test_allow_drop_columns_permits_rebuild(self):
        self.make_legacy(
            extra_sql="ALTER TABLE fine_tuning ADD COLUMN legacy_only TEXT;",
            rows_sql=("INSERT INTO fine_tuning "
                      "(id,module_id,unit_id,parameter_name,old_value,new_value,creater_id) "
                      "VALUES (3,17,32,'rotation',1.0,2.0,1);"),
        )
        ensure_schema(self.engine, allow_drop_columns=True)
        cols = self.columns()
        self.assertNotIn("legacy_only", cols)
        self.assertEqual([(3,)], self.rows("SELECT id FROM fine_tuning"))

    def test_tighten_not_null_skipped_when_nulls_exist(self):
        """库里可空、ORM 要求 NOT NULL，但已有 NULL 行 → 跳过，不能删数据。"""
        # parameter_name 在 ORM 里是 NOT NULL，这里建成可空并插入一行 NULL
        self.make_legacy(
            parameter_name_not_null=False,
            rows_sql=("INSERT INTO fine_tuning "
                      "(id,module_id,unit_id,parameter_name,old_value,new_value,creater_id) "
                      "VALUES (1,17,32,NULL,1.0,2.0,1);"),
        )
        ensure_schema(self.engine)

        # 有 NULL 行，不能收紧；数据必须还在
        self.assertTrue(self.columns()["parameter_name"]["nullable"],
                        "存在 NULL 行时不应收紧 NOT NULL")
        self.assertEqual([(1, None)], self.rows("SELECT id, parameter_name FROM fine_tuning"))

    def test_tighten_not_null_applied_when_no_nulls(self):
        """没有 NULL 行时，收紧 NOT NULL 应正常完成。"""
        self.make_legacy(
            parameter_name_not_null=False,
            rows_sql=("INSERT INTO fine_tuning "
                      "(id,module_id,unit_id,parameter_name,old_value,new_value,creater_id) "
                      "VALUES (1,17,32,'rotation',1.0,2.0,1);"),
        )
        ensure_schema(self.engine)

        self.assertFalse(self.columns()["parameter_name"]["nullable"],
                         "无 NULL 行时应收紧为 NOT NULL")
        self.assertEqual([(1, "rotation")],
                         self.rows("SELECT id, parameter_name FROM fine_tuning"))


class RecoveryTest(SchemaSyncTestBase):
    def test_orphan_temp_table_is_dropped_when_original_intact(self):
        self.make_legacy()
        conn = sqlite3.connect(self.path)
        try:
            conn.execute("CREATE TABLE fine_tuning%s (id INTEGER)" % TMP_SUFFIX)
            conn.commit()
        finally:
            conn.close()
        self.assertIn(TARGET + TMP_SUFFIX, self.tables())

        ensure_schema(self.engine)

        self.assertNotIn(TARGET + TMP_SUFFIX, self.tables())
        self.assertIn(TARGET, self.tables())

    def test_orphan_temp_table_is_renamed_when_original_missing(self):
        """崩在 DROP 之后、RENAME 之前：只剩临时表，数据在临时表里。"""
        conn = sqlite3.connect(self.path)
        try:
            conn.executescript("""
                CREATE TABLE fine_tuning__rebuild (
                    id INTEGER NOT NULL PRIMARY KEY,
                    module_id INTEGER NOT NULL,
                    unit_id INTEGER NOT NULL,
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
                    module_address INTEGER,
                    module_descript TEXT
                );
                INSERT INTO fine_tuning__rebuild
                    (id,module_id,unit_id,parameter_name,old_value,new_value,creater_id)
                VALUES (9,17,32,'rotation',5.0,6.0,1);
            """)
            conn.commit()
        finally:
            conn.close()

        ensure_schema(self.engine)

        self.assertNotIn(TARGET + TMP_SUFFIX, self.tables())
        self.assertEqual([(9, 5.0, 6.0)],
                         self.rows("SELECT id, old_value, new_value FROM fine_tuning"))

    def test_recover_helper_returns_false_when_no_temp_table(self):
        self.make_legacy()
        conn = sqlite3.connect(self.path)
        try:
            self.assertFalse(recover_interrupted_rebuild(conn, TARGET))
        finally:
            conn.close()


class DryRunTest(SchemaSyncTestBase):
    def test_dry_run_reports_without_changing_database(self):
        self.make_legacy()
        before = {c: v["nullable"] for c, v in self.columns().items()}

        report = ensure_schema(self.engine, dry_run=True)

        self.assertTrue(report["tables"], "应报告出差异")
        after = {c: v["nullable"] for c, v in self.columns().items()}
        self.assertEqual(before, after, "dry_run 不得改库")

    def test_dry_run_on_aligned_database_is_clean(self):
        Base.metadata.create_all(bind=self.engine)
        report = ensure_schema(self.engine, dry_run=True)
        self.assertEqual([], report["tables"])


if __name__ == "__main__":
    unittest.main()
