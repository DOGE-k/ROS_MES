# ROS MES 零基础部署手册（V1.1）

> 读者：没装过 ROS、没用过 Ubuntu，也能一步一步跟着做。
> 技术细节和配置含义见 [部署指南 V1.1](README_DEPLOY.md)；逐项验收见 [部署检查清单](DEPLOY_CHECKLIST_V1.1.md)。

---

## 0. 先选路线，不要一上来就接真机

| 路线 | 你需要什么 | 能做什么 | 建议 |
|---|---|---|---|
| **路线 A：只看页面** | 一台 Ubuntu 或 Windows 电脑 | 登录、看页面、演示流程，不需要 ROS 和机械臂 | **先做这个**，确认项目能跑 |
| **路线 B：接真机** | Ubuntu 20.04 + ROS + ZLG USBCAN-II + 机械臂 | 真实模块确认、三轴微调、批次下发 | 路线 A 成功后再做 |

本手册的顺序就是：**先做路线 A，成功后再做路线 B**。不要跳过 A 直接接真机。

> **想最快跑起来？** 路线 A 在项目根目录执行 `bash deploy/install_all.sh --mock-only`；路线 B 执行 `bash deploy/install_all.sh`。脚本会自动装依赖、初始化配置，并在最后运行 `deploy/check_deploy.sh` 自检。下面的手动步骤用于理解过程或排错。

> 如果电脑是 Ubuntu 22.04/24.04：ROS Noetic 不支持，路线 B 需要换成 Ubuntu 20.04。路线 A 不受影响。
> 如果只有 Windows：路线 A 可以做（见第 7 节），路线 B 必须有一台 Ubuntu 20.04。

---

## 1. 你需要准备

- [ ] 一台能正常上网的电脑。
- [ ] 项目压缩包（`ROS_MES.zip` 或整个 `ROS_MES` 文件夹）。
- [ ] 如果是路线 B：机械臂已上电、ZLG USBCAN-II 适配器、CAN 线。
- [ ] 如果是路线 B：无需单独准备 `libusbcan.so`，驱动包已内置（见 6.2）。

---

## 2. 先认识 5 个东西

1. **终端**：Ubuntu 里按 `Ctrl + Alt + T` 打开的黑框，用来输入命令。
2. **复制粘贴**：终端里粘贴用 `Ctrl + Shift + V`，不是 `Ctrl + V`。
3. **不要输入 `$`**：文档里的 `$` 只是提示“这是命令”，复制时不要带。
4. **终端不能关**：启动服务的终端一关，服务就停了。
5. **路径**：本项目统一放在 `~/robot_ws/src/ROS_MES`。`~` 表示你的用户主目录。

检查系统版本：

```bash
lsb_release -a
```

✅ 成功标志：`Release:` 显示 `20.04`。
❌ 如果不是 20.04：路线 B 先装 Ubuntu 20.04；路线 A 可继续。

---

## 3. 把项目放到正确位置

先建工作空间目录：

```bash
mkdir -p ~/robot_ws/src
```

把 `ROS_MES.zip` 放到 `~/Downloads`，然后解压：

```bash
sudo apt update
sudo apt install -y unzip
cd ~/Downloads
unzip ROS_MES.zip -d ~/robot_ws/src/
```

检查路径是否正确：

```bash
ls ~/robot_ws/src/ROS_MES
```

✅ 成功标志：能看到 `README.md`、`robot_control_backend`、`mes_web`、`deploy` 这些内容。

❌ 如果看到的是 `~/robot_ws/src/ROS_MES/ROS_MES`（套了两层），把它移出来：

```bash
mv ~/robot_ws/src/ROS_MES/ROS_MES ~/robot_ws/src/ROS_MES_tmp
rmdir ~/robot_ws/src/ROS_MES
mv ~/robot_ws/src/ROS_MES_tmp ~/robot_ws/src/ROS_MES
```

---

