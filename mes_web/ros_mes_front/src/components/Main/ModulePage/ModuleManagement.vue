<template>
  <div class="module-management mes-page">
    <div class="mes-page-header">
      <div>
        <h2 class="mes-page-title">模块管理与姿态调度</h2>
        <p class="mes-page-sub">{{ debugSettings.skipDrawingBinding ? '调试模式：选择模块后确认机械臂，跳过图纸绑定' : '先锁定模块坐标，下一步一次完成机械臂确认与图纸下发' }}</p>
      </div>
    </div>
    <div class="outer-table">
      <!-- 会话保持开启时提示可续接；不自动跳转，避免阻断换模块 -->
      <el-card v-if="heldSession" shadow="never" class="session-banner">
        <div class="session-banner-body">
          <div class="session-banner-text">
            <span class="step-kicker">SESSION HELD</span>
            <strong>
              进行中的微调会话 · 模块 {{ heldSession.module_id
              }}<span v-if="heldSession.x && heldSession.y"> ({{ heldSession.x }},{{ heldSession.y }})</span>
            </strong>
            <span class="session-banner-meta">
              机械臂 {{ heldUnitText }} · {{ heldRemainingText }} · 续接不再握手，按 MES 记录恢复
            </span>
          </div>
          <div class="session-banner-actions">
            <el-button type="primary" :loading="sessionBusy" @click="handleResumeSession">继续微调</el-button>
            <el-button :disabled="sessionBusy" @click="handleCloseSession">结束会话</el-button>
          </div>
        </div>
      </el-card>
      <div class="module-command-card">
        <div class="command-card-topline">
          <span class="step-kicker">STEP 01 · MODULE</span>
          <span class="module-registration" :class="{ ready: currentDeviceId }">
            {{ currentDeviceId ? "模块已登记" : "等待选择已登记模块" }}
          </span>
        </div>
        <div class="command-card-title">选择目标模块</div>
        <div class="command-card-subtitle">{{ debugSettings.skipDrawingBinding ? '选择坐标后，进入下一步确认本次要操作的机械臂。调试模式下仍可保存配置。' : '选择坐标后，进入下一步配置本次要操作的机械臂与目标图纸。' }}</div>
        <div class="input-row">
          <div class="input-group">
            <span class="prefix">X 坐标</span>
            <el-input
              v-model.number="inputX"
              class="binary-input"
              maxlength="4"
              @input="handleXChange(inputX)"
            />
          </div>
          <div class="input-group">
            <span class="prefix">Y 坐标</span>
            <el-input
              v-model.number="inputY"
              class="binary-input"
              maxlength="4"
              @input="handleYChange(inputY)"
            />
          </div>
          <el-button type="primary" class="lock-btn" :loading="moduleBusy" :disabled="moduleBusy" @click="handleLockAndJump"
            >进入机械臂配置</el-button
          >
        </div>
        <div class="module-target-line">
          当前目标 <strong>({{ selectedCell.x }}, {{ selectedCell.y }})</strong>
          <span>·</span>
          <span>模块号 {{ currentModuleId ?? "—" }}</span>
        </div>
      </div>

      <!-- 8x8 模块矩阵 -->
      <div class="matrix-section">
        <div class="matrix-section-heading">
          <div>
            <span class="step-kicker">MODULE MAP</span>
            <h3>模块坐标</h3>
          </div>
          <span class="matrix-help">点击任意格子切换目标</span>
        </div>
      <div class="matrix-container">
        <div class="matrix">
          <div v-for="(row, yIndex) in matrix" :key="yIndex" class="matrix-row">
            <div
              v-for="cell in row"
              :key="`${cell.x}-${cell.y}`"
              class="matrix-cell"
              :class="{
                selected:
                  selectedCell.x === cell.x && selectedCell.y === cell.y,
              }"
              @click="handleCellClick(cell)"
            >
              ({{ cell.x }},{{ cell.y }})
            </div>
          </div>
        </div>
      </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useRouter } from "vue-router";
import { getDeviceListApi } from "@/api/rosApi";
import { closeControlSession, getControlSession, type ControlSession } from "@/api/session";
import { useDebugSettingsStore } from '@/stores/debugSettings';
import { useFineTuningSessionStore } from '@/stores/fineTuningSession';


const router = useRouter();
const debugSettings = useDebugSettingsStore();
const sessionStore = useFineTuningSessionStore();

