import request from "@/utils/request";
import { mockSuccess, useMock } from "./mock";
import type {
  ApiResponse,
  RosStatus,
  HardwareItem,
  HardwareCreatePayload,
  ModuleCreatePayload,
  CoordinationPayload,
  FineTuningPayload,
  DrawingItem,
} from "./types";

let mockHardwareList: any[] = [
  {
    id: 1,
    device_id: 1,
    hardware_id: 1,
    name: "机械臂 A",
    hardware_name: "机械臂 A",
    type: "机械臂",
    hardware_type: "机械臂",
    status: "normal",
    description: "六轴机械臂",
    specification: "六轴机械臂",
    updated_at: new Date().toLocaleString(),
    create_time: new Date().toLocaleString(),
  },
  {
    id: 2,
    device_id: 2,
    hardware_id: 2,
    name: "压力传感器 A",
    hardware_name: "压力传感器 A",
    type: "压力传感器",
    hardware_type: "压力传感器",
    status: "normal",
    description: "标准压力传感器",
    specification: "标准压力传感器",
    updated_at: new Date().toLocaleString(),
    create_time: new Date().toLocaleString(),
  },
];

export function getHardwareList(): Promise<ApiResponse<any[]>> {
  if (useMock) {
    return mockSuccess(mockHardwareList, "获取硬件列表成功");
  }

  return request.get("/hardware/");
}

export function createHardware(data: any): Promise<ApiResponse<any>> {
  if (useMock) {
    const deviceId = Number(data.device_id ?? data.hardware_id ?? Date.now());

    const item = {
      id: deviceId,
      device_id: deviceId,
      hardware_id: deviceId,
      name: data.name || data.hardware_name || "未命名硬件",
      hardware_name: data.hardware_name || data.name || "未命名硬件",
      type: data.type || data.hardware_type || "机械臂",
      hardware_type: data.hardware_type || data.type || "机械臂",
      status: data.status || "normal",
      description: data.description || data.specification || "",
      specification: data.specification || data.description || "",
      updated_at: new Date().toLocaleString(),
      create_time: new Date().toLocaleString(),
    };

    mockHardwareList.push(item);

    return mockSuccess(item, "新增硬件成功");
  }

  return request.post("/hardware/", data);
}

export function deleteHardware(id: number | string): Promise<ApiResponse> {
  if (useMock) {
    mockHardwareList = mockHardwareList.filter(
      (item) =>
        String(item.id) !== String(id) &&
        String(item.device_id) !== String(id) &&
        String(item.hardware_id) !== String(id)
    );

    return mockSuccess({ id }, "删除硬件成功");
  }

  return request.delete(`/hardware/${id}`);
}

export function sendRosMessage(msg: string): Promise<ApiResponse> {
  if (useMock) {
    return mockSuccess(
      {
        msg,
        topic: "/web_cmd",
      },
      `已模拟发送到 ROS：${msg}`
    );
  }

  return request.get("/send_ros", {
    params: { msg },
  });
}

export function getRosStatus(): Promise<ApiResponse<RosStatus>> {
  if (useMock) {
    return mockSuccess({
      robot_status: "running",
      battery: 85,
      node: "ros_mock_node",
    });
  }

  return request.get("/get_ros_status");
}



export function createModule(data: ModuleCreatePayload): Promise<ApiResponse> {
  if (useMock) {
    return mockSuccess(data, "模块创建成功，已模拟下发 ROS");
  }

  return request.post("/module/", data);
}

export function sendCoordination(data: CoordinationPayload): Promise<ApiResponse> {
  if (useMock) {
    return mockSuccess(data, "坐标已模拟下发 ROS");
  }

  return request.post("/coordination/", data);
}

export function sendFineTuning(data: FineTuningPayload): Promise<ApiResponse> {
  if (useMock) {
    return mockSuccess(data, `微调指令 ${data.position} 已模拟发送`);
  }

  return request.post("/finetuning/", data);
}

// 保存微调配置
export function saveFineTuningConfig(data: any): Promise<ApiResponse> {
  if (useMock) {
    return mockSuccess(data, "配置保存成功");
  }

  return request.post("/finetuning/config", data);
}

// ========== 图纸管理 API ==========

let mockDrawingList: any[] = [
  { id: 1, name: "机械臂底座点云图", filePath: null, jsonData: '{"points": 1024, "resolution": "0.01mm"}', createdAt: "2026-05-01 10:00:00", updatedAt: null },
  { id: 2, name: "夹具装配点云图", filePath: null, jsonData: '{"points": 2048, "resolution": "0.005mm", "format": "pcd"}', createdAt: "2026-05-03 14:30:00", updatedAt: null },
];

export function getDrawingList(): Promise<ApiResponse<DrawingItem[]>> {
  if (useMock) {
    return mockSuccess(mockDrawingList, "获取图纸列表成功");
  }
  return request.get("/drawing/");
}

export function getDrawingDetail(id: number): Promise<ApiResponse<DrawingItem>> {
  if (useMock) {
    const item = mockDrawingList.find(d => d.id === id);
    return mockSuccess(item || null, item ? "获取图纸详情成功" : "图纸不存在");
  }
  return request.get(`/drawing/${id}`);
}

export function createDrawing(formData: FormData): Promise<ApiResponse<DrawingItem>> {
  if (useMock) {
    const name = formData.get("name") as string;
    const jsonData = formData.get("json_data") as string;
    const newItem = {
      id: Date.now(),
      name,
      filePath: null,
      jsonData,
      createdAt: new Date().toLocaleString(),
      updatedAt: null,
    };
    mockDrawingList.unshift(newItem);
    return mockSuccess(newItem, "上传图纸成功");
  }
  return request.post("/drawing/", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
}

export function updateDrawing(id: number, formData: FormData): Promise<ApiResponse<DrawingItem>> {
  if (useMock) {
    const item = mockDrawingList.find(d => d.id === id);
    if (item) {
      const name = formData.get("name") as string;
      const jsonData = formData.get("json_data") as string;
      if (name) item.name = name;
      if (jsonData) item.jsonData = jsonData;
      item.updatedAt = new Date().toLocaleString();
    }
    return mockSuccess(item, "更新图纸成功");
  }
  return request.put(`/drawing/${id}`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
}

export function deleteDrawing(id: number): Promise<ApiResponse> {
  if (useMock) {
    mockDrawingList = mockDrawingList.filter(d => d.id !== id);
    return mockSuccess({ id }, "删除图纸成功");
  }
  return request.delete(`/drawing/${id}`);
}