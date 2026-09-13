<!-- eslint-disable -->
<template>
  <div class="aside-container" :class="{ 'is-collapsed': layoutStore.fold }">
    <!-- 品牌区 -->
    <div class="logo">
      <div class="logo-mark">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <rect x="4" y="9" width="16" height="11" rx="2"/>
          <circle cx="9" cy="14.5" r="1.4" fill="currentColor" stroke="none"/>
          <circle cx="15" cy="14.5" r="1.4" fill="currentColor" stroke="none"/>
          <path d="M12 9V5"/>
          <circle cx="12" cy="3.6" r="1.4"/>
        </svg>
      </div>
      <div v-if="!layoutStore.fold" class="logo-text">
        <span class="logo-title">ROS·MES</span>
        <span class="logo-sub">智能制造执行系统</span>
      </div>
    </div>

    <el-menu
        :default-active="activeMenu"
        class="aside-menu"
        :collapse="layoutStore.fold"
        :collapse-transition="false"
        @select="handleMenuSelect"
    >
      <el-menu-item index="/Dashboard">
        <el-icon><Odometer /></el-icon>
        <span>首页仪表盘</span>
      </el-menu-item>
      <el-menu-item index="/HardWorkPage">
        <el-icon><icon-menu /></el-icon>
        <span>设备信息管理</span>
      </el-menu-item>
      <el-menu-item index="/ModuleManagement">
        <el-icon><document /></el-icon>
        <span>模块管理</span>
      </el-menu-item>
      <el-menu-item index="/DrawingManage">
        <el-icon><PictureFilled /></el-icon>
        <span>图纸管理</span>
      </el-menu-item>
      <el-menu-item index="/WorkflowManage">
        <el-icon><List /></el-icon>
        <span>工作流管理</span>
      </el-menu-item>
      <el-menu-item index="/TaskManagement">
        <el-icon><Management /></el-icon>
        <span>任务管理</span>
      </el-menu-item>
      <el-menu-item v-if="isAdmin" index="/UserManagement">
        <el-icon><User /></el-icon>
        <span>用户管理</span>
      </el-menu-item>
      <el-menu-item index="/Profile">
        <el-icon><Setting /></el-icon> <span>个人中心</span>
      </el-menu-item>
    </el-menu>

    <!-- 底部急停按钮 -->
    <div class="sidebar-bottom">
      <el-button
          class="e-stop-btn"
          :class="{ 'pressing': isPressing, 'is-collapsed': layoutStore.fold }"
          @mousedown="startLongPress"
          @mouseup="cancelLongPress"
          @mouseleave="cancelLongPress"
          @touchstart="startLongPress"
          @touchend="cancelLongPress"
          @touchcancel="cancelLongPress"
      >
        <span v-if="!layoutStore.fold" class="e-stop-inner">
          <span class="e-stop-dot"></span>
          长按两秒急停
        </span>
        <span v-else style="font-size: 13px; letter-spacing: 0;">急停</span>
      </el-button>
    </div>

  </div>

  <!-- 急停遮罩层
  <div v-if="isEmergencyActive" class="emergency-overlay">
    <div class="emergency-content">
      <h1 style="color: white;">SYSTEM EMERGENCY STOP</h1>
      <h1 style="color: white;">系统已触发急停</h1>
      <el-button type="danger" @click="resetEmergency" class="reset-button">解除急停 (仅调试)</el-button>
    </div>
  </div> -->

</template>

<script setup>
import {
  Document,
  List,
  Management,
  Menu as IconMenu,
  User,
  Setting,
  PictureFilled,
  Odometer,
} from '@element-plus/icons-vue';
import { useRouter, useRoute } from 'vue-router';
import { computed, ref } from 'vue';
import { ElMessage } from 'element-plus';
import request from '@/utils/request';
import { useLayoutSettingStore } from '@/stores/layoutSetting';
import { useUserStore } from '@/stores/user';

const router = useRouter();
const route = useRoute();
const layoutStore = useLayoutSettingStore();

const userStore = useUserStore();
const isAdmin = computed(() => userStore.isAdmin());

const activeMenu = computed(() => {
 return route.meta?.activeMenu || route.path
});
const handleMenuSelect = (index) => {
  router.push(index);
};

// ========== 急停长按逻辑（完全保持不变） ==========
const isPressing = ref(false);
const isEmergencyActive = ref(false);
let pressTimer = null;
const LONG_PRESS_DURATION = 2000;

const startLongPress = (event) => {
  if (isEmergencyActive.value) return;
  event.preventDefault();
  if (pressTimer) clearTimeout(pressTimer);
  isPressing.value = true;
  pressTimer = setTimeout(() => {
    if (isPressing.value) {
      triggerEmergency();
    }
    isPressing.value = false;
    pressTimer = null;
  }, LONG_PRESS_DURATION);
};

