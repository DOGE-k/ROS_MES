# ============================================================
# ROS MES 一键部署脚本 (Windows)
# 用法：右键 - 使用 PowerShell 运行，或在 PowerShell 中执行：
#   .\deploy_windows.ps1
# ============================================================
# 注意：
#   1. 运行前请确保已安装 Node.js 18+ 和 Python 3.8+
#   2. ROS 部分需要在 Linux 环境（Ubuntu）下运行，本脚本仅处理前端和后端
#   3. 如需完整功能，需另外配置 ROS 环境和 rosbridge
# ============================================================

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  ROS MES 系统部署脚本 (Windows)" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ---- 项目根目录 ----
$PROJECT_ROOT = Split-Path -Parent $PSScriptRoot
$FRONT_DIR = Join-Path $PROJECT_ROOT "ROS_MES\ros_mes_front"
$BACK_DIR = Join-Path $PROJECT_ROOT "ROS_MES\ros_mes_hou"
$DEPLOY_DIR = $PSScriptRoot
$CONFIG_DIR = Join-Path $DEPLOY_DIR "config"

Write-Host "项目根目录: $PROJECT_ROOT" -ForegroundColor Yellow
Write-Host ""

# ---- 1. 检查环境 ----
Write-Host "[1/6] 检查运行环境..." -ForegroundColor Green

# 检查 Node.js
try {
    $nodeVer = node --version
    Write-Host "  ✓ Node.js: $nodeVer" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Node.js 未安装，请先安装 Node.js 18+" -ForegroundColor Red
    Write-Host "    下载地址: https://nodejs.org/" -ForegroundColor Red
    exit 1
}

# 检查 Python
try {
    $pyVer = python --version 2>&1
    Write-Host "  ✓ Python: $pyVer" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Python 未安装，请先安装 Python 3.8+" -ForegroundColor Red
    Write-Host "    下载地址: https://www.python.org/downloads/" -ForegroundColor Red
    exit 1
}

Write-Host ""

# ---- 2. 配置文件 ----
Write-Host "[2/6] 部署配置文件..." -ForegroundColor Green

# 后端配置
$backendEnvSrc = Join-Path $CONFIG_DIR "backend.env"
$backendEnvDst = Join-Path $BACK_DIR ".env"
if (Test-Path $backendEnvSrc) {
    Copy-Item $backendEnvSrc $backendEnvDst -Force
    Write-Host "  ✓ 后端配置已复制: ros_mes_hou/.env" -ForegroundColor Green
} else {
    Write-Host "  ⚠ 后端配置文件不存在: $backendEnvSrc" -ForegroundColor Yellow
}

# 前端配置
$frontendEnvSrc = Join-Path $CONFIG_DIR "frontend.env"
$frontendEnvDst = Join-Path $FRONT_DIR ".env.development"
if (Test-Path $frontendEnvSrc) {
    Copy-Item $frontendEnvSrc $frontendEnvDst -Force
    Write-Host "  ✓ 前端配置已复制: ros_mes_front/.env.development" -ForegroundColor Green
} else {
    Write-Host "  ⚠ 前端配置文件不存在: $frontendEnvSrc" -ForegroundColor Yellow
}

Write-Host ""

# ---- 3. 初始化数据库 ----
Write-Host "[3/6] 初始化数据库..." -ForegroundColor Green

$dbScript = Join-Path $PROJECT_ROOT "ROS_MES\sqlite_create.py"
$dbFile = Join-Path $PROJECT_ROOT "ROS_MES\ros_database.db"

if (Test-Path $dbScript) {
    if (Test-Path $dbFile) {
        $answer = Read-Host "  数据库已存在，是否重新生成？(y/N)"
        if ($answer -eq "y" -or $answer -eq "Y") {
            Remove-Item $dbFile -Force
            python $dbScript
            Write-Host "  ✓ 数据库已重新生成" -ForegroundColor Green
        } else {
            Write-Host "  ✓ 保留现有数据库" -ForegroundColor Green
        }
    } else {
        python $dbScript
        Write-Host "  ✓ 数据库已生成: ros_database.db" -ForegroundColor Green
    }
} else {
    Write-Host "  ⚠ 数据库初始化脚本不存在: $dbScript" -ForegroundColor Yellow
}

Write-Host ""

# ---- 4. 后端依赖安装 ----
Write-Host "[4/6] 安装后端 Python 依赖..." -ForegroundColor Green

$venvDir = Join-Path $BACK_DIR "venv"
$requirements = Join-Path $BACK_DIR "requirements.txt"

if (-not (Test-Path $venvDir)) {
    Write-Host "  创建虚拟环境..." -ForegroundColor Yellow
    python -m venv $venvDir
    Write-Host "  ✓ 虚拟环境已创建" -ForegroundColor Green
}

$pipPath = Join-Path $venvDir "Scripts\pip.exe"
if (Test-Path $pipPath) {
    Write-Host "  安装依赖中，请稍候..." -ForegroundColor Yellow
    & $pipPath install -r $requirements
    Write-Host "  ✓ 后端依赖安装完成" -ForegroundColor Green
} else {
    Write-Host "  ✗ 虚拟环境 pip 未找到" -ForegroundColor Red
}

Write-Host ""

# ---- 5. 前端依赖安装 ----
Write-Host "[5/6] 安装前端 npm 依赖..." -ForegroundColor Green

if (Test-Path $FRONT_DIR) {
    Push-Location $FRONT_DIR
    Write-Host "  安装依赖中，请稍候（首次可能需要 3-5 分钟）..." -ForegroundColor Yellow
    npm install
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ 前端依赖安装完成" -ForegroundColor Green
    } else {
        Write-Host "  ✗ 前端依赖安装失败" -ForegroundColor Red
    }
    Pop-Location
} else {
    Write-Host "  ✗ 前端目录不存在: $FRONT_DIR" -ForegroundColor Red
}

Write-Host ""

# ---- 6. 完成 ----
Write-Host "[6/6] 部署完成！" -ForegroundColor Green
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  启动方式：" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  【后端】" -ForegroundColor Yellow
Write-Host "    cd ROS_MES\ros_mes_hou"
Write-Host "    .\venv\Scripts\activate"
Write-Host "    uvicorn app.main:app --reload"
Write-Host "    访问: http://127.0.0.1:8000/docs"
Write-Host ""
Write-Host "  【前端】" -ForegroundColor Yellow
Write-Host "    cd ROS_MES\ros_mes_front"
Write-Host "    npm run dev"
Write-Host "    访问: http://127.0.0.1:5173"
Write-Host ""
Write-Host "  【默认账号】" -ForegroundColor Yellow
Write-Host "    用户名: admin"
Write-Host "    密码: 123456"
Write-Host ""
Write-Host "  【ROS 部分】" -ForegroundColor Yellow
Write-Host "    ROS 需要在 Ubuntu 环境下运行"
Write-Host "    详见 deploy\README_DEPLOY.md"
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
