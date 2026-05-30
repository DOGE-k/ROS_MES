# ROS MES 前后端开发文档

本文档用于说明 ROS MES 系统的前后端结构、运行方式、路由机制、接口通信方式以及后端 API 清单。文档面向两类读者：

- 项目答辩、评审人员：了解系统整体架构和核心实现思路。
- 后续开发或第三方前端开发人员：根据后端 API 自行设计和实现前端页面。

## 1. 项目结构

项目根目录：

```text
ROS_MES/
├─ ros_mes_front/          # 前端项目，Vue 3 + TypeScript + Vite
├─ ros_mes_hou/            # 后端项目，FastAPI + SQLAlchemy + SQLite
├─ robot_control_backend/  # 机器人控制相关后端模块
├─ ros_database.db         # SQLite 数据库文件
├─ sqlite_create.py        # 数据库初始化脚本
└─ docs/                   # 项目文档
```

前端主要目录：

```text
ros_mes_front/src/
├─ main.ts                 # 前端入口，挂载 Vue、Router、Pinia、Element Plus
├─ App.vue                 # 根组件，提供第一层 router-view
├─ router/                 # 前端路由配置
├─ components/             # 页面和业务组件
├─ api/                    # 前端 API 方法封装
├─ utils/request.ts        # axios 实例、请求拦截、响应拦截
└─ stores/                 # Pinia 状态管理
```

后端主要目录：

```text
ros_mes_hou/app/
├─ main.py                 # FastAPI 应用入口
├─ api/
│  ├─ api.py               # 汇总注册所有接口路由
│  ├─ deps.py              # 登录认证依赖
│  └─ endpoints/           # 各业务模块接口
├─ core/                   # 配置与安全模块
├─ db/                     # 数据库连接、模型、迁移
├─ schemas/                # Pydantic 请求/响应模型
├─ crud/                   # 数据库 CRUD 封装
└─ services/               # ROS、串口、调度等服务逻辑
```

## 2. 技术栈

前端：

- Vue 3
- TypeScript
- Vite
- Vue Router
- Pinia
- Element Plus
- Axios
- ECharts

后端：

- FastAPI
- Uvicorn
- SQLAlchemy
- SQLite
- Pydantic
- python-jose JWT
- passlib/bcrypt
- WebSocket

## 3. 本地运行

### 3.1 启动后端

进入后端目录：

```bash
cd ros_mes_hou
```

激活虚拟环境：

```powershell
.\venv\Scripts\activate
```

安装依赖：

```bash
pip install -r requirements.txt
```

启动服务：

```bash
uvicorn app.main:app --reload
```

如果遇到本机 Python/OpenSSL 兼容问题，也可以使用项目提供的兼容启动脚本：

```bash
python start_server.py
```

后端默认监听：

```text
http://127.0.0.1:8000
```

FastAPI 自动文档地址：

```text
http://127.0.0.1:8000/docs
```

### 3.2 生成数据库

数据库文件位于项目根目录：

```text
ROS_MES/ros_database.db
```

数据库结构和初始数据以项目根目录的 `sqlite_create.py` 为准。首次部署、数据库结构调整后重建数据库，或需要恢复默认初始数据时，在项目根目录执行：

```powershell
python sqlite_create.py
```

执行成功后会生成或更新：

```text
ros_database.db
```

注意：

- 生成数据库前，先关闭后端服务和正在占用数据库的 SQLite 可视化工具。
- 如果要完全重新生成数据库，可以先删除旧的 `ros_database.db`，再执行 `python sqlite_create.py`。
- 后端启动时的 `models.Base.metadata.create_all(bind=engine)` 只负责创建缺失的表，不会执行 `sqlite_create.py` 中的初始数据插入逻辑。
- 后端连接的默认数据库路径在 `ros_mes_hou/app/core/config.py` 中配置，默认指向项目根目录的 `ros_database.db`。
- 当前设计不再使用旧的 `Model`、`Device` 表；型号类型和模块分别以 `Type`、`Module` 表为准。

推荐顺序：

```powershell
cd D:\university\competition\ROS_MES_System\2.0\ROS_MES
python sqlite_create.py
cd ros_mes_hou
.\venv\Scripts\activate
uvicorn app.main:app --reload
```

### 3.3 启动前端

进入前端目录：

