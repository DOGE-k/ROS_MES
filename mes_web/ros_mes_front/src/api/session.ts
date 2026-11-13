import request from '@/utils/request';

// 微调会话记录：握手成功后由后端登记，续接只读记录，不发送模块确认或运动指令。
export type ControlSessionReason =
  | 'closed'
  | 'superseded'
  | 'connection_changed'
  | 'expired'
  | 'missing'
  | null;

export interface ControlSession {
  id: string;
  module_id: number;
  device_id: number | null;
  x: number | null;
  y: number | null;
  seg: number;
  unit_ids: number[];
  connection_revision: number | null;
  creator_id: number;
  created_at: string | null;
  last_active_at: string | null;
  expires_at: string | null;
  invalidated_at: string | null;
  invalid_reason: string | null;
}

export interface ControlSessionState {
  session: ControlSession | null;
  latest: ControlSession | null;
  reason: ControlSessionReason;
  connection_revision?: number | null;
}

export interface ControlSessionResume {
  valid: boolean;
  reason: ControlSessionReason;
  session: ControlSession | null;
  connection_revision?: number | null;
}

export const SESSION_REASON_LABELS: Record<string, string> = {
  closed: '已结束',
  superseded: '已被新的握手取代',
  connection_changed: '连接设置已变更',
  expired: '已超过保持时长',
  missing: '没有可续接的记录',
};

const ttlParams = (ttlSeconds: number | null) =>
  ttlSeconds === null ? {} : { ttl_seconds: ttlSeconds };

export const getControlSession = (ttlSeconds: number | null) =>
  request<any, { data: ControlSessionState }>({
    url: '/control/session',
    method: 'get',
    params: ttlParams(ttlSeconds),
  });

export const resumeControlSession = (sessionId: string, ttlSeconds: number | null) =>
  request<any, { data: ControlSessionResume }>({
    url: `/control/session/${encodeURIComponent(sessionId)}/resume`,
    method: 'post',
    data: ttlSeconds === null ? {} : { ttl_seconds: ttlSeconds },
  });

export const closeControlSession = (sessionId: string) =>
  request<any, { data: ControlSession }>({
    url: `/control/session/${encodeURIComponent(sessionId)}/close`,
    method: 'post',
  });
