# ROS_MES 前后端改动记录（交接日志）

> 参照 ROS 侧的记录方式：**边改边记录，一事一条**，状态标注、未定事项打 `???`、详情交叉引用到对应文档，便于随时交接。
>
> **记录规则：**
> - 每次改动前后端代码/文档，在本文件新增一条（新日期写在最上面）
> - 状态标注：（已完成）/（进行中）/（未做）/（暂缓，写明理由）
> - 未定事项、待确认事项用 `???` 开头
> - 具体内容不在这里展开的，注明"见《文档名》章节"
> - 涉及 robot_control_backend（队友侧）的条目只作背景记录，不由本侧修改

---

## 2026-10-30（建库脚本 sqlite_create.py 移回仓库根）

- `mes_web/ros_mes_hou/sqlite_create.py` → 仓库根 `sqlite_create.py`（已完成，`git mv` 重命名追踪，脚本内容未改）
  - 理由：该脚本建的是仓库根的 `ros_database.db`（后端 `DATABASE_URL` 默认 `sqlite:///../../ros_database.db` 指向它），属于整个项目的库初始化，不是后端应用代码；`e1bfe9e` 目录重构前它本来就在仓库根，重构时被一并扫进了 `mes_web/ros_mes_hou/`
  - 脚本内 `_find_project_root()` 未改：从新位置向上第一层即命中 `.git`，`DB_PATH` 仍解析为仓库根，与后端 `app/core/config.py` 的 `PROJECT_ROOT` 判定一致；脚本仍独立可运行，只依赖后端 venv 里的 `passlib`，所以运行时继续用后端 venv 的 Python
  - 同步更新引用：`README.md`（目录表新增脚本一行、第 2 步命令改为 `.\mes_web\ros_mes_hou\venv\Scripts\python.exe .\sqlite_create.py`）、`deploy/deploy_windows.ps1:80`（`$dbScript` 改为 `ROS_MES\sqlite_create.py`）、`deploy/README_DEPLOY.md`（§2 改为在 `ROS_MES` 根执行）、《接口字段文档》§10 注明脚本在仓库根
- `???` 作废提示：2026-10-29 条目里"脚本方式可直接在 `mes_web/ros_mes_hou` 下执行 `python sqlite_create.py`"已不适用，改为在仓库根执行 `python sqlite_create.py`
- 验证：`py_compile sqlite_create.py` 通过；用后端 venv 导入脚本打印 `DB_PATH = D:\...\ROS_MES\ros_database.db`（存在，110,592 B，未被写入）；`git grep sqlite_create` 确认后端 `app/`、`tests/` 无引用，用例不受影响；`git diff --check` 通过（本地 venv 未装 pytest，未跑测试套件）

---

## 2026-10-29（部署文档数据库路径修正 + 工作区残留清理）

- 修正 `deploy/README_DEPLOY.md` §6 配置表中 `DATABASE_URL` 默认值：`sqlite:///../ros_database.db` → `sqlite:///../../ros_database.db`，与 `deploy/config/backend.env` 对齐；并在说明列注明该相对路径按**后端启动时的工作目录**解析，必须在 `mes_web/ros_mes_hou` 下启动 uvicorn（已完成）
  - 背景：旧值少一级，照表格手填 `mes_web/ros_mes_hou/.env` 时会连到 `mes_web/ros_database.db`（空库），`/api/device/` 返回空数组，模块管理页随即报"该坐标模块尚未在设备信息管理中登记，请先添加模块"——ROS 侧联调遇到的就是这个现象，不是前端代码未更新
  - 判别依据：`ModuleManagement.vue:128-134` 用 `DeviceAddress === x*16+y` 匹配设备（(1,1) → 17），卡片徽标显示"等待选择已登记模块"即表示设备列表无此行；`crud/device.py:6-7` 只返回 `del_flag=0` 的行
- 清理工作区残留（两者均被 `.gitignore` 忽略，不产生提交内容）：删除 `e1bfe9e` 目录重构后遗留的空目录 `ROS_MES/ros_mes_hou/`，以及旧 `DATABASE_URL` 相对路径误连产生的 0 字节空库 `mes_web/ros_database.db`；正式库仍为仓库根 `ros_database.db`（110,592 B，`Module_ID=17`、`Unit_ID=32/64/96`）（已完成）
- ??? ROS 侧若已按旧表格生成过 `mes_web/ros_database.db`，需自行删除该空文件并把 `.env` 的 `DATABASE_URL` 改为 `sqlite:///../../ros_database.db`，否则后端仍连空库；脚本方式可直接在 `mes_web/ros_mes_hou` 下执行 `python sqlite_create.py`（幂等，会补 `Module_ID=17` 与各臂 Unit/传感器）
- 验证：仅文档修改与工作区清理，无代码改动；`git diff --check` 通过