// 进行中的微调会话：只做提示与入口，不自动跳转。
const heldSession = ref<ControlSession | null>(null);
const sessionBusy = ref(false);
const heldUnitText = computed(() =>
  (heldSession.value?.unit_ids ?? []).map((item) => String(item)).join("、") || "—"
);
const heldRemainingText = computed(() => {
  const expiresAt = heldSession.value?.expires_at;
  if (!expiresAt) return "不限时";
  const left = new Date(expiresAt).getTime() - Date.now();
  if (!Number.isFinite(left) || left <= 0) return "即将失效";
  const minutes = Math.ceil(left / 60000);
  return minutes >= 60 ? `剩余约 ${Math.round(minutes / 60)} 小时` : `剩余约 ${minutes} 分钟`;
});

const loadHeldSession = async () => {
  if (!sessionStore.enabled) {
    heldSession.value = null;
    return;
  }
  try {
    heldSession.value = (await getControlSession(sessionStore.ttlSeconds)).data.session;
  } catch {
    heldSession.value = null;
  }
};

const handleResumeSession = async () => {
  const session = heldSession.value;
  if (!session || sessionBusy.value) return;
  sessionBusy.value = true;
  try {
    await router.push({
      name: "FineTuningPage",
      query: {
        module_id: session.module_id,
        ...(session.device_id !== null ? { device_id: session.device_id } : {}),
        ...(session.x !== null ? { x: session.x } : {}),
        ...(session.y !== null ? { y: session.y } : {}),
        session: session.id,
      },
    });
  } finally {
    sessionBusy.value = false;
  }
};

const handleCloseSession = async () => {
  const session = heldSession.value;
  if (!session || sessionBusy.value) return;
  try {
    await ElMessageBox.confirm(
      "结束会话只清除 MES 的续接记录，不会解绑设备、不会发送任何指令。之后进入微调页需要重新握手。",
      "结束微调会话",
      { type: "warning", confirmButtonText: "结束会话", cancelButtonText: "取消" },
    );
  } catch {
    return;
  }
  sessionBusy.value = true;
  try {
    await closeControlSession(session.id);
    sessionStore.clearSnapshot(session.id);
    ElMessage.success("已结束会话记录");
    await loadHeldSession();
  } catch {
    /* 请求失败已由拦截器提示，保留原状态 */
  } finally {
    sessionBusy.value = false;
  }
};

// 矩阵数据 (8x8)
const matrixSize = 8;
const matrix = ref<any[]>([]);


// 初始化矩阵
for (let y = 1; y <= matrixSize; y++) {
  const row = [];
  for (let x = 1; x <= matrixSize; x++) {
    row.push({ x, y });
  }
  matrix.value.push(row);
}

// 1. 输入框绑定值
const inputX = ref(1);
const inputY = ref(1);
const moduleBusy = ref(false);
const deviceList = ref<any[]>([]);

// 2. 当前选中的格子
const selectedCell = ref({ x: 1, y: 1 });

// 3. 根据 x/y 计算 module_id
const xyToModuleId = (x: number, y: number): number | undefined => {
  const xVal = Number(x);
  const yVal = Number(y);

  if (xVal >= 1 && xVal <= 8 && yVal >= 1 && yVal <= 8) {
    return xVal * 16 + yVal;
  }

  return undefined;
};

const currentModuleId = computed(() =>
  xyToModuleId(inputX.value, inputY.value)
);

const currentDeviceId = computed(() => {
  const matched = deviceList.value.find(
    (item: any) => Number(item.DeviceAddress) === Number(currentModuleId.value)
  );
  return matched ? Number(matched.Device_ID) : 0;
});

const unwrapList = (response: any): any[] => {
  if (Array.isArray(response)) return response;
  return Array.isArray(response?.data) ? response.data : [];
};

// 2. 监听下方矩阵点击：一旦格子变化，更新上方输入框
watch(
  selectedCell,
  (newVal) => {
    inputX.value = newVal.x;
    inputY.value = newVal.y;
  },
  { deep: true, immediate: true }
);

//X/Y 输入函数
const handleXChange = (val: number) => {
  const x = Number(val);

  if (x < 1 || x > 8 || Number.isNaN(x)) {
    ElMessage.warning("请输入范围[1-8]内的 X 坐标");
    return;
  }

  selectedCell.value = {
    x,
    y: selectedCell.value.y,
  };
};

