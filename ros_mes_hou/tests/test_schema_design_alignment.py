import unittest

from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import StaticPool

from app.db import models
from app.db.database import Base


class SchemaDesignAlignmentTest(unittest.TestCase):
    def test_user_type_is_plain_role_code_not_self_referencing_user_fk(self):
        foreign_keys = {fk.column.table.name for fk in models.User.__table__.c.Type_ID.foreign_keys}
        self.assertEqual(set(), foreign_keys)

    def test_drawing_latest_version_can_be_empty_until_first_version_is_created(self):
        self.assertTrue(models.Drawing.__table__.c.NewVersion_ID.nullable)

    def test_create_all_does_not_create_legacy_model_device_tables(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        Base.metadata.create_all(bind=engine)

        table_names = set(inspect(engine).get_table_names())
        self.assertNotIn("Model", table_names)
        self.assertNotIn("Device", table_names)


if __name__ == "__main__":
    unittest.main()
