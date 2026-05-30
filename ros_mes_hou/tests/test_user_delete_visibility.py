import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.endpoints.user import delete_user, list_users
from app.db import models
from app.db.database import Base


class UserDeleteVisibilityTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db = TestingSession()
        self.admin = models.User(
            User_ID=1,
            Username="admin",
            Password="x",
            Type_ID=1,
            Creator_ID=1,
            del_flag=False,
        )
        self.operator = models.User(
            User_ID=2,
            Username="operator",
            Password="x",
            Type_ID=2,
            Creator_ID=1,
            del_flag=False,
        )
        self.db.add_all([self.admin, self.operator])
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_deleted_user_is_hidden_from_user_list(self):
        delete_user(2, db=self.db, current_user=self.admin)

        response = list_users(keyword="", type_id=0, db=self.db, current_user=self.admin)

        usernames = [item["username"] for item in response["data"]]
        self.assertNotIn("operator", usernames)
        self.assertIn("admin", usernames)


if __name__ == "__main__":
    unittest.main()
