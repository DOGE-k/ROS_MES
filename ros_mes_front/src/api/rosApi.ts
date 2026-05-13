import request from '../utils/request';
import type {
	ApiResponse,
	DashboardStats,
	DrawingFileContent,
	DrawingForm,
	DrawingItem,
	FineTuningConfigItem,
	FineTuningItem,
	HardwareItem,
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
