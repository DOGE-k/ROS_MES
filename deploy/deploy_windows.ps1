# ============================================================
# ROS MES 一键部署脚本 (Windows，仅前端 + 后端)
# 用法：在 PowerShell 中执行：
#   cd ROS_MES\deploy
#   .\deploy_windows.ps1
#
# 注意：
#   1. 需要 Node.js 18+ 和 Python 3.10+；
#   2. ROS 部分必须在 Ubuntu 20.04 + ROS Noetic 下运行，本脚本不处理；
#   3. 脚本只安装前后端依赖并初始化数据库，不启动服务。
# ============================================================

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  ROS MES 部署脚本 V1.1 (Windows 前后端)" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ---- 项目根目录（本脚本位于 ROS_MES\deploy）----
$PROJECT_ROOT = Split-Path -Parent $PSScriptRoot
$FRONT_DIR = Join-Path $PROJECT_ROOT "mes_web\ros_mes_front"
$BACK_DIR = Join-Path $PROJECT_ROOT "mes_web\ros_mes_hou"
$CONFIG_DIR = Join-Path $PSScriptRoot "config"

Write-Host "项目根目录: $PROJECT_ROOT" -ForegroundColor Yellow
Write-Host ""

# ---- 1. 检查环境 ----
Write-Host "[1/5] 检查运行环境..." -ForegroundColor Green

try {
    $nodeVer = node --version
    Write-Host "  OK Node.js: $nodeVer" -ForegroundColor Green
} catch {
    Write-Host "  X Node.js 未安装，请安装 Node.js 18+（推荐 20 LTS）" -ForegroundColor Red
    Write-Host "    https://nodejs.org/" -ForegroundColor Red
    exit 1
}

try {
    $pyVer = python --version 2>&1
    Write-Host "  OK Python: $pyVer" -ForegroundColor Green
} catch {
    Write-Host "  X Python 未安装，请安装 Python 3.10+" -ForegroundColor Red
    Write-Host "    https://www.python.org/downloads/" -ForegroundColor Red
    exit 1
}

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Host "  X 当前 Python 低于 3.10，后端无法运行" -ForegroundColor Red
    Write-Host "    请安装 Python 3.10+ 并确保 python 指向新版本" -ForegroundColor Red
    exit 1
}

Write-Host ""

# ---- 2. 配置文件 ----
Write-Host "[2/5] 部署配置文件..." -ForegroundColor Green

$backendEnvSrc = Join-Path $CONFIG_DIR "backend.env"
$backendEnvDst = Join-Path $BACK_DIR ".env"
if (Test-Path $backendEnvSrc) {
    Copy-Item $backendEnvSrc $backendEnvDst -Force
    Write-Host "  OK 后端配置: mes_web\ros_mes_hou\.env" -ForegroundColor Green
    Write-Host "     请按现场修改 ROSBRIDGE_URL、POINTCLOUD_VIEW_BASE_URL、ROS_MODULE_SEG_MAP、SECRET_KEY" -ForegroundColor Yellow
} else {
    Write-Host "  ! 缺少后端配置模板: $backendEnvSrc" -ForegroundColor Yellow
}

$frontendEnvSrc = Join-Path $CONFIG_DIR "frontend.env"
$frontendEnvDst = Join-Path $FRONT_DIR ".env.development"
if (Test-Path $frontendEnvSrc) {
    Copy-Item $frontendEnvSrc $frontendEnvDst -Force
    Write-Host "  OK 前端配置: mes_web\ros_mes_front\.env.development" -ForegroundColor Green
} else {
    Write-Host "  ! 缺少前端配置模板: $frontendEnvSrc" -ForegroundColor Yellow
}

Write-Host ""

# ---- 3. 后端虚拟环境与依赖 ----
Write-Host "[3/5] 安装后端 Python 依赖..." -ForegroundColor Green

$venvDir = Join-Path $BACK_DIR "venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$requirements = Join-Path $BACK_DIR "requirements.txt"

if (-not (Test-Path $venvPython)) {
    Write-Host "  创建虚拟环境..." -ForegroundColor Yellow
    python -m venv $venvDir
}

if (Test-Path $venvPython) {
    Write-Host "  安装依赖，请稍候..." -ForegroundColor Yellow
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r $requirements
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  X 后端依赖安装失败" -ForegroundColor Red
        exit 1
    }
    Write-Host "  OK 后端依赖安装完成" -ForegroundColor Green
} else {
    Write-Host "  X 虚拟环境创建失败" -ForegroundColor Red
    exit 1
}

Write-Host ""

# ---- 4. 初始化数据库 ----
Write-Host "[4/5] 初始化数据库..." -ForegroundColor Green

$dbScript = Join-Path $PROJECT_ROOT "sqlite_create.py"
$dbFile = Join-Path $PROJECT_ROOT "ros_database.db"

if (-not (Test-Path $dbScript)) {
    Write-Host "  ! 找不到建库脚本: $dbScript" -ForegroundColor Yellow
} elseif (Test-Path $dbFile) {
    $answer = Read-Host "  数据库已存在，是否删除并重新生成？(y/N)"
    if ($answer -eq "y" -or $answer -eq "Y") {
        Remove-Item $dbFile -Force
        & $venvPython $dbScript
        Write-Host "  OK 数据库已重新生成" -ForegroundColor Green
    } else {
        Write-Host "  OK 保留现有数据库" -ForegroundColor Green
    }
} else {
    & $venvPython $dbScript
    Write-Host "  OK 数据库已生成: ros_database.db" -ForegroundColor Green
}

Write-Host ""

# ---- 5. 前端依赖 ----
Write-Host "[5/5] 安装前端 npm 依赖..." -ForegroundColor Green

if (Test-Path $FRONT_DIR) {
    Push-Location $FRONT_DIR
    npm install
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK 前端依赖安装完成" -ForegroundColor Green
    } else {
        Write-Host "  X 前端依赖安装失败" -ForegroundColor Red
    }
    Pop-Location
} else {
    Write-Host "  X 前端目录不存在: $FRONT_DIR" -ForegroundColor Red
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  部署完成，启动方式：" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  【后端】" -ForegroundColor Yellow
Write-Host "    cd `"$BACK_DIR`""
Write-Host "    .\venv\Scripts\activate"
Write-Host "    python start_server.py"
Write-Host "    访问: http://127.0.0.1:8000/docs"
Write-Host ""
Write-Host "  【前端】" -ForegroundColor Yellow
Write-Host "    cd `"$FRONT_DIR`""
Write-Host "    npm run dev -- --host 0.0.0.0"
Write-Host "    访问: http://127.0.0.1:5173"
Write-Host ""
Write-Host "  【默认账号】admin / 123456" -ForegroundColor Yellow
Write-Host ""
Write-Host "  【ROS】Ubuntu 20.04 + ROS Noetic，见 deploy\README_DEPLOY.md" -ForegroundColor Yellow
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