```bash
cd ros_mes_front
```

安装依赖：

```bash
npm install
```

启动开发服务器：

```bash
npm run dev
```

前端默认监听：

```text
http://127.0.0.1:5173
```

生产构建：

```bash
npm run build
```

当前前端构建工具链固定为：

```text
vite 6.3.5
@vitejs/plugin-vue 5.2.4
```

构建完成后会生成 `dist/` 目录，正式部署和交付应以 `npm run build` 生成的最新产物为准。

前端开发环境后端地址配置在：

```text
ros_mes_front/.env.development
```

当前配置：

```env
VITE_API_TARGET=http://127.0.0.1:8000
```

## 4. 前端路由实现

前端路由使用 Vue Router。

入口文件 `src/main.ts` 中注册路由：

```ts
createApp(App).use(router).use(ElementPlus).use(pinia).mount('#app')
```

路由实例在 `src/router/index.ts` 中创建：

```ts
const router = createRouter({
  history: createWebHistory(),
  routes,
});
```

路由表在 `src/router/routes.ts` 中定义。系统使用两层页面结构：

- `/login`、`/register` 等登录注册页面直接渲染到 `App.vue` 的 `<router-view/>`。
- `/Dashboard`、`/TaskManagement`、`/UserManagement` 等业务页面作为 `/` 的子路由，先进入 `MainPage.vue` 布局，再渲染到 `MainPage.vue` 内部的 `<router-view/>`。

示例：

```ts
{
  path: '/',
  name: 'Main',
  component: MainPage,
  redirect: '/Dashboard',
  children: [
    {
      path: '/Dashboard',
      name: 'Dashboard',
      component: DashboardPage,
      meta: { activeMenu: '/Dashboard' }
    }
  ]
}
```

## 5. 侧边栏跳转机制

侧边栏组件为：

```text
src/components/Main/AsidePage.vue
```

Element Plus 菜单项的 `index` 就是目标路由路径：

```vue
<el-menu-item index="/Dashboard">...</el-menu-item>
<el-menu-item index="/TaskManagement">...</el-menu-item>
<el-menu-item index="/UserManagement">...</el-menu-item>
```

点击菜单后触发 `select` 事件：

```vue
<el-menu @select="handleMenuSelect">
```

跳转逻辑：

```js
const handleMenuSelect = (index) => {
  router.push(index);
};
```

完整流程：

```text
用户点击侧边栏按钮
-> Element Plus 读取 el-menu-item 的 index
-> 调用 handleMenuSelect(index)
-> router.push(index)
-> Vue Router 在 routes.ts 中匹配 path
-> 渲染对应页面组件到 router-view
```

菜单高亮由当前路由决定：

```js
const activeMenu = computed(() => {
  return route.meta?.activeMenu || route.path
});
```

如果一个页面不在侧边栏中，也可以通过 `meta.activeMenu` 指定高亮哪个菜单。例如微调页面 `/FineTuningPage` 高亮 `/ModuleManagement`。

## 6. 前后端通信机制

前端统一使用 `src/utils/request.ts` 中的 axios 实例。

```ts
const service = axios.create({
  baseURL: "/api",
  timeout: 15000,
  headers: {
    "Content-Type": "application/json;charset=utf-8",
  },
});
```

前端业务 API 写在 `src/api/rosApi.ts` 中。例如：

```ts
export function getTaskListApi() {
  return request({
    url: '/task/list',
    method: 'get'
  });
}
```

因为 axios 的 `baseURL` 是 `/api`，所以实际请求地址是：

```text
/api/task/list
```

开发环境下 Vite 代理会把 `/api` 请求转发到后端：

```ts
proxy: {
  "/api": {
    target: env.VITE_API_TARGET || "http://127.0.0.1:8000",
    changeOrigin: true,
    ws: true,
  },
}
```

因此浏览器请求：

```text
http://127.0.0.1:5173/api/task/list
```

实际被转发到：

```text
http://127.0.0.1:8000/api/task/list
```

## 7. 登录认证

登录接口：

```text
POST /api/login
```

登录成功后，后端返回 JWT token。前端将 token 保存到 `localStorage`：

```text
token
account
nickname
role
avatar
updateTime
```

前端路由守卫会检查 token：

```ts
if (!token) {
  return "/login";
}
```

