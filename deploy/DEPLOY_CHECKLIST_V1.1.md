# ROS MES 新环境部署检查清单（V1.1）

> 适用：把项目部署到一台新电脑/新工控机，并确认可运行。
> 配套文档：[部署指南 V1.1](README_DEPLOY.md) ｜ 零基础操作步骤：[零基础部署手册](BEGINNER_DEPLOY_GUIDE_V1.1.md)
> 使用方式：按顺序逐项打勾；出现「阻断项」未通过时不要继续后续步骤。
> 建议记录：目标机 IP、ROS 机 IP、项目路径、Git 提交号、数据库路径。

---

## 0. 部署信息登记

| 项目 | 填写 |
|---|---|
| 部署日期 | |
| 部署人 | |
| 目标机系统/版本 | |
| 项目路径 | `/home/____/robot_ws/src/ROS_MES` |
| Git 提交号 | |
| ROS 机 IP | |
| Web/后端机 IP | |
| 数据库路径 | |
| CAN 适配器型号/通道 | ZLG USBCAN-II / CH____ |
| 现场模块号 → SEG 映射 | |

---

## 1. 交付包检查

- [ ] 已复制完整项目目录，不是只复制 `mes_web` 或单个脚本。
- [ ] 已排除 `mes_web/ros_mes_hou/venv`、`mes_web/ros_mes_front/node_modules`、`__pycache__`、`*.pyc`、日志。
- [ ] 已确认是否需要携带 `ros_database.db`：
  - [ ] 携带：账号/图纸/微调记录保留；已确认文件完整。
  - [ ] 不携带：新环境首次执行 `sqlite_create.py`。
- [ ] 已备份原环境的 `ros_database.db`、`rob_arm.env`、后端 `.env`。
- [ ] 已记录当前 Git 提交号或代码版本，便于回滚。
- [ ] 交付包中不含生产密钥、真实密码或个人隐私数据（如必须携带，部署后立即更换）。

**阻断项：** 项目目录不完整、数据库来源不明、未记录版本 → 不得继续。

---

## 2. 目标机基础环境

### 2.1 运行 ROS 的机器（Ubuntu）

- [ ] 系统为 **Ubuntu 20.04**（ROS Noetic 官方支持）。
- [ ] 已安装 ROS Noetic（`rosversion -d` 输出 `noetic`）。
- [ ] 已安装 `ros-noetic-ros-base`、`ros-noetic-message-generation`、`ros-noetic-rosbridge-server`。
- [ ] `python3 --version` 为 3.8（ROS 系统 Python）。
- [ ] 磁盘剩余空间足够（建议 ≥ 10GB，open3d/依赖较占空间）。
- [ ] 系统时间正确（`date`），否则会影响反馈新鲜度和日志排查。

### 2.2 运行后端的机器

- [ ] 后端 Python 为 **3.10+**（`python --version`），与 ROS 的 3.8 相互隔离。
- [ ] 推荐使用 Conda 或独立 venv，未替换系统 Python。
- [ ] 已安装 Node.js **18+**（推荐 20 LTS），`node -v`、`npm -v` 正常。
- [ ] 目标端口未被占用：8000、5173（或 80）。

**阻断项：** 用 Python 3.8 跑后端、Node 低于 18 → 不得继续。

---

## 3. ROS 依赖与编译

- [ ] 已执行并成功：
  ```bash
  source /opt/ros/noetic/setup.bash
  cd ~/robot_ws
  catkin_make
  source devel/setup.bash
  ```
- [ ] `rospack find robot_control_backend` 能返回正确路径。
- [ ] 消息生成成功：`rosmsg show robot_control_backend/AxisStatus` 有输出。
- [ ] `python3 -c "import rospy, numpy, scipy, flask, can; print('ok')"` 无报错。
- [ ] `python3 -c "import open3d; print(open3d.__version__)"` 无报错。
- [ ] 已把 ROS 环境变量写入 `~/.bashrc`（或每次启动前手动 source）。
- [ ] 若项目路径变更过，已重新 `catkin_make`（不是直接拷贝旧 `devel/build`）。

