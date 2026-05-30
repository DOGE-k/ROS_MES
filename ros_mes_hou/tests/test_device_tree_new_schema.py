import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.endpoints.model_api import get_device_tree
from app.db.database import Base
from app.db import models


class DeviceTreeNewSchemaTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = TestingSession()

        self.db.add(models.User(User_ID=1, Username="admin", Password="x", Type_ID=1, Creator_ID=1))
        self.db.add(models.Type(Type_ID=1, Typename="adaptive tooling", Typedescripte="type", creater_id=1))
        self.db.add(models.Module(Module_ID=17, Type_ID=1, Moduledescript="module one", ModuleAddress="17", creater_id=1))
        self.db.add(models.Unit(Unit_ID=32, UnitDescript="arm one", Module_ID=17, creater_id=1))
        self.db.add(models.Sensor(sensor_ID=33, sensordescript="rotation motor", IsRead=1, Module_ID=17, Unit_ID=32, Unit_address=1, creater_id=1))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_device_tree_uses_type_module_unit_sensor_schema(self):
        response = get_device_tree(self.db)

        self.assertEqual(response["code"], 200)
        tree = response["data"]
        self.assertEqual(len(tree), 1)
        self.assertEqual(tree[0]["type"], "model")
        self.assertEqual(tree[0]["raw_id"], 1)

        module_node = tree[0]["children"][0]
        self.assertEqual(module_node["type"], "device")
        self.assertEqual(module_node["raw_id"], 17)
        self.assertEqual(module_node["module_id"], 17)

        unit_node = module_node["children"][0]
        self.assertEqual(unit_node["type"], "unit")
        self.assertEqual(unit_node["arm_type"], 32)
        self.assertEqual(unit_node["module_id"], 17)

        sensor_node = unit_node["children"][0]
        self.assertEqual(sensor_node["type"], "sensor")
        self.assertEqual(sensor_node["sensor_type"], 33)
        self.assertEqual(sensor_node["module_id"], 17)


if __name__ == "__main__":
    unittest.main()