---

## 2026-10-28（模块选择与微调切换流程调整）

- 模块管理页恢复为只选择模块坐标，检查登记信息后导航；机械臂选择、握手和图纸下发统一放到微调页弹窗中。
- 首次弹窗可多选 1~5 台机械臂和一张图纸，先以 `unit_ids` 数组调用 `/module/` 完成批量确认，再为确认成功的每台机械臂调用 `/coordination/send` 下发同一张图纸。失败保留弹窗；重新下发当前机械臂图纸时不重复本次已成功的模块确认。
- 微调主页面常驻机械臂切换入口和图纸下发入口，只在本次确认成功的机械臂之间切换；切换机械臂不会再次弹出选择框，页面会恢复当前会话内各自的图纸、三视图和微调状态。请求中禁止切换目标，压力/IMU 与轴反馈按当前机械臂匹配。
- 业务命名、ROS `[100, seg, arm]` 及成功/失败回执不变；后端批量确认能力保留。此前“模块页多选机械臂”的界面安排作为历史记录，由本条取代。
- 验证：前端 `npm run build` 与 `git diff --check` 已通过；无 ROS 模拟不能证明 rosbridge、ROS 节点或真机/CAN 已联调。操作顺序见《ROS_MES_前后端ROS接口清单_三轴版_V2.1》§6.3。

---

## 2026-10-28（SQLite 启动数据库修复）

- 修复后端启动时报 `sqlite3.DatabaseError: database disk image is malformed`：仓库误跟踪的 `ros_database.db-wal`、`ros_database.db-shm` 与本地数据库主文件不一致，已移除版本控制并加入 `.gitignore`。
- 保留并核验主数据库 `ros_database.db`，`PRAGMA integrity_check` 返回 `ok`；当前本地数据为 `Module_ID=17`、`Unit_ID=32/64/96`。
- 修正部署模板 `DATABASE_URL`，从 `mes_web/ros_mes_hou/.env` 使用 `sqlite:///../../ros_database.db` 指向仓库根数据库。

---

## 2026-10-28（模块确认协议分层调整）

- 模块确认前后端业务层与 ROS 下行层分离（已完成）
  - 业务接口继续使用现有 `module_id`、`device_id`、`unit_id/unit_ids` 字段，移除现场不使用的 `station`；当时页面为先选模块和多个机械臂、后端逐个确认（该页面安排已被同日“模块选择与微调切换流程调整”取代）。
  - 后端新增显式 `ROS_MODULE_SEG_MAP` 配置，用于 `module_id → seg`；禁止把业务模块号直接猜作 ROS `seg`，缺少映射时拒绝下发。
  - 后端根据机械臂 `Unit_ID` 映射 ROS `arm=1~5`，向 `/control/module_cmd` 发送 `IntCmd`：`module_id` 原样透传、ROS `device_id=0`、`position=[100, seg, arm]`。
  - 成功/失败回执契约保持不变：成功 `/hardware/module_confirm_success` 的 `position=[100]`，失败 `/hardware/web_module_cmd` 的 `position=[1]`；模块号按业务 `module_id` 匹配。
  - 默认种子代码包含五臂 `Unit_ID=32/64/96/128/160`，部署数据库仍需实际核对；详见《ROS_MES_前后端ROS接口清单_三轴版_V2.1》§6、§7.2。

## 2026-10-25（八）

- 伸缩轴单位契约定稿：**话题边界两向均为 mm，后端零换算**（51 passed 全绿）
  - 经过：ROS 端负责人先口头说"单位 0.01mm"，前端一度按"话题线上 0.01mm"实现（下发 ×100 / 反馈 position_mm）；随后 ROS 端推送 3ed42f3《更新伸缩杆执行层逻辑》，核实 `TelescopicCmd.msg` 注释与节点源码后确认：**0.01mm 是 CAN/下位机层字段单位，ROS 节点内部完成换算，话题边界（下发 /control/adjust_telescopic_cmd、反馈 /hardware/telescope_feedback）两向均为 mm**
  - 结论：与前后端既有语义（伸缩 mm）天然一致，撤销 ×100 / position_mm 预实现；**MM_PER_REV 参数废弃**（ROS 节点不再做 mm↔角度换算）；前端 FineTuningPage 的 position_mm 优先逻辑保留为无害兼容（字段暂无则回退 position）
  - ROS 端同步变化：telescopic_node 增加基准保护（首帧反馈到达前拒绝增量累加）；0~30mm 软限位节点侧执行；超位回执 CmdAck（后端已订阅转发）
  - 交接：伸缩下发/显示今晚联调直接按 mm，无需任何换算

## 2026-10-25（七）

