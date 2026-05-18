import unittest

from app.db import models


class SchemaDesignAlignmentTest(unittest.TestCase):
    def test_user_type_is_plain_role_code_not_self_referencing_user_fk(self):
        foreign_keys = {fk.column.table.name for fk in models.User.__table__.c.Type_ID.foreign_keys}
        self.assertEqual(set(), foreign_keys)

    def test_drawing_latest_version_can_be_empty_until_first_version_is_created(self):
        self.assertTrue(models.Drawing.__table__.c.NewVersion_ID.nullable)


if __name__ == "__main__":
    unittest.main()
