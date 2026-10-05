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

- 认证缺口整改（前后端一起改，约半小时）：后端给 `/module`、`/coordination`、`/finetuning`、四层 CRUD、`/dashboard/stats` 等裸奔接口加鉴权；前端 `request.ts` 白名单缩减为 `/login`、`/register`；`/RosTestPage` 仅开发模式开放
- 路由懒加载：当前打包为单个 1.24MB JS 巨包，改 `() => import(...)` 收益最大
- 遗留死代码清理：`AddItem.vue`（调用不存在的 `/hardware` 接口）、未被页面调用的 API 封装（`GET /finetuning/`、`GET /drawing/{id}`、`GET /task/{id}` 等）
- work/workflow 写接口参数迁移到 JSON body（现走 query string，与其它模块不一致）