**阻断项：** `catkin_make` 失败、消息包找不到、open3d 导入失败 → 不得继续。

---

## 4. CAN / ZLG 硬件检查

- [ ] 驱动包已内置：`deploy/drivers/usbcan_ii_libusb_251028/` 存在（无需额外下载）。
- [ ] 驱动包架构与目标机匹配（x64/x86/aarch64）。
- [ ] 已运行 `sudo bash deploy/install_zlg_can.sh`，或按文档手动完成安装。
- [ ] `libusbcan.so` 已放到目标机，路径与 `ZLG_LIBUSB_PATH` 一致。
- [ ] `python3 -c "import ctypes; ctypes.CDLL('/usr/local/lib/libusbcan.so')"` 能成功加载。
- [ ] 已执行 `sudo ldconfig`（库放在 `/usr/local/lib` 时）。
- [ ] `lsusb | grep 0471` 能看到 USBCAN-II 设备。
- [ ] 已配置 udev 权限规则并执行 `udevadm control --reload-rules && udevadm trigger`。
- [ ] 适配器插在主板直出 USB2.0 口，未经过外接 HUB。
- [ ] `rob_arm.env` 中 `CAN_INTERFACE=zlg`、`CAN_BITRATE=500000`、`CAN_CHANNEL` 正确。
- [ ] 下位机已上电，CAN 线/终端电阻/接线正常。
- [ ] 无其他程序占用同一 CAN 适配器。

**阻断项：** 看不到 USB 设备、库路径错误、CAN 打不开 → 不得进行真机运动测试。

---

## 5. 配置检查

### 5.1 ROS：`robot_control_backend/rob_arm.env`

- [ ] `DB_PATH` 已改成目标机**绝对路径**，且目录存在、可写。
- [ ] `DB_PATH` 与后端 `DATABASE_URL` 指向**同一个** `ros_database.db`。
- [ ] `ZLG_LIBUSB_PATH` 已改成目标机实际路径。
- [ ] `CAN_INTERFACE` / `CAN_CHANNEL` / `CAN_BITRATE` 与现场一致。
- [ ] `CAN_DEFAULT_SEG` 符合现场（单工位通常 0）。
- [ ] 三轴软限位正确：旋转 ±180、摆动 -15~15（`MAX_SWING_ANGLE`）、伸缩 -20~20。
- [ ] 话题名未被旧版本配置覆盖（尤其 `/control/axis_zero`、`/hardware/axis_status`）。
- [ ] 未直接用旧版 `deploy/config/rob_arm.env` 覆盖而未改占位路径。

### 5.2 后端：`mes_web/ros_mes_hou/.env`

- [ ] 已从模板复制 `.env`，不是空文件。
- [ ] `DATABASE_URL` 正确；从 `mes_web/ros_mes_hou` 目录启动。
- [ ] `ROSBRIDGE_URL` 指向 ROS 机 `ws://<IP>:9010`（同机 `127.0.0.1`）。
- [ ] `POINTCLOUD_VIEW_BASE_URL` 指向 ROS 机 `http://<IP>:5000`。
- [ ] `ROS_MODULE_SEG_MAP` 已按现场模块填写（如 `{"17": 0}`）。
- [ ] `SECRET_KEY` 已换成随机值，不是模板默认值。
- [ ] `ROS_VERSION=1`（ROS2 未联调前不要改）。
- [ ] 生产环境已把 `BACKEND_CORS_ORIGINS` 从 `*` 改成实际前端地址。
- [ ] 管理员默认密码已修改。

### 5.3 前端：`mes_web/ros_mes_front/.env.development`

- [ ] `VITE_API_TARGET` 指向后端实际地址（同机 `http://127.0.0.1:8000`）。
- [ ] `VITE_USE_MOCK=false`（正常联调；不要依赖已废弃的 `VITE_DEBUG_NO_ROS`）。
- [ ] 若前端在另一台机器访问，`VITE_API_TARGET` 不是 `127.0.0.1`。

**阻断项：** `DB_PATH`、`ZLG_LIBUSB_PATH`、`ROS_MODULE_SEG_MAP`、`SECRET_KEY` 未改 → 不得启动。

