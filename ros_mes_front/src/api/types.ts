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

/** 登录响应 data —— 字段与《ROS_MES_前后端接口字段文档》5.1（POST /api/login）一致 */
export interface LoginResponse {
	account: string;
	name: string;
	typeId: number;
	token: string;
	tokenType: string;
	headImage: string;
	updateTime: string;
}

// 用户信息相关
/** 用户列表/详情行 —— 字段与《ROS_MES_前后端接口字段文档》9.1（后端 user_to_dict）一致 */
export interface UserItem {
	id: number;
	account: string;
	username: string;
	name: string | null;
	typeId: number;
	typeLabel: string;
	headImage: string;
	isLock: boolean;
	birthday: string | null;
	sex: number | null;
	creatorId: number;
	createtime: string;
	locktime: string | null;
	modifytime: string | null;
	delFlag: boolean;
	notes: string | null;
}

// 硬件相关
// 微调相关
export interface FineTuningItem {
	id: number;
	module_id: number;
	unit_id: number;
	module_address?: number | null;
	module_descript?: string | null;
	parameter_name: string;
	old_value?: number | null;
	new_value: number;
	creater_id: number;
	create_time?: string | null;
	notes?: string | null;
	del_flag: boolean;
}

export interface FineTuningConfigItem {
	id: number;
	module_id: number;
	unit_id: number;
	sensor_id: number;
	config: Record<string, any>;
	creater_id: number;
	create_time?: string | null;
	notes?: string | null;
	del_flag: boolean;
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
	Module_ID: number | null;
	Device_id?: number | null;
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
