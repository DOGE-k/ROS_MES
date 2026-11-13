import request from '@/utils/request';

export type ConnectionMode = 'real' | 'mock';
export interface ConnectionSettings {
  revision: number;
  ros_mode: ConnectionMode;
  drawing_mode: ConnectionMode | 'skip';
  emergency_mode: ConnectionMode;
  finetuning_preflight_enabled: boolean;
  ros_url: string;
  drawing_ros_url: string;
  emergency_ros_url: string;
  pointcloud_url: string;
}

export const getConnectionSettings = () => request<any, { data: ConnectionSettings }>({ url: '/control/debug-settings', method: 'get' });
export const changeConnectionSettings = (expected_revision: number, changes: Partial<ConnectionSettings>) =>
  request<any, { data: ConnectionSettings }>({ url: '/control/debug-settings', method: 'patch', data: { expected_revision, changes } });