---

## 6. 数据库检查

- [ ] 选择了正确的数据库来源（沿用旧库或新建）。
- [ ] 沿用旧库时：文件已复制到 `DB_PATH` 指定位置，权限可读写。
- [ ] 新建库时：只在首次执行一次 `sqlite_create.py`，使用的是后端 venv 的 Python。
- [ ] 已确认建库后表结构存在（已安装 sqlite3 时执行 `sqlite3 ros_database.db ".tables"`；否则用后端 Python 查询）。
- [ ] 可用默认账号登录，或已确认现有账号存在。
- [ ] 若旧库和新库混用，已停止所有服务再替换文件（不要热覆盖）。

**阻断项：** ROS 与后端指向不同数据库、库文件只读 → 不得继续。

---

## 7. 依赖安装检查

- [ ] 后端 venv 已创建，`pip install -r requirements.txt` 成功。
- [ ] 后端 `pip check` 无依赖冲突。
- [ ] 前端 `npm install` 成功，无缺失依赖报错。
- [ ] ROS 侧 `python3 -m pip install --user -r deploy/config/ros_requirements.txt` 成功。
- [ ] ROS 与后端没有共用同一个 Python 环境。
- [ ] Windows 部署使用 `deploy_windows.ps1` 时，脚本执行到最后无红色报错。

---

## 8. 启动检查

按顺序启动，确认每一步成功后再进行下一步。

### 8.1 ROS

- [ ] 终端已 source ROS 与工作空间。
- [ ] `roslaunch robot_control_backend ros_robot.launch` 启动，无节点崩溃。
- [ ] 日志中无 `KeyError: 'DB_PATH'`、`No module named rospy`、CAN 打开失败。
- [ ] rosbridge 已监听 **9010**。
- [ ] 点云 Flask 已监听 **5000**。
- [ ] 轴状态聚合节点已启动，且没有同时启动 `sim_axis_status_node.py`。
- [ ] `rostopic list` 能看到关键话题：`/hardware/axis_status`、三轴 feedback、`/hardware/module_status`、`/control/axis_zero`。

### 8.2 后端

- [ ] 在 `mes_web/ros_mes_hou` 下启动，`uvicorn` 无异常退出。
- [ ] `curl -s http://127.0.0.1:8000/docs` 返回正常。
- [ ] 后端日志连上 rosbridge，没有持续重连报错。

### 8.3 前端

- [ ] `npm run dev -- --host 0.0.0.0` 启动成功。
- [ ] 浏览器可打开页面，静态资源无 404。
- [ ] 登录成功，个人中心能正常读取后端配置。

**阻断项：** ROS 节点崩溃、后端 8000 不通、前端无法登录 → 不得进行功能测试。

---

## 9. 功能验证

### 9.1 状态与反馈

- [ ] 模块管理页能识别机械臂/模块。
- [ ] 模块已绑定时，已给模块**断电重启**再确认（上电不会主动广播 UID）。
- [ ] `/hardware/axis_status` 在绑定后约 **5Hz** 输出；未绑定无输出属正常。
- [ ] 三轴 `base_valid=1`、状态为空闲、位置新鲜。
- [ ] 静止时位置反馈不会突然跳 0（排除残留 `sim_axis_status`）。
- [ ] `rostopic hz /hardware/rotation_feedback` 等有合理频率。

### 9.2 图纸与前端

- [ ] 上传图纸成功，三视图能打开（5000 端口）。
- [ ] 图纸模式基准能正常锁定。
- [ ] 基准未锁定时，下发按钮按预期置灰并提示。

### 9.3 微调与下发

- [ ] 单轴小增量可下发，轴节点日志有增量换算记录。
- [ ] 批次接口返回 202，状态可查询，不重复下发。
- [ ] 发送前检查能拿到新鲜状态和位置；无反馈时快速 `blocked`，不是空等。
- [ ] 结果五段值显示正常：初始 / 微调 / 应到 / 到位实测 / 偏差。
- [ ] 到位事件、停止事件、故障/限位事件能在后端/前端体现。
- [ ] 人工「标记未动」只改记录，不触发运动。