const handleYChange = (val: number) => {
  const y = Number(val);

  if (y < 1 || y > 8 || Number.isNaN(y)) {
    ElMessage.warning("请输入范围[1-8]内的 Y 坐标");
    return;
  }

  selectedCell.value = {
    x: selectedCell.value.x,
    y,
  };
};


// 点击矩阵格子（【修复】赋值为一个新对象，防止后续操作污染矩阵原数据）
const handleCellClick = (cell: any) => {
  selectedCell.value = { x: cell.x, y: cell.y };
};
// ========== 锁定并下发：跳转到微调页面 ==========
const handleLockAndJump = async () => {
  if (moduleBusy.value) return;
  const x = Number(selectedCell.value.x);
  const y = Number(selectedCell.value.y);
  const module_id = xyToModuleId(x, y);

  if (!x || !y || x < 1 || x > 8 || y < 1 || y > 8) {
    ElMessage.warning("请先选择 1-8 范围内的有效坐标");
    return;
  }

  if (module_id === undefined || module_id === null) {
    ElMessage.warning("未能获取到有效的模块编号");
    return;
  }

  if (!currentDeviceId.value) {
    ElMessage.warning("该坐标模块尚未在设备信息管理中登记，请先添加模块");
    return;
  }

  moduleBusy.value = true;
  try {
    await router.push({
      name: "FineTuningPage",
      query: { module_id, device_id: currentDeviceId.value, x, y },
    });
  } finally {
    moduleBusy.value = false;
  }
};

onMounted(async () => {
  void loadHeldSession();
  try {
    deviceList.value = unwrapList(await getDeviceListApi());
  } catch (err) {
    ElMessage.error("获取模块设备信息失败，请检查后端服务");
  }
});
</script>

<style scoped>
.module-management {
  overflow: auto;
}
/* 新的操作栏样式 */
.action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #f5f7fa;
  padding: 12px 20px;
  border-radius: 8px;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 15px;
}
.module-info {
  font-size: 14px;
  color: #333;
}
.info-label {
  font-weight: 500;
  color: #606266;
}
.info-value {
  font-weight: bold;
  color: var(--mes-primary);
  margin-right: 8px;
}
.action-buttons {
  display: flex;
  gap: 15px;
  align-items: center;
  flex-wrap: wrap;
}
.device-select {
  display: flex;
  align-items: center;
  gap: 10px;
}
.device-select label {
  font-weight: 500;
  color: #606266;
}
.matrix-container {
  display: flex;
  justify-content: center;
  overflow-x: auto;
}
.matrix {
  border: 1px solid var(--mes-border-light);
  border-radius: var(--mes-radius-lg);
  padding: 14px;
  background-color: #ffffff;
  box-shadow: var(--mes-shadow-card);
  display: inline-block;
}
.matrix-row {
  display: flex;
  gap: 6px;
  margin-bottom: 6px;
}
.matrix-cell {
  width: 70px;
  height: 50px;
  border: 1px solid var(--mes-border);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  color: var(--mes-text-sub);
  cursor: pointer;
  background-color: #f8fafc;
  transition: all 0.2s ease;
}
.matrix-cell:hover {
  background-color: var(--el-color-primary-light-9);
  border-color: var(--el-color-primary-light-5);
  color: var(--mes-primary);
  transform: translateY(-2px);
}
.matrix-cell.selected {
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  border-color: transparent;
  color: #fff;
  font-weight: bold;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4);
}

/* 新增的还原截图样式 */
/* 新增的还原截图样式 (精修版) */
.action-bar-restored {
  background-color: #ffffff;
  padding: 16px 24px;
  border-radius: var(--mes-radius-lg);
  margin-bottom: 24px;
  border: 1px solid var(--mes-border-light);
  border-left: 4px solid var(--mes-primary);
  box-shadow: var(--mes-shadow-card);
  display: flex;
  flex-direction: column;
  align-items: center; /* 内部元素居中 */
  gap: 12px;
  width: min(100%, 980px);
  box-sizing: border-box;
  margin-left: auto;
  margin-right: auto; /* 整个面板整体居中 */
}

