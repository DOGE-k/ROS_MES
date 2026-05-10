import request from '../utils/request';
import type {
	ApiResponse,
	DrawingFileContent,
	DrawingForm,
	DrawingItem,
	FineTuningConfigItem,
	FineTuningItem,
	HardwareItem,
	LoginForm,
	LoginResponse,
	UserInfo
} from './types';

// ==================== 登录 ====================
export function loginApi(data: LoginForm) {
	return request<any, ApiResponse<LoginResponse>>({
		url: '/login',
		method: 'post',
		data: new URLSearchParams({
			username: data.username,
			password: data.password
		}).toString(),
		headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
	});
}

// ==================== 用户信息 ====================
export function getUserInfoApi() {
	return request<any, ApiResponse<UserInfo>>({
		url: '/user/info',
		method: 'get'
	});
}

// ==================== 硬件管理 ====================
export function getHardwareList(params?: { type?: string; status?: string }) {
	return request<any, ApiResponse<HardwareItem[]>>({
		url: '/hardware/',
		method: 'get',
		params
	});
}

export function getHardwareDetail(id: number) {
	return request<any, ApiResponse<HardwareItem>>({
		url: `/hardware/${id}`,
		method: 'get'
	});
}

export function createHardware(data: Partial<HardwareItem>) {
	return request<any, ApiResponse<HardwareItem>>({
		url: '/hardware/',
		method: 'post',
		data
	});
}

export function updateHardware(id: number, data: Partial<HardwareItem>) {
	return request<any, ApiResponse<HardwareItem>>({
		url: `/hardware/${id}`,
		method: 'put',
		data
	});
}

export function deleteHardware(id: number) {
	return request<any, ApiResponse<null>>({
		url: `/hardware/${id}`,
		method: 'delete'
	});
}

// ==================== 微调管理 ====================
export function getFineTuningList(params?: { hardwareId?: number }) {
	return request<any, ApiResponse<FineTuningItem[]>>({
		url: '/finetuning/',
		method: 'get',
		params
	});
}

export function createFineTuning(data: Partial<FineTuningItem>) {
	return request<any, ApiResponse<FineTuningItem>>({
		url: '/finetuning/',
		method: 'post',
		data
	});
}

export function getFineTuningHistory() {
	return request<any, ApiResponse<FineTuningItem[]>>({
		url: '/finetuning/',
		method: 'get'
	});
}

export function saveFineTuningConfigApi(data: {
	moduleId: number;
	deviceId: number;
	configJson: string;
	savedBy?: string;
}) {
	return request<any, ApiResponse<FineTuningConfigItem>>({
		url: '/finetuning/config',
		method: 'post',
		data
	});
}

export function getFineTuningConfig(params: { moduleId?: number; deviceId?: number }) {
	return request<any, ApiResponse<FineTuningConfigItem[]>>({
		url: '/finetuning/config',
		method: 'get',
		params
	});
}

// ==================== ROS 测试页面 ====================
export function sendRosMessage(data: any) {
	return request<any, ApiResponse<any>>({
		url: '/ros/send',
		method: 'post',
		data
	});
}

export function getRosStatus() {
	return request<any, ApiResponse<any>>({
		url: '/ros/status',
		method: 'get'
	});
}

// ==================== 模块管理 ====================
export function createModule(data: any) {
	return request<any, ApiResponse<any>>({
		url: '/module/',
		method: 'post',
		data
	});
}

// ==================== 坐标协调 ====================
export function sendCoordinate(data: any) {
	return request<any, ApiResponse<any>>({
		url: '/coordination/send',
		method: 'post',
		data
	});
}

// ==================== 微调控制 ====================
export function sendFineTuning(data: any) {
	return request<any, ApiResponse<any>>({
		url: '/control/finetuning',
		method: 'post',
		data
	});
}

export const sendCoordination = sendCoordinate;

export const saveFineTuningConfig = saveFineTuningConfigApi;

// ==================== 图纸管理 ====================
export function getDrawingListApi(params?: Record<string, any>) {
	return request<any, ApiResponse<DrawingItem[]>>({
		url: '/drawing/',
		method: 'get',
		params
	});
}

export function getDrawingDetailApi(drawingId: number) {
	return request<any, ApiResponse<DrawingItem>>({
		url: `/drawing/${drawingId}`,
		method: 'get'
	});
}

export function getDrawingFileContentApi(drawingId: number) {
	return request<any, ApiResponse<DrawingFileContent>>({
		url: `/drawing/${drawingId}/file`,
		method: 'get'
	});
}

export function importDrawingApi(formData: FormData) {
	return request<any, ApiResponse<DrawingItem>>({
		url: '/drawing/import',
		method: 'post',
		data: formData
	});
}

export function updateDrawingApi(drawingId: number, formData: FormData) {
	return request<any, ApiResponse<DrawingItem>>({
		url: `/drawing/${drawingId}`,
		method: 'put',
		data: formData
	});
}

export function deleteDrawingApi(drawingId: number) {
	return request<any, ApiResponse<null>>({
		url: `/drawing/${drawingId}`,
		method: 'delete'
	});
}
