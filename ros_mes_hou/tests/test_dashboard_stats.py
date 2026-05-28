import unittest

from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.api.endpoints.dashboard import get_dashboard_stats
from app.db import models
from app.db.database import Base


class DashboardStatsTest(unittest.TestCase):
    def test_dashboard_stats_uses_existing_device_unit_sensor_models(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        db = SessionLocal()
        try:
            db.add(
                models.User(
                    Username="tester",
                    Password="pwd",
                    Type_ID=2,
                    Creator_ID=1,
                    del_flag=False,
                )
            )
            db.add(
                models.Type(
                    Type_ID=1,
                    Typename="model",
                    creater_id=1,
                    del_flag=False,
                )
            )
            db.add(
                models.Module(
                    Module_ID=17,
                    Type_ID=1,
                    ModuleAddress="17",
                    Moduledescript="module",
                    creater_id=1,
                    del_flag=False,
                )
            )
            db.add(
                models.Unit(
                    id=7,
                    Unit_ID=32,
                    Module_ID=17,
                    UnitDescript="arm",
                    creater_id=1,
                    del_flag=False,
                )
            )
            db.add(
                models.Sensor(
                    id=8,
                    sensor_ID=49,
                    Module_ID=17,
                    Unit_ID=32,
                    sensordescript="pressure",
                    Unit_address=0,
                    IsRead=1,
                    creater_id=1,
                    del_flag=False,
                )
            )
            db.commit()

            response = get_dashboard_stats(db)

            self.assertEqual(response["code"], 200)
            self.assertEqual(response["data"]["deviceConnections"]["value"], 3)
            self.assertEqual(response["data"]["faultCount"]["value"], 0)
            self.assertEqual(response["data"]["onlineUsers"]["value"], 1)
            self.assertIn("deviceStatus", response["data"])
        finally:
            db.close()

    def test_dashboard_stats_supports_legacy_fine_tuning_adjusted_at_column(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE Users (
                    User_ID INTEGER PRIMARY KEY,
                    Username TEXT NOT NULL,
                    Password TEXT NOT NULL,
                    Type_ID INTEGER NOT NULL,
                    Creator_ID INTEGER NOT NULL,
                    del_flag BOOLEAN DEFAULT 0
                )
            """))
            conn.execute(text("""
                CREATE TABLE Type (
                    Type_ID INTEGER PRIMARY KEY,
                    Typename TEXT NOT NULL,
                    creater_id INTEGER NOT NULL,
                    del_flag BOOLEAN DEFAULT 0
                )
            """))
            conn.execute(text("""
                CREATE TABLE Module (
                    Module_ID INTEGER PRIMARY KEY,
                    Type_ID INTEGER NOT NULL,
                    ModuleAddress TEXT NOT NULL,
                    creater_id INTEGER NOT NULL,
                    del_flag BOOLEAN DEFAULT 0
                )
            """))
            conn.execute(text("""
                CREATE TABLE Unit (
                    id INTEGER PRIMARY KEY,
                    Unit_ID INTEGER NOT NULL,
                    Module_ID INTEGER NOT NULL,
                    creater_id INTEGER NOT NULL,
                    del_flag BOOLEAN DEFAULT 0
                )
            """))
            conn.execute(text("""
                CREATE TABLE sensors (
                    id INTEGER PRIMARY KEY,
                    sensor_ID INTEGER NOT NULL,
                    IsRead INTEGER NOT NULL,
                    Module_ID INTEGER NOT NULL,
                    Unit_ID INTEGER NOT NULL,
                    Unit_address INTEGER NOT NULL,
                    creater_id INTEGER NOT NULL,
                    del_flag BOOLEAN DEFAULT 0
                )
            """))
            conn.execute(text("""
                CREATE TABLE fine_tuning (
                    id INTEGER PRIMARY KEY,
                    Device_ID INTEGER NOT NULL,
                    parameter_name TEXT NOT NULL,
                    new_value REAL NOT NULL,
                    adjusted_at DATETIME NOT NULL
                )
            """))
            conn.execute(text("""
                INSERT INTO Users (User_ID, Username, Password, Type_ID, Creator_ID, del_flag)
                VALUES (1, 'admin', 'x', 1, 1, 0)
            """))

        db = SessionLocal()
        try:
            response = get_dashboard_stats(db)

            self.assertEqual(response["code"], 200)
            self.assertIn("taskCount", response["data"])
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
