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
export interface HardwareItem {
	id: number;
	name: string;
	type: string;
	status: string;
	ipAddress: string;
	description: string;
	updatedAt: string;
}

// 微调相关
export interface FineTuningItem {
	id: number;
	hardwareId: number;
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
