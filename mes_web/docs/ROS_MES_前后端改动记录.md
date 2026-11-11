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

## 2026-11-11（到位误差容差改为“只提示、不阻止”，已完成）

- 背景：另一侧排查到批次 `expected_position=3.15` 而实际到位 3.60°，差 0.45° 超出 0.2° 容差，60 秒后转 `uncertain` 并保留 `target_locked`，导致前端一直警告、下发按钮禁用。用户决定：**去掉到位容差这个判定条件，误差过大可以弹警告，但不能限制下发**。
- 后端 [finetuning_batch.py](../ros_mes_hou/app/ros/finetuning_batch.py)：`arrived` 只保留硬条件（收到到位事件、`status_bits & 4`、`flags & 1`、无超位/故障、带 angle 与 pos_error）；角度差与 `pos_error` 超阈值时写入 `steps[].deviation / observed_angle / position_error / warning`，该轴仍记 `completed`，继续下一轴；批次完成消息追加“N 个轴到位误差超出容差，已记录提示但未阻止下发”，`unlock=True` 照常解锁。
- 前端 [FineTuningPage.vue](../ros_mes_front/src/components/Main/ModulePage/FineTuningPage.vue)：批次面板在对应轴后面用琥珀色显示 warning 文案；有 warning 时完成提示条改为黄色；每个批次只弹一次「到位误差超出容差，不影响后续下发」的 toast（`warnedDeviationBatches` 去重，避免每秒轮询重复）。`FineTuningBatch.steps` 类型补 `expected_position/observed_angle/deviation/position_error/warning`。
- 保留的硬判定（未放松）：没观测到 RUN → 仍按待核实；完全没收到到位事件 → 60 秒超时转 `uncertain` 并保留锁；限位/故障/失压/并行运动 → 停止后续下发。
- 验证（2026-11-11 21:24，本机 Windows）：
  - 后端 `test_finetuning_batch.py` **16 条 OK**（新增 2 条：到位超差 0.45° 仍记 completed 且带 warning；超差批次 completed + 解锁且可立刻开下一批）；全量 **Ran 173, OK**。
  - 前端 `npm run test:finetuning` **100 pass / 0 fail**（新增 1 条：超差完成后 busy=false、状态 completed、弹一次 warning）；`vue-tsc` 与 `npm run build` 通过。
  - 运行中的后端已重启（`--reload` 实测未生效，改为不带 reload 启动；启动时把旧 worker 进程一并清理）。
- `???` 风险与未验证：容差不再拦截后，**真机"实际没到位"也会被记成完成**，只剩提示；是否接受由现场按 `warning` 判断。真机未验证超差场景的实际表现。

---

## 2026-11-11（微调页「刷新执行状态」补回执，已完成）

- 用户反馈走查：微调页点「刷新执行状态」像没反应。查后端日志确认按钮**确实在调接口**：`GET /api/control/finetuning/batches/{id}` 连续 5 次 200。原因是批次已 `completed`，返回内容与页面完全一致，前端既无重绘差异也无任何提示，属于纯反馈缺失。
- 前端 [FineTuningPage.vue](../ros_mes_front/src/components/Main/ModulePage/FineTuningPage.vue)：`pollBatch` 增加 `silent` 参数（自动轮询默认静默），模板改为 `@click="pollBatch(false)"`；手动点击后按批次状态弹一次「已刷新 · 本批次各轴已完成 · 21:13:05」。另补四种提示：正在刷新、当前没有批次、无 ROS 模拟批次、查询失败（并保留“未重发任何指令”的措辞）。后端未改动。
- 验证：`npm run test:finetuning` **99 pass / 0 fail**（新增 1 条：手动刷新会弹出状态回执）；`vue-tsc` 与 `npm run build` 通过。

---

## 2026-11-11（局部停新增“臂停”一级 + 侧栏弹窗下拉不可选修复，已完成）

- 用户反馈两点：① 侧栏弹窗里「模块 / 机械臂」下拉点不开；② 现场只需要“停一整台机械臂”，不需要轴级选择。
- 下拉打不开的根因：`LocalStopPanel` 的 `el-dialog` 写了 `:z-index="100002"`，Element Plus 的 Select 面板按 2000 段分配层级，被压在弹窗下面（DOM 存在但看不见、点不到）。移除自定义 `z-index`、交回组件库分配后正常。
- 后端新增 `scope=arm`（臂停）：`LocalStopRequest.scope` 增加 `arm`，`device_id` 传臂号 1~5；[rosbridge.publish_local_stop](../ros_mes_hou/app/ros/rosbridge.py) 对该臂 3 个轴号各发一帧 `position=[0x0C, 1]`；`validate_target` 增加 1~5 校验；`stop_holds.blocked` 用 `(axis-1)//3+1` 反推臂号匹配；`BatchManager.hold_target` 新增 `axes` 参数，臂停只命中该臂自己的批次，不再误伤同模块其他臂。
- 前端：侧栏弹窗「停哪一级」改为 **整模块 / 整个机械臂**，去掉轴下拉；`scope=arm` 时 `device_id = armIndexFromUnitId(unitId)`（臂号，不是 V2 轴号）。微调页姿态卡片内的「单轴停」三个按钮保留，现场调单轴仍在原地。
- 验证（2026-11-11 20:58，本机 Windows）：
  - 后端 `test_local_stop.py`：**Ran 20, OK**（新增 5 条：臂停记录与报文、臂号 0/6/15 拒发 422、臂锁只锁该臂 3 轴、臂停发 3 帧 4/5/6、臂停不误伤其他臂批次）；全量 `Ran 171, OK`。
  - 前端 `npm run test:finetuning`：**98 pass / 0 fail**（面板用例改为断言 `scope=arm` 且 `device_id` 是臂号）。
  - 运行中的后端已热重载，`/api/control/stop/holds` 401（需登录）、`/docs` 200，服务正常。