- 测试页通道统一走 rosbridge（ROS1/ROS2 行为一致）+ 同机部署 Python 指南（已完成，**51 passed 全绿**，双模式端到端冒烟通过）
  - 起因：ROS 端负责人将把前后端部署到 ROS 机器上同机自测（不走虚拟网络），而后端锁版依赖要求 Python ≥3.10，干净 venv 里没有 rospy——ROS1 模式的测试页 `send_ros` 原走 rospy 会 503
  - 修正：`_RosbridgeStatusWatcher` 迁入共用层，`/ros/**` 测试通道在 **ROS1/ROS2 两版统一经 rosbridge**（publish_web_cmd + /robot_status 状态订阅），rospy 原生通道降级为 ROS1 历史兼容（随 start_native_node 附带启动）；两份差异表同步更新（测试通道不再是差异项）
  - 冒烟：ROS1 模式（无 rospy 的 venv）send_ros 200 且 bridge 收到 /web_cmd、状态 ros_ready=true；ROS2 模式同通过
  - **同机部署 Python 指南**（已写入 deploy/README_DEPLOY.md）：Ubuntu 24.04（ROS2 机器）系统 Python 3.12 直接可用；Ubuntu 20.04（ROS1 机器）系统 Python 3.8 **不可用**，用 Miniconda/deadsnakes 建独立 3.10+ 环境，勿动系统 Python（Noetic 依赖）
  - 前端：RosTestPage 补工位号输入（station 必传契约的测试页落地），build 通过

## 2026-10-25（六）

- ROS2 测试页通道完成 + 前后端 ROS2 适配全面收口（已完成，**50 passed 全绿**，前端 build 通过，端到端冒烟通过）
  - **新增**：ROS2 适配器补齐测试通道（原任务收窄项）——`/api/ros/send_ros` 在 `ROS_VERSION=2` 下经 rosbridge 发布 `/web_cmd`（std_msgs/String JSON，与 ROS1 rospy 同契约）；`/api/ros/get_ros_status` 由后台常驻线程订阅 `/robot_status` 维护（断线 5s 自动重连，`test_data=true` 标记测试数据，无数据显示 unknown）；`main.py` 增加 shutdown 钩子结束后台连接；rosbridge 不可达时发送接口返回 503（ros.py 同时捕获 RosbridgeError）
  - **前端**：ModuleManagement 增加"工位号"选择（1~15，station 必传契约的 UI 落地），payload 随 `/module/` 下发
  - **端到端冒烟**（本机假 rosbridge，ROS_VERSION=2）：send_ros 200 且 bridge 收到 /web_cmd advertise+publish；连接中 get_ros_status 返回 `ros_ready=true` + 推送状态；杀掉 bridge 后 7s 内 `ros_ready=false`。三种场景全部符合"ROS 测试页接 ROS2"任务验收标准
  - **ROS2 适配就绪清单**：类型串 `pkg/msg/X`、stamp `sec/nanosec`、8 路反馈话题、模块确认握手（station）、急停/解除、测试页通道——全部走 `ROS_VERSION=2` 一键切换，前端除三轴编码外零改动
  - 挂起项不变：MM_PER_REV（等下位机）、大屏 robot_status 数据流（web_data_node 在 ROS 端 launch 中被注释）

## 2026-10-25（五）

- 与 ROS 端负责人确认最后两个待决项（沟通完成，结论已写入三轴版清单）
  - **图纸话题前缀**：ROS 端答复"按接口的来"——话题定为无前缀 `/frontend_pointcloud_topic`，ROS 端自行修正其 `rob_arm.env`；后端零改动，协议不一致②正式闭环。**联调时验证一次"图纸下发 → 三视图"链路**
  - **MM_PER_REV=0.7**：ROS 端确认换算还没测完、真实系数等下位机提供——前端"度→mm"反馈换算**挂起**。拿到真值后的动作（勿忘）：ROS 端改 `rob_arm.env` + `deploy/config/rob_arm.env` 两处，前端用同一系数加换算（三轴版清单 §7.5 已标注状态）

## 2026-10-25（四）

