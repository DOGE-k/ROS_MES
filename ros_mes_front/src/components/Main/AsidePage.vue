<!-- eslint-disable -->
<template>
  <div class="aside-container" :class="{ 'is-collapsed': layoutStore.fold }">
    <div class="logo">
      <span v-if="!layoutStore.fold">MES 核心控制台</span>
      <span v-else>MES</span>
    </div>

    <el-menu
        :default-active="activeMenu"
        class="el-menu-vertical-demo"
        :collapse="layoutStore.fold"
        :collapse-transition="false"
        @select="handleMenuSelect"
        background-color="#2b3243"
        active-text-color="#409eff"
        text-color="#fff"
    >
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
      <el-menu-item v-if="isAdmin" index="/UserManagement">
        <el-icon><User /></el-icon>
        <span>用户管理</span>
      </el-menu-item>
      <el-menu-item index="/Profile">
        <el-icon><Setting /></el-icon> <span>个人中心</span>
      </el-menu-item>
    </el-menu>

    <!-- 底部急停按钮（样式与 Mes.html 完全一致） -->
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
        <span v-if="!layoutStore.fold">长按两秒急停</span>
        <span v-else style="font-size: 14px; letter-spacing: 0;">急停</span>
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
  Menu as IconMenu,
  User,
  Setting,
  PictureFilled,
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
/* 侧边栏容器：宽度由父组件控制，这里设置 100% 撑满 */
.aside-container {
  height: 100%;
  width: 100%;
  background-color: #2b3243;
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
  overflow-x: hidden;
}

/* Logo 样式（与 Mes.html 完全一致） */
.logo {
  height: 50px;
  line-height: 50px;
  text-align: center;
  color: #fff;
  font-size: 16px;
  font-weight: bold;
  border-bottom: 1px solid #1f2430;
  white-space: nowrap;
  overflow: hidden;
}

/* 菜单样式：边框、背景继承自 el-menu 属性 */
.el-menu-vertical-demo {
  flex: 1;
  border-right: none;
  background-color: #2b3243;
}

/* 底部容器（与 Mes.html 一致） */
.sidebar-bottom {
  padding: 8px;
}

/* 急停按钮样式（完全复制 Mes.html） */
.e-stop-btn {
  width: 100%;
  height: 45px;
  font-size: 15px;
  font-weight: bold;
  letter-spacing: 2px;
  border: none !important;
  color: white;
  background: linear-gradient(90deg, #8b0000 50%, #f56c6c 50%);
  background-size: 200% 100%;
  background-position: 100% 0;
  transition: background-position 0s, transform 0.2s ease;
  padding: 0;
  border-radius: 4px;
}

.e-stop-btn.is-collapsed {
  border-radius: 4px;
}

.e-stop-btn.pressing {
  transform: scale(0.95);
  box-shadow: inset 0 0 20px rgba(0,0,0,0.6);
  background-position: 0 0;
  transition: background-position 2s linear, transform 0.2s ease;
}

/* 折叠时菜单项文字隐藏（Element Plus 自动处理，无需额外代码） */

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