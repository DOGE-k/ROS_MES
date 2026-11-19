"""The new message package must work without the running backend or ROS."""

import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest


class Ros2ContractIsolationTest(unittest.TestCase):
    def test_public_package_is_offline_and_independent_of_ros_version(self):
        backend_root = str(Path(__file__).resolve().parents[1])
        script = textwrap.dedent("""
            import sys

            sys.path.insert(0, BACKEND_ROOT)
            assert sys.flags.no_site == 1

            class OfflineImports:
                def find_spec(self, fullname, path=None, target=None):
                    forbidden = (
                        'app.ros', 'app.db', 'app.core', 'app.api', 'app.main',
                        'fastapi', 'sqlalchemy', 'dotenv', 'websockets',
                        'rospy', 'rclpy',
                    )
                    if any(fullname == item or fullname.startswith(item + '.')
                           for item in forbidden):
                        raise AssertionError('Backend dependency imported: ' + fullname)

            def offline_audit(event, args):
                if event in (
                    'socket.connect', 'socket.bind', 'socket.getaddrinfo',
                    'sqlite3.connect', 'subprocess.Popen', 'os.system',
                ) or event.startswith('os.spawn'):
                    raise AssertionError('External operation attempted: ' + event)

            sys.meta_path.insert(0, OfflineImports())
            sys.addaudithook(offline_audit)
            loaded_before = set(sys.modules)

            import app.ros2_contract as contract

            address = contract.Address(0, 32)
            assert (address.module_id, address.device_id) == (0, 32)
            assert contract.arm_of(32) == 2
            assert contract.arm_of(37) == 2
            unknown = contract.parse_feedback('FutureUnspecifiedMessage', {'value': 7})
            assert unknown.is_known is False
            assert unknown.address is None
            assert unknown.values == {}
            assert unknown.raw == {'value': 7}

            for name in sys.modules:
                root = name.split('.')[0]
                if name not in loaded_before and root != 'app' and root not in sys.stdlib_module_names:
                    raise AssertionError('Non-standard dependency loaded: ' + name)
                if name == 'app.ros' or name.startswith('app.ros.'):
                    raise AssertionError('Legacy ROS package loaded: ' + name)
                if name == 'app.db' or name.startswith('app.db.'):
                    raise AssertionError('Database package loaded: ' + name)
            print('isolated')
        """).replace('BACKEND_ROOT', json.dumps(backend_root))
        for version in ("1", "2", "invalid-version"):
            with self.subTest(ros_version=version):
                environment = {**os.environ, "ROS_VERSION": version}
                result = subprocess.run(
                    [sys.executable, "-S", "-c", script],
                    cwd=backend_root,
                    env=environment,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=20,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(result.stdout.strip(), "isolated")


if __name__ == "__main__":
    unittest.main()