请求拦截器会为非白名单接口添加认证头：

```http
Authorization: Bearer <token>
```

后端通过 `app/api/deps.py` 中的 `get_current_user` 解析 token，验证当前用户身份。

## 8. 后端架构

后端入口为 `app/main.py`。

```py
app = FastAPI(title=settings.PROJECT_NAME, openapi_url=f"{settings.API_STR}/openapi.json")
app.include_router(api_router, prefix=settings.API_STR)
```

统一接口前缀由 `app/core/config.py` 配置：

```py
API_STR = "/api"
```

所有接口最终都以 `/api` 开头。

路由汇总文件为 `app/api/api.py`：

```py
api_router.include_router(login.router, tags=["login"])
api_router.include_router(user.router, prefix="/user", tags=["user"])
api_router.include_router(task.router, prefix="/task", tags=["task"])
api_router.include_router(model_api.router, prefix="/model", tags=["model"])
```

数据库连接在 `app/db/database.py`：

```py
engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

默认数据库为项目根目录下的 SQLite 文件：

```text
ros_database.db
```

## 9. 通用响应格式

大部分接口返回格式：

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {}
}
```

列表接口通常返回：

```json
{
  "code": 200,
  "message": "查询成功",
  "data": []
}
```

认证失败时，后端通常返回 HTTP 401，前端会清除本地 token 并跳转登录页。

## 10. 后端 API 接口清单

说明：

- 接口基地址：`http://127.0.0.1:8000`
- 所有 HTTP 接口统一带 `/api` 前缀。
- “需认证”表示请求头需要携带 `Authorization: Bearer <token>`。
- 文件上传接口使用 `multipart/form-data`。
- WebSocket 地址开发环境通常为 `ws://127.0.0.1:8000/...`。

### 10.1 登录与注册

| 方法 | 路径 | 需认证 | 参数 | 说明 |
|---|---|---:|---|---|
| POST | `/api/login` | 否 | form: `username`, `password` | 登录，返回用户信息和 JWT token |
| POST | `/api/register` | 否 | JSON: `username`, `password` | 注册普通用户 |

登录请求示例：

```http
POST /api/login
Content-Type: application/x-www-form-urlencoded

username=admin&password=123456
```

登录响应示例：

```json
{
  "code": 200,
  "message": "登录成功",
  "data": {
    "account": "admin",
    "name": "admin",
    "typeId": 1,
    "token": "jwt-token",
    "tokenType": "bearer",
    "headImage": "",
    "updateTime": "2026-05-27T00:00:00"
  }
}
```

### 10.2 用户管理

| 方法 | 路径 | 需认证 | 参数 | 说明 |
|---|---|---:|---|---|
| GET | `/api/user/me` | 是 | 无 | 获取当前登录用户信息，前端 `getUserInfoApi()` 使用该接口 |
| GET | `/api/user/` | 是 | query: `keyword`, `type_id` | 查询用户列表 |
| POST | `/api/user/` | 是 | JSON: `username`, `password`, `type_id`, `name` | 新增用户 |
| POST | `/api/user/password` | 是 | JSON: `old_password`, `new_password` | 修改当前用户密码 |
| POST | `/api/user/avatar` | 是 | form-data: `file` | 上传头像 |
| PUT | `/api/user/profile/me` | 是 | JSON: `name`, `birthday`, `sex`, `type_id` | 修改当前用户资料 |
| PUT | `/api/user/{user_id}` | 是 | JSON: `username`, `type_id`, `password`, `name` | 修改指定用户 |
| DELETE | `/api/user/{user_id}` | 是 | path: `user_id` | 删除用户 |
| PUT | `/api/user/{user_id}/lock` | 是 | path: `user_id` | 锁定用户 |
| PUT | `/api/user/{user_id}/unlock` | 是 | path: `user_id` | 解锁用户 |
| PUT | `/api/user/{user_id}/role` | 是 | JSON: `type_id` | 修改用户角色 |
| POST | `/api/user/import` | 是 | form-data: `file` | 批量导入用户 |
| GET | `/api/user/export` | 是 | 无 | 导出用户数据 |

### 10.3 仪表盘

| 方法 | 路径 | 需认证 | 参数 | 说明 |
|---|---|---:|---|---|
| GET | `/api/dashboard/stats` | 否 | 无 | 获取首页统计数据 |

