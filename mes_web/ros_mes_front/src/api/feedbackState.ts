export const FEEDBACK_FIELDS = [
  'rotation', 'swing', 'telescopic', 'pressure',
  'swing_angle', 'rotation_angle', 'x', 'y', 'z',
] as const;
export type FeedbackField = typeof FEEDBACK_FIELDS[number];
export type FeedbackStatus = 'waiting' | 'current' | 'history' | 'stale' | 'simulated';
export type FeedbackMark = { receivedAt: number | null; historical: boolean };

export function emptyFeedbackMarks(): Record<FeedbackField, FeedbackMark> {
  return Object.fromEntries(FEEDBACK_FIELDS.map(key => [key, { receivedAt: null, historical: false }])) as Record<FeedbackField, FeedbackMark>;
}

export function finiteFeedbackNumber(value: unknown): number | null {
  if (typeof value !== 'number' && typeof value !== 'string') return null;
  if (typeof value === 'string' && !value.trim()) return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

export function feedbackTimeouts(env: Record<string, unknown>) {
  const milliseconds = (key: string, fallback: number) => {
    const value = finiteFeedbackNumber(env[key]);
    return value !== null && value >= 100 ? value : fallback;
  };
  // 显示新鲜度策略，不代表硬件发布周期或故障判断；现场可分别调整。
  return {
    axis: milliseconds('VITE_ROS_AXIS_STALE_MS', 5000),
    pressure: milliseconds('VITE_ROS_PRESSURE_STALE_MS', 10000),
    imu: milliseconds('VITE_ROS_IMU_STALE_MS', 5000),
  };
}

export function feedbackStatus(mark: FeedbackMark, now: number, timeout: number, connected: boolean, simulated: boolean): FeedbackStatus {
  if (mark.receivedAt === null) return 'waiting';
  if (simulated) return 'simulated';
  if (mark.historical) return 'history';
  if (!connected || now - mark.receivedAt >= timeout) return 'stale';
  return 'current';
}

export const FEEDBACK_STATUS_LABELS: Record<FeedbackStatus, string> = {
  waiting: '等待反馈', current: '实时反馈', history: '历史缓存 · 等待新反馈',
  stale: '数据已过期', simulated: '模拟数据',
};
