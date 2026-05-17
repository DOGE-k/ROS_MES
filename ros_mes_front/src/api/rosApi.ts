import request from '../utils/request';
import type {
	ApiResponse,
	DashboardStats,
	DrawingFileContent,
	DrawingForm,
	DrawingItem,
	FineTuningConfigItem,
	FineTuningItem,
	LoginForm,
	LoginResponse,
	TaskForm,
	TaskItem,
	TaskTracingItem,
	UserInfo,
	WorkItem,
	WorkSubsetItem,
	WorkflowItem,
	WorkflowDetail
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

export function getUserListApi(params?: { keyword?: string; type_id?: number }) {
	return request<any, ApiResponse<UserInfo[]>>({
		url: '/user/',
		method: 'get',
		params
	});
}

// ==================== 硬件管理 ====================
// ==================== 微调管理 ====================
export function getFineTuningList(params?: { device_id?: number }) {
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
	module_id?: number;
	device_id?: number;
	unit_id?: number;
	unit_row_id?: number;
	drawing_id?: number;
	moduleId?: number;
	deviceId?: number;
	configJson?: string;
	savedBy?: string;
	devices?: any[];
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

// ==================== 串口连接测试 ====================
export function testSerialConnection() {
	return request<any, ApiResponse<{ success: boolean; connected: boolean; message: string; bytes_received?: number }>>({
		url: '/control/serial_test',
		method: 'get'
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

// ==================== 仪表盘 ====================
export function getDashboardStats() {
	return request<any, ApiResponse<DashboardStats>>({
		url: '/dashboard/stats',
		method: 'get'
	});
}

// ==================== 工作管理 ====================
export function createWorkApi(data: {
	Workname: string;
	WorkDescript?: string;
	Drawing_ID?: number | null;
	Device_id?: number | null;
	unit_id?: number | null;
	sensor_id?: number | null;
	data?: string;
	Notes?: string;
}) {
	return request<any, ApiResponse<WorkItem>>({
		url: '/work/create',
		method: 'post',
		params: data
	});
}

export function getWorkListApi(params?: { keyword?: string }) {
	return request<any, ApiResponse<WorkItem[]>>({
		url: '/work/list',
		method: 'get',
		params
	});
}

export function updateWorkApi(workId: number, data: {
	Workname?: string;
	WorkDescript?: string;
	Drawing_ID?: number | null;
	Device_id?: number | null;
	unit_id?: number | null;
	sensor_id?: number | null;
	data?: string;
	Notes?: string;
}) {
	return request<any, ApiResponse<WorkItem>>({
		url: `/work/${workId}`,
		method: 'put',
		params: data
	});
}

export function deleteWorkApi(workId: number) {
	return request<any, ApiResponse<null>>({
		url: `/work/${workId}`,
		method: 'delete'
	});
}

// ==================== 工作流管理 ====================
export function createWorkflowApi(data: {
	Workflowname: string;
	WorkflowDescript?: string;
	Notes?: string;
	work_ids: string;
}) {
	return request<any, ApiResponse<WorkflowItem>>({
		url: '/workflow/create',
		method: 'post',
		params: data
	});
}

export function getWorkflowListApi() {
	return request<any, ApiResponse<WorkflowItem[]>>({
		url: '/workflow/list',
		method: 'get'
	});
}

export function getWorkflowDetailApi(workflowId: number) {
	return request<any, ApiResponse<WorkflowDetail>>({
		url: `/workflow/${workflowId}`,
		method: 'get'
	});
}

export function updateWorkflowApi(workflowId: number, data: {
	Workflowname?: string;
	WorkflowDescript?: string;
	Notes?: string;
	work_ids?: string;
}) {
	return request<any, ApiResponse<WorkflowItem>>({
		url: `/workflow/${workflowId}`,
		method: 'put',
		params: data
	});
}

export function deleteWorkflowApi(workflowId: number) {
	return request<any, ApiResponse<null>>({
		url: `/workflow/${workflowId}`,
		method: 'delete'
	});
}

// ==================== 任务管理 ====================
export function getTaskListApi(params?: {
	keyword?: string;
	status?: string;
	drawing_id?: number;
	workflow_id?: number;
}) {
	return request<any, ApiResponse<TaskItem[]>>({
		url: '/task/list',
		method: 'get',
		params
	});
}

export function getTaskDetailApi(taskId: number) {
	return request<any, ApiResponse<TaskItem>>({
		url: `/task/${taskId}`,
		method: 'get'
	});
}

export function createTaskApi(data: TaskForm) {
	return request<any, ApiResponse<TaskItem>>({
		url: '/task/create',
		method: 'post',
		data
	});
}

export function updateTaskApi(taskId: number, data: Partial<TaskForm>) {
	return request<any, ApiResponse<TaskItem>>({
		url: `/task/${taskId}`,
		method: 'put',
		data
	});
}

export function deleteTaskApi(taskId: number) {
	return request<any, ApiResponse<null>>({
		url: `/task/${taskId}`,
		method: 'delete'
	});
}

export function startTaskApi(taskId: number) {
	return request<any, ApiResponse<TaskItem>>({
		url: `/task/${taskId}/start`,
		method: 'post'
	});
}

export function pauseTaskApi(taskId: number) {
	return request<any, ApiResponse<TaskItem>>({
		url: `/task/${taskId}/pause`,
		method: 'post'
	});
}

export function resumeTaskApi(taskId: number) {
	return request<any, ApiResponse<TaskItem>>({
		url: `/task/${taskId}/resume`,
		method: 'post'
	});
}

export function finishTaskApi(taskId: number) {
	return request<any, ApiResponse<TaskItem>>({
		url: `/task/${taskId}/finish`,
		method: 'post'
	});
}

export function dispatchTaskApi(taskId: number) {
	return request<any, ApiResponse<TaskItem>>({
		url: `/task/${taskId}/dispatch`,
		method: 'post'
	});
}

export function getTaskTracingApi(taskId: number) {
	return request<any, ApiResponse<TaskTracingItem[]>>({
		url: `/task/${taskId}/tracing`,
		method: 'get'
	});
}

export function addTaskProgressApi(taskId: number, data: { Notes: string }) {
	return request<any, ApiResponse<TaskTracingItem>>({
		url: `/task/${taskId}/progress`,
		method: 'post',
		data
	});
}

export function getTaskWorksApi(taskId: number) {
	return request<any, ApiResponse<WorkSubsetItem[]>>({
		url: `/task/${taskId}/works`,
		method: 'get'
	});
}

// ==================== 设备树（四层结构：型号→模块→机械臂→传感器） ====================
export interface TreeNode {
	id: string;
	label: string;
	type: 'model' | 'device' | 'unit' | 'sensor';
	raw_id: number;
	arm_type?: number;
	sensor_type?: number;
	device_id?: number;
	children?: TreeNode[];
}

export function getDeviceTreeApi() {
	return request<any, ApiResponse<TreeNode[]>>({
		url: '/model/tree',
		method: 'get'
	});
}

// ==================== 型号 CRUD ====================
export function getModelListApi() {
	return request<any, ApiResponse<any[]>>({
		url: '/model/',
		method: 'get'
	});
}

export function getModelApi(id: number) {
	return request<any, ApiResponse<any>>({
		url: `/model/${id}`,
		method: 'get'
	});
}

export function createModelApi(data: { Modelname: string; Modeldescripte?: string; Notes?: string }) {
	return request<any, ApiResponse<any>>({
		url: '/model/',
		method: 'post',
		data
	});
}

export function updateModelApi(id: number, data: { Modelname?: string; Modeldescripte?: string; Notes?: string }) {
	return request<any, ApiResponse<any>>({
		url: `/model/${id}`,
		method: 'put',
		data
	});
}

export function deleteModelApi(id: number) {
	return request<any, ApiResponse<any>>({
		url: `/model/${id}`,
		method: 'delete'
	});
}

// ==================== 模块(Device) CRUD ====================
export function getDeviceListApi() {
	return request<any, ApiResponse<any[]>>({
		url: '/device/',
		method: 'get'
	});
}

export function getDevicesByModelApi(modelId: number) {
	return request<any, ApiResponse<any[]>>({
		url: `/device/by_model/${modelId}`,
		method: 'get'
	});
}

export function getDeviceApi(id: number) {
	return request<any, ApiResponse<any>>({
		url: `/device/${id}`,
		method: 'get'
	});
}

export function createDeviceApi(data: { Model_ID: number; DeviceAddress: number; Devicedescript?: string; Notes?: string }) {
	return request<any, ApiResponse<any>>({
		url: '/device/',
		method: 'post',
		data
	});
}

export function updateDeviceApi(id: number, data: { Model_ID?: number; DeviceAddress?: number; Devicedescript?: string; Notes?: string }) {
	return request<any, ApiResponse<any>>({
		url: `/device/${id}`,
		method: 'put',
		data
	});
}

export function deleteDeviceApi(id: number) {
	return request<any, ApiResponse<any>>({
		url: `/device/${id}`,
		method: 'delete'
	});
}

// ==================== 机械臂(Unit) CRUD ====================
export function getUnitListApi() {
	return request<any, ApiResponse<any[]>>({
		url: '/unit/',
		method: 'get'
	});
}

export function getUnitsByDeviceApi(deviceId: number) {
	return request<any, ApiResponse<any[]>>({
		url: `/unit/by_device/${deviceId}`,
		method: 'get'
	});
}

export function getUnitApi(id: number) {
	return request<any, ApiResponse<any>>({
		url: `/unit/${id}`,
		method: 'get'
	});
}

export function createUnitApi(data: { Unit_ID: number; Device_ID: number; UnitDescript?: string; Notes?: string }) {
	return request<any, ApiResponse<any>>({
		url: '/unit/',
		method: 'post',
		data
	});
}

export function updateUnitApi(id: number, data: { Device_ID?: number; UnitDescript?: string; Notes?: string }) {
	return request<any, ApiResponse<any>>({
		url: `/unit/${id}`,
		method: 'put',
		data
	});
}

export function deleteUnitApi(id: number) {
	return request<any, ApiResponse<any>>({
		url: `/unit/${id}`,
		method: 'delete'
	});
}

// ==================== 传感器(sensors) CRUD ====================
export function getSensorListApi() {
	return request<any, ApiResponse<any[]>>({
		url: '/sensors/',
		method: 'get'
	});
}

export function getSensorApi(id: number) {
	return request<any, ApiResponse<any>>({
		url: `/sensors/${id}`,
		method: 'get'
	});
}

export function createSensorApi(data: { sensor_ID: number; Device_ID: number; Unit_ID: number; unit_row_id: number; sensordescript?: string; Unit_address: number; IsRead?: number; Notes?: string }) {
	return request<any, ApiResponse<any>>({
		url: '/sensors/',
		method: 'post',
		data
	});
}

export function getSensorsByUnitApi(unitId: number) {
	return request<any, ApiResponse<any[]>>({
		url: `/sensors/by_unit/${unitId}`,
		method: 'get'
	});
}

export function updateSensorApi(id: number, data: { sensor_ID?: number; Device_ID?: number; Unit_ID?: number; unit_row_id?: number; sensordescript?: string; Unit_address?: number; IsRead?: number; Notes?: string }) {
	return request<any, ApiResponse<any>>({
		url: `/sensors/${id}`,
		method: 'put',
		data
	});
}

export function deleteSensorApi(id: number) {
	return request<any, ApiResponse<any>>({
		url: `/sensors/${id}`,
		method: 'delete'
	});
}