### 10.4 型号类型 Type（兼容 `/api/model` 路径）

说明：当前数据库设计以 `sqlite_create.py` 为准，不再使用旧的 `Model` 表。为减少前端改动，后端保留 `/api/model` 路径，但实际读写的是 `Type` 表；响应中会同时返回兼容字段 `Model_ID`、`Modelname`，以及真实字段 `Type_ID`、`Typename`。

| 方法 | 路径 | 需认证 | 参数 | 说明 |
|---|---|---:|---|---|
| GET | `/api/model/` | 否 | 无 | 查询型号类型列表，数据来源为 `Type` |
| GET | `/api/model/tree` | 否 | 无 | 查询型号类型-模块-机械臂-传感器树；数据来源为 `Type`、`Module`、`Unit`、`sensors` |
| GET | `/api/model/{model_id}` | 否 | path: `model_id`（对应 `Type.Type_ID`） | 查询型号类型详情 |
| POST | `/api/model/` | 否 | JSON: `Modelname`, `Modeldescripte`, `Notes`（映射到 `Typename`, `Typedescripte`, `Notes`） | 新增型号类型 |
| PUT | `/api/model/{model_id}` | 否 | JSON: `Modelname`, `Modeldescripte`, `Notes` | 修改型号类型 |
| DELETE | `/api/model/{model_id}` | 否 | path: `model_id`（对应 `Type.Type_ID`） | 删除型号类型 |

### 10.5 模块 Module（兼容 `/api/device` 路径）

说明：当前数据库设计不再使用旧的 `Device` 表。为减少前端改动，后端保留 `/api/device` 路径，但实际读写的是 `Module` 表；响应中会同时返回兼容字段 `Device_ID`、`Model_ID`、`DeviceAddress`、`Devicedescript`，以及真实字段 `Module_ID`、`Type_ID`、`ModuleAddress`、`Moduledescript`。

| 方法 | 路径 | 需认证 | 参数 | 说明 |
|---|---|---:|---|---|
| GET | `/api/device/` | 否 | 无 | 查询模块列表，数据来源为 `Module` |
| GET | `/api/device/by_model/{model_id}` | 否 | path: `model_id`（对应 `Type.Type_ID`） | 按型号类型查询模块 |
| GET | `/api/device/{device_id}` | 否 | path: `device_id`（对应 `Module.Module_ID`） | 查询模块详情 |
| POST | `/api/device/` | 否 | JSON: `Model_ID`, `DeviceAddress`, `Devicedescript`, `Notes`（映射到 `Type_ID`, `ModuleAddress`, `Moduledescript`, `Notes`） | 新增模块 |
| PUT | `/api/device/{device_id}` | 否 | JSON: `Model_ID`, `DeviceAddress`, `Devicedescript`, `Notes` | 修改模块 |
| DELETE | `/api/device/{device_id}` | 否 | path: `device_id`（对应 `Module.Module_ID`） | 删除模块 |

### 10.6 机械臂 Unit

| 方法 | 路径 | 需认证 | 参数 | 说明 |
|---|---|---:|---|---|
| GET | `/api/unit/` | 否 | 无 | 查询机械臂列表 |
| GET | `/api/unit/by_device/{device_id}` | 否 | path: `device_id`（当前按 `Module_ID` 查询，保留旧路径名兼容前端封装） | 按模块查询机械臂 |
| GET | `/api/unit/{unit_id}` | 否 | path: `unit_id` | 查询机械臂详情 |
| POST | `/api/unit/` | 否 | JSON: `Unit_ID`, `Module_ID`, `UnitDescript`, `Notes`（兼容旧字段 `Device_ID`） | 新增机械臂 |
| PUT | `/api/unit/{unit_id}` | 否 | JSON: `Module_ID`, `UnitDescript`, `Notes`（兼容旧字段 `Device_ID`） | 修改机械臂 |
| DELETE | `/api/unit/{unit_id}` | 否 | path: `unit_id` | 删除机械臂 |

### 10.7 传感器 Sensors