- 确认《三轴版 V2.1 接口清单》为 ROS 对接唯一权威，按文档收尾（已完成，**46 passed 全绿**）
  - **修正**：模块确认 station 改为 **`/module/` 请求体必传**（操作员选组 1~15，缺省 422），删除上一条目里"默认 station=module_id+1"的推导——文档 §7.2 明确由前端选择确认第几组，且 §7.6 确认 module_id 为业务模块号（与 SEG 不同空间），无 0~14 限制
  - **闭环**：协议不一致②（图纸话题）按清单定为无前缀 `/frontend_pointcloud_topic`，后端无需改；ROS 端 rob_arm.env 的 `/control` 前缀值与清单矛盾，待 ROS 端修正
  - **从 ROS 源码补全**（清单未给全的部分）：cmd_ack 枚举=仅超位拒绝（`ack_msg=1, result=3, detail=1上限/2下限`，无成功回执，三轴版清单 §4 已标注）；解除急停契约=发 `/control/softstop_release`（softstop_node 转发 [0x04]）
  - **新增**：`POST /api/control/emergency_stop/release`（急停解除，登录态）；种子数据补齐 5 臂（Unit_ID 128/160，延续每臂 +32；sensor_ID 同规律），`armIndexFromUnitId` 的 3 臂限制随之解除
  - **前端待办**：① 模块锁定页加"确认第几组"选择并把 `station` 带进 `/module/` 请求；② FineTuningPage 按 `cmd_ack`（result=3）提示超位拒绝；③ 伸缩 °→mm 换算（系数待 ROS 确认）
  - **仍待 ROS 端**：① rob_arm.env 图纸话题前缀修正；② MM_PER_REV 真实值（0.7 为假设值）；③（低优先）ROS2 移植时间表/包名/是否继续走 rosbridge
  - 文档结构决定：**不按 ROS1/ROS2 拆两份接口文档**（契约版本无关，双份必然漂移）；三轴版清单末尾新增"§8 ROS1/ROS2 差异速查表"（类型串/stamp 字段/原生通道/部署四项差异 + 对 ROS2 移植的契约要求），代码层差异真相在 `app/ros/profile.py`；部署文档等 ROS2 动工时再在 `deploy/` 单独成文

## 2026-10-25（三）

- 对齐《三轴版 V2.1 接口清单》（ROS 端三轴化，每臂 3 轴，轴号 1~15）（已完成，**45 passed 全绿**，前端 build 通过）
  - 文档已收录进 `docs/ROS_MES_前后端ROS接口清单_三轴版_V2.1.md`（取代旧接口文档的 ROS 部分，旧文档已加横幅）；清单 §7 各项处理状态见该文档标注
  - P0 模块确认：回执等待超时与普通超时分离，默认 35s（`ROS_MODULE_CONFIRM_ACK_WAIT_S`，对齐 ROS 端 30s 等宣告窗口，否则必然 502）
  - P0 三轴化：后端反馈标签表 `(臂-1)*3+关节`（臂1=1/2/3 … 臂5=13/14/15）、微调校验 1~15；前端 `deviceEncoding.ts` 同步（`AXES_PER_ARM=3`、偏移 `{1,2,3}`、臂级 21~25 不变）
  - P1 `/hardware/cmd_ack` 加入反馈流（`data_type=cmd_ack`，透传 `ack_msg/result/detail`）——超位拒绝不再静默丢失
  - **待办交接**：① 前端 ModuleManagement 需让操作员选"确认第几组"并传 `station`（7.2，后端已支持）；② 伸缩反馈 °→mm 换算（7.5，MM_PER_REV=0.7 是假设值，待 ROS 确认）；③ 种子数据仅 3 臂，`armIndexFromUnitId` 无法识别臂 4/5（7.3，需补种子或改映射）；④ 反馈 `module_id` 是 SEG 不是业务模块号（7.6，按 module_id 关联的逻辑会错）
  - **`???` 与 ROS 端核对**：图纸路径话题——三轴版清单写 `/frontend_pointcloud_topic`（无前缀），但已推送的 `rob_arm.env` 仍是 `/control/frontend_pointcloud_topic`，文档与源码矛盾，以哪边为准需 ROS 端确认（此前记录的协议不一致②仍未闭环）

## 2026-10-25（二）

- 整合远端 main（ROS 端 V2.1 更新）并适配新协议（已完成，**全套 40 passed 全绿**）
  - 远端新增：ROS 端会话式模块确认（`module_confirme_node.py` V2.1 + `UidAnnounce/SegAssign/SegConfirm.msg`）、`pressure_avg`/`vacuum_loss` 两路反馈话题、`can_event_log` 表（`sqlite_create.py`，合并时经重命名追踪自动落到 `mes_web/ros_mes_hou/`）
  - 旧路径 `rosbridge_gateway.py` 的远端改动（两路新话题）已移植进 `app/ros/`（profile 话题表 + normalizer 分支 + 反馈流订阅列表）
  - **模块确认契约变更（前端需配合）**：ROS 端 V2.1 要求 `position=[100, station]`，station=工位号 1~15，模块号=SEG=工位-1；后端默认 `station = module_id + 1`（module_id 须在 0~14），前端可在 `/module/` 请求体显式传 `station` 覆盖；`module_id=18` 这类越界值现在构造期就报 422。**前端 ModuleManagement 若下发 x*16+y 的大模块号会被拒，需和 ROS 端对齐模块号→工位映射**（`???` 待确认：前端 x*16+y 编码与 SEG 0~14 的对应关系）
  - 好消息：改动记录 2026-10-25（一）里的协议不一致①（失败码 -1 vs 1）**ROS 端已在 V2.1 修复**（`RESULT_FAILED = 1`）；不一致②（图纸话题 `/control` 前缀）仍未解决