- `???` 未验证：真机未验证 3 帧 `0x0C` 能否整体停住、固件是否按轴锁存；下拉层级只在代码层修正，未在浏览器实际点选确认。
- 21:15 界面微调（仅侧栏底部急停区）：两行按钮统一 42px 高、13px 字号、10px 圆角、10px 间距，中间加 1px 细分隔线；修正 Element Plus 相邻 `el-button` 默认 `margin-left: 12px` 把第二个按钮顶出侧栏的问题；局部停数量角标改为按钮右上角绝对定位，不再把按钮文字挤偏；「停模块」按钮补一个琥珀色小圆点，与整机急停的白色脉冲点形成层级区分。前端 98 项测试与 `npm run build` 仍通过。

---

## 2026-11-11（局部停入口上移到侧栏，已完成）

- 用户反馈：模块停藏在微调页，「在别的页面想要马上停止模块还得跑到微调页面去」，分级急停失去意义。按确认口径改为：入口并入侧栏底部急停区、弹窗默认预选当前微调会话模块、模块停与单轴停都搬上去、微调页工具栏「停本模块」删除。
- 新增 [LocalStopPanel.vue](../ros_mes_front/src/components/Main/LocalStopPanel.vue)：弹窗内选模块（`GET /device/`）→ 整模块 / 单轴（再选机械臂 `GET /unit/by_device/{id}` 与轴）→ 二次确认后调 `POST /control/stop`；轴号由 `armIndexFromUnitId` + `axisDeviceId` 换算，不在前端硬编码。打开时读 `GET /control/session` 预选会话模块（无会话则手动选），并读 `GET /control/stop/holds` 列出生效记录、支持逐条清除（`POST /control/stop/clear?module_id=`）。轮询 8 秒，记录数通过 `count` 事件回传给侧栏做角标。
- 侧栏 [AsidePage.vue](../ros_mes_front/src/components/Main/AsidePage.vue)：底部改为上下两块——上「停模块 / 停轴」（橙描边，有记录时显示红色数量角标；侧栏折叠显示「停」），下仍是长按两秒的全局急停；弹窗组件挂在侧栏，跨页面可用。
- 微调页 [FineTuningPage.vue](../ros_mes_front/src/components/Main/ModulePage/FineTuningPage.vue)：删除工具栏「停本模块」及 `stopModule`，模块停统一走侧栏；姿态卡片内的「单轴停」和局部停红色横幅/清除按钮保留（现场调单轴时仍在原地，且页面需要显示为何下发被禁用）。
- 连接版本：弹窗不带会虚构版本号，改为使用 `GET /control/stop/holds` 返回的 `connection_revision` 随停指令提交，版本漂移时后端仍会 409。
- 后端未重启时的表现：`/control/stop/holds` 或 `/control/session` 返回 404 时，弹窗内直接提示“后端没有加载局部停接口，请用最新代码重启后端”，不再只剩一个空列表加两条 `Not Found` 提示；模块列表仍正常可用。已用 19:36 启动的旧进程复现并定位（新进程代码里路由齐全）。
- 验证（2026-11-11 20:40，本机 Windows，Node 22.22.2）：
  - 前端 `npm run test:finetuning`：**98 pass / 0 fail**（新增 `tests/local-stop-panel.test.mjs` 7 条：会话模块预选与机械臂加载、模块停报文、单轴停轴号换算、无模块/机械臂时拒发、记录回传与按模块清除、发送失败仍刷新记录、后端缺接口时提示重启）；微调页用例改为断言「本页不再有停本模块、单轴停与横幅仍在」，原模块停用例移入新文件。
  - `npm run build`：两套 `vue-tsc` 通过，vite 构建成功（仅既有包体积提示）。
  - 后端未改动，未重跑后端套件；`POST /control/stop` 报文形态与既有用例一致。
- `???` 未验证：未做浏览器实际点击；弹窗在真实数据（多模块、多臂、无会话）下的预选表现未现场确认；从任务管理页停模块后，微调页横幅依赖下一次 8 秒轮询才更新。

---

## 2026-11-11（基准初始值固定 0 + 校准标记，已完成）