| 方法 | 路径 | 需认证 | 参数 | 说明 |
|---|---|---:|---|---|
| GET | `/api/sensors/` | 否 | 无 | 查询传感器列表 |
| GET | `/api/sensors/by_unit/{unit_id}` | 否 | path: `unit_id` | 按机械臂查询传感器 |
| GET | `/api/sensors/{sensor_id}` | 否 | path: `sensor_id` | 查询传感器详情 |
| POST | `/api/sensors/` | 否 | JSON: `sensor_ID`, `Module_ID`, `Unit_ID`, `Unit_address`, `IsRead`, `sensordescript`, `Notes`（兼容旧字段 `Device_ID`、`unit_row_id`） | 新增传感器 |
| PUT | `/api/sensors/{sensor_id}` | 否 | JSON: 同新增字段，可选 | 修改传感器 |
| DELETE | `/api/sensors/{sensor_id}` | 否 | path: `sensor_id` | 删除传感器 |

### 10.8 图纸 Drawing

| 方法 | 路径 | 需认证 | 参数 | 说明 |
|---|---|---:|---|---|
| GET | `/api/drawing/` | 是 | 无 | 查询图纸列表 |
| GET | `/api/drawing/{drawing_id}` | 是 | path: `drawing_id` | 查询图纸详情 |
| GET | `/api/drawing/{drawing_id}/versions` | 是 | path: `drawing_id` | 查询图纸版本 |
| GET | `/api/drawing/{drawing_id}/file` | 是 | path: `drawing_id` | 获取图纸文件内容 |
| POST | `/api/drawing/import` | 是 | form-data: `drawing_name`, `drawing_description`, `drawing_id`, `file` | 导入图纸 |
| PUT | `/api/drawing/{drawing_id}` | 是 | form-data: `drawing_name`, `drawing_description`, `notes` | 修改图纸信息 |
| DELETE | `/api/drawing/{drawing_id}` | 是 | path: `drawing_id` | 删除图纸 |

### 10.9 工作 Work

| 方法 | 路径 | 需认证 | 参数 | 说明 |
|---|---|---:|---|---|
| POST | `/api/work/create` | 是 | query: `Workname`, `WorkDescript`, `Drawing_ID`, `Module_ID`, `unit_id`, `sensor_id`, `data`, `Notes`（兼容旧字段 `Device_id`） | 新增工序/工作项 |
| GET | `/api/work/list` | 是 | query: `keyword` | 查询工作项列表 |
| PUT | `/api/work/{work_id}` | 是 | query: 工作项字段 | 修改工作项 |
| DELETE | `/api/work/{work_id}` | 是 | path: `work_id` | 删除工作项 |

### 10.10 工作流 Workflow

| 方法 | 路径 | 需认证 | 参数 | 说明 |
|---|---|---:|---|---|
| POST | `/api/workflow/create` | 是 | query: `Workflowname`, `WorkflowDescript`, `Notes`, `work_ids` | 新增工作流 |
| GET | `/api/workflow/list` | 是 | 无 | 查询工作流列表 |
| GET | `/api/workflow/{workflow_id}` | 是 | path: `workflow_id` | 查询工作流详情 |
| PUT | `/api/workflow/{workflow_id}` | 是 | query: `Workflowname`, `WorkflowDescript`, `Notes`, `work_ids` | 修改工作流 |
| DELETE | `/api/workflow/{workflow_id}` | 是 | path: `workflow_id` | 删除工作流 |

### 10.11 任务 Task

| 方法 | 路径 | 需认证 | 参数 | 说明 |
|---|---|---:|---|---|
| POST | `/api/task/create` | 是 | JSON: 任务字段 | 新增任务 |
| GET | `/api/task/list` | 是 | query: `keyword`, `status`, `drawing_id`, `workflow_id` | 查询任务列表 |
| GET | `/api/task/{task_id}` | 是 | path: `task_id` | 查询任务详情 |
| PUT | `/api/task/{task_id}` | 是 | JSON: 任务字段 | 修改任务 |
| DELETE | `/api/task/{task_id}` | 是 | path: `task_id` | 删除任务 |
| POST | `/api/task/{task_id}/start` | 是 | path: `task_id` | 开始任务 |
| POST | `/api/task/{task_id}/pause` | 是 | path: `task_id` | 暂停任务 |
| POST | `/api/task/{task_id}/resume` | 是 | path: `task_id` | 恢复任务 |
| POST | `/api/task/{task_id}/finish` | 是 | path: `task_id` | 完成任务 |
| POST | `/api/task/{task_id}/dispatch` | 是 | path: `task_id` | 下发任务 |
| GET | `/api/task/{task_id}/tracing` | 是 | path: `task_id` | 查询任务执行记录 |
| GET | `/api/task/{task_id}/works` | 是 | path: `task_id` | 查询任务关联工作项 |
| POST | `/api/task/{task_id}/progress` | 是 | JSON: `Notes` | 新增任务进度记录 |

