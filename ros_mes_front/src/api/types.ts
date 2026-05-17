// 接口响应基础结构
export interface ApiResponse<T = any> {
	code: number;
	message: string;
	data: T;
}

// 登录相关
export interface LoginForm {
	username: string;
	password: string;
}

export interface LoginResponse {
	access_token: string;
	token_type: string;
}

// 用户信息相关
export interface UserInfo {
	id: number;
	username: string;
	role: string;
	email: string;
	phone: string;
	avatar: string;
	status: number;
	lastLogin: string;
	createdAt: string;
}

// 硬件相关
// 微调相关
export interface FineTuningItem {
	id: number;
	Device_ID: number;
	DeviceAddress?: number;
	Devicedescript?: string;
	parameterName: string;
	oldValue: number;
	newValue: number;
	adjustedBy: string;
	adjustedAt: string;
}

export interface FineTuningConfigItem {
	id: number;
	moduleId: number;
	deviceId: number;
	configJson: string;
	savedBy: string;
	createdAt: string;
}

// 图纸管理相关
export interface DrawingItem {
	drawingId: number;
	drawingName: string;
	drawingDescription: string;
	drawingFile: string;
	creatorId: number;
	createTime: string;
	modifyTime: string;
	latestVersionId: number | null;
	delFlag: boolean;
	notes: string;
}

export interface DrawingVersionItem {
	versionId: number;
	drawingId: number;
	drawingFile: string;
	creatorId: number;
	createTime: string;
	modifyId: number | null;
	modifyTime: string;
	delFlag: boolean;
	notes: string;
}

export interface DrawingFileContent {
	content: string;
	fullLength: number;
	truncated: boolean;
}

// 图纸信息表单
export interface DrawingForm {
	drawingId?: number;
	drawingName: string;
	drawingDescription: string;
	notes?: string;
}

// 仪表盘统计
export interface DashboardStatItem {
	label: string;
	value: string | number;
	unit: string;
	trend: number;
}

export interface DashboardStats {
	deviceStatus: DashboardStatItem;
	taskCount: DashboardStatItem;
	faultCount: DashboardStatItem;
	onlineUsers: DashboardStatItem;
	responseTime: DashboardStatItem;
	concurrency: DashboardStatItem;
	deviceConnections: DashboardStatItem;
}

// 工作管理相关
export interface WorkItem {
	Work_ID: number;
	Workname: string;
	WorkDescript: string;
	Drawing_ID: number | null;
	Device_id: number | null;
	unit_id: number | null;
	sensor_id: number | null;
	data: string;
	creater_id: number;
	Createtime: string;
	Modifytime: string;
	del_flag: boolean;
	Notes: string;
}

// 工作流相关
export interface WorkflowItem {
	Workflow_ID: number;
	Workflowname: string;
	WorkflowDescript: string;
	creater_id: number;
	Createtime: string;
	Modifytime: string;
	del_flag: boolean;
	Notes: string;
	work_count?: number;
	works?: WorkItem[];
}

export interface WorkflowDetail extends WorkflowItem {
	works: (WorkItem & { flow_seq: number })[];
}

// 任务管理相关
export interface TaskItem {
	Task_ID: number;
	Taskname: string;
	Taskdescripte: string;
	Workflow_ID: number | null;
	Drawing_ID: number | null;
	creater_id: number;
	Createtime: string;
	TaskAssignment_id: number | null;
	Status: string;
	Modifytime: string;
	del_flag: boolean;
	Notes: string;
	DrawingName?: string;
	WorkflowName?: string;
	AssigneeName?: string;
	WorksSubset?: WorkSubsetItem[];
}

export interface WorkSubsetItem {
	Work_ID: number;
	Workname: string;
	WorkDescript: string;
	flow_seq: number;
}

export interface TaskTracingItem {
	TasksTracing_ID: number;
	Task_ID: number;
	operate_type: number;
	Workflow_ID: number;
	operater_ID: number;
	operate_time: string;
	Notes: string;
	OperatorName?: string;
}

export interface TaskForm {
	Taskname: string;
	Taskdescripte?: string;
	Workflow_ID?: number | null;
	Drawing_ID?: number | null;
	TaskAssignment_id?: number | null;
	Notes?: string;
}