## 4. 安装 Python 3.10+ 和 Node.js

后端需要 Python 3.10 以上，**不能用 Ubuntu 自带的 3.8**。前端需要 Node 18 以上。

### 4.1 安装 Python 3.11

```bash
sudo apt update
sudo apt install -y software-properties-common curl
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip
```

检查：

```bash
python3.11 --version
```

✅ 成功标志：显示 `Python 3.11.x`。

### 4.2 安装 Node.js 20

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

检查：

```bash
node -v
npm -v
```

✅ 成功标志：`node -v` 显示 `v20.x`，`npm -v` 显示版本号。

---

## 5. 路线 A：先让页面跑起来（不需要 ROS）

这一节全部在同一个用户下完成，不要用 `sudo` 跑 `pip` 或 `npm`。

> 最快方式：`cd ~/robot_ws/src/ROS_MES && bash deploy/install_all.sh --mock-only`，完成后直接跳到 5.6 打开页面。下面的 5.1~5.5 是手动步骤，用于理解或排错。

### 5.1 安装后端依赖

```bash
cd ~/robot_ws/src/ROS_MES/mes_web/ros_mes_hou
cp ../../deploy/config/backend.env .env
python3.11 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

✅ 成功标志：最后没有红色 `ERROR`，并且命令行前面出现 `(venv)`。

❌ 下载很慢时，可以改用国内镜像重试：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 5.2 初始化数据库

先退出后端环境：

```bash
deactivate
```

然后建库：

```bash
cd ~/robot_ws/src/ROS_MES
mes_web/ros_mes_hou/venv/bin/python sqlite_create.py
ls -lh ros_database.db
```

✅ 成功标志：生成 `ros_database.db`，命令没有报错。

> 如果项目包里已经带了 `ros_database.db`，**不要**再执行 `sqlite_create.py`，直接跳到 5.3。

### 5.3 安装前端依赖

```bash
cd ~/robot_ws/src/ROS_MES/mes_web/ros_mes_front
cp ../../deploy/config/frontend.env .env.development
npm install
```

✅ 成功标志：生成 `node_modules` 目录，最后没有 `npm ERR!`。

❌ 下载慢时可以设置镜像后重试：

```bash
npm config set registry https://registry.npmmirror.com
npm install
```

### 5.4 启动后端（终端 1）

新开一个终端：

```bash
cd ~/robot_ws/src/ROS_MES/mes_web/ros_mes_hou
source venv/bin/activate
python start_server.py
```

✅ 成功标志：出现 `Uvicorn running on http://0.0.0.0:8000`。
**这个终端不要关。**

### 5.5 启动前端（终端 2）

再新开一个终端：

```bash
cd ~/robot_ws/src/ROS_MES/mes_web/ros_mes_front
npm run dev -- --host 0.0.0.0
```

✅ 成功标志：出现 `Local: http://localhost:5173/`。
**这个终端也不要关。**

### 5.6 打开页面并切到模拟模式

浏览器访问：

```text
http://127.0.0.1:5173
```

- 账号：`admin`
- 密码：`123456`

> 如果用的是别人已经用过的数据库，账号密码可能已经改过，请用原来的账号登录；`admin / 123456` 只适用于新建的库。

登录后进入「个人中心 → 调试设置」：

1. ROS 通信：选择**模拟连接**（`ros_mode=mock`）。
2. 图纸/微调数据源：选择**模拟**（`drawing_mode=mock`）。
3. 保存。

✅ 路线 A 成功标志：

- 页面能正常打开，不白屏。
- 能登录。
- 能进入图纸、微调等页面，不报“连接失败”。

> 路线 A 不需要 ROS、不需要 CAN、不需要机械臂。先做到这里，再考虑路线 B。

---

## 6. 路线 B：接真机

前置条件：路线 A 已经成功。