### 10.12 微调 FineTuning

微调相关数据库表以项目根目录 `sqlite_create.py` 的建表语句为准：

- `fine_tuning`：微调记录表。字段使用 `module_id`、`unit_id` 关联 `Unit(Module_ID, Unit_ID)`，用于记录某个模块下某个机械臂的微调操作历史，包括参数名、旧值、新值、操作者和时间。
- `fine_tuning_config`：微调配置表。字段使用 `module_id`、`unit_id`、`sensor_id`，其中 `(module_id, sensor_id)` 关联 `sensors(Module_ID, sensor_ID)`，`config_json` 保存微调页面配置 JSON。

说明：后端 ORM、schema 和接口字段需要与 `sqlite_create.py` 保持一致；如果发现字段命名不一致，应优先按 `sqlite_create.py` 对齐。

| 方法 | 路径 | 需认证 | 参数 | 说明 |
|---|---|---:|---|---|
| POST | `/api/finetuning/` | 否 | JSON: `module_id`, `unit_id`, `device_id`, `position`, `parameter_name`, `old_value`, `new_value` | 新增微调记录 |
| GET | `/api/finetuning/` | 否 | query: `skip`, `limit`, `module_id`, `unit_id` | 查询微调记录，直接返回记录数组 |
| POST | `/api/finetuning/config` | 否 | JSON: `module_id`, `unit_id`, `sensor_id`, `drawing_id`, `devices` | 保存微调配置 |
| POST | `/api/control/finetuning` | 否 | JSON: 微调下发数据 | 向 ROS/下位机下发微调指令 |
| WS | `/api/control/feedback/ws` | 否 | WebSocket | 微调反馈数据流 |

微调下发请求示例：

```json
{
  "module_id": 17,
  "device_id": 33,
  "unit_id": 32,
  "parameter_name": "rotation",
  "position": 10.5
}
```

### 10.13 控制 Control

| 方法 | 路径 | 需认证 | 参数 | 说明 |
|---|---|---:|---|---|
| GET | `/api/control/serial_test` | 是 | 无 | 串口连接测试 |
| GET | `/api/control/hardware/realtime` | 是 | 无 | 获取实时硬件状态 |
| POST | `/api/control/emergency_stop` | 是 | 无 | 触发急停 |

### 10.14 坐标协调 Coordination

| 方法 | 路径 | 需认证 | 参数 | 说明 |
|---|---|---:|---|---|
| GET | `/api/coordination/views/{view_name}` | 否 | path: `view_name` | 获取点云视图 |
| POST | `/api/coordination/send` | 否 | JSON: 坐标/图纸下发数据 | 下发坐标协调任务 |

### 10.15 模块下发 Module

| 方法 | 路径 | 需认证 | 参数 | 说明 |
|---|---|---:|---|---|
| POST | `/api/module/` | 否 | JSON: 模块锁定和下发数据 | 锁定并下发模块数据 |

### 10.16 ROS 测试

| 方法 | 路径 | 需认证 | 参数 | 说明 |
|---|---|---:|---|---|
| GET | `/api/ros/send_ros` | 否 | query: `msg` | 发送 ROS 测试消息，前端 `sendRosMessage(msg)` 使用该接口 |
| GET | `/api/ros/get_ros_status` | 否 | 无 | 获取 ROS 状态，前端 `getRosStatus()` 使用该接口 |

### 10.17 WebSocket

| 类型 | 路径 | 参数 | 说明 |
|---|---|---|---|
| WS | `/api/control/feedback/ws` | 无 | 微调/硬件反馈流 |
| WS | `/api/ws/ws/robot_status` | query: `token` | 机器人状态流 |

说明：`ws_stream.py` 内部路由为 `/ws/robot_status`，在 `api.py` 中又挂载到 `/ws` 前缀下，因此完整路径为 `/api/ws/ws/robot_status`。

