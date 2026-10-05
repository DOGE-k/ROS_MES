/**
 * V2 device_id 编码助手 —— 全前端唯一的 device_id 编码出处
 *
 * 编码规则来源：《ROS_MES_前后端接口字段文档》6.1 / 团队基准《ROS_MES_前后端ROS接口清单》
 *   0           系统级指令（急停等）
 *   1~20  轴级  4轴ID布局 × 5臂：每臂 J1旋转 / J2摆动 / J3空置 / J4伸缩
 *         臂1: 1/2/3/4   臂2: 5/6/7/8   臂3: 9/10/11/12   臂4: 13~16   臂5: 17~20
 *   21~25 臂级  压力传感器 + IMU 共用（同一 device_id，按话题/data_type 区分），臂号 = device_id - 20
 */

export const AXES_PER_ARM = 4;
export const ARM_LEVEL_BASE = 20;

export type AxisParameterName = "rotation" | "swing" | "telescopic";

/** J1/J2/J4 在臂内的偏移（J3 空置 = 3） */
const AXIS_OFFSETS: Record<AxisParameterName, number> = {
  rotation: 1,
  swing: 2,
  telescopic: 4,
};

/**
 * 由数据库 Unit_ID 推算臂号（1~5）。
 * 种子数据：一号臂=32、二号臂=64、三号臂=96（每臂 +32）；无法识别时按一号臂兜底。
 */
export function armIndexFromUnitId(unitId: number): number {
  const id = Number(unitId || 0);
  if (id > 0 && id % 32 === 0) {
    return Math.min(Math.floor(id / 32), 5);
  }
  return 1;
}

/** 某臂某轴的 device_id，如 armIndex=3、rotation → 9 */
export function axisDeviceId(armIndex: number, parameter: AxisParameterName): number {
  return (armIndex - 1) * AXES_PER_ARM + AXIS_OFFSETS[parameter];
}

/** 某臂臂级传感器（压力/IMU 共用）的 device_id，臂1 → 21 */
export function armLevelDeviceId(armIndex: number): number {
  return ARM_LEVEL_BASE + armIndex;
}