> 最快方式：`cd ~/robot_ws/src/ROS_MES && bash deploy/install_all.sh`，脚本会完成 6.1~6.9 的依赖安装、配置和编译，然后从 6.10 模块确认继续。下面的手动步骤用于理解或排错。

### 6.1 安装 ROS Noetic

```bash
sudo apt update
sudo apt install -y curl gnupg2 lsb-release
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  -o /usr/share/keyrings/ros-archive-keyring.gpg

echo "deb [signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros/ubuntu focal main" \
  | sudo tee /etc/apt/sources.list.d/ros-latest.list

sudo apt update
sudo apt install -y ros-noetic-desktop-full ros-noetic-rosbridge-server \
  ros-noetic-message-generation build-essential cmake
```

把 ROS 环境写入终端配置：

```bash
echo "source /opt/ros/noetic/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

检查：

```bash
rosversion -d
```

✅ 成功标志：输出 `noetic`。

❌ 报 `Unable to locate package ros-noetic-desktop-full`：
说明 ROS 软件源没加成功，或系统不是 20.04。先执行 `lsb_release -a` 确认版本，再重新执行上面的软件源命令。

### 6.2 安装 ZLG CAN 驱动（最容易卡住）

先说明：**`libusbcan.so` 是 ZLG 官方预编译库，不是本项目编译生成的**。
驱动包里的 `Makefile` 只编译 `test`/`test_zuds` 示例；项目里的 `zlg_bus.py` 只是用 `ctypes` 调用它，也不会生成这个库。

**驱动包已内置在项目里，无需额外下载。** 位置：

```text
~/robot_ws/src/ROS_MES/deploy/drivers/usbcan_ii_libusb_251028/
├── usbcan_ii_libusb_x64/      # Intel/AMD 64 位（大多数电脑）
├── usbcan_ii_libusb_x86/      # 32 位
└── usbcan_ii_libusb_aarch64/  # ARM 64 位
```

> 驱动库版权归 ZLG；如果仓库要公开，先确认厂商的再分发授权。

推荐用项目自带脚本自动安装（会自动判断架构、装 libusb、复制库、写 udev 规则）：

```bash
cd ~/robot_ws/src/ROS_MES
sudo bash deploy/install_zlg_can.sh
```

如果要指定其他驱动目录，用 `--driver-dir`：

```bash
sudo bash deploy/install_zlg_can.sh \
  --driver-dir deploy/drivers/usbcan_ii_libusb_251028/usbcan_ii_libusb_x64
```

先预览、不改系统（不需要 sudo）：

```bash
bash deploy/install_zlg_can.sh --dry-run
```

✅ 成功标志：

- 脚本显示 `libusbcan.so 加载成功`；
- 插着适配器时能看到 `0471:1200`；
- 最后提示 `安装完成`。

❌ 如果提示“找不到驱动库”：

- 确认 `~/robot_ws/src/ROS_MES/deploy/drivers/usbcan_ii_libusb_251028/` 存在；
- 如果这个目录被裁剪掉了，从原机器复制整个 `can驱动` 文件夹，或向 ZLG/设备供应商索取 Linux 对应架构版本，再用 `--driver-dir` 指定；
- 不要把 x86 的库拷到 x64 机器上，架构不匹配会加载失败。

<details>
<summary>不想用脚本时，手动安装（点开）</summary>

```bash
sudo apt install -y libusb-1.0-0 usbutils
sudo install -m 0644 /你的路径/libusbcan.so /usr/local/lib/libusbcan.so
sudo ldconfig

echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="0471", ATTR{idProduct}=="1200", MODE="0666"' \
  | sudo tee /etc/udev/rules.d/99-zlg-usbcan.rules
sudo udevadm control --reload-rules && sudo udevadm trigger

