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

    <!-- 底部急停区：上为分级局部停，下为整机急停 -->
    <div class="sidebar-bottom">
      <div class="stop-stack">
        <el-button
            class="module-stop-btn"
            :class="{ 'is-collapsed': layoutStore.fold }"
            @click="openLocalStop"
        >
          <span class="module-stop-inner">
            <span v-if="!layoutStore.fold" class="module-stop-dot"></span>
            <span>{{ layoutStore.fold ? '停' : '停模块 / 停轴' }}</span>
          </span>
          <span
            v-if="localStopVisibleCount"
            class="stop-count"
            :class="{ 'is-collapsed': layoutStore.fold }"
          >{{ localStopVisibleCount }}</span>
        </el-button>

        <div v-if="!layoutStore.fold" class="stop-divider"></div>

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
          <span v-else class="e-stop-collapsed-text">急停</span>
        </el-button>
      </div>
    </div>

  </div>

  <LocalStopPanel ref="localStopPanel" @count="localStopVisibleCount = $event" />

  <!-- 急停/解除提示：发送状态与设备实测分开，禁止定时自动恢复。 -->
  <div v-if="isEmergencyActive" class="emergency-overlay">
    <div class="emergency-content">
      <h1 style="color: white;">SYSTEM EMERGENCY STOP</h1>
      <h1 style="color: white;">{{ emergencyTitle }}</h1>
      <div class="emergency-actions">
        <el-button type="danger" :loading="releasing" :disabled="sendingStop || releasing || manuallyReleasing" @click="resetEmergency">发送解除急停指令</el-button>
        <el-button type="warning" :loading="manuallyReleasing" :disabled="sendingStop || releasing || manuallyReleasing || !safetySnapshot" @click="manuallyReleaseEmergency">人工解除急停</el-button>
        <el-button @click="isEmergencyActive = false">返回页面（保留急停状态）</el-button>
      </div>
      <p>确认机械臂已停止并完成现场处理后，可人工解除系统急停状态。</p>
      <p><el-link type="info" @click="connectionDialogVisible = true">打开调试设置</el-link></p>
    </div>
  </div>
  <el-alert v-if="safetyState !== 'clear' && !isEmergencyActive" class="release-pending-notice" :type="simulatedEmergency ? 'warning' : 'error'" :closable="false" :title="safetyNotice">
    <el-button size="small" @click="showEmergencyDetails">查看急停状态</el-button>
    <el-button size="small" @click="connectionDialogVisible = true">调试设置</el-button>
  </el-alert>
  <el-dialog v-model="connectionDialogVisible" title="调试设置" width="min(640px, 94vw)" append-to-body :z-index="100001" destroy-on-close>
    <RosConnectionSettings />
  </el-dialog>

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
import { computed, ref, onMounted, onBeforeUnmount } from 'vue';
import { ElMessage } from 'element-plus';
import { sendEmergencyStop, releaseEmergencyStop, manualReleaseEmergencyStop, getEmergencyStopState } from '@/api/rosApi';
import { useLayoutSettingStore } from '@/stores/layoutSetting';
import { useUserStore } from '@/stores/user';
import RosConnectionSettings from './UserManage/RosConnectionSettings.vue';
import LocalStopPanel from './LocalStopPanel.vue';

const router = useRouter();
const route = useRoute();
const layoutStore = useLayoutSettingStore();

// 局部停入口与全局急停并排：任何页面都能停到模块或单轴，不用先回微调页
const localStopPanel = ref(null);
const localStopVisibleCount = ref(0);
const openLocalStop = () => localStopPanel.value?.open();

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
const safetyState = ref('clear');
const safetySnapshot = ref(null);
const simulatedEmergency = ref(false);
const localEmergencyRequested = ref(false);
const emergencyTitle = computed(() => simulatedEmergency.value
  ? '模拟急停状态（未连接真实设备）'
  : safetyState.value === 'release_sent' ? '解除指令已发送，设备状态待确认'
  : localEmergencyRequested.value ? '已请求急停，设备停止状态待确认' : '检测到未确认的急停记录，请核实设备状态');
const safetyNotice = computed(() => simulatedEmergency.value ? '模拟急停状态尚未解除，模拟任务保持暂停。'
  : safetyState.value === 'release_sent' ? '解除指令已发送，设备解除状态尚未确认；新运动需通过实时状态检查。'
  : '检测到未确认的真实急停记录，运动下发保持锁定；当前没有自动发送新的急停。');
