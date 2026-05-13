#!/usr/bin/env python3
import serial
import time
import json
import sys


def test_serial_connection(port="/dev/ttyUSB0", baud=115200, timeout=3.0):
    try:
        ser = serial.Serial(port, baud, timeout=0.5)
    except Exception as e:
        return {
            "success": False,
            "connected": False,
            "message": f"串口打开失败: {str(e)}，请检查串口线是否连接",
        }

    try:
        test_bytes = bytes([0x11, 0xFF, 0x00, 0x01])
        ser.write(test_bytes)

        start_time = time.time()
        received_data = b""
        while time.time() - start_time < timeout:
            if ser.in_waiting > 0:
                chunk = ser.read(ser.in_waiting)
                received_data += chunk
            time.sleep(0.05)

        ser.close()

        if len(received_data) > 0:
            return {
                "success": True,
                "connected": True,
                "message": "串口连接正常，收到下位机响应数据",
                "bytes_received": len(received_data),
            }
        else:
            return {
                "success": True,
                "connected": True,
                "message": "串口已连接，但未收到下位机响应（请检查下位机是否通电运行）",
                "bytes_received": 0,
            }
    except Exception as e:
        try:
            ser.close()
        except Exception:
            pass
        return {
            "success": False,
            "connected": True,
            "message": f"通信失败: {str(e)}",
        }


if __name__ == "__main__":
    port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
    result = test_serial_connection(port=port)
    print(json.dumps(result, ensure_ascii=False))