lsusb | grep 0471
python3 -c "import ctypes; ctypes.CDLL('/usr/local/lib/libusbcan.so'); print('lib OK')"
```

</details>

把适配器插在**主板直出的 USB2.0 口**，不要用外接 HUB。

### 6.3 安装 ROS 节点依赖

```bash
cd ~/robot_ws/src/ROS_MES
python3 -m pip install --user --upgrade pip
python3 -m pip install --user -r deploy/config/ros_requirements.txt
```

✅ 成功标志：没有 `ERROR`。

检查关键包：

```bash
python3 -c "import rospy, numpy, scipy, flask, can; print('ROS deps OK')"
python3 -c "import open3d; print(open3d.__version__)"
```

❌ `open3d` 安装失败时，先升级 pip 再重试：

```bash
python3 -m pip install --user --upgrade pip
python3 -m pip install --user "open3d==0.15.2"
```

### 6.4 编译 ROS 工作空间

```bash
cd ~/robot_ws
catkin_make
source devel/setup.bash
```

✅ 成功标志：最后出现 `[100%] Built target ...`，没有 `Error`。

检查：

```bash
rospack find robot_control_backend
rosmsg show robot_control_backend/AxisStatus
```

✅ 成功标志：第一条输出项目路径；第二条能显示消息字段。

### 6.5 修改 ROS 配置（只改 3 行）

先查你的用户名和主目录：

```bash
whoami
echo $HOME
```

用文本编辑器打开配置：

```bash
gedit ~/robot_ws/src/ROS_MES/robot_control_backend/rob_arm.env
```

找到并修改：

```ini
# 改成你自己的实际路径
DB_PATH=/home/你的用户名/robot_ws/src/ROS_MES/ros_database.db

# 适配器通道，一般是 0
CAN_CHANNEL=0
```

如果文件里**没有** `ZLG_LIBUSB_PATH`，就在 `CAN_CHANNEL` 下面新增一行：

```ini
ZLG_LIBUSB_PATH=/usr/local/lib/libusbcan.so
```

保存后确认：

```bash
grep -n "^DB_PATH\|^ZLG_LIBUSB_PATH\|^CAN_CHANNEL" \
  ~/robot_ws/src/ROS_MES/robot_control_backend/rob_arm.env