## 11. 第三方前端对接建议

如果其他人只根据后端接口设计前端，建议按以下步骤对接：

1. 先调用 `POST /api/login` 获取 token。
2. 将 token 存储在前端本地状态中。
3. 对需要认证的接口统一添加请求头：

```http
Authorization: Bearer <token>
```

4. 统一封装请求函数，处理以下情况：
   - HTTP 401：登录过期，跳转登录页。
   - HTTP 403：权限不足。
   - 非 2xx：展示后端返回的 `detail` 或 `message`。
5. 文件上传接口使用 `multipart/form-data`。
6. WebSocket 如果需要认证，按接口说明通过 query 参数传入 token。

## 12. 常见开发任务

### 12.1 新增前端页面

1. 在 `src/components/Main/` 下新建页面组件。
2. 在 `src/router/routes.ts` 中引入组件并添加路由。
3. 如需侧边栏入口，在 `AsidePage.vue` 中新增 `el-menu-item`。
4. 如果页面需要请求后端，在 `src/api/rosApi.ts` 中新增 API 方法。

### 12.2 新增后端接口

1. 在 `app/api/endpoints/` 中选择或新增模块文件。
2. 使用 `APIRouter` 定义接口。
3. 如需数据库，添加 `db: Session = Depends(get_db)`。
4. 如需登录认证，添加 `current_user = Depends(get_current_user)`。
5. 在 `app/api/api.py` 中注册路由模块。
6. 在前端 API 封装中添加对应请求方法。

### 12.3 新增数据库字段

1. 修改 `app/db/models.py` 中的 SQLAlchemy 模型。
2. 修改项目根目录 `sqlite_create.py` 中对应表的建表语句，保证新环境初始化数据库时包含新字段。
3. 修改对应 `schemas/` 中的 Pydantic 模型。
4. 修改 CRUD 或 endpoint 逻辑。
5. 如已有数据库，需要编写迁移逻辑或手动更新 SQLite 表结构。
6. 更新相关接口文档或测试用例。

## 13. 调试与注意事项

### 13.1 NO ROS 调试模式

前端 `.env.development` 中存在：

```env
VITE_DEBUG_NO_ROS=true
```

开启后，部分模块下发、图纸列表、设备列表、微调等功能会使用前端模拟数据，不直接依赖 ROS 后端。

### 13.2 前端模拟数据

项目中保留了 `VITE_USE_MOCK` 配置，用于早期无后端时的模拟开发：

```env
VITE_USE_MOCK=true
```

当前项目主要使用 `VITE_DEBUG_NO_ROS` 进行无 ROS 环境调试。它会在前端模拟设备、图纸、模块下发、坐标下发和微调相关数据，便于在未连接 ROS 或下位机时调试页面流程。

正式联调和交付时建议关闭模拟配置，使用真实后端和 ROS 环境。

### 13.3 编码问题

当前部分源码注释和中文字符串显示为乱码，可能是历史编码不一致导致。开发时建议：

- 新增文件统一使用 UTF-8。
- 修改旧文件前先确认编辑器编码。
- 文档、接口字段、正式展示文案尽量保持 UTF-8。

### 13.4 接口文档校验

第三方前端对接前，建议通过 FastAPI 自动文档确认接口路径、请求方法、参数和响应结构：

```text
http://127.0.0.1:8000/docs
```

## 14. 核心流程图

### 14.1 前端页面跳转

```mermaid
flowchart LR
  A[点击侧边栏菜单] --> B[读取 el-menu-item index]
  B --> C[router.push(index)]
  C --> D[Vue Router 匹配 routes.ts]
  D --> E[渲染页面组件到 router-view]
```

### 14.2 前后端请求

```mermaid
flowchart LR
  A[前端页面] --> B[api/rosApi.ts]
  B --> C[utils/request.ts axios]
  C --> D[Vite 代理 /api]
  D --> E[FastAPI /api 路由]
  E --> F[endpoint]
  F --> G[数据库/ROS/业务服务]
```

### 14.3 登录认证

```mermaid
flowchart LR
  A[POST /api/login] --> B[后端验证账号密码]
  B --> C[生成 JWT token]
  C --> D[前端保存 token]
  D --> E[后续请求携带 Authorization]
  E --> F[后端 get_current_user 校验 token]
```
