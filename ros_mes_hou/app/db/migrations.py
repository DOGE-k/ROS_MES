from sqlalchemy import text
from sqlalchemy.engine import Engine


def _table_exists(conn, table_name: str) -> bool:
    return (
        conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
            {"name": table_name},
        ).fetchone()
        is not None
    )


def _columns(conn, table_name: str) -> set[str]:
    return {row[1] for row in conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()}


def migrate_fine_tuning_device_fields(engine: Engine) -> None:
    with engine.begin() as conn:
        if not _table_exists(conn, "fine_tuning"):
            return

        columns = _columns(conn, "fine_tuning")
        if "Device_ID" in columns and "hardware_id" not in columns:
            conn.execute(text("DROP TABLE IF EXISTS hardware"))
            return

        conn.execute(text("PRAGMA foreign_keys = OFF"))
        conn.execute(text("ALTER TABLE fine_tuning RENAME TO fine_tuning_old_device_migration"))
        conn.execute(
            text(
                """
                CREATE TABLE fine_tuning (
                    id INTEGER PRIMARY KEY,
                    Device_ID INTEGER NOT NULL,
                    DeviceAddress INTEGER,
                    Devicedescript TEXT,
                    parameter_name TEXT NOT NULL,
                    old_value REAL,
                    new_value REAL NOT NULL,
                    adjusted_by TEXT,
                    adjusted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (Device_ID) REFERENCES Device(Device_ID)
                )
                """
            )
        )

        source_device = "Device_ID" if "Device_ID" in columns else "hardware_id"
        conn.execute(
            text(
                f"""
                INSERT INTO fine_tuning (
                    id, Device_ID, DeviceAddress, Devicedescript, parameter_name,
                    old_value, new_value, adjusted_by, adjusted_at
                )
                SELECT
                    f.id,
                    COALESCE(f.{source_device}, 0),
                    d.DeviceAddress,
                    d.Devicedescript,
                    f.parameter_name,
                    f.old_value,
                    f.new_value,
                    f.adjusted_by,
                    f.adjusted_at
                FROM fine_tuning_old_device_migration AS f
                LEFT JOIN Device AS d ON d.Device_ID = f.{source_device}
                WHERE COALESCE(f.{source_device}, 0) != 0
                """
            )
        )
        conn.execute(text("DROP TABLE fine_tuning_old_device_migration"))
        conn.execute(text("DROP TABLE IF EXISTS hardware"))
        conn.execute(text("PRAGMA foreign_keys = ON"))