```

✅ 成功标志：三条都显示正确，`DB_PATH` 不是 `/home/yang/...`。

> 如果没有 `gedit`，把命令里的 `gedit` 换成 `nano`，保存按 `Ctrl + O`、回车，退出按 `Ctrl + X`。

### 6.6 修改后端配置

打开：

```bash
gedit ~/robot_ws/src/ROS_MES/mes_web/ros_mes_hou/.env
```

确认或修改：

```ini
DATABASE_URL=sqlite:///../../ros_database.db
ROSBRIDGE_URL=ws://127.0.0.1:9010
POINTCLOUD_VIEW_BASE_URL=http://127.0.0.1:5000
ROS_MODULE_SEG_MAP={"17": 0}
SECRET_KEY=改成一长串随机字符
```

说明：

- 前后端在同一台电脑：保持 `127.0.0.1`。
- 后端在另一台电脑：把 `127.0.0.1` 改成 ROS 机器的 IP。
- `ROS_MODULE_SEG_MAP` 按现场模块号改，不确定就问负责硬件的人。
- `SECRET_KEY` 随便改成一长串字母数字即可，不要保留模板默认值。

### 6.7 启动 ROS（终端 1）

```bash
source /opt/ros/noetic/setup.bash
source ~/robot_ws/devel/setup.bash
roslaunch robot_control_backend ros_robot.launch
```

✅ 成功标志：

- 终端持续输出节点日志，没有节点反复崩溃。
- 没有 `KeyError: 'DB_PATH'`。
- 没有 `No module named rospy`。
- 没有 CAN 打开失败。

**这个终端不要关。**

### 6.8 检查 ROS 端口（终端 4）

新开终端：

```bash
ss -lntp | grep -E '9010|5000'
```

✅ 成功标志：能看到 9010（rosbridge）和 5000（点云服务）。

❌ 只有 5000、没有 9010：看 6.7 的终端日志，rosbridge 没启动成功。

### 6.9 启动后端和前端

后端（终端 2）：

```bash
cd ~/robot_ws/src/ROS_MES/mes_web/ros_mes_hou
source venv/bin/activate
python start_server.py
```

前端（终端 3）：

```bash
cd ~/robot_ws/src/ROS_MES/mes_web/ros_mes_front
npm run dev -- --host 0.0.0.0
```

然后回到页面「个人中心 → 调试设置」，把 ROS 通信改回**真实连接**，保存。

### 6.10 模块确认

1. 打开模块管理页面。
2. 如果提示模块未确认：给模块**断电再上电**，然后重新确认。
   - 原因：模块已绑定时，上电不会主动广播 UID。
3. 确认后观察三轴状态：应显示基准有效、空闲、位置有反馈。

✅ 成功标志：能看到三轴状态和位置，不再是“未绑定/无效”。

### 6.11 第一次动轴（必须小增量）

- 先只动一个轴，输入很小的值（例如 1° 或 1mm）。
- 观察页面反馈和机械臂动作。
- 如果指令被接受但电机不动作，立即停止，不要连续下发。
- 摆动轴到达约 2.65° 上行软限位后，不要继续同向下发。
- 伸缩轴到机械限位后，立即发送停止，避免 CAN 总线被刷满。
- **绝对不要下发全 0 的急停指令**，会锁死系统，只能重新上电。

✅ 路线 B 成功标志：

- 模块确认成功。
- 三轴状态有效、位置正常。
- 单轴小增量能下发并看到反馈。
- 停止功能正常。

---

## 7. 只有 Windows，怎么做路线 A

Windows 不能跑 ROS 真机，但可以跑前端 + 后端看页面。

### 7.1 安装软件

- Python 3.10 以上：https://www.python.org/downloads/
- Node.js 18 以上：https://nodejs.org/
- 解压项目到 `C:\robot_ws\src\ROS_MES`。

### 7.2 运行一键脚本

打开 PowerShell：

```powershell
cd C:\robot_ws\src\ROS_MES\deploy
Set-ExecutionPolicy -Scope Process Bypass
.\deploy_windows.ps1
```

✅ 成功标志：脚本最后显示“部署完成”，没有红色报错。

### 7.3 启动

后端（PowerShell 窗口 1）：

```powershell
cd C:\robot_ws\src\ROS_MES\mes_web\ros_mes_hou
.\venv\Scripts\activate
python start_server.py
```

前端（PowerShell 窗口 2）：

```powershell
cd C:\robot_ws\src\ROS_MES\mes_web\ros_mes_front
npm run dev -- --host 0.0.0.0
```

浏览器打开 `http://127.0.0.1:5173`，登录后在调试设置里选模拟连接。

---

## 8. 怎么判断真的成功了

| 检查 | 路线 A | 路线 B |
|---|---|---|
| 后端 8000 | `curl http://127.0.0.1:8000/docs` 有页面 | 同左 |
| 前端 5173 | 能登录、不白屏 | 同左 |
| ROS 9010 | 不需要 | `ss -lntp \| grep 9010` 有输出 |
| 点云 5000 | 不需要 | `ss -lntp \| grep 5000` 有输出 |
| 轴状态 | 不需要 | 模块确认后约 5Hz，状态有效 |
| 下发 | 页面演示即可 | 单轴小增量有反馈 |

---

## 9. 最常见的报错（照着查）