const showEmergencyDetails = () => { localEmergencyRequested.value = false; isEmergencyActive.value = true; };
const connectionDialogVisible = ref(false);
const releasing = ref(false);
const manuallyReleasing = ref(false);
const sendingStop = ref(false);
let safetyRevision = 0;
let safetyPolling = false;
let safetyPollTimer;
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
  if (sendingStop.value) return;
  sendingStop.value = true;
  safetyRevision++;
  safetySnapshot.value = null;
  localEmergencyRequested.value = true;
  isEmergencyActive.value = true;
  safetyState.value = 'stop_requested';
  try {
    const result = await sendEmergencyStop();
    if (result.success !== true) throw new Error('急停发送结果未确认');
    simulatedEmergency.value = result.simulated === true;
    safetyState.value = 'stop_sent';
    ElMessage.warning(result.simulated ? '模拟急停成功，未连接真实设备' : '急停指令已发送，设备是否停止仍需核实');
  } catch (error) {
    const errMsg =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      "急停失败，请检查后端服务或 ROS 控制节点";

    safetyState.value = 'stop_unknown';
    ElMessage.error(errMsg);
  } finally {
    sendingStop.value = false;
    cancelLongPress();
  }
};

const resetEmergency = async () => {
  if (releasing.value || sendingStop.value || manuallyReleasing.value) return;
  releasing.value = true;
  safetyRevision++;
  safetySnapshot.value = null;
  try {
    const result = await releaseEmergencyStop();
    if (result.success !== true) throw new Error('解除发送结果未确认');
    simulatedEmergency.value = result.simulated === true;
    safetyState.value = result.simulated ? 'clear' : 'release_sent';
    if (result.simulated) isEmergencyActive.value = false;
    ElMessage.info(result.simulated ? '模拟解除成功，未连接真实设备' : '解除指令已发送，设备解除状态待确认');
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || error.message || '解除失败，请核实设备状态');
  } finally {
    releasing.value = false;
  }
};

const manuallyReleaseEmergency = async () => {
  if (sendingStop.value || releasing.value || manuallyReleasing.value || !safetySnapshot.value) return;
  const snapshot = safetySnapshot.value;
  const revision = ++safetyRevision;
  manuallyReleasing.value = true;
  try {
    const result = await manualReleaseEmergencyStop({
      operator_confirmed: true,
      expected_generation: snapshot.generation,
      connection_revision: snapshot.connection_revision,
    });
    if (revision !== safetyRevision) return;
    if (result.code !== 200 || result.data?.state !== 'clear') throw new Error('人工解除结果未确认');
    safetySnapshot.value = result.data;
    safetyState.value = 'clear';
    simulatedEmergency.value = result.data.simulated === true;
    localEmergencyRequested.value = false;
    isEmergencyActive.value = false;
    ElMessage.info(result.message);
  } catch (error) {
    if (revision === safetyRevision) {
      ElMessage.error(error.response?.data?.detail || error.message || '人工解除失败，请查看最新急停状态');
    }
  } finally {
    manuallyReleasing.value = false;
    await refreshSafetyState();
  }
};

const refreshSafetyState = async (initial = false) => {
  if (safetyPolling || sendingStop.value || releasing.value || manuallyReleasing.value) return;
  safetyPolling = true;
  const revision = safetyRevision;
  try {
    const result = await getEmergencyStopState();
    // 状态加载期间若操作者已按急停，不得以旧快照覆盖。
    if (revision === safetyRevision) {
      safetySnapshot.value = result.data;
      simulatedEmergency.value = result.data.simulated === true;
      safetyState.value = result.data.state;
      // 查询和恢复历史状态只更新提示，不能当作操作者新触发急停。
      if (result.data.state === 'clear') isEmergencyActive.value = false;
    }
  } catch {
    if (initial) ElMessage.warning('无法获取控制联锁状态，请核实后端连接');
  } finally {
    safetyPolling = false;
  }
};
const connectionChanged = () => {
  safetyRevision++;
  safetySnapshot.value = null;
  localEmergencyRequested.value = false;
  isEmergencyActive.value = false;
  void refreshSafetyState();
};
onMounted(async () => {
  await refreshSafetyState(true);
  safetyPollTimer = setInterval(() => { void refreshSafetyState(); }, 1000);
  if (typeof window !== 'undefined') window.addEventListener?.('ros-connection-changed', connectionChanged);
});
onBeforeUnmount(() => {
  cancelLongPress();
  if (safetyPollTimer !== undefined) clearInterval(safetyPollTimer);
  if (typeof window !== 'undefined') window.removeEventListener?.('ros-connection-changed', connectionChanged);
});
</script>

