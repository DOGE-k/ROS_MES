import unittest

from app.api.endpoints.coordination import send_coordination


class CoordinationPayloadTest(unittest.TestCase):
    def test_send_coordination_accepts_unit_and_drawing_without_xyz(self):
        response = send_coordination(
            {
                "module_id": 18,
                "device_id": 1,
                "unit_id": 32,
                "unit_row_id": 7,
                "drawing_id": 5,
            }
        )

        self.assertEqual(response["code"], 200)
        self.assertEqual(response["data"]["module_id"], 18)
        self.assertEqual(response["data"]["device_id"], 1)
        self.assertEqual(response["data"]["unit_id"], 32)
        self.assertEqual(response["data"]["unit_row_id"], 7)
        self.assertEqual(response["data"]["drawing_id"], 5)


if __name__ == "__main__":
    unittest.main()