| 报错/现象 | 原因 | 处理 |
|---|---|---|
| `Unable to locate package ros-noetic-desktop-full` | ROS 源没加/系统不是 20.04 | 确认 `lsb_release -a`，重做 6.1 |
| `catkin_make: command not found` | 没 source ROS | `source /opt/ros/noetic/setup.bash` |
| `KeyError: 'DB_PATH'` | `rob_arm.env` 没改 | 按 6.5 改绝对路径 |
| `No module named rospy` | 在 ROS 终端里激活了后端 venv | 关掉终端重开，不要再 `source venv/bin/activate` |
| `ModuleNotFoundError: No module named 'fastapi'` | 后端 venv 没激活，或用了 Python 3.8 | 确认 `(venv)` 且 `python --version` ≥ 3.10 |
| `libusbcan.so: cannot open shared object file` | 库路径不对/没 `ldconfig` | 检查 `ZLG_LIBUSB_PATH`，执行 `sudo ldconfig` |
| `VCI_OpenDevice` 失败 | USB 权限/端口/适配器状态 | 查 `lsusb`、udev、换 USB 口 |
| `Address already in use` | 端口被旧进程占用 | `ss -lntp \| grep 8000`，结束旧进程 |
| 前端能开但接口 404 | `VITE_API_TARGET` 错/后端没起 | 改地址，确认 8000 可访问 |
| 页面白屏 | 前端构建/依赖问题 | 看浏览器 F12 控制台，重跑 `npm install` |
| 模块确认失败 | 模块已绑定未广播/SEG 映射错 | 模块断电重启，改 `ROS_MODULE_SEG_MAP` |
| 下发一直被拦截 | 没有有效轴状态/位置 | 确认聚合节点在跑、模块已绑定、无故障/限位 |

---

## 10. 每天怎么启动、怎么关闭

### 启动顺序

1. ROS：`roslaunch robot_control_backend ros_robot.launch`
2. 后端：`python start_server.py`
3. 前端：`npm run dev -- --host 0.0.0.0`

### 关闭顺序

1. 前端终端按 `Ctrl + C`
2. 后端终端按 `Ctrl + C`
3. ROS 终端按 `Ctrl + C`

> 机械臂运动过程中不要关任何终端，先停止动作再关。

### 每次关机前

```bash
cp ~/robot_ws/src/ROS_MES/ros_database.db ~/ros_database_backup_$(date +%F).db
```

---

## 11. 术语表

| 词 | 一句话解释 |
|---|---|
| Ubuntu | 本项目的操作系统，ROS 必须跑在它上面 |
| 终端 | 输入命令的窗口 |
| ROS | 机器人控制系统，负责和机械臂通信 |
| Noetic | 本项目使用的 ROS 版本，只支持 Ubuntu 20.04 |
| `catkin_make` | 编译 ROS 程序的命令 |
| `roslaunch` | 一次启动多个 ROS 节点 |
| rosbridge | ROS 对外的 WebSocket 接口，端口 9010 |
| venv | Python 独立环境，避免污染系统 |
| SEG | 机械臂/工位编号，和业务模块号绑定 |
| CAN | 机械臂通信总线，本项目 500kbps |
| Mock/模拟 | 不接硬件，用假数据跑页面 |

---

## 12. 文件位置速查

| 内容 | 路径 |
|---|---|
| 项目根目录 | `~/robot_ws/src/ROS_MES` |
| ROS 配置 | `~/robot_ws/src/ROS_MES/robot_control_backend/rob_arm.env` |
| 后端配置 | `~/robot_ws/src/ROS_MES/mes_web/ros_mes_hou/.env` |
| 前端配置 | `~/robot_ws/src/ROS_MES/mes_web/ros_mes_front/.env.development` |
| 数据库 | `~/robot_ws/src/ROS_MES/ros_database.db` |
| 后端启动 | `~/robot_ws/src/ROS_MES/mes_web/ros_mes_hou/start_server.py` |
| 前端启动 | `~/robot_ws/src/ROS_MES/mes_web/ros_mes_front` |
| ROS 启动 | `robot_control_backend/launch/ros_robot.launch` |

---

*手册版本：V1.1（2026-11-20）。先完成路线 A，再动真机；任何一步出现“阻断项”，先停下排查，不要继续往下做。*
