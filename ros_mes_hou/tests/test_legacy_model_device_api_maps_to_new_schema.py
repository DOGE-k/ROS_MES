import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.endpoints import device_api, model_api
from app.db import models
from app.db.database import Base
from app.schemas import device as device_schemas
from app.schemas import model as model_schemas


class LegacyModelDeviceApiMapsToNewSchemaTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db = TestingSession()
        self.db.add(models.User(User_ID=1, Username="admin", Password="x", Type_ID=1, Creator_ID=1))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_model_api_uses_type_table(self):
        created = model_api.create_model(
            model_schemas.ModelCreate(Modelname="type one", Modeldescripte="desc"),
            self.db,
        )

        self.assertEqual(created["data"]["Model_ID"], created["data"]["Type_ID"])
        self.assertEqual(created["data"]["Modelname"], "type one")
        self.assertEqual(self.db.query(models.Type).count(), 1)

    def test_device_api_uses_module_table(self):
        self.db.add(models.Type(Type_ID=1, Typename="type one", creater_id=1))
        self.db.commit()

        created = device_api.create_device(
            device_schemas.DeviceCreate(Model_ID=1, DeviceAddress=17, Devicedescript="module one"),
            self.db,
        )

        self.assertEqual(created["data"]["Device_ID"], created["data"]["Module_ID"])
        self.assertEqual(created["data"]["Model_ID"], 1)
        self.assertEqual(created["data"]["DeviceAddress"], 17)
        self.assertEqual(self.db.query(models.Module).count(), 1)


if __name__ == "__main__":
    unittest.main()