.input-row {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.input-group {
  display: flex;
  align-items: center;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  overflow: hidden;
  background: #fff;
  height: 36px; /* 降低整体高度，更秀气 */
}

.prefix {
  padding: 0 12px;
  color: #606266;
  font-size: 13px;
  background-color: #f5f7fa;
  border-right: 1px solid #dcdfe6;
  line-height: 36px;
  white-space: nowrap; /* 防止文字换行 */
}

.binary-input :deep(.el-input__wrapper) {
  box-shadow: none !important;
  width: 70px; /* 缩窄输入框，只需放4位数字 */
  padding: 0;
}

/* 让二进制数字居中并使用等宽字体，更像极客面板 */
.binary-input :deep(.el-input__inner) {
  text-align: center;
  font-family: monospace;
  font-size: 15px;
  letter-spacing: 1px;
}

.lock-btn {
  height: 36px;
  padding: 0 20px;
}

.hint-text {
  font-size: 13px;
  color: #909399;
}

.hint-text .highlight {
  color: var(--mes-primary);
  font-weight: bold;
  font-size: 14px;
}

/* 模块页视觉层级：把坐标选择作为唯一主任务，下一步动作单独突出。 */
.module-management {
  background:
    radial-gradient(circle at 88% 8%, rgba(37, 99, 235, 0.08), transparent 28%),
    var(--mes-bg);
}

.module-command-card,
.matrix-section,
.session-banner {
  width: min(100%, 1040px);
  margin: 0 auto;
}

.session-banner {
  margin-bottom: 18px;
  border: 1px solid rgba(37, 99, 235, 0.25);
  border-left: 4px solid var(--mes-primary);
  border-radius: 14px;
  background: #f5f9ff;
}

.session-banner-body {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  flex-wrap: wrap;
}

.session-banner-text {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 0;
}

.session-banner-text strong {
  color: var(--mes-text-title);
  font-size: 16px;
}

.session-banner-meta {
  color: var(--mes-text-sub);
  font-size: 12px;
}

.session-banner-actions {
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}

.module-command-card {
  padding: 24px 28px 20px;
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-left: 4px solid var(--mes-primary);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 18px 45px rgba(15, 23, 42, 0.08);
}

.command-card-topline,
.matrix-section-heading,
.module-target-line {
  display: flex;
  align-items: center;
}

.command-card-topline,
.matrix-section-heading {
  justify-content: space-between;
  gap: 16px;
}

.step-kicker {
  color: var(--mes-primary);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.14em;
}

.module-registration {
  padding: 5px 10px;
  border: 1px solid #fed7aa;
  border-radius: 999px;
  color: #b45309;
  background: #fff7ed;
  font-size: 12px;
}

.module-registration.ready {
  border-color: #bbf7d0;
  color: #15803d;
  background: #f0fdf4;
}

.command-card-title {
  margin-top: 16px;
  color: var(--mes-text-title);
  font-size: 23px;
  font-weight: 750;
  letter-spacing: -0.02em;
}

.command-card-subtitle {
  margin-top: 6px;
  color: var(--mes-text-sub);
  font-size: 13px;
}

.module-target-line {
  gap: 9px;
  margin-top: 15px;
  color: var(--mes-text-sub);
  font-size: 13px;
}

.module-target-line strong {
  color: var(--mes-primary-dark);
  font-size: 15px;
}

.matrix-section {
  margin-top: 24px;
  padding: 22px 24px 24px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.86);
  box-shadow: var(--mes-shadow-card);
}

.matrix-section-heading {
  margin-bottom: 15px;
}

.matrix-section-heading h3 {
  margin: 5px 0 0;
  color: var(--mes-text-title);
  font-size: 17px;
}

.matrix-help {
  color: var(--mes-text-faint);
  font-size: 12px;
}

.matrix-section .matrix-container {
  width: 100%;
}

.matrix-section .matrix {
  width: 100%;
  padding: 12px;
  border: 1px solid var(--mes-border-light);
  border-radius: 14px;
  box-shadow: none;
  background: #f8fafc;
}

.matrix-section .matrix-row {
  display: grid;
  grid-template-columns: repeat(8, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 8px;
}

.matrix-section .matrix-row:last-child {
  margin-bottom: 0;
}

.matrix-section .matrix-cell {
  width: auto;
  height: 52px;
  border-color: #e2e8f0;
  background: #fff;
  font-size: 13px;
}

.matrix-section .matrix-cell.selected {
  border-color: transparent;
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  color: #fff;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.32);
}

@media (max-width: 720px) {
  .module-command-card,
  .matrix-section {
    padding-left: 16px;
    padding-right: 16px;
  }

  .command-card-topline,
  .matrix-section-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .matrix-section .matrix {
    overflow-x: auto;
  }

  .matrix-section .matrix-row {
    min-width: 620px;
  }
}
</style>
