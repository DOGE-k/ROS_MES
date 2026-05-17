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
            record = create_fine_tuning_record(
                db=db,
                record=FineTuningCreate(module_id=18, device_id=1, position=12.5),
                username="tester",
            )

            self.assertEqual(record.Device_ID, 1)
            self.assertEqual(record.parameter_name, "module_18_position")
            self.assertEqual(record.new_value, 12.5)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
