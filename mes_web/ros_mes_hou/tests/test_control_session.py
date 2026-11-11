import unittest
from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import models
from app.db.database import Base
from app.ros.control_session import (
    ControlSessionManager,
    REASON_CLOSED,
    REASON_CONNECTION_CHANGED,
    REASON_EXPIRED,
    REASON_MISSING,
    REASON_SUPERSEDED,
    utcnow_naive,
)


class ControlSessionTest(unittest.TestCase):
    """会话记录只做 MES 侧登记与失效判定，不发送任何指令。"""

    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.manager = ControlSessionManager()

    def tearDown(self):
        self.engine.dispose()

    def _create(self, **overrides):
        payload = dict(module_id=17, seg=3, unit_ids=[32, 64], device_id=3,
                       x=1, y=2, connection_revision=5)
        payload.update(overrides)
        with self.Session() as db:
            return self.manager.create(db, **payload)

    def test_create_returns_resumable_session_with_bound_units(self):
        record = self._create()

        with self.Session() as db:
            state = self.manager.state(db, ttl_seconds=1800, current_revision=5)

        self.assertEqual(state["reason"], None)
        self.assertEqual(state["session"]["id"], record["id"])
        self.assertEqual(state["session"]["module_id"], 17)
        self.assertEqual(state["session"]["seg"], 3)
        self.assertEqual(state["session"]["unit_ids"], [32, 64])
        self.assertEqual(state["session"]["connection_revision"], 5)

    def test_new_handshake_supersedes_previous_session_on_same_seg(self):
        first = self._create()
        second = self._create(unit_ids=[96], device_id=4)

        with self.Session() as db:
            stale = self.manager.resume(db, first["id"], ttl_seconds=1800, current_revision=5)
            fresh = self.manager.resume(db, second["id"], ttl_seconds=1800, current_revision=5)

        self.assertFalse(stale["valid"])
        self.assertEqual(stale["reason"], REASON_SUPERSEDED)
        self.assertTrue(fresh["valid"])

    def test_new_handshake_supersedes_previous_session_on_shared_unit(self):
        first = self._create(seg=1, unit_ids=[32])
        second = self._create(seg=9, unit_ids=[32])

        with self.Session() as db:
            stale = self.manager.resume(db, first["id"], ttl_seconds=1800, current_revision=5)

        self.assertEqual(stale["reason"], REASON_SUPERSEDED)
        with self.Session() as db:
            fresh = self.manager.resume(db, second["id"], ttl_seconds=1800, current_revision=5)
        self.assertTrue(fresh["valid"])

    def test_connection_revision_change_invalidates_session(self):
        record = self._create(connection_revision=5)

        with self.Session() as db:
            result = self.manager.resume(db, record["id"], ttl_seconds=1800, current_revision=6)

        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], REASON_CONNECTION_CHANGED)

    def test_expired_session_is_finalized_not_silently_reused(self):
        record = self._create()
        with self.Session() as db:
            row = db.get(models.ControlSession, record["id"])
            row.last_active_at = utcnow_naive() - timedelta(seconds=120)
            db.commit()

        with self.Session() as db:
            result = self.manager.resume(db, record["id"], ttl_seconds=60, current_revision=5)
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], REASON_EXPIRED)

        with self.Session() as db:
            row = db.get(models.ControlSession, record["id"])
            self.assertIsNotNone(row.invalidated_at)
            self.assertEqual(row.invalid_reason, REASON_EXPIRED)

    def test_resume_slides_last_active_time(self):
        record = self._create()
        with self.Session() as db:
            row = db.get(models.ControlSession, record["id"])
            row.last_active_at = utcnow_naive() - timedelta(seconds=50)
            db.commit()
            before = db.get(models.ControlSession, record["id"]).last_active_at

        with self.Session() as db:
            self.assertTrue(self.manager.resume(db, record["id"], ttl_seconds=60, current_revision=5)["valid"])
            after = db.get(models.ControlSession, record["id"]).last_active_at

        self.assertGreater(after, before)
        with self.Session() as db:
            # 滑动后仍在有效期内：原本剩余 10s 不应成为判定依据
            self.assertTrue(self.manager.resume(db, record["id"], ttl_seconds=60, current_revision=5)["valid"])

    def test_unlimited_ttl_never_expires(self):
        record = self._create()
        with self.Session() as db:
            row = db.get(models.ControlSession, record["id"])
            row.last_active_at = utcnow_naive() - timedelta(days=2)
            db.commit()

        with self.Session() as db:
            result = self.manager.resume(db, record["id"], ttl_seconds=None, current_revision=5)

        self.assertTrue(result["valid"])

    def test_closed_session_cannot_be_resumed(self):
        record = self._create()
        with self.Session() as db:
            self.manager.close(db, record["id"])
            result = self.manager.resume(db, record["id"], ttl_seconds=1800, current_revision=5)

        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], REASON_CLOSED)

    def test_unknown_session_reports_missing(self):
        with self.Session() as db:
            result = self.manager.resume(db, "not-a-session", ttl_seconds=1800, current_revision=5)

        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], REASON_MISSING)

    def test_state_without_records_reports_missing(self):
        with self.Session() as db:
            state = self.manager.state(db, ttl_seconds=1800, current_revision=5)

        self.assertIsNone(state["session"])
        self.assertIsNone(state["latest"])
        self.assertEqual(state["reason"], REASON_MISSING)

    def test_invalidate_all_clears_every_active_session(self):
        first = self._create(seg=1, unit_ids=[32])
        second = self._create(seg=2, unit_ids=[64])

        with self.Session() as db:
            self.assertEqual(self.manager.invalidate_all(db, REASON_CONNECTION_CHANGED), 2)
            state = self.manager.state(db, ttl_seconds=1800, current_revision=5)

        self.assertIsNone(state["session"])
        self.assertEqual(state["reason"], REASON_CONNECTION_CHANGED)
        with self.Session() as db:
            for session_id in (first["id"], second["id"]):
                self.assertIsNotNone(db.get(models.ControlSession, session_id).invalidated_at)


if __name__ == "__main__":
    unittest.main()