- 需求口径（用户确认）：下位机与 ROS 都不回传轴初始值，三轴基准初始值统一按 **0**；「校准」**不是**下发归零动作，而是"点亮后影响下一次保存"的标记，用来在数据库备注里区分"校零值"和"微调值"。下发按钮保持原样，不拆成逐轴按钮。
- 前端 [FineTuningPage.vue](../ros_mes_front/src/components/Main/ModulePage/FineTuningPage.vue)：三轴 `initialLocked` 恒 true、`initial` 恒 0，`updateAxisCurrent` 只更新 `current` 不覆盖基准；文案「初始值: —」→「基准初始值: 0.00」；卡片头 `保存当前配置` 左侧新增「校准」切换按钮（`warning`/`info` 两态），点亮时显示「保存时备注记为校零」；保存请求新增 `calibrated`、`notes`，备注含机械臂号、三轴基准值、保存时间；保存成功自动熄灭，保存失败保持点亮以便重试；`resetControlState`（换臂/重新配置）清零，不串到别的臂。
- 后端：`FineTuningConfigCreate` 新增 `calibrated: bool = False`、`notes: Optional[str]`（≤1000 字）；[crud/finetuning.py](../ros_mes_hou/app/crud/finetuning.py) 把 `notes` 写入 `fine_tuning_config.notes`（该列此前一直为 NULL），`calibrated=true` 且未给备注时补默认校零文案。**未改表结构、未加端点、未动下发/ROS 链路**。字段说明见[接口字段文档 2.4.2](ROS_MES_前后端接口字段文档.md#242-基准初始值与校准标记2026-11-11)。
- 与 20:05 那版的口径差异：上一版曾计划"逐轴下发 + 校准按钮自动下发归零 + 新增 `GET /finetuning/config/latest` + 批次 `purpose` 字段"，经用户确认全部作废，代码已还原，工作树不留残留。
- 验证（2026-11-11 20:24，本机 Windows，后端 venv + Node 22.22.2）：
  - 前端 `npm run test:finetuning`：92 pass / 0 fail（新增 1 条校准用例；改 2 处 `initial` 断言：反馈不再写基准、无反馈时保存写 0 而非 null）。
  - 后端 `PYTHONPATH=. python -m unittest discover -s tests`：**Ran 166 tests，OK**（上一轮 163 + 新增 3 条：指定备注落库、只给 `calibrated` 补默认备注、普通保存 notes 为空）。
  - `npx vue-tsc --noEmit -p tsconfig.app.json` 通过；`git diff --check` 无空白问题。
- `???` 未验证/边界：未做浏览器实际点击与真机验证；历史快照的 `notes` 仍为 NULL，只有本轮之后"点亮校准保存"的记录才有校零备注；校准状态不跨刷新保留（刷新后按钮回到未点亮，数据库记录不受影响）。

---

## 2026-11-11（局部停：模块停/单轴停，已完成）

- 用户提出“急停是全部一起急停，想做分级急停”。按范围确认三档：单轴 / 本模块 / 全局。协议早有定义，本轮把模块停与单轴停接到 MES。
- 只读核查 ROS 侧：`softstop_node.py` 只订阅 `/control/softstop`、`/control/softstop_release`，`stop_callback` 固定发 `[0x01]`，因此把局部停发给它会升级成整机全停；而 `hardware_node.py:345` 已实现 `0x08` 模块停（按 `_seg_for(module_id)` 组 `0x08|SEG<<18`）与 `0x0C` 单轴停（先清该轴增量队列）。**未修改 `robot_control_backend`**，后端改为直发 `/arm/cmd_vel`，等价于省掉 softstop_node 一跳。
- 后端：新增 `control_stop_holds` 表与 [局部停管理](../ros_mes_hou/app/ros/stop_holds.py)；`/arm/cmd_vel` 话题键 `arm_cmd`（可用 `ROS_TOPIC_ARM_CMD` 覆盖）；新增 `publish_local_stop`（rosbridge）、`trigger_local_stop`（适配层，基类默认拒绝而不降级为全停）、模拟实现；端点 `POST /control/stop`、`GET /control/stop/holds`、`POST /control/stop/clear`、`POST /control/stop/{id}/clear`。
- 锁定规则：`assert_available` 增加 scope 判断——模块停拦该模块全部下发，轴停只拦 `(arm-1)*3+轴序` 命中的轴，轴号无法判定时按整模块拦截；`BatchManager.hold_target` 把命中的在途批次停止后续下发并转 `uncertain`，沿用既有“已现场核实”关闭流程。全局急停仍写 `control_safety`，与局部停互不影响。
- 先落记录再发送：发送失败（502 或 `state=unknown`）保留 MES 锁，避免操作员以为已停住继续下发。scope 非法、轴号不在 1~15、模块缺少 SEG 映射返回 422；连接版本不符返回 409。
- 前端：微调页工具栏「停本模块」、姿态控制卡片内「单轴停 · 停旋转/停摆动/停伸缩」（轴号来自 `armList.device[i].deviceId`）、局部停红色横幅 + 「清除局部停记录」；受限时「确认下发三轴调整」禁用；进入页面与每 8 秒读取记录，连接配置变更时重新读取。侧栏长按两秒仍是全局急停，未改动。
- 明确边界：协议只有全局 `[0x04]` 解除。清除局部停记录**只恢复 MES 下发能力，不发送解除或运动指令**；设备侧是否锁存由固件决定，恢复运动需现场确认后清除记录并重新下发，界面与文档均写明，不自动重发。
- 验证（2026-11-11，本机 Windows，后端 venv + Node 22.22.2）：
  - 后端 `python -m unittest discover -s tests`：Ran 163 tests，OK（新增 15 项：模块/轴停记录与报文、发送失败保留锁、非法轴号与未映射模块 422、版本不符 409、模块锁只影响本模块、轴锁只影响该轴、轴号换算、清除恢复、记录查询、在途批次命中与否、`/arm/cmd_vel` 报文形态、未知 scope 不发布）。
  - 前端 `npm run test:finetuning`：91 pass / 0 fail（新增 6 项：控件存在、模块停报文、轴停轴号、局部停阻止下发、清除后恢复、其他模块不受影响）。`npm run test:drawing`：12/12 通过。
  - `npm run build`：两套 `vue-tsc` 类型检查通过，vite 生产构建成功，仅有既有资源包体积提示。
- `???` 未测项：真机未验证模块停/单轴停是否真的停住、是否锁存、断电或重新上电后的状态；`0x0C` 与普通增量 12 的区分仅在源码层面核对。多模块并行时“解除只对某个模块生效”在协议层无支持，需固件扩展。
- 过程记录：本轮期间另一会话曾在 `FineTuningPage.vue`、`rosApi.ts` 并发加入“逐轴下发 + 基准校准”，因缺少 `canDispatch/dispatchAxis/baseline*` 实现导致构建失败；对方已自行回退，本次构建在上述回退后通过，本侧未删除任何他人代码。

---

## 2026-11-11（微调会话保持与续接，已完成）

- 用户现场复现：绑定模块后在微调页做一半、切到任务管理等页面再回来，组件状态全部丢失，只能重新走握手弹窗，返回即退回模块选择；而 `module_confirme_node` 的握手要等目标臂重新上电宣告 UID，已绑定的臂不会再次宣告，因此必须断电才能重绑。本轮把“握手结果”升级为可续接的会话记录，避免为了继续微调去断电。
- 后端新增 `control_sessions` 表（`id/module_id/device_id/x/y/seg/unit_ids/connection_revision/creator_id/created_at/last_active_at/invalidated_at/invalid_reason`）与 [会话管理器](../ros_mes_hou/app/ros/control_session.py)。`POST /module/` 握手成功后登记会话并在响应中返回 `session_id`/`session`；登记失败只返回 `session_id=null` 与 `session_error`，不把已完成的物理握手判为失败。新增 `GET /control/session`、`POST /control/session/{id}/resume`、`POST /control/session/{id}/close`。有效期由前端偏好按请求传入（15/30/60 分钟或不限），从最后一次续接滑动，服务端不落库。
- 失效口径：同组号或机械臂有交集的新握手把旧记录标 `superseded`；`runtime_settings.update` 在连接配置变更时批量作废（`connection_changed`）；超过偏好时长 `expired`（判定时落终态）；手动结束 `closed`。急停不使会话失效，下发仍受既有联锁与批次检查。
- 前端新增 [会话 store](../ros_mes_front/src/stores/fineTuningSession.ts)（开关、时长、`sessionStorage` 界面快照）与 [会话接口](../ros_mes_front/src/api/session.ts)。个人中心“调试设置”新增“微调会话保持”面板（开关+时长+当前会话+结束会话）；模块管理页顶部显示进行中会话卡片（模块坐标、机械臂、剩余时间）与“继续微调/结束会话”，**不自动跳转**，避免阻断换模块；微调页挂载时先尝试续接（同一模块、`session` 参数直连），成功后跳过初始化弹窗、用后端返回的 `seg` 恢复反馈归属、有在途批次时恢复轮询，顶部显示“已续接会话 · 未重新握手”。
- 跨端或本机快照丢失时按绑定重建最小状态：机械臂行以当前 `Unit` 数据为准，图纸置空并加载可选列表；为让该状态下可以补发图纸，“下发图纸”按钮的启用条件由 `isReady` 改为“该臂已配置”，`openDrawingDialog` 同步改为检查已配置，避免续接后卡在不能选图也不能下发的死锁。真实模式仍未下发图纸前不能提交调整。
- 验证（2026-11-11，本机 Windows，后端 venv + Node 22.22.2）：
  - 后端 `python -m unittest discover -s tests`：Ran 148 tests，OK（新增 11 项：登记、同组号/同机械臂抢占、连接版本失效、过期落终态、续接滑动有效期、不限时、手动结束、未知会话、空记录、批量作废）。
  - 前端 `npm run test:finetuning`：85 pass / 0 fail（新增 7 项：有效会话续接不发模块确认、快照还原各臂数值、跨模块拒绝续接、显式链接失效告警并回落握手、关闭开关不访问会话接口、握手登记并写快照、结束会话清记录）。`npm run test:drawing`：12/12 通过。
  - `npm run build`：两套 `vue-tsc` 类型检查通过，vite 生产构建成功，仅有既有资源包体积提示。
- `???` 未测项与边界：续接只读 MES 记录，**未经设备复核**；ROS 侧无“查询当前绑定”的对外入口，若节点重启或机械臂断电，MES 无法自动感知，需现场核对。真机续接、断电后状态、刷新/换端恢复均未做设备验证；页面交互只经脚本检查与构建，未做浏览器实际点击。
- 与需求 B（分级急停）无关：本轮未改急停链路，仍只有全局 `0x01`，`0x08` 模块停与 `0x0C` 单轴停仍无入口。

---

## 2026-11-11（角度微调步长与人工解除急停，已完成）

- 按用户确认，底座旋转、摆动输入框采用 0.01° 步长与两位小数，提交增量继续按度传递。单位仍为度（伸缩为 mm），前后端不做单位换算，底层整数编码仍由 ROS 轴节点处理。
- 急停全屏新增“人工解除急停”，操作员现场处理完成后可清除当前环境的 MES 急停记录，成功后关闭全屏。新增登录鉴权业务接口 `POST /api/control/emergency_stop/manual_release`，校验操作员确认、连接版本及急停版本，清除结果持久化。模拟环境同步清除模拟锁存，中断批次继续使用已有现场核实流程。
- 批次闭环沿用既有流程，未新增接口：急停时后端把当前环境在执行批次置 `uncertain` 并保留目标锁，微调页继续显示“已现场核实，关闭待确认批次”；人工解除急停只清联锁记录，不关闭批次、不重发指令，操作者核实并关闭批次后目标锁才释放，新批次重新走实时空闲/无急停检查。
- 验证结果（2026-11-11，本机 Windows，后端 venv + Node 22.22.2）：
  - 后端 `python -m unittest discover -s tests`：Ran 137 tests，OK（含人工解除的持久化、重复清除幂等、迟到确认不清新急停、连接版本变更 409、在途控制 409、真实/模拟隔离、中断批次保留至人工核实、鉴权与字段校验）。
  - 前端 `npm run test:finetuning`：78 pass / 0 fail（含 0.01° 步长与两位小数、小数增量提交不截断，以及人工解除的按钮、防止重复点击、迟到响应、连接变更失效、刷新恢复）。
  - `npm run build`：两套 `vue-tsc` 类型检查通过，vite 生产构建成功，仅有既有资源包体积提示。
  - 实际应用 `app.main:app` 已注册 `/api/control/emergency_stop/manual_release`，与前端 `baseURL=/api` 拼接结果一致。
- `???` 未测项：真实 ROS/CAN 与机械臂急停、解除、到位反馈仍未做真机验证；本地页面按钮与文案只经脚本检查和生产构建，未做浏览器实际点击。上述结果只证明代码路径与模拟行为，不能当作设备已停或急停已解除的证据。
- 本机 `.env.development`（`VITE_DEBUG_NO_ROS=true`）属上一轮本地调试改动，未纳入本次提交；真机验证前需改回 `false`。

---

## 2026-11-07（急停按钮对齐与发布检查，已完成）

- 急停全屏的两个操作按钮改为同一居中布局，统一高度、字号、内边距和间距，去掉解除按钮独有的顶部外边距；窄屏改为上下等宽排列，并限制内容宽度。
- 类型检查及生产构建通过，仅有现有资源包体积提示。自动页面截图检查因无法确认 Windows 浏览器地址而停止，本次排版尚未完成截图复核；不影响此前隔离浏览器已验证的控制流程。
- 发布核查保留本机 `.env.development` 修改，不提交运行数据库、构建输出或临时测试产物；提交范围限于本轮 `mes_web/` 前后端代码、测试及配套文档。真实 ROS/CAN/设备联调仍未验证。

---

## 2026-11-07（空库模拟、图纸设置与历史急停修正，已完成）

- 用户复现空图纸库被要求导入、未点击急停却出现全屏。只读核查：当前运行日志新急停 POST 为 0，真实联锁保留旧 stop_unknown；前端轮询把历史记录直接当作全屏触发，未再次发送急停。
- 已修正历史状态显示：历史/其他窗口状态只显示持续提示，不清除真实锁、不自动发送任何控制；全屏仅由主动长按或手动查看打开，并可返回页面保留联锁。已关闭全屏时，解除失败或状态轮询不会再次弹出遮罩；真实解除发送成功仍为设备状态待确认。
- 图纸设置合并为“不使用图纸/模拟下发/真实下发”，去掉独立跳过开关；三者由后端持久化配置统一管理，刷新不再恢复另一套前端临时开关。不使用图纸时仍须确认机械臂，但跳过图纸选择、下发和三视图。
- 新增 GET `/drawing/?for_tuning=true` 的微调选择用途。mock 模式提供后端内置示例，正式图纸库为零条也可完整调试；普通图纸管理不显示此项，不向正式图纸表写入假记录。图纸下发及配置保存明确传 `drawing_source=builtin_mock/drawing_id=null`，只允许当前 mock 模式；真实空库仍要求导入正式图纸。配置保存与图纸请求均核验会话连接版本。
- 后端补充来源参数类型校验：`drawing_source` 为对象/数组等非法值时返回 422，避免集合判断触发 500。来源组合、过期版本、skip 模式禁发和真实/模拟急停隔离加入回归。
- 隔离浏览器已从真实登录、零条正式图纸、真实历史 stop_unknown 开始验证：刷新和切换到真实环境仅显示提示，没有自动发送新急停；mock 下双机械臂内置图纸确认、三轴编辑时零批次请求、一次确认登记一个批次并完成三轴、保存内置来源及 null 图纸编号通过。无图纸模式不下发图纸且可保存；主动模拟急停后刷新只显示提示，手动查看并解除成功；真实空库仍提示导入且不展示模拟示例。
- 浏览器另发现切换机械臂后残留上一臂批次详情，已增加批次和 ACK 提示的按臂保存/恢复及旧查询结果身份保护；新会话清除旧臂缓存，防止迟到响应覆盖新批次或其他机械臂。最终浏览器复测通过：切至 B 不显示 A 记录，切回 A 恢复其记录；另确认一次单轴调整用于切臂回归，整轮共两个完成的模拟批次，没有刷新重发。
- 本轮急停请求核对：仅主动长按一次产生一次急停 POST，手动解除一次产生一次解除 POST；刷新及切到真实环境没有新急停请求。真实联锁 id=1 始终保留 stop_unknown/generation=8，模拟联锁 id=2 解除后为 clear，未用模拟成功清除真实记录。
- 最终自动检查通过：前端微调/急停/请求/连接配置 68/68 项（原 55 项加切臂、新会话和竞态/ACK 回归 13 项）、图纸 12/12 项、后端 129/129 项；类型检查及生产构建通过，仅有现有资源包体积提示。
- 自测使用隔离 SQLite、真实业务路由/JWT 和禁止真实设备调用的测试环境；正式图纸表保持零条，未写运行库业务记录，未连接真实 ROS/串口，不以模拟结果宣称真机通过。临时测试进程、脚本及 SQLite 已清理，截图和诊断 JSON 留在外部任务产物目录。
- 本地后端已重启，8000 后端与 5173 前端均正常，新接口描述中的 for_tuning 和 drawing_source 可读取；服务保留供用户继续测试。代码仍在本地，未提交或上传 GitHub。

---

## 2026-11-06（页面配置真实/模拟连接，本地实现已完成）

- 根据用户确认，在现有调试设置中增加 ROS 通信/微调、图纸下发、急停及解除的手动模式选择和地址输入；不增加批量切换、测试连接或保存按钮，逐项自动应用。
- 先记录接口文档 §2.6，再实现后端统一配置、模拟传输及来源隔离。保留跳过图纸绑定；前端业务请求走后端，逐轴模拟运行/到位，模拟急停解除成功可退出遮罩，真实模式不伪造成功。
- 急停遮罩可打开同一配置面板；模拟与真实状态隔离，真实下发要求真实急停，存在执行/待核实批次时禁止更改连接。不操作真实设备，不修改 ROS 节点或消息。
- 已实现 GET/PATCH `/control/debug-settings`，登录后逐项自动应用模式与地址；版本冲突/在途操作/目标锁定时拒绝覆盖。增加 `ros_debug_settings` 表保存当前服务配置；模式/连接快照复用批次 JSON，控制联锁 id=1/2 分别存真实/模拟，不对既有业务表追加列。首次无保存配置时沿用真实连接，用户在页面手动选择模拟，不自动切换或降级。
- 后端模拟覆盖模块确认、图纸与三视图预览、三轴 RUN/目标到位/空闲、压力、急停及解除；批次与配置保存均经过后端数据库。模拟源显式标记，未生成的 IMU 分量仍等待；重启不恢复动作。ROS 模拟时，串口/硬件/底层数据工具也不执行真实 ROS/串口脚本。
- 模块确认返回连接版本，微调/图纸可核验版本；连接变更使前端旧确认与缓存失效，三视图 URL 也带版本。图纸等待视图期间保持配置快照，真实图纸/微调要求真实急停；两个真实入口分别核验模块确认。急停联锁同时阻止后续模块/图纸下发，模拟解除保留真实联锁。
- 当前自动检查通过：前端微调/急停/请求/连接配置 50 项、图纸 12 项，后端 117 项；Vue/TypeScript 与生产构建通过，仅有现有资源包体积提示。新增覆盖手动自动应用、地址校验、版本冲突、在途锁定、真实/模拟路由、完整后端模拟批次、急停中断不恢复、模拟解除隔离、真实拒绝不伪造成功、旧确认/视图失效及模拟工具不拉真实脚本。
- 隔离浏览器使用本次生产构建、真实业务路由/JWT、独立测试 SQLite 和禁用真实设备调用的模拟适配层。逐项选择/地址移出输入框自动应用、刷新恢复设置通过；模拟急停遮罩能打开同一设置面板，模拟解除成功后正常退出；图纸/三视图模拟、三轴逐轴完成与来源标记、实际配置保存通过。预览期间未连接真实 ROS/串口，未写运行库业务记录；临时服务/数据库/脚本已清理，截图随任务交付。
- 前后端本地服务保留供用户继续测试。运行后端正常启动会补建缺失配置表，未运行根初始化/种子脚本；用户现有环境文件保留，但历史 `VITE_DEBUG_NO_ROS` 已不再截走 API。详细现行契约见接口文档 §2.6；代码仍在本地，未提交或推送 GitHub，真实 ROS/CAN/设备联调未验证。

---

## 2026-11-06（三轴统一确认与急停解除，前后端本地实现已完成）

- 用户已确认三个轴共用一个确认按钮；先在接口文档 §2.4.1 和 §2.5 记录交互、顺序执行、幂等、异常和重启处理，再实施前后端。
- 已接入轴状态、到位、停止、故障/限位五类反馈，反馈订阅从 8 路增至 13 路。后端维护持久化批次和 SEG+arm 目标锁，取得新鲜实测及有效空闲状态后逐轴发送；仅接受 ACK 不推进。故障/限位/非正常停止/失压、断线、急停或超时停止后续下发，结果不明保留锁，不自动重试。普通单轴接口保留兼容，并校验轴号、参数、机械臂及批次锁。
- 前端三轴输入仅修改草稿，一个按钮统一提交非零项；执行中禁止切臂、重配、保存或重复下发。刷新先恢复后端批次，提交响应丢失只按请求号查询；后台重启不恢复旧动作。现场核实关闭仅释放 MES 锁，不解除故障/急停；已发送项不自动重做。
- 解除操作对接已有真实接口，删除遮罩五秒自动恢复；发送与设备确认分开显示。现有 `.env.development` 的用户模拟设置保留，自动验证不访问设备。
- ROS 节点/消息/硬件配置只读；压力均值混样为 ROS 侧待确认问题，本次不把其显示接通冒充计算正确。无设备请求序号时，MES 幂等号不能提供固件级精确回执关联，真机启用需核实反馈及独占条件。
- 新增 `fine_tuning_batches` 和 `control_safety` 表；重启后端由现有 `create_all` 创建缺失表，不重建/清空库，不运行根初始化/种子脚本。批次执行限定单后端 worker；真机使用前必须保证本控制会话独占目标，其他 ROS 流程不能同时运动。接口、字段、默认等待/容差及升级边界见接口文档 §2.4.1、§2.5、§3.1、§10。
- 请求层补充批次接口的登录凭据处理，避免被历史 `/finetuning` 子串白名单误判为免认证；原单轴/配置接口兼容保留。实际 Axios 拦截器测试覆盖批次提交/查询/中止/人工关闭带凭据，缺凭据在发出请求前阻断。
- 自动检查已通过：`npm run test:finetuning` 39 项（微调 31 + 急停侧栏 5 + 请求鉴权 3）、原图纸回归 12 项、后端 `unittest discover -s tests` 99 项。新增覆盖草稿不发、统一提交、锁定/刷新恢复、响应丢失只查询、人工关闭/重配、急停解除失败与成功未确认、顺序完成、ACK 不推进、缺运行/缺状态、错误归属、超时/幂等、故障事件、急停/重启及旧接口/物理编号别名绕锁防护。Vue/TypeScript 检查及生产构建通过，保留既有资源包体积提示。
- 隔离浏览器使用本次生产构建、真实控制路由/批次管理器、内存 SQLite 和模拟设备消息：三个输入调整期间运动发送 0 次；确认后按 1/2/3 轴各发送一次；执行中刷新恢复进度且不重复下发。恢复批次结束后重新加载图纸建立新会话通过；急停解除首次模拟失败时遮罩保留，随后发送成功仍显示设备状态待确认，刷新继续保留提示。页面预览截图随任务交付。
- 证据范围限前后端软件及模拟 ROS 消息，未操作真实 ROS/CAN/设备；到位字段单位、反馈时序、短动作 RUN 可观测性、固件状态及独占条件仍待现场确认。未自动运行现有库初始化或种子脚本。临时预览服务/脚本已清理；本次修改保持本地，未提交或推送 GitHub。

---

## 2026-11-05（微调控件对齐，已完成）

- 仅调整微调页 CSS：三轴标签和输入框使用统一列宽，输入框起始位置与宽度一致；初始值/实际反馈也按固定列对齐，统一垂直居中和行间距。窄屏将控件和反馈分行，避免长反馈状态挤压输入。
- 不改变控制事件、增量语义、调试开关或数据接口；保留用户当前环境配置。
- 验证：`npm run build`（含 Vue/TypeScript 检查）通过；隔离静态预览使用测试接口检查 1280px 和 1024px 窗口，三行输入框均为 150px 宽、左边缘一致，窄窗口反馈自动分行，页面无横向溢出。未调用实际服务的设备控制接口或写入业务数据。构建仍有现有的大体积资源包提示。

---

## 2026-11-05（当前运行库五臂登记补齐，已完成）

- 用户确认模块 17 的既定配置已扩展为五臂；当前代码和设备配置已支持五臂，但运行库仍只有 Unit_ID=32/64/96，缺少现有库的增量补齐步骤。
- 已先对正在使用的仓库根 `ros_database.db` 做 SQLite 在线一致性备份并通过完整性检查。只通过现有设备登记 API 补齐模块 17 的 Unit_ID=128/160 和各八类传感器，已有三臂及其他业务数据保留；不重建数据库、不运行初始化/种子脚本、不下发 ROS 指令。
- 已完成：通过现有 `/api/unit/`、`/api/sensors/` 登记接口新增两臂及 16 条传感器；编号和臂内地址由后端配置生成。模块 17 当前为 Unit_ID=32/64/96/128/160，每臂八条传感器，共 40 条。该结果只说明本地业务登记完成，不代表设备在线、ROS 已绑定或真机已验证。
- 验证：设备树返回一至五号臂，微调使用的 `/api/unit/by_device/17`（含前端 5173 代理）返回五台；四、五号臂的压力业务编号分别为 145、177。与补齐前一致性备份逐表比较，所有原有记录及其他业务表保持不变，仅 Unit/sensors 新增目标记录；数据库 `PRAGMA integrity_check` 为 `ok`。未触发机械臂确认或运动接口。
- 备份：`C:\Users\DOGE\.codex\backups\ROS_MES\20261105_222127_five_arms\ros_database.before_five_arms.db`；同目录保留 `manifest.json`（含备份 SHA-256）及 `repair_result.json`。此次为已确认五臂配置补做现有库增量登记，不改变新模块的登记规则，不自动给其他模块填充设备。

---

## 2026-11-05（文档归属整理与手动微调反馈修正，已完成）

- 已确认计划：仅迁移前后端专属文档至 `mes_web/docs/`，共享三轴契约、ROS/CAN 资料、跨系统报告和整仓历史 ZIP 保持原位置；不新建根 AGENTS，全项目 README 只调整中立导航。前后端任务的代码边界及阅读入口写入 `mes_web/AGENTS.md`。
- 代码修正范围：普通发布结果区分已发送与设备确认；有效反馈按已确认 SEG 和当前机械臂核验，逐轴/压力/IMU记录接收时间并区分等待、更新、历史和过期；坏样本不补零、不终止反馈流；仅展示可可靠归属的 CmdAck 事件，不推断某次请求完成、不自动重发。
- 保留上次未提交的调试模式及保存工作、已完成的 HTTP 回显隔离、模块确认和急停/解除；ROS 执行代码只读。未接入能力和来源/固件不确定性记入前后端对接状态清单。
- 验证计划：实际组件脚本、模拟消息与测试替身覆盖错误确认、跨模块/跨臂、无效零值、等待/过期/断线/缓存、回执归属和原有流程；不自动操作设备或改写现有数据库。完成后补充结果与证据边界。
- 文档整理已完成：接口字段、命名规范、更新日志迁至 `mes_web/docs/`，V1.1 历史适配清单及旧优化报告/UI 原型归入该目录的 `archive/`；旧常用入口保留简短迁移指引。共享三轴契约、两份 CAN 资料、跨系统报告、整仓 ZIP 与部署指南保持原位置，根 README 仅调整中立导航，不新建根 AGENTS；前后端入口及任务边界由 `mes_web/AGENTS.md` 维护。
- 合并重复调试文档：现行流程/配置字段及显示语义归接口文档，原调试测试证据保留在下一条历史日志；移除重复的单功能设计文档，并撤回上次仅由本侧新增到共享三轴清单的调试页面长段，不重写 ROS 协议正文。接口文档移除旧四轴消息/编码大段，改为引用共享契约。
- 本次自动检查已通过：`test:finetuning` 24 项（原 14 项加新增 10 项）、`test:drawing` 12 项、后端 85 项。新增覆盖模块确认缺 SEG、跨模块/臂/类型隔离、非法及非有限样本、逐分量时效、缓存历史/断线、未知实测 null 及快照状态、ACK 归属/不推断完成/不重发、阈值及原无 ROS 模拟。测试使用实际组件逻辑和后端处理函数、模拟连接及隔离数据，不能证明现场固件或设备行为。
- 类型检查和生产构建通过，仅保留既有产物体积提示。CmdAck 只保留页面会话内最多 20 条事件，尚未实现逐请求指令追踪。
- 浏览器复查使用本次生产构建、真实 FastAPI 配置端点和内存 SQLite，ROS 确认与反馈为隔离替身。验证无图纸进入、已确认 SEG 遥测隔离（同号轴的 SEG 7 样本不覆盖模块 17/SEG 0 的 12.5）、逐项等待/更新、暂停消息后过期、切回缓存显示历史、接受及归属待确认的拒绝回执提示。两次配置保存成功，历史状态正确落库，未收到的压力和 IMU y 保存为 null；整个浏览器流程图纸请求 0 次、运动下发 0 次。
- 现行入口/文档的 88 个本地链接及章节锚点检查通过；`git diff --check` 通过。ROS 执行代码、部署配置、共享协议/报告与整仓 ZIP 无变更；未操作真实设备、未写项目现有数据库。临时测试服务与脚本已在验证后清理，截图随任务交付。

---

## 2026-11-05（个人中心调试开关与无图纸微调）

- 按先文档、后代码的顺序新增《微调调试模式设计与验收.md》，明确入口、正常/调试两种流程、配置保存字段和验收边界；同步接口字段文档与三轴版页面流程说明。
- 在现有“个人中心”增加“调试设置”页签，提供“跳过图纸绑定”开关；独立 Pinia 状态跨页共享，刷新、登录或退出后关闭，进入微调时固定模式。模块页及公共页头显示状态，不新增独立设置页。
- 调试模式继续真实模块确认，成功后无需图纸进入微调，不加载图纸列表、不下发图纸、不依赖点云服务；控制、反馈、多臂切换及保存配置继续可用。正常模式仍要求完成图纸下发；`VITE_DEBUG_NO_ROS` 模拟模式保持独立。
- 配置请求模型增加 `is_debug=false` 和可空正整数 `drawing_id`，实际写入既有 `config_json` 并随保存响应返回；调试配置携带图纸编号返回 422。旧客户端不传新增字段仍兼容，不改数据库结构、不补写现有数据。
- 修正相关微调状态：无图纸也可缓存已确认臂，切换恢复正确的压力传感器业务编号；缺少登记传感器时明确提示。微调及保存统一阻止重复提交和请求中切换；发送回显不再覆盖设备实测反馈，成功提示明确为指令发送。保存增加当前 IMU x/y/z，原无 ROS 模拟保存提示未写数据库。
- 验证：新增 `npm run test:finetuning` 14 项、原 `test:drawing` 12 项、后端 69 项测试、前端构建（含 TypeScript 检查）和 `git diff --check` 通过。浏览器使用生产构建、真实配置保存端点及内存数据库，验证个人中心入口、两臂确认与分别保存、调试阶段无图纸请求和刷新恢复正常流程。
- 验证边界：ROS 确认与反馈为隔离替身，未连接真实 rosbridge/ROS/CAN 或操作设备；未写入项目现有数据库，未运行建库脚本。构建仅有既有大包体积提示。

---

## 2026-11-04（图纸分页复查与页面状态修正）

- 在 PR #7 合并版本上完善连续查询处理：仅最新请求可更新列表及加载状态；编辑/删除/导入后的刷新使用最后一次已提交的筛选条件，不采用输入框里尚未查询的文字。
- 复查同页既有导入逻辑，修复“重导某图纸 → 取消 → 新导入”仍携带旧 `drawing_id`、误追加旧图纸版本的问题。显式声明导入目标并在重置时清空，导入中拦截重复提交和切换目标；新图纸导入成功回到第一页，重导保留当前页。
- 新增可重复运行的 `npm run test:drawing`：直接运行实际 Vue 组件脚本、使用模拟 API，覆盖分页、查询乱序、加载状态、错误保留、草稿筛选与已提交筛选分离、导入目标清理及重复提交，共 12 项。修复前测试确认相关问题，修复后全部通过。
- 验证：`npm run test:drawing` 的 12 项回归检查、`npm run build`（含 TypeScript 检查）与 `git diff --check` 全部通过。保留现有列表接口和前端分页方式；测试使用模拟 API，未调用真实后端写接口，未进行浏览器交互验证。构建仅有产物体积提示。

---

## 2026-11-04（合并 PR #7：图纸列表分页）

- 接入 PR #7 的图纸列表分页，默认每页 10 条，可切换 20/50 条；分页总数从当前查询结果计算。
- 合并时补齐查询/重置回到第一页、删除末页最后一项及调整每页条数后的页码回退；导入/编辑/删除后的列表刷新保留当前查询条件。
- 保留主分支真实接口配置（`VITE_USE_MOCK=false`、`VITE_DEBUG_NO_ROS=false`），不采用 PR 中与分页无关的模拟数据开关变更；保留贡献者提交历史。
- 验证：前端 `npm run build`（含 TypeScript 检查）与 `git diff --check` 通过；以实际组件脚本和模拟 API 检查 7 个分页场景（25 条数据分 10/10/5、查询回首页、重置、删除末页最后一项、调整每页条数、编辑/删除刷新保留查询、空列表），全部通过。未进行浏览器交互或真实后端联调。

---

## 2026-11-04（设备管理配置集中到后端）

- 后端 `app/core/device_catalog.py` 集中维护五臂选项、八类传感器及数据库业务编号规则，新增只读接口 `GET /api/device/config`（已完成，本地待审阅）。配置给出可登记范围，不代表数据库已登记相应设备。
- 设备信息管理页删除 `ARM_OPTIONS`、`SENSOR_OPTIONS` 和 `getSensorId` 的本地规则，改读配置生成选项；新增/编辑传感器时由后端生成业务编号及地址。配置失败时提示重试，禁止依赖缺失配置继续操作；新增前等待已登记列表加载，过滤重复选项。
- 写接口校验机械臂是否在配置范围、模块/机械臂归属、传感器类型和显式传入的编号/地址；错误返回 422，重复返回 409。保留旧客户端显式传值的兼容，但数值须与配置一致。软删除后重新新增复用原记录，避免唯一约束冲突。
- `sensor_ID = Unit_ID + offset` 规则留在后端，不属于 ROS 编码；ROS `device_id` 继续由 `deviceEncoding.ts` 按三轴规则生成。修正相关过期注释，未修改机器人控制代码。
- 未修改数据库结构，未运行建库脚本、未补写现有数据。微调页继续使用接口实际返回的已登记机械臂；接口详情见《前后端接口字段文档》§9.3。
- 验证：前端 `npm run build`（含 TypeScript 检查）、后端 `python -m unittest discover -s tests`（64 项，含新增 12 项配置及写接口测试）、`git diff --check` 全部通过。测试对照五臂全部 40 条传感器种子，覆盖编号/地址/类型错误、归属错误、重复登记、跨臂编辑、软删除后重新登记等；测试使用内存数据库，未执行页面交互或真机联调。前端构建仅提示产物体积较大。

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
- ~~FineTuningPage 硬编码 `deviceId: 41/42/43`~~：历史问题已由动态三轴编码解决，2026-11-05 整理时移出当前待办；旧四轴编号不再作为现行依据。
- `???` `/control/finetuning` 免认证路径下写库 `creater_id=1` 写死，无法区分实际操作人
- ~~`types.ts` 登录类型与实际响应不一致~~：当前使用已对齐的 `LoginResponse`，2026-11-05 复核，不再按旧 `UserInfo` 描述重复修改。
- 前后端交互接口已总结完毕 → 见《ROS_MES_前后端接口字段文档.md》（对应 ROS 侧"总结与前端交互的接口"条目）

## 后面版本考虑的事情

> 2026-10-05（七）：《优化建议报告》归档，历史待办曾并入本清单。原报告现位于 [archive/ROS_MES_优化建议报告.md](archive/ROS_MES_优化建议报告.md)，以下仍须以当前代码复核，不能直接视为全部尚未完成。

**安全 / 接口**

- 认证缺口整改（前后端一起改，约半小时）：后端给 `/module`、`/coordination`、`/finetuning`、四层 CRUD、`/dashboard/stats` 等裸奔接口加鉴权；前端 `request.ts` 白名单缩减为 `/login`、`/register`；`/RosTestPage` 仅开发模式开放（原报告 待办1）
- 种子账号 `admin/123456`：部署前改密码（用户决定暂不修 `sqlite_create.py` 的默认密码种子）

**性能**

- 路由懒加载：12 个页面静态 import 打成 1.24MB 单包，改 `() => import(...)` 按路由分包，收益最大（原报告 性能1）
- 同步接口阻塞等待（原报告 性能5，报告认为最值得改）：`coordination /send` 的 5 秒 `time.sleep` 轮询 + `rosbridge_gateway.dispatch()` 每次 `asyncio.run()` 新建连接，并发图纸下发会占满 FastAPI 线程池；改 `async def` + `httpx.AsyncClient` + rosbridge 长连接复用
- 列表分页：图纸列表已于 2026-11-04 完成前端分页及查询状态回归；任务/工作流的数据规模与分页需求另行核查（原报告 性能4），不要重复执行图纸分页旧待办。
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
