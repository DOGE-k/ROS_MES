from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import unittest

from app.crud.finetuning import create_fine_tuning_record
from app.db.database import Base
from app.schemas.finetuning import FineTuningCreate


class FineTuningDeviceFieldTest(unittest.TestCase):
    def test_create_fine_tuning_record_uses_device_fields(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        db = SessionLocal()
        try:
            # V1.1：schema 强制要求 module_id + unit_id；未显式给 parameter_name 时自动生成含单元号的名称
            record = create_fine_tuning_record(
                db=db,
                record=FineTuningCreate(module_id=18, unit_id=32, device_id=1, position=12.5),
                creater_id=1,
            )

            self.assertEqual(record.module_id, 18)
            self.assertEqual(record.unit_id, 32)
            self.assertEqual(record.parameter_name, "module_18_unit_32_position")
            self.assertEqual(record.new_value, 12.5)
        finally:
            db.close()

    def test_create_fine_tuning_record_uses_previous_value_for_same_parameter_only(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        db = SessionLocal()
        try:
            create_fine_tuning_record(
                db=db,
                record=FineTuningCreate(module_id=18, unit_id=32, device_id=1, parameter_name="rotation", position=10),
                creater_id=1,
            )
            create_fine_tuning_record(
                db=db,
                record=FineTuningCreate(module_id=18, unit_id=32, device_id=1, parameter_name="swing", position=20),
                creater_id=1,
            )
            record = create_fine_tuning_record(
                db=db,
                record=FineTuningCreate(module_id=18, unit_id=32, device_id=1, parameter_name="rotation", position=15),
                creater_id=1,
            )

            # old_value 只取同一 (module, unit, parameter) 的最近一次 new_value
            self.assertEqual(record.old_value, 10)
            self.assertEqual(record.new_value, 15)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