### 9.4 安全与异常

- [ ] 局部停止能停止当前动作，且不会误发全 0 急停。
- [ ] 急停/解除链路按预期工作（注意：禁止发送全 0 急停指令）。
- [ ] 伸缩到机械限位时立即停止，未出现 CAN 洪泛。
- [ ] 轴 1（旋转）已做单轴小增量验证（历史上存在电机不动作问题）。
- [ ] 摆动轴到达约 2.65° 上行软限位后，不再强行同向下发。

**阻断项：** 状态/位置无效、下发无响应、急停异常、CAN 洪泛 → 立即停止测试并排查。

---

## 10. 跨机与网络（双机部署时）

- [ ] 后端能连通 ROS 机 9010（`nc -vz <ROS_IP> 9010`）。
- [ ] 后端能连通 ROS 机 5000（点云 Flask）。
- [ ] 前端能连通后端 8000。
- [ ] 防火墙/安全组已放行 9010、5000、8000、5173（或 80）。
- [ ] 后端 `.env` 中的 IP 不是 `127.0.0.1`（跨机时）。
- [ ] 前端 `.env.development` 中的 `VITE_API_TARGET` 不是 `127.0.0.1`（跨机时）。
- [ ] 浏览器从另一台电脑访问时，WebSocket 反馈正常刷新。

---

## 11. 生产部署（如适用）

- [ ] 前端已执行 `npm run build`，`dist/` 生成成功。
- [ ] Nginx 已配置静态目录、`/api/` 反向代理和 WebSocket Upgrade。
- [ ] 后端使用 `uvicorn --workers 1`（多 worker 会导致批次状态不一致）。
- [ ] `BACKEND_CORS_ORIGINS` 已限制为实际前端地址。
- [ ] 后端、前端、ROS 已配置开机自启或明确了人工启动责任人。
- [ ] 已配置日志轮转与数据库定期备份。
- [ ] 已记录回滚步骤：停服务 → 恢复代码/配置/数据库 → 重新编译 → 按顺序启动。

---

## 12. 最终签字确认

| 检查项 | 结果 | 备注 |
|---|---|---|
| ROS 节点全部启动 | PASS / FAIL | |
| rosbridge 9010 / Flask 5000 | PASS / FAIL | |
| 后端 8000 / 前端页面 | PASS / FAIL | |
| CAN 适配器与下位机通信 | PASS / FAIL | |
| 模块确认 | PASS / FAIL | |
| 三轴状态/位置有效 | PASS / FAIL | |
| 单轴小增量下发 | PASS / FAIL | |
| 批次微调与五段值 | PASS / FAIL | |
| 停止/急停安全链路 | PASS / FAIL | |
| 数据库读写与备份 | PASS / FAIL | |

**部署结论：** 通过 / 有条件通过 / 阻断

**遗留问题与责任人：**

---

## 13. 快速排障索引

| 现象 | 优先检查 |
|---|---|
| ROS 启动报 `KeyError: 'DB_PATH'` | `rob_arm.env` 的 `DB_PATH` |
| CAN 打不开 | `ZLG_LIBUSB_PATH`、`lsusb`、udev、USB 口 |
| 后端起不来/依赖报错 | Python 是否 3.10+、venv 是否正确 |
| `No module named rospy` | 是否在 ROS 终端误激活后端 venv |
| 前端 404/跨域 | `VITE_API_TARGET`、`BACKEND_CORS_ORIGINS` |
| 后端连不上 ROS | 9010、防火墙、rosbridge 日志 |
| 模块确认失败 | 模块断电重启、`ROS_MODULE_SEG_MAP` |
| 预检一直 `blocked` | 聚合节点、绑定状态、`base_valid`、故障/限位 |
| 数据对不上 | ROS `DB_PATH` 与后端 `DATABASE_URL` 是否同一个库 |

---

*清单版本：V1.1（2026-11-20）；配套部署步骤见 [README_DEPLOY.md](README_DEPLOY.md)。*
