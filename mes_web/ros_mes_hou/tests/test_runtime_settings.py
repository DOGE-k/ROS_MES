import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.endpoints import control, coordination, drawing, finetuning
from app.core.security import create_access_token
from app.db import models
from app.db.database import Base, get_db
from app.ros import get_ros_dispatcher, reset_ros_dispatcher
from app.ros.finetuning_batch import BatchManager
from app.ros.base import RosbridgeError
from app.ros.mock_client import mock_robot
from app.ros.rosbridge import RosbridgeClient
from app.ros.runtime_settings import RuntimeSettings, SettingsChange
from app.schemas.finetuning import FineTuningBatchCreate, FineTuningConfigCreate
from app.schemas.hardware import ManualEmergencyRelease
from test_finetuning_batch import FakeClient, status, position


class RuntimeSettingsTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        with self.sessions() as db:
            db.add(models.User(User_ID=1, Username='test', Password='x', Type_ID=1, Creator_ID=1))
            db.add(models.Type(Type_ID=1, Typename='type', creater_id=1))
            db.add(models.Module(Module_ID=17, Type_ID=1, ModuleAddress='17', creater_id=1))
            db.add(models.Unit(Module_ID=17, Unit_ID=32, creater_id=1))
            db.commit()
        self.settings = RuntimeSettings(self.sessions)
        self.manager = BatchManager(self.sessions, state_timeout=0.3, motion_timeout=1)
        self.patches = [patch('app.ros.runtime_settings.runtime_settings', self.settings),
                        patch.object(control, 'runtime_settings', self.settings),
                        patch.object(control, 'batch_manager', self.manager)]
        for item in self.patches: item.start()
        reset_ros_dispatcher()
        mock_robot.stop(False)
        mock_robot.positions.clear()
        self.user = SimpleNamespace(User_ID=1, Username='test')

    async def asyncTearDown(self):
        for task in list(self.manager.tasks.values()):
            task.cancel()
            await task
        reset_ros_dispatcher()
        for item in reversed(self.patches): item.stop()
        self.engine.dispose()

    def update(self, **changes):
        return self.settings.update(SettingsChange(expected_revision=self.settings.snapshot()['revision'], changes=changes))

    def mock(self):
        return self.update(ros_mode='mock', drawing_mode='mock', emergency_mode='mock')

    def request(self, **kwargs):
        return FineTuningBatchCreate(request_id='runtime_request_001', module_id=17, unit_id=32,
            adjustments=[{'parameter_name': key, 'position': value} for key, value in
                         [('rotation', 2), ('swing', 1), ('telescopic', 0.5)]], **kwargs)

    def manual_release_request(self):
        connection = self.settings.snapshot()
        return ManualEmergencyRelease(operator_confirmed=True,
            expected_generation=self.manager.safety(connection['emergency_mode'])['generation'],
            connection_revision=connection['revision'])

    async def test_configuration_persists_and_restart_reads_the_saved_revision(self):
        value = self.update(ros_mode='mock', ros_url='ws://192.0.2.1:9010')
        reloaded = RuntimeSettings(self.sessions)
        reloaded.load()
        self.assertEqual(value, reloaded.snapshot())
        self.assertEqual('real', value['emergency_mode'])

    async def test_real_commands_cannot_use_mock_emergency(self):
        with self.assertRaises(HTTPException) as caught:
            self.update(emergency_mode='mock')
        self.assertEqual(422, caught.exception.status_code)
        self.assertEqual(0, self.settings.snapshot()['revision'])

    async def test_invalid_addresses_and_unknown_fields_are_rejected(self):
        for changes in [{'ros_url': 'http://host:9010'}, {'ros_url': 'ws://u:p@host:9010'},
                        {'ros_url': 'ws://host:70000'}, {'pointcloud_url': 'file:///tmp/x'}, {'unknown': True}]:
            with self.assertRaises(HTTPException): self.update(**changes)
        self.assertEqual(0, self.settings.snapshot()['revision'])

    async def test_stale_window_cannot_overwrite_other_settings(self):
        self.update(ros_mode='mock')
        with self.assertRaises(HTTPException) as caught:
            self.settings.update(SettingsChange(expected_revision=0, changes={'drawing_mode': 'mock'}))
        self.assertEqual(409, caught.exception.status_code)

    async def test_active_operation_freezes_settings_and_old_snapshot_cannot_send(self):
        with self.settings.operation(0):
            with self.assertRaises(HTTPException): self.update(ros_mode='mock')
        self.update(ros_mode='mock')
        with self.assertRaises(HTTPException):
            with self.settings.operation(0): pass

    async def test_unresolved_batch_prevents_connection_changes(self):
        job = await self.manager.start(self.request(), FakeClient(initial=False), 1)
        with self.assertRaises(HTTPException) as caught: self.update(ros_mode='mock')
        self.assertEqual(409, caught.exception.status_code)
        await self.manager.tasks[job['id']]

    async def test_full_backend_mock_batch_runs_sequentially_without_any_socket(self):
        self.mock()
        with patch('app.ros.rosbridge.websockets.connect', side_effect=AssertionError('mock opened a socket')):
            job = await control.create_finetuning_batch(self.request(connection_revision=1), self.user)
            batch_id = job['data']['id']
            await self.manager.tasks[batch_id]
            result = self.manager.get(batch_id)
        self.assertEqual('completed', result['status'])
        self.assertTrue(result['simulated'])
        self.assertFalse(result['target_locked'])
        self.assertEqual([2, 1, 0.5], [mock_robot.positions[(0, axis)] for axis in (1, 2, 3)])
        with self.sessions() as db:
            self.assertEqual(3, db.query(models.FineTuning).count())
            self.assertTrue(all('mode=mock' in row.notes for row in db.query(models.FineTuning)))

    async def test_mock_stop_release_preserves_real_interlock(self):
        self.mock()
        self.manager.set_safety('stop_unknown', 'real')
        with patch('app.ros.rosbridge.websockets.connect', side_effect=AssertionError('mock opened a socket')):
            stopped = await control.activate_emergency_stop(self.user)
            self.assertTrue(stopped['simulated'])
            released = await control.release_emergency_stop(self.user)
        self.assertTrue(released['simulated'])
        self.assertEqual('clear', self.manager.safety('mock')['state'])
        self.assertEqual('stop_unknown', self.manager.safety('real')['state'])

    async def test_real_release_reports_sent_only_and_does_not_clear_mock_record(self):
        self.manager.set_safety('stop_sent', 'mock')
        with patch.object(RosbridgeClient, 'publish_stop_release', return_value=True):
            result = await control.release_emergency_stop(self.user)
        self.assertFalse(result['simulated'])
        self.assertEqual('release_sent', self.manager.safety('real')['state'])
        self.assertEqual('stop_sent', self.manager.safety('mock')['state'])

    async def test_manual_release_persists_and_only_clears_the_current_environment(self):
        with patch('app.ros.rosbridge.websockets.connect', side_effect=AssertionError('manual release opened a socket')):
            for mode in ('real', 'mock'):
                if mode == 'mock':
                    self.mock()
                other_mode = 'mock' if mode == 'real' else 'real'
                other = self.manager.set_safety('stop_unknown', other_mode)
                for state in ('stop_requested', 'stop_sent', 'stop_unknown', 'release_sent'):
                    with self.subTest(mode=mode, state=state):
                        stopped = self.manager.set_safety(state, mode)
                        result = await control.manually_release_emergency_stop(self.manual_release_request(), self.user)
                        self.assertEqual(200, result['code'])
                        self.assertEqual('clear', result['data']['state'])
                        self.assertEqual(mode == 'mock', result['data']['simulated'])
                        self.assertEqual(stopped['generation'] + 1, result['data']['generation'])
                        self.assertEqual(result['data']['generation'], BatchManager(self.sessions).safety(mode)['generation'])
                        self.assertEqual('clear', BatchManager(self.sessions).safety(mode)['state'])
                        self.assertEqual(other, self.manager.safety(other_mode))

    async def test_repeated_manual_release_is_idempotent(self):
        self.manager.set_safety('stop_sent')
        request = self.manual_release_request()
        first = await control.manually_release_emergency_stop(request, self.user)
        second = await control.manually_release_emergency_stop(request, self.user)
        self.assertEqual(first, second)

    async def test_stale_manual_confirmation_cannot_clear_a_new_stop(self):
        self.manager.set_safety('stop_sent')
        request = self.manual_release_request()
        newer = self.manager.set_safety('stop_sent')
        with self.assertRaises(HTTPException) as caught:
            await control.manually_release_emergency_stop(request, self.user)
        self.assertEqual(409, caught.exception.status_code)
        self.assertEqual(newer, self.manager.safety())

    async def test_manual_release_rejects_a_changed_connection(self):
        stopped = self.manager.set_safety('stop_sent')
        request = self.manual_release_request()
        self.mock()
        with self.assertRaises(HTTPException) as caught:
            await control.manually_release_emergency_stop(request, self.user)
        self.assertEqual(409, caught.exception.status_code)
        self.assertEqual(stopped, self.manager.safety())

    async def test_manual_release_waits_for_inflight_control_operations(self):
        stopped = self.manager.set_safety('stop_requested')
        with self.settings.operation(0):
            with self.assertRaises(HTTPException) as caught:
                await control.manually_release_emergency_stop(self.manual_release_request(), self.user)
        self.assertEqual(409, caught.exception.status_code)
        self.assertEqual(stopped, self.manager.safety())

    async def test_manual_release_preserves_the_interrupted_batch_until_operator_acknowledges(self):
        client = FakeClient(initial=False)
        job = await self.manager.start(self.request(), client, self.user.User_ID)
        self.manager.set_safety('stop_sent')
        await self.manager.tasks[job['id']]
        await control.manually_release_emergency_stop(self.manual_release_request(), self.user)
        result = self.manager.get(job['id'])
        self.assertEqual('uncertain', result['status'])
        self.assertTrue(result['target_locked'])
        self.assertEqual([], client.sent)
        with self.sessions() as db:
            with self.assertRaises(HTTPException):
                self.manager.assert_available(db, 17, 32)
        self.manager.acknowledge(job['id'])
        with self.sessions() as db:
            self.manager.assert_available(db, 17, 32)

    async def test_mock_manual_release_allows_a_new_fractional_batch_after_stop(self):
        self.mock()
        with patch('app.ros.rosbridge.websockets.connect', side_effect=AssertionError('mock opened a socket')):
            await control.activate_emergency_stop(self.user)
            self.assertTrue(mock_robot.stopped)
            await control.manually_release_emergency_stop(self.manual_release_request(), self.user)
            self.assertFalse(mock_robot.stopped)
            request = FineTuningBatchCreate(request_id='after_manual_release', module_id=17, unit_id=32,
                adjustments=[{'parameter_name': 'rotation', 'position': 0.01},
                             {'parameter_name': 'swing', 'position': -0.01}], connection_revision=1)
            job = await control.create_finetuning_batch(request, self.user)
            await self.manager.tasks[job['data']['id']]
        self.assertEqual('completed', self.manager.get(job['data']['id'])['status'])
        self.assertEqual(0.01, mock_robot.positions[(0, 1)])
        self.assertEqual(-0.01, mock_robot.positions[(0, 2)])

    async def test_manual_release_http_requires_login_confirmation_and_versions(self):
        app = FastAPI()
        app.include_router(control.router, prefix='/api/control')
        def database():
            with self.sessions() as db:
                yield db
        app.dependency_overrides[get_db] = database
        async def request(payload, token=None):
            events = []
            headers = [(b'host', b'test'), (b'content-type', b'application/json')]
            if token:
                headers.append((b'authorization', f'Bearer {token}'.encode()))
            path = '/api/control/emergency_stop/manual_release'
            scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1', 'method': 'POST',
                     'scheme': 'http', 'path': path, 'raw_path': path.encode(), 'query_string': b'',
                     'headers': headers, 'server': ('test', 80), 'client': ('127.0.0.1', 1)}
            async def receive():
                return {'type': 'http.request', 'body': json.dumps(payload).encode(), 'more_body': False}
            async def send(event):
                events.append(event)
            await app(scope, receive, send)
            return events[0]['status'], json.loads(b''.join(event.get('body', b'') for event in events))
        self.manager.set_safety('stop_sent')
        payload = self.manual_release_request().model_dump()
        code, _ = await request(payload)
        self.assertIn(code, (401, 403))
        token = create_access_token({'sub': 'test'})
        for invalid in ({}, {**payload, 'operator_confirmed': False}, {**payload, 'expected_generation': -1}):
            code, _ = await request(invalid, token)
            self.assertEqual(422, code)
            self.assertEqual('stop_sent', self.manager.safety()['state'])
        with patch('app.ros.rosbridge.websockets.connect', side_effect=AssertionError('manual release opened a socket')):
            code, response = await request(payload, token)
        self.assertEqual(200, code)
        self.assertEqual('clear', response['data']['state'])
        self.assertEqual('clear', control.get_emergency_state(self.user)['data']['state'])

    async def test_mock_emergency_interrupts_batch_and_release_does_not_resume_it(self):
        self.mock()
        job = await control.create_finetuning_batch(self.request(), self.user)
        batch_id = job['data']['id']
        for _ in range(100):
            if mock_robot.running: break
            await asyncio.sleep(0.002)
        await control.activate_emergency_stop(self.user)
        await self.manager.tasks[batch_id]
        await control.release_emergency_stop(self.user)
        self.assertEqual('uncertain', self.manager.get(batch_id)['status'])
        self.assertTrue(self.manager.get(batch_id)['target_locked'])
        self.assertEqual({}, mock_robot.positions)

    async def test_old_arm_confirmation_revision_cannot_create_new_motion(self):
        self.mock()
        with self.assertRaises(HTTPException) as caught:
            await control.create_finetuning_batch(self.request(connection_revision=0), self.user)
        self.assertEqual(409, caught.exception.status_code)
        self.assertEqual({}, mock_robot.positions)

    async def test_separate_drawing_and_emergency_addresses_route_to_selected_destinations(self):
        self.update(ros_url='ws://192.0.2.1:9010', drawing_ros_url='ws://192.0.2.2:9010',
                    emergency_ros_url='ws://192.0.2.3:9010')
        dispatcher, targets = get_ros_dispatcher(), []
        def dispatched(client, action, payload):
            targets.append((client.url, action))
            return {'confirmed': True, 'sent': True}
        with patch.object(RosbridgeClient, 'dispatch', dispatched):
            dispatcher.dispatch('module_confirm', {})
            dispatcher.dispatch('drawing_path', {})
        self.assertEqual([('ws://192.0.2.1:9010', 'module_confirm'), ('ws://192.0.2.2:9010', 'module_confirm'),
                          ('ws://192.0.2.2:9010', 'drawing_path')], targets)
        self.assertEqual('ws://192.0.2.3:9010', dispatcher.emergency_client.url)

    async def test_mock_pointcloud_previews_do_not_fetch_upstream(self):
        self.mock()
        with patch.object(coordination._VIEW_OPENER, 'open', side_effect=AssertionError('mock fetched a view')):
            response = coordination.proxy_pointcloud_view('front')
        self.assertIn(b'SIMULATED FRONT', response.body)
        self.assertEqual('image/svg+xml', response.media_type)

    async def test_emergency_latch_also_blocks_drawing_dispatch(self):
        self.mock()
        self.manager.set_safety('stop_sent', 'mock')
        with self.assertRaises(RosbridgeError): get_ros_dispatcher().dispatch('drawing_path', {})

    async def test_old_view_revision_cannot_read_another_environment_image(self):
        self.mock()
        with self.assertRaises(HTTPException) as caught: coordination.proxy_pointcloud_view('front', connection_revision=0)
        self.assertEqual(409, caught.exception.status_code)

    async def test_mock_hardware_tools_never_launch_real_ros_scripts(self):
        self.mock()
        dispatcher = get_ros_dispatcher()
        with patch('asyncio.create_subprocess_exec', side_effect=AssertionError('mock launched a script')):
            self.assertTrue((await dispatcher.test_serial_connection())['simulated'])
            self.assertTrue((await dispatcher.get_hardware_status())['simulated'])
            stream = dispatcher.stream_robot_data()
            self.assertTrue(json.loads(await anext(stream))['simulated'])
            await stream.aclose()

    async def test_empty_drawing_library_offers_virtual_mock_only_to_tuning(self):
        self.mock()
        with self.sessions() as db:
            options = drawing.list_drawings(for_tuning=True, db=db, current_user=self.user)['data']
            self.assertEqual(1, len(options))
            self.assertEqual('builtin_mock', options[0]['drawingSource'])
            self.assertIsNone(options[0]['drawingId'])
            self.assertTrue(options[0]['simulated'])
            self.assertEqual([], drawing.list_drawings(db=db, current_user=self.user)['data'])
            self.assertEqual(0, db.query(models.Drawing).count())

    async def test_real_and_skip_drawing_lists_never_invent_a_business_drawing(self):
        with self.sessions() as db:
            self.assertEqual([], drawing.list_drawings(for_tuning=True, db=db, current_user=self.user)['data'])
            self.update(ros_mode='mock', drawing_mode='skip', emergency_mode='mock')
            self.assertEqual([], drawing.list_drawings(for_tuning=True, db=db, current_user=self.user)['data'])
            self.assertEqual(0, db.query(models.Drawing).count())

    def builtin_payload(self, **overrides):
        return {'module_id': 17, 'device_id': 17, 'unit_id': 32, 'unit_row_id': 1,
                'drawing_id': None, 'drawing_source': 'builtin_mock',
                'connection_revision': self.settings.snapshot()['revision'], **overrides}

    async def test_builtin_mock_dispatch_needs_no_business_row_file_or_socket(self):
        self.mock()
        with self.sessions() as db, \
                patch('app.ros.rosbridge.websockets.connect', side_effect=AssertionError('mock opened a socket')), \
                patch.object(coordination, 'build_drawing_path_publish_payload', side_effect=AssertionError('builtin built a real path')), \
                patch.object(coordination._VIEW_OPENER, 'open', side_effect=AssertionError('mock fetched a view')):
            result = coordination.send_coordination(self.builtin_payload(), db=db)
            self.assertTrue(result['simulated'])
            self.assertEqual('builtin_mock', result['data']['drawing_source'])
            self.assertIsNone(result['data']['drawing_id'])
            self.assertEqual({'top', 'front', 'side'}, set(result['views']))
            self.assertTrue(all('connection_revision=1' in url for url in result['views'].values()))
            self.assertEqual(0, db.query(models.Drawing).count())

    async def test_real_dispatch_rejects_builtin_source_before_any_ros_call(self):
        with self.sessions() as db, patch.object(RosbridgeClient, 'dispatch', side_effect=AssertionError('builtin reached real ROS')):
            with self.assertRaises(HTTPException) as caught:
                coordination.send_coordination(self.builtin_payload(), db=db)
        self.assertEqual(422, caught.exception.status_code)

    async def test_builtin_source_does_not_accept_a_fake_numeric_drawing_id(self):
        self.mock()
        with self.sessions() as db:
            for drawing_id in (0, -1, 123):
                with self.assertRaises(HTTPException) as caught:
                    coordination.send_coordination(self.builtin_payload(drawing_id=drawing_id), db=db)
                self.assertEqual(422, caught.exception.status_code)
            self.assertEqual(0, db.query(models.Drawing).count())

    async def test_malformed_drawing_source_returns_validation_error_not_server_error(self):
        self.mock()
        with self.sessions() as db:
            for source in ('unknown', {}, []):
                with self.subTest(source=source):
                    with self.assertRaises(HTTPException) as caught:
                        coordination.send_coordination(self.builtin_payload(drawing_source=source), db=db)
                    self.assertEqual(422, caught.exception.status_code)

    async def test_skip_drawing_persists_and_rejects_dispatch_and_views(self):
        saved = self.update(ros_mode='mock', drawing_mode='skip', emergency_mode='mock')
        reloaded = RuntimeSettings(self.sessions)
        reloaded.load()
        self.assertEqual(saved, reloaded.snapshot())
        self.assertEqual('skip', reloaded.snapshot()['drawing_mode'])
        with self.sessions() as db, patch('app.ros.rosbridge.websockets.connect', side_effect=AssertionError('skip opened a socket')):
            with self.assertRaises(HTTPException) as caught:
                coordination.send_coordination(self.builtin_payload(), db=db)
            self.assertEqual(409, caught.exception.status_code)
            with self.assertRaises(HTTPException) as caught:
                coordination.proxy_pointcloud_view('front')
            self.assertEqual(409, caught.exception.status_code)
            with self.assertRaises(RosbridgeError):
                get_ros_dispatcher().dispatch('drawing_path', {})
            self.assertTrue(get_ros_dispatcher().dispatch('module_confirm', {})['confirmed'])

    def builtin_config(self, **overrides):
        return FineTuningConfigCreate(module_id=17, unit_id=32, sensor_id=49,
            drawing_source='builtin_mock', drawing_id=None,
            connection_revision=self.settings.snapshot()['revision'], **overrides)

    async def test_builtin_config_save_records_source_and_null_id_without_inserting_drawing(self):
        self.mock()
        with self.sessions() as db:
            db.add(models.Sensor(Module_ID=17, Unit_ID=32, sensor_ID=49, Unit_address=0,
                                 IsRead=1, sensordescript='压力传感器', creater_id=1))
            db.commit()
            result = finetuning.save_config(self.builtin_config(), db=db)
            snapshot = result['data']['config']
            self.assertEqual('builtin_mock', snapshot['drawing_source'])
            self.assertIsNone(snapshot['drawing_id'])
            self.assertFalse(snapshot['is_debug'])
            self.assertEqual(1, snapshot['connection_revision'])
            self.assertEqual(1, db.query(models.FineTuningConfig).count())
            self.assertEqual(0, db.query(models.Drawing).count())

    async def test_builtin_config_cannot_be_saved_in_real_or_skip_mode(self):
        with self.sessions() as db:
            with self.assertRaises(HTTPException) as caught:
                finetuning.save_config(self.builtin_config(), db=db)
            self.assertEqual(422, caught.exception.status_code)
            self.update(ros_mode='mock', drawing_mode='skip', emergency_mode='mock')
            with self.assertRaises(HTTPException) as caught:
                finetuning.save_config(self.builtin_config(), db=db)
            self.assertEqual(422, caught.exception.status_code)
            self.assertEqual(0, db.query(models.FineTuningConfig).count())

    async def test_stale_builtin_dispatch_and_config_are_rejected_without_writes(self):
        self.mock()
        old_config = self.builtin_config()
        old_payload = self.builtin_payload()
        self.update(pointcloud_url='http://192.0.2.30:5000')
        with self.sessions() as db:
            for action in (lambda: coordination.send_coordination(old_payload, db=db),
                           lambda: finetuning.save_config(old_config, db=db)):
                with self.assertRaises(HTTPException) as caught: action()
                self.assertEqual(409, caught.exception.status_code)
            self.assertEqual(0, db.query(models.FineTuningConfig).count())
            self.assertEqual(0, db.query(models.Drawing).count())

    async def test_builtin_config_schema_rejects_business_binding_and_skip_combination(self):
        for changes in ({'drawing_id': 123}, {'is_debug': True}):
            with self.assertRaises(ValueError):
                FineTuningConfigCreate(module_id=17, unit_id=32, sensor_id=49,
                    drawing_source='builtin_mock', **changes)

    async def test_mixed_mode_status_read_retains_real_history_without_stop_or_release(self):
        self.manager.set_safety('stop_unknown', 'real')
        self.update(ros_mode='mock', drawing_mode='mock')
        with patch.object(RosbridgeClient, 'publish_softstop', side_effect=AssertionError('read sent stop')), \
                patch.object(RosbridgeClient, 'publish_stop_release', side_effect=AssertionError('read sent release')):
            result = control.get_emergency_state(self.user)['data']
        self.assertEqual('stop_unknown', result['state'])
        self.assertFalse(result['simulated'])
        self.assertEqual('stop_unknown', self.manager.safety('real')['state'])
        self.assertEqual('clear', self.manager.safety('mock')['state'])

    async def test_mock_events_cannot_open_real_preflight(self):
        client = FakeClient(initial=False)
        for axis in (1, 2, 3):
            client.queue.put_nowait({**status(axis), 'simulated': True})
            client.queue.put_nowait({**position(axis), 'simulated': True})
        job = await self.manager.start(self.request(), client, 1)
        await self.manager.tasks[job['id']]
        self.assertEqual([], client.sent)
        self.assertEqual('blocked', self.manager.get(job['id'])['status'])

    async def test_settings_http_requires_login_and_accepts_authenticated_read(self):
        app = FastAPI()
        app.include_router(control.router, prefix='/api/control')
        def database():
            with self.sessions() as db: yield db
        app.dependency_overrides[get_db] = database
        async def request(token=None):
            events = []
            headers = [(b'host', b'test')]
            if token: headers.append((b'authorization', f'Bearer {token}'.encode()))
            scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1', 'method': 'GET',
                     'scheme': 'http', 'path': '/api/control/debug-settings', 'raw_path': b'/api/control/debug-settings',
                     'query_string': b'', 'headers': headers, 'server': ('test', 80), 'client': ('127.0.0.1', 1)}
            async def receive(): return {'type': 'http.request', 'body': b'', 'more_body': False}
            async def send(event): events.append(event)
            await app(scope, receive, send)
            return events[0]['status'], json.loads(b''.join(event.get('body', b'') for event in events))
        code, _ = await request()
        self.assertIn(code, (401, 403))
        code, body = await request(create_access_token({'sub': 'test'}))
        self.assertEqual(200, code)
        self.assertEqual('real', body['data']['ros_mode'])


if __name__ == '__main__': unittest.main()