- PR 评审与合并（已完成，合并后全套 43 passed 全绿）
  - **PR #4**（fulan0721：急停地址配置化 + 测试去盘符依赖）→ **已合并**（本地 merge 解决冲突后推送，GitHub 自动标记 merged，队友署名保留）：急停地址修复已被适配层等价实现（保持旧文件删除）；3 个急停新用例移植到 `RosbridgeClient`；`tools/verify_emergency_stop_config.py` 移入 `mes_web/ros_mes_hou/tools/` 并改用适配层接口；`test_coordination_payload` 去盘符改动自动应用、路径按新布局修正为向上 3 级
  - **PR #6**（czyhelp：ROS2 消息通道原型）→ **暂不合并**，已留评审意见：文件放错位置（根目录 vs `robot_control_backend/scripts/` 与 `mes_web/ros_mes_front/`）、个人 ZeroTier IP 硬编码、需基于最新 main（mes_web 重构 + V2.1 握手协议）重做；已向其说明 ROS2 接入后端侧已就绪（`ROS_VERSION=2` 切换即可）
  - 合并远端 main 时发现 ROS 端 V2.1 更新（见上一条），PR 评审基于新结构完成

## 2026-10-25（一）

- 仓库结构调整：前后端归入 `mes_web/`（已完成，全套 27 passed 全绿）
  - `ros_mes_front/`、`ros_mes_hou/` 整目录移入 `mes_web/`，与 `robot_control_backend/`（队友侧，未动）平级；`sqlite_create.py` 移入 `mes_web/ros_mes_hou/`；`ros_database.db` 仍在仓库根（本地文件，git 忽略）
  - 路径逻辑收敛到 `mes_web/ros_mes_hou/app/core/config.py`：新增 `BACKEND_ROOT` / `PROJECT_ROOT`（向上自动查找含 `robot_control_backend` 或 `.git` 的目录，可用环境变量 `PROJECT_ROOT` 覆盖）/ `ROS_SCRIPTS_DIR`（可用环境变量覆盖）；`ros_control.py`、`coordination.py`、`sqlite_create.py` 原先各自向上数层级拼路径的代码统一改为读配置
  - README / deploy 三份文件 / 接口字段文档 / 命名规范中的路径同步更新；`.gitignore` 增加 `.zcode/`
  - `???` 提醒：队友 pull 后需重新 `cd mes_web\ros_mes_hou` 激活 venv；deploy_windows.ps1 的路径约定是"仓库文件夹的上一级 + 显式 `ROS_MES\` 前缀"，未改变
- ROS1/ROS2 适配层拆分（已完成，**全套 35 passed 全绿**，原 27 + 新增 8）
  - 新建 `mes_web/ros_mes_hou/app/ros/`：`profile.py`（ROS1/ROS2 协议差异表：消息类型串 `pkg/X` vs `pkg/msg/X`、stamp 字段 `secs/nsecs` vs `sec/nanosec`、话题表支持 `ROS_TOPIC_<键名>` 环境变量覆盖）、`rosbridge.py`（共用传输层，原 `rosbridge_gateway.py` 泛化 + 急停收编，顺带消灭 `ros_control.py` 硬编码的 `ws://localhost:9010`）、`base.py`（适配器接口 + 子进程工具）、`normalizer.py`（原反馈归一化）、`ros1/`（rospy 原生通道由 `ros_service.py` 迁入）、`ros2/`（预设实现，ROS 端定稿后微调 profile 即可）
  - 工厂 `get_ros_dispatcher()` 读环境变量 `ROS_VERSION`（1/ros1/2/ros2，默认 1）返回适配器单例；端点默认参数改为 `dispatcher=None` 惰性解析，测试注入 DummyDispatcher 的方式不变；对外 API 路径/请求/响应零变化
  - 删除：`app/services/ros_dispatcher.py`（死代码）、`app/services/` 目录整体移除；`WEBSOCKET_URI` 死常量
  - 配置收口：`ROSBRIDGE_URL` 进入 `core/config.py`；`deploy/config/backend.env` 新增 `ROS_VERSION=1`
  - 文档：《接口字段文档》新增"第 12 节 ROS1/ROS2 适配说明"（差异表 + 附录文件索引更新）；README 增适配层说明
  - **记录未修的协议不一致（用户决定本次不修，待与 ROS 端确认）**：① 模块确认失败码——ROS 端 `module_confirme_node` 实际发布 `-1`（`RESULT_FAILED = -1`），后端沿用文档值只识别 `1`，真失败时会等超时而非立即报错；② 图纸路径话题——后端发 `/frontend_pointcloud_topic`，ROS 端 `rob_arm.env` 里 `ROS_TOPIC_FRONTEND_POINTCLOUD=/control/frontend_pointcloud_topic`（`data_process_node` 实际订阅值），文档写的也是无前缀版；两处不一致，需 ROS 端确认现网实际生效的话题后统一

