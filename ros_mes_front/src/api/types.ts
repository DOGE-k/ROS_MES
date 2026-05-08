//统一规定 前端和后端约定的数据格式
export interface ApiResponse<T = any> {
  code: number;
  message: string;
  data: T;
}

export interface RosStatus {
  robot_status: string;
  battery: number | null;
  node: string;
}

export interface HardwareItem {
  id: number;
  name: string;
  device_id: number;
  type?: string;
  status?: string;
  description?: string;
}

export interface HardwareCreatePayload {
  name: string;
  device_id: number;
  type?: string;
  description?: string;
}

export interface ModuleCreatePayload {
  module_id: number;
  x: number;
  y: number;
  device_id?: number;
  position?: number;
}

export interface CoordinationPayload {
  module_id: number;
  device_id: number;
  x: number;
  y: number;
  z: number;
}

export interface FineTuningPayload {
  module_id: number;
  device_id: number;
  position: string;
}

export interface DrawingItem {
  id: number;
  name: string;
  filePath: string | null;
  jsonData: string | null;
  createdAt: string | null;
  updatedAt: string | null;
}