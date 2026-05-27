import { mockSuccess } from "./mock";

export const noRosDebug = import.meta.env.VITE_DEBUG_NO_ROS === "true";

const delay = (ms = 300) => new Promise((resolve) => setTimeout(resolve, ms));

export function getNoRosDebugDeviceList() {
  const devices = [];

  for (let x = 1; x <= 8; x++) {
    for (let y = 1; y <= 8; y++) {
      const address = x * 16 + y;
      devices.push({
        id: address,
        Device_ID: address,
        DeviceAddress: address,
        Devicedescript: `NO_ROS_DEBUG module (${x},${y})`,
      });
    }
  }

  return mockSuccess(devices, "NO_ROS_DEBUG: 模拟模块设备列表");
}

export function getNoRosDebugUnitsByDevice(deviceId: number) {
  return mockSuccess(
    [
      {
        id: deviceId * 10 + 1,
        Unit_ID: 1,
        Device_ID: deviceId,
        UnitDescript: "NO_ROS_DEBUG 默认机械臂",
      },
    ],
    "NO_ROS_DEBUG: 模拟机械臂列表"
  );
}

export function getNoRosDebugDrawingList() {
  const now = new Date().toISOString();

  return mockSuccess(
    [
      {
        drawingId: 1,
        drawingName: "NO_ROS_DEBUG 示例图纸",
        drawingDescription: "用于无 ROS 环境调试微调页面",
        drawingFile: "",
        creatorId: 0,
        createTime: now,
        modifyTime: now,
        latestVersionId: null,
        delFlag: false,
        notes: "debug only",
      },
    ],
    "NO_ROS_DEBUG: 模拟图纸列表"
  );
}

export function createNoRosDebugModule(data: any) {
  return mockSuccess(
    {
      ...data,
      debug: true,
    },
    "NO_ROS_DEBUG: 模块锁定模拟成功"
  );
}

export async function sendNoRosDebugCoordination(data: any) {
  await delay();

  return {
    code: 200,
    message: "NO_ROS_DEBUG: 目标图纸下发模拟成功",
    data,
    views: {},
  };
}

export function sendNoRosDebugFineTuning(data: any) {
  const position = Number(data?.position || 0);
  const feedbackDeviceMap: Record<string, number> = {
    rotation: 41,
    swing: 42,
    telescopic: 43,
  };

  return mockSuccess(
    [
      {
        device_id: feedbackDeviceMap[data?.parameter_name] || Number(data?.device_id || 0),
        position,
        type: "axis",
        parameter_name: data?.parameter_name,
      },
      {
        device_id: -1,
        position: Number((Math.abs(position) * 0.1 + 0.5).toFixed(2)),
        type: "pressure",
      },
      {
        device_id: 50,
        swing_angle: data?.parameter_name === "swing" ? position : Number((position * 0.3).toFixed(2)),
        rotation_angle: data?.parameter_name === "rotation" ? position : Number((position * 0.2).toFixed(2)),
        x: Number((10 + position * 0.05).toFixed(2)),
        y: Number((5 + position * 0.03).toFixed(2)),
        z: data?.parameter_name === "telescopic" ? position : Number((2 + position * 0.04).toFixed(2)),
        type: "imu_pose",
      },
    ],
    "NO_ROS_DEBUG: 微调模拟成功"
  );
}

export function saveNoRosDebugFineTuningConfig(data: any) {
  return mockSuccess(
    {
      id: Date.now(),
      ...data,
      debug: true,
    },
    "NO_ROS_DEBUG: 配置保存模拟成功"
  );
}
