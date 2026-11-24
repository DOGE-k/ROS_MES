import io
import os
import sys
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(TESTS_DIR)
DOC = os.path.join(os.path.dirname(BACKEND), "docs", "ROS_MES_数据库表结构.md")

sys.path.insert(0, BACKEND)
sys.path.insert(0, os.path.join(BACKEND, "tools"))

import dump_schema_md  # noqa: E402


class DbSchemaDocInSyncTest(unittest.TestCase):
    """数据库表结构文档必须与 app/db/models.py 一致。

    改字段后忘了重新生成文档时，这里会失败。修复方式：
        cd mes_web/ros_mes_hou && python tools/dump_schema_md.py --write
    """

    def test_doc_file_exists(self):
        self.assertTrue(
            os.path.exists(DOC),
            "缺少数据库表结构文档：%s\n生成：python tools/dump_schema_md.py --write" % DOC,
        )

    def test_doc_matches_models(self):
        with io.open(DOC, encoding="utf-8") as f:
            on_disk = f.read().replace("\r\n", "\n")
        expected = dump_schema_md.build().replace("\r\n", "\n")
        if on_disk == expected:
            return

        on_disk_lines = on_disk.splitlines()
        expected_lines = expected.splitlines()
        diff = []
        for i in range(max(len(on_disk_lines), len(expected_lines))):
            a = on_disk_lines[i] if i < len(on_disk_lines) else "<缺行>"
            b = expected_lines[i] if i < len(expected_lines) else "<缺行>"
            if a != b:
                diff.append("第 %d 行\n  文档: %s\n  代码: %s" % (i + 1, a, b))
            if len(diff) >= 8:
                diff.append("……（仅显示前 8 处差异）")
                break
        self.fail(
            "数据库表结构文档与 models.py 不一致，请重新生成：\n"
            "    cd mes_web/ros_mes_hou && python tools/dump_schema_md.py --write\n\n"
            + "\n".join(diff)
        )

    def test_every_orm_table_is_documented(self):
        doc = dump_schema_md.build()
        for cls in dump_schema_md.models.Base.__subclasses__():
            name = getattr(cls, "__tablename__", None)
            if not name:
                continue
            self.assertIn("## `%s`" % name, doc, "表 %s 未出现在文档中" % name)


if __name__ == "__main__":
    unittest.main()
