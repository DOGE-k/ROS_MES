/**
 * V2.1 device_id 编码助手 —— 全前端唯一的 device_id 编码出处
 *
 * 编码规则来源：《ROS_MES_前后端ROS接口清单_三轴版 V2.1》（2026-10-24，ROS 端三轴化）
 *   0           系统级指令（急停/解除/模块停）
 *   1~15  轴级  3轴ID布局 × 5臂：每臂 关节1=旋转 / 关节2=摆动 / 关节3=伸缩
 *         臂1: 1/2/3   臂2: 4/5/6   臂3: 7/8/9   臂4: 10/11/12   臂5: 13/14/15
 *   21~25 臂级  压力传感器 + IMU 共用（同一 device_id，按话题/data_type 区分），臂号 = device_id - 20
 */

export const AXES_PER_ARM = 3;
export const ARM_LEVEL_BASE = 20;

export type AxisParameterName = "rotation" | "swing" | "telescopic";

/** 关节1/2/3 在臂内的偏移（旋转 / 摆动 / 伸缩） */
const AXIS_OFFSETS: Record<AxisParameterName, number> = {
  rotation: 1,
  swing: 2,
  telescopic: 3,
};

/**
 * 由数据库 Unit_ID 推算臂号（1~5）。
 * 种子定义：五臂 Unit_ID 分别为 32/64/96/128/160（每臂 +32）；实际登记数量以数据库为准。
 * 兼容直接传入臂号 1~5；无法识别时按一号臂兜底。
 */
export function armIndexFromUnitId(unitId: number): number {
  const id = Number(unitId || 0);
  if (id >= 1 && id <= 5) {
    return id;
  }
  if (id > 0 && id % 32 === 0) {
    return Math.min(Math.floor(id / 32), 5);
  }
  return 1;
}

/** 某臂某轴的 ROS device_id，如 armIndex=3、rotation → 7 */
export function axisDeviceId(armIndex: number, parameter: AxisParameterName): number {
  return (armIndex - 1) * AXES_PER_ARM + AXIS_OFFSETS[parameter];
}

/** 某臂臂级传感器（压力/IMU 共用）的 device_id，臂1 → 21 */
export function armLevelDeviceId(armIndex: number): number {
  return ARM_LEVEL_BASE + armIndex;
}