## 2026-10-05（七）

- 文档目录整理（已完成）
  - 新建 `docs/`：4 份活文档移入（接口字段 / 命名规范 / 改动记录 / V1.1 修改清单）；`docs/archive/`：3 份归档（优化建议报告、UI改版预览.html、ROS_MES-v1.0版本代码.zip），均用 `git mv` 保留历史
  - 新增根 `README.md`（项目简介 / 启动方式 / 文档索引 / 分工说明）；`.gitignore` 补充 `.mimosa/`、`.zcodeignore`
  - 归档前已把《优化建议报告》全部未完成 📌 待办搬迁至本文件"后面版本考虑"，未丢项
  - `???` 提醒：交接日志位置变更为 `docs/ROS_MES_前后端改动记录.md`，此后在此更新

## 2026-10-05（六）

- 修复 4 个陈旧测试文件至 V1.1 预期（已完成，**全套 27 passed + 6 subtests 全绿**，此前 13 failed）
  - `test_rosbridge_gateway.py`：喂旧编码 33/41/42/43/49/50 → 改 V2 轴号（臂1 旋转=1/臂2 摆动=6/臂3 伸缩=12、臂级 21），标签断言加"臂N"前缀；新增 1 条用例覆盖"IMU 话题遇非臂级 device_id 回退 FEEDBACK_LABELS"分支
  - `test_control_finetuning_endpoint.py`：旧"请求 2 → 消息 33"换算断言 → V2 透传语义（请求 device_id 原样进消息），三参数分别用规范轴号 1/2/4
  - `test_finetuning_device_fields.py`：payload 补上 V1.1 必填的 module_id/unit_id；crud 签名 username → creater_id；自动参数名断言更新为 `module_18_unit_32_position`
  - `test_emergency_stop_payload.py`：旧载荷（module_id=17/device_id=1/position=[]）→ V2 系统级急停（module_id=0/device_id=0/position=[0x01]）
  - 结论：4 个文件均为断言过期，**未发现 v1.1 后端真 bug**；仅动 tests/，业务代码零改动

## 2026-10-05（五）

- 安全整改：修复 Mimosa 扫描 8 个高危中用户批准的 5 项（已完成，py_compile + 冒烟通过，pytest 无回归）
  - ① 命令注入 `ros_dispatcher.py:53`：`shell=True` → `shlex.split` + `shell=False`。⚠ 行为变化：`ROS_DISPATCH_COMMAND` 现按 shell 词法拆分后直连执行，Windows 路径需用正斜杠/引号（默认未配置该变量，现网不受影响）
  - ② SSRF `coordination.py`：请求点云视图前校验目标 URL 的协议与主机必须与 `POINTCLOUD_VIEW_BASE_URL` 配置完全一致
  - ③④ 路径穿越 `drawing.py` / `user.py`：上传文件写入前增加 `realpath` 包含性断言（最终路径必须仍在上传/头像目录内）
  - ⑥ SQL 拼接 `sqlite_create.py:484`：f-string 循环 → 14 条预构建字面语句（表名无法参数化，逐表列出）
  - **未修（用户决定）**：⑤ `sqlite_create.py:351` 默认密码种子；⑦⑧ robot_control_backend 两处 exec（队友侧，已需转告）
- 发现：后端 13 个测试为 v1.1 之前的陈旧用例（仍在断言旧编码 41/42/43 等），修复前后对照实验确认与本侧改动无关（均 13 failed / 19 passed）
  - `???` 待办：把 `tests/` 更新到 V1.1 预期（FEEDBACK_LABELS 1~20/21~25 等），否则测试套件长期红着失去回归价值
- Mimosa 门禁当晚已失效（插件缓存清空），本次修复后若插件恢复，剩余高危为 ⑤⑦⑧ 三项

## 2026-10-05（四）

- 全部积压改动已提交并推送 GitHub（已完成）
  - `9f2c36b` docs：命名规范 + 交接日志 + 接口文档基准重构版 + V1.1 修改清单执行版
  - `405f888` feat(front)：V1.1 适配（device_id 编码动态化、sensor_id 体系分离、UserInfo 类型对齐接口文档）
  - 推送前队友推入 `b9bc2b7`（仅 robot_control_backend 12 个文件小调整，与本侧零冲突），已 rebase 整合
  - 注：Mimosa 提交门禁当晚不再拦截（插件缓存被清空，疑似插件更新/重装）；`.mimosa/`、`.zcodeignore` 等工具产物仍未提交