<style scoped>
.release-pending-notice { position: fixed; right: 20px; bottom: 20px; width: min(480px, 90vw); z-index: 2100; }
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
  padding: 12px 10px 14px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

/* 两行按钮共用同一套尺寸，避免一高一矮、字号不一 */
.stop-stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

/* Element Plus 默认给相邻 el-button 加 margin-left，会把第二个按钮顶出侧栏 */
.stop-stack :deep(.el-button + .el-button) {
  margin-left: 0;
}

.module-stop-btn,
.e-stop-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  height: 42px;
  margin: 0;
  padding: 0 10px;
  border-radius: 10px;
  font-size: 13px;
  letter-spacing: 1px;
  line-height: 1;
}

.module-stop-btn {
  color: #fbbf24;
  border: 1px solid rgba(245, 158, 11, 0.45) !important;
  background: rgba(245, 158, 11, 0.12);
  box-shadow: none;
  transition: color 0.2s ease, background 0.2s ease, border-color 0.2s ease;
}

.module-stop-btn:hover {
  color: #fcd34d;
  border-color: rgba(245, 158, 11, 0.72) !important;
  background: rgba(245, 158, 11, 0.2);
}

.module-stop-btn:active {
  background: rgba(245, 158, 11, 0.28);
}

.module-stop-btn.is-collapsed {
  letter-spacing: 0;
}

.module-stop-inner {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.module-stop-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #f59e0b;
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.18);
}

/* 分级停 / 整机急停之间的细分隔，避免两块糊在一起 */
.stop-divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.07);
}

.stop-count {
  position: absolute;
  top: 50%;
  right: 8px;
  transform: translateY(-50%);
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  background: #dc2626;
  color: #fff;
  font-size: 11px;
  line-height: 18px;
  text-align: center;
  box-shadow: 0 0 0 2px rgba(17, 24, 39, 0.55);
}

.stop-count.is-collapsed {
  top: 3px;
  right: 3px;
  transform: none;
}

.e-stop-btn {
  font-weight: 600;
  border: 1px solid rgba(255, 255, 255, 0.12) !important;
  color: #fff;
  /* 保留原有的长按进度机制：背景从右向左推进 */
  background: linear-gradient(90deg, #7f1d1d 50%, #dc2626 50%);
  background-size: 200% 100%;
  background-position: 100% 0;
  transition: background-position 0s, transform 0.2s ease, box-shadow 0.2s ease;
  box-shadow: 0 4px 14px rgba(220, 38, 38, 0.35);
}

.e-stop-btn:hover {
  box-shadow: 0 6px 18px rgba(220, 38, 38, 0.5);
}

.e-stop-collapsed-text {
  font-size: 13px;
  letter-spacing: 0;
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

/* 急停遮罩层样式 */
.emergency-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  box-sizing: border-box;
  padding: 24px;
  overflow-y: auto;
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
  box-sizing: border-box;
  max-width: 100%;
  border-radius: 8px;
  background-color: rgba(255, 255, 255, 0.1);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.emergency-content h1 {
  font-size: clamp(22px, 3vw, 36px);
  margin-bottom: 20px;
  font-weight: bold;
  letter-spacing: 2px;
}

.emergency-actions {
  display: flex;
  align-items: stretch;
  justify-content: center;
  gap: 12px;
  max-width: 760px;
  margin: 24px auto 0;
}

.emergency-actions .el-button {
  flex: 1;
  height: auto;
  min-height: 44px;
  margin: 0;
  font-size: 16px;
  line-height: 1.5;
  white-space: normal;
  padding: 10px 20px;
}

@media (max-width: 600px) {
  .emergency-content {
    padding: 24px;
  }

  .emergency-actions {
    flex-direction: column;
  }

  .emergency-actions .el-button {
    width: 100%;
    flex: none;
  }
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
</style>