const cancelLongPress = () => {
  if (pressTimer) {
    clearTimeout(pressTimer);
    pressTimer = null;
  }
  isPressing.value = false;
};

const triggerEmergency = async () => {
  try {
    await request.post("/control/emergency_stop");

    ElMessage.warning("急停指令已下发，所有机械臂停止运动");
    isEmergencyActive.value = true;

    setTimeout(() => {
      if (isEmergencyActive.value) {
        isEmergencyActive.value = false;
        ElMessage.info("系统已恢复，请谨慎操作");
      }
    }, 5000);
  } catch (error) {
    const errMsg =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      "急停失败，请检查后端服务或 ROS 控制节点";

    ElMessage.error(errMsg);
  } finally {
    cancelLongPress();
  }
};

const resetEmergency = () => {
  isEmergencyActive.value = false;
  ElMessage.info('急停已解除');
};
</script>

<style scoped>
/* 侧边栏容器：深海军蓝渐变 */
.aside-container {
  height: 100%;
  width: 100%;
  background: linear-gradient(180deg, var(--mes-aside-bg-1) 0%, var(--mes-aside-bg-2) 100%);
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
  overflow-x: hidden;
  border-right: 1px solid rgba(255, 255, 255, 0.04);
}

/* ===== 品牌区 ===== */
.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 10px;
  padding: 0 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  white-space: nowrap;
  overflow: hidden;
  flex-shrink: 0;
}

.is-collapsed .logo {
  justify-content: center;
  padding: 0;
}

.logo-mark {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.45);
  flex-shrink: 0;
}

.logo-text {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
}

.logo-title {
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 1px;
}

.logo-sub {
  color: var(--mes-aside-text);
  font-size: 11px;
  letter-spacing: 1px;
}

/* ===== 菜单 ===== */
.aside-menu {
  flex: 1;
  border-right: none;
  background: transparent;
  padding: 10px 8px;
  overflow-y: auto;
  overflow-x: hidden;
}

/* 折叠时由 Element 控制宽度，这里去掉内边距避免图标偏移 */
.aside-menu.el-menu--collapse {
  padding: 10px 4px;
  width: 100%;
}

.aside-menu :deep(.el-menu-item) {
  height: 44px;
  line-height: 44px;
  margin: 4px 0;
  border-radius: 10px;
  color: var(--mes-aside-text);
  transition: all 0.2s ease;
}

.aside-menu :deep(.el-menu-item .el-icon) {
  font-size: 17px;
}

.aside-menu :deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.06);
  color: #dbe7ff;
}

.aside-menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(90deg, #2563eb, #1d4ed8);
  color: var(--mes-aside-active);
  font-weight: 600;
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.4);
}

/* ===== 底部急停 ===== */
.sidebar-bottom {
  padding: 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.e-stop-btn {
  width: 100%;
  height: 44px;
  font-size: 14px;
  font-weight: bold;
  letter-spacing: 2px;
  border: 1px solid rgba(255, 255, 255, 0.12) !important;
  color: #fff;
  /* 保留原有的长按进度机制：背景从右向左推进 */
  background: linear-gradient(90deg, #7f1d1d 50%, #dc2626 50%);
  background-size: 200% 100%;
  background-position: 100% 0;
  transition: background-position 0s, transform 0.2s ease, box-shadow 0.2s ease;
  padding: 0;
  border-radius: 10px;
  box-shadow: 0 4px 14px rgba(220, 38, 38, 0.35);
}

.e-stop-btn:hover {
  box-shadow: 0 6px 18px rgba(220, 38, 38, 0.5);
}

.e-stop-inner {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.e-stop-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.25);
  animation: estop-pulse 2s infinite;
}

@keyframes estop-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.e-stop-btn.is-collapsed {
  border-radius: 10px;
  letter-spacing: 0;
}

.e-stop-btn.pressing {
  transform: scale(0.96);
  box-shadow: inset 0 0 20px rgba(0, 0, 0, 0.6);
  background-position: 0 0;
  transition: background-position 2s linear, transform 0.2s ease;
}

/* 急停遮罩层样式（原样保留） */
.emergency-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background-color: #df3b3b;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  animation: fadeIn 0.5s ease-in-out;
}

.emergency-content {
  text-align: center;
  color: white;
  padding: 40px;
  border-radius: 8px;
  background-color: rgba(255, 255, 255, 0.1);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.emergency-content h1 {
  font-size: 36px;
  margin-bottom: 20px;
  font-weight: bold;
  letter-spacing: 2px;
}

.reset-button {
  font-size: 16px;
  padding: 20px 36px;
  margin-top: 20px;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
</style>
