import unittest

from sqlalchemy import create_engine
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
                models.ModelTooling(
                    Model_ID=1,
                    Modelname="model",
                    creater_id=1,
                    del_flag=False,
                )
            )
            db.add(
                models.Device(
                    Device_ID=2,
                    Model_ID=1,
                    DeviceAddress=18,
                    Devicedescript="module",
                    creater_id=1,
                    del_flag=False,
                )
            )
            db.add(
                models.Unit(
                    id=7,
                    Unit_ID=32,
                    Device_ID=2,
                    UnitDescript="arm",
                    creater_id=1,
                    del_flag=False,
                )
            )
            db.add(
                models.Sensor(
                    id=8,
                    sensor_ID=49,
                    Device_ID=2,
                    Unit_ID=32,
                    unit_row_id=7,
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


if __name__ == "__main__":
    unittest.main()
