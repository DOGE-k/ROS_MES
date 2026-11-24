"""对比库与 models.py 的差异。

    python tools/check_schema_drift.py            # 只看差异，不改库
    python tools/check_schema_drift.py --quiet    # 无差异时静默（可用于 CI）

真正的对齐由后端启动时的 ensure_schema() 完成；本命令只读，用来在重启前
确认这次改动会影响哪些表。
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from app.db.database import engine  # noqa: E402
from app.db.schema import format_report, inspect_schema  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="对比数据库实际结构与 models.py 定义")
    ap.add_argument("--quiet", action="store_true", help="无差异时不输出，有差异返回码 1")
    args = ap.parse_args()

    report = inspect_schema(engine)
    clean = not report["missing_tables"] and not report["tables"]

    if clean and args.quiet:
        return 0

    print(format_report(report))
    print()
    if clean:
        print("结论：库已与 models.py 对齐，启动时不会改动任何结构。")
    else:
        print("结论：下次后端启动时 ensure_schema() 会按上表自动对齐。")
        print("     本命令只读；不启动后端就不会改动数据库。")
    return 0 if clean else 1


if __name__ == "__main__":
    sys.exit(main())
