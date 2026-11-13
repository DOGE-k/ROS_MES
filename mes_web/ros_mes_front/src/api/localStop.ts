import request from '@/utils/request';

// 局部停：按范围分级（模块 / 整台机械臂 / 单轴），只锁目标，不动全局急停联锁。
export type LocalStopScope = 'module' | 'arm' | 'axis';

export interface LocalStopHold {
  id: number;
  mode: string;
  scope: LocalStopScope;
  module_id: number;
  device_id: number | null;
  state: string;
  message: string | null;
  created_at: string | null;
  cleared_at: string | null;
  cleared_reason: string | null;
  active: boolean;
}

export interface LocalStopResult {
  code: number;
  message: string;
  data: LocalStopHold & { simulated: boolean; connection_revision?: number | null };
}

export interface LocalStopHoldList {
  mode: string;
  holds: LocalStopHold[];
  connection_revision?: number | null;
}

export const requestLocalStop = (payload: {
  scope: LocalStopScope;
  module_id: number;
  device_id?: number;
  connection_revision?: number | null;
}) => request<any, LocalStopResult>({ url: '/control/stop', method: 'post', data: payload });

export const getLocalStopHolds = () =>
  request<any, { data: LocalStopHoldList }>({ url: '/control/stop/holds', method: 'get' });

export const clearLocalStopHolds = (moduleId: number) =>
  request<any, { data: { module_id: number; cleared: number } }>({
    url: '/control/stop/clear',
    method: 'post',
    params: { module_id: moduleId },
  });
