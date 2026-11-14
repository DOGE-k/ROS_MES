from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import unittest

from app.crud.finetuning import create_fine_tuning_record
from app.db import models
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
            # 新语义：old_value 初始值 / requested_delta 微调量 / new_value 应到值
            self.assertIsNone(record.old_value)
            self.assertEqual(record.requested_delta, 12.5)
            self.assertIsNone(record.new_value)
        finally:
            db.close()

    def test_create_fine_tuning_record_uses_previous_value_for_same_parameter_only(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        db = SessionLocal()
        try:
            # 起点只认同一 (module, unit, parameter) 的最近一次到位实测位置
            db.add(models.FineTuning(
                module_id=18, unit_id=32, parameter_name="rotation",
                old_value=9.0, requested_delta=10.0, new_value=19.0, observed_position=10.0,
                creater_id=1,
            ))
            db.add(models.FineTuning(
                module_id=18, unit_id=32, parameter_name="swing",
                old_value=40.0, requested_delta=20.0, new_value=60.0, observed_position=55.0,
                creater_id=1,
            ))
            db.commit()
            record = create_fine_tuning_record(
                db=db,
                record=FineTuningCreate(module_id=18, unit_id=32, device_id=1, parameter_name="rotation", position=15),
                creater_id=1,
            )

            # 旋转轴取自己的实测 10，不串用摆动轴的 55
            self.assertEqual(record.old_value, 10)
            self.assertEqual(record.requested_delta, 15)
            self.assertEqual(record.new_value, 25)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