- `???` 若门禁恢复：8 个既有高危仍未修复，提交会再次被拦——修复项见 2026-10-05（一）记录

## 2026-10-05（三）

- 修复 `types.ts` 类型与后端实际响应不一致问题（已完成，vue-tsc 通过）
  - `UserInfo`（含 email/phone/status 等后端不存在的字段，模板遗留）删除 → 新增 `UserItem`，字段逐字对齐文档 9.1 的 `user_to_dict`
  - `LoginResponse` 原为 `access_token/token_type`（FastAPI 默认形状，本系统并非如此）→ 改为文档 5.1 的 `account/name/typeId/token/tokenType/headImage/updateTime`
  - `rosApi.ts`：`getUserInfoApi`/`getUserListApi` 返回类型改用 `UserItem`
  - `stores/user.ts`：删除局部假 `UserInfo` 接口，`setUserInfo` 入参改用 `LoginResponse`；去掉对 `data.nickname/data.role/data.avatar`（登录响应中不存在）的兜底
  - **约定：前端类型字段名必须与《接口字段文档》记录的后端字段逐字一致，不允许自行新增/改名**（已存为持久记忆）
- 遗留说明：`profile/me` 编辑提交的字段（name/birthday/sex）与文档一致，未受影响；UserManagement/Profile 字段访问经类型检查验证全部兼容

## 2026-10-05（二）

- 按《前端V1.0到V1.1修改清单》完成前端 V1.1 适配（已完成，vue-tsc 通过）
  - 逐项先核对 V1.1 事实再改：26 项中**已修改 10 项、无需修改 9 项（附证据）、暂缓 7 项**，执行版清单落库见《ROS_MES_前端V1.0到V1.1修改清单.md》
  - 新增 `src/api/deviceEncoding.ts`：V2 轴号编码唯一出处（臂号由 Unit_ID 32/64/96 推算，轴号 = (臂-1)*4+偏移，臂级 21~25）
  - FineTuningPage：三轴 deviceId 动态化、微调下发改用各轴自身 device_id（原 bug：三轴都发模块级 ID）、反馈映射动态构建（删 33/34/35、41/42/43 硬编码）、IMU 判断改按 type、保存配置的 device_id/sensor_id 两套编码分离、sensorId 改从传感器列表获取（原 bug：误取轴 deviceId）
  - noRosDebug：模拟反馈改用 V2 编码（1/2/4、臂级 21）
  - RosTestPage：测试 ID 输入框化，修正 coordination/finetuning 测试 payload 与后端契约不符问题
  - AsidePage：启用急停遮罩（"解除急停(仅调试)"保留，注明生产需权限控制）
  - 单位显示统一：度→°；mm/cm 与 V2 消息定义一致保留
- 清单中暂缓项的依赖条件（后续触发点）：
  - 心跳/急停通知/限位故障处理（P1-08/P1-09/P2-07）→ 等后端 `rosbridge_gateway.py` 订阅 Heartbeat / StopNotification / LimitEvent / AxisFault 话题后在 `applyFeedback` 补分支
  - 轴数动态化（P2-02）、真空吸盘（P2-08）→ 等 V2 规范变更或后端支持

## 2026-10-05

- 同步远端 v1.1（commit `b03b57a`）：拉取队友更新——robot_control_backend 新增 9 个消息定义（Heartbeat、CmdAck、AxisStatus 等）、hardware_node.py 大幅重构（队友侧，背景记录）
  - `???` 后端 `rosbridge_gateway.py` 是否需要适配新增消息类型（如订阅 Heartbeat/CmdAck 用于链路健康监测）——未评估
- 新增《ROS_MES_前后端接口字段文档.md》，并按团队基准《ROS_MES_前后端ROS接口清单》重构（已完成）
  - 基准文档逐项对照代码核验，3 处修正见该文档 8.9 节：finetuning 系列实际免认证；`/hardware/imu_angles` 消息类型实为 TuoLuoYi；web_data_node.py 整文件被注释导致大屏 WS 无数据
- 新增《ROS_MES_前后端命名规范.md》（已完成）
  - 规则从现有代码提炼，含 10 条历史遗留不一致清单；新代码按规范执行，旧代码保持兼容
- Mimosa 深度安全扫描完成（scanId `scan-2026-10-05T08-41-29...`，封印 sha256:2727...）＋ 未修复
  - 前后端范围 6 个高危：`ros_dispatcher.py:53` 命令注入、`coordination.py:39` SSRF、`drawing.py:209` / `user.py:167` 路径穿越、`sqlite_create.py:351` 硬编码凭据、`sqlite_create.py:484` SQL 拼接
  - 队友侧 2 个（需转告）：`robot_control_backend/scripts/rosbridge_wrapper.py:91`、`test/fix_rosbridge.py:23` 代码注入
- git 提交被 Mimosa 门禁拦截：门禁在代理层实现（非 git 钩子，`--no-verify` 无效），存在高危即阻断一切 commit（进行中，阻塞项）
  - 《接口字段文档》重构版已暂存未提交，《命名规范》未跟踪
  - `???` 待决定：手动在终端提交 / 先修复 6 个范围内部高危再重扫
- 已写入持久记忆：分工范围（只动前后端）、基准文档约定、门禁机制

## 遗留问题清单（跨日期跟踪）

- `???` 大屏 WebSocket `/api/ws/ws/robot_status`：数据源 `web_data_node.py` 被整文件注释，前端大屏当前无实时数据。恢复脚本后前端是否需要改动待确认（队友侧脚本）
- `???` FineTuningPage 硬编码 `deviceId: 41/42/43` 与 V2 轴号规范 1~20 不一致，真实 ROS 环境需从设备树动态获取轴号（见《接口字段文档》6.1）
- `???` `/control/finetuning` 免认证路径下写库 `creater_id=1` 写死，无法区分实际操作人
- `???` `types.ts` 的 `UserInfo` 与登录实际响应字段不一致（`username/role/email` vs `account/name/typeId`），类型定义需对齐
- 前后端交互接口已总结完毕 → 见《ROS_MES_前后端接口字段文档.md》（对应 ROS 侧"总结与前端交互的接口"条目）

## 后面版本考虑的事情

> 2026-10-05（七）：《优化建议报告》归档，其全部未完成 📌 待办并入本清单，原报告见 `docs/archive/`。

**安全 / 接口**

- 认证缺口整改（前后端一起改，约半小时）：后端给 `/module`、`/coordination`、`/finetuning`、四层 CRUD、`/dashboard/stats` 等裸奔接口加鉴权；前端 `request.ts` 白名单缩减为 `/login`、`/register`；`/RosTestPage` 仅开发模式开放（原报告 待办1）
- 种子账号 `admin/123456`：部署前改密码（用户决定暂不修 `sqlite_create.py` 的默认密码种子）

**性能**

- 路由懒加载：12 个页面静态 import 打成 1.24MB 单包，改 `() => import(...)` 按路由分包，收益最大（原报告 性能1）
- 同步接口阻塞等待（原报告 性能5，报告认为最值得改）：`coordination /send` 的 5 秒 `time.sleep` 轮询 + `rosbridge_gateway.dispatch()` 每次 `asyncio.run()` 新建连接，并发图纸下发会占满 FastAPI 线程池；改 `async def` + `httpx.AsyncClient` + rosbridge 长连接复用
- 表格无分页：任务/图纸/工作流列表全量拉取渲染，数据量大后卡顿；可复用用户管理页的前端分页或后端加 limit/offset（原报告 性能4）
- Element Plus 按需引入：`unplugin-vue-components` + `unplugin-auto-import`，产物可减 50%+（原报告 性能3）
- SQLite 并发写入：`create_engine` 加 `timeout: 15` + 开 WAL；多工位部署时迁 MySQL/PostgreSQL（原报告 性能6）

**代码质量**

- 遗留死代码清理：`AddItem.vue`（调用不存在的 `/hardware` 接口）、未被页面调用的 API 封装（`GET /finetuning/`、`GET /drawing/{id}`、`GET /task/{id}` 等）
- work/workflow 写接口参数迁移到 JSON body（现走 query string，与其它模块不一致）
- `on_event("startup")` 已弃用 → 改 FastAPI lifespan 写法（原报告 质量7）
- `datetime.utcnow()` 已弃用 + 时区混用：`security.py`(utcnow) / `user.py`(now+utc) / `login.py`(now 本地) 三处统一为 `datetime.now(timezone.utc)`（原报告 质量8）
- crud 层被绕过：`user.py`/`task.py`/`workflow.py` 在 endpoint 里直接写查询，与 device/unit/sensor 走 crud 层的风格不统一（原报告 质量5）
- 响应格式手工拼接：每接口手写 `{code, message, data}`，建议抽 `ok(data, message)` 帮助函数（原报告 质量6）
- 命名不一致集中重命名（`Modeldescripte`/`Taskdescripte` 拼写、Module↔device 双命名等）：《命名规范》已管住新增代码，存量重命名比赛后统一做（原报告 质量3）
- echarts 依赖：package.json 有 `echarts@^6` 但全项目零 import；要么删掉，要么仪表盘加趋势图（比赛演示加分项，数据源 `/dashboard/stats` 现成）（原报告 性能2）

**已解决（备查）**

- ~~`ros_dispatcher.py` shell=True~~ → 2026-10-05（五）已修
- ~~venv/__pycache__/dist 未忽略~~ → `.gitignore` 已覆盖
