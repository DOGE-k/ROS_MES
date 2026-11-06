<template>
  <div class="fine-tuning-container mes-page">
    <!-- 顶部标题和返回按钮 -->
    <div class="mes-page-header">
      <div class="header-left">
        <el-button @click="goBack" :disabled="busy" class="back-button" :icon="ArrowLeft" round>返回</el-button>
        <div>
          <h2 class="mes-page-title">机械臂姿态微调与压力监控</h2>
          <p class="mes-page-sub">{{ isDebugMode ? '调试模式：无需绑定图纸，确认机械臂后可微调并保存配置' : '在已确认的机械臂之间切换，实时调整姿态并查看传感器反馈' }}</p>
        </div>
      </div>
    </div>
    <div class="arm-list">
      <div class="runtime-toolbar">
        <div class="runtime-context">
          <span class="context-kicker">运行状态</span>
          <strong>模块 {{ moduleId }}</strong>
          <el-tag v-if="isDebugMode" type="warning">调试模式 · 未绑定图纸</el-tag>
          <el-tag :type="feedbackSimulated ? 'warning' : 'info'">{{ noRosDebug || feedbackSimulated ? '后端模拟 · 未连接真实设备' : feedbackConnected ? '反馈通道已连接' : '反馈通道未连接' }}</el-tag>
          <span class="context-divider"></span>
          <span>当前机械臂</span>
          <span class="active-arm-chip">机械臂 {{ armNumber(initConfig.unitId) }}</span>
        </div>
        <div class="runtime-actions">
          <el-select v-model="selectedArmRowId" class="arm-switcher" :disabled="busy || !isReady" placeholder="切换机械臂" @change="handleArmSwitch">
            <el-option v-for="item in armIdList" :key="item.id" :label="`机械臂 ${armNumber(item.Unit_ID)}`" :value="item.id" />
          </el-select>
          <el-button type="primary" plain :disabled="busy || !isReady || isDebugMode" @click="openDrawingDialog">
            {{ activeProfile?.drawingId || activeProfile?.drawingSource === 'builtin_mock' ? "重新下发图纸" : "下发图纸" }}
          </el-button>
          <el-button type="primary" plain :disabled="busy || isDebugMode || !pointCloudViews.length" @click="togglePointCloudViews">
            {{ showPointCloudViews ? "隐藏点云图" : "查看点云图" }}
          </el-button>
        </div>
      </div>

      <el-card v-if="showPointCloudViews && pointCloudViews.length" shadow="hover" class="pointcloud-card">
        <template #header>
          <div class="card-header">
            <span class="header-text">点云三视图</span>
          </div>
        </template>
        <div class="pointcloud-grid">
          <div v-for="view in pointCloudViews" :key="view.name" class="pointcloud-view">
            <div class="pointcloud-title">{{ view.label }}</div>
            <img :src="view.url" :alt="view.label" class="pointcloud-image" />
          </div>
        </div>
      </el-card>

      <el-card shadow="never" class="main-control-card">
        <template #header>
          <div class="card-header">
            <div class="control-heading">
              <span class="header-text">姿态控制参数 · 机械臂 {{ armNumber(armList.id) }}</span>
              <span class="control-caption">{{ isDebugMode ? '不使用图纸' : activeProfile?.drawingSource === 'builtin_mock' ? '内置模拟图纸' : `图纸 ${activeProfile?.drawingId || '未下发'}` }}</span>
              <el-tag v-if="!isDebugMode && drawingSimulated" type="warning">图纸/三视图模拟</el-tag>
            </div>
            <el-button type="success" :disabled="busy || !isReady" @click="handleSaveConfig"
              >保存当前配置</el-button
            >
          </div>
        </template>
        <div class="control-grid">
          <div class="control-item">
            <div class="label-box">
              <div class="input-box">
                <span class="label-title"
                  >{{ armList.device[0].label }}(°)</span
                >
                <el-input-number
                  v-model="armList.device[0].adjust"
                  :min="-360"
                  :max="360"
                  placeholder="本次旋转增量"
                  :disabled="busy || !isReady"
                />
              </div>

              <span class="real-time-tag"
                >初始值: {{ armList.device[0].initialLocked ? armList.device[0].initial : '—' }}</span
              >
              <span class="real-time-tag"
                >当前实际值: {{ displayFeedback('rotation', armList.device[0].current) }} · {{ fieldStatusLabel('rotation') }}</span
              >
            </div>
          </div>
        </div>
        <div class="control-grid">
          <div class="control-item">
            <div class="label-box">
              <div class="input-box">
                <span class="label-title"
                  >{{ armList.device[1].label }}(°)</span
                >
                <el-input-number
                  v-model="armList.device[1].adjust"
                  :min="-360"
                  :max="360"
                  placeholder="本次摆动增量"
                  :disabled="busy || !isReady"
                />
              </div>

              <span class="real-time-tag"
                >初始值: {{ armList.device[1].initialLocked ? armList.device[1].initial : '—' }}</span
              >
              <span class="real-time-tag"
                >当前实际值: {{ displayFeedback('swing', armList.device[1].current) }} · {{ fieldStatusLabel('swing') }}</span
              >
            </div>
          </div>
        </div>
        <div class="control-grid">
          <div class="control-item">
            <div class="label-box">
              <div class="input-box">
                <span class="label-title"
                  >{{ armList.device[2].label }}(mm)</span
                >
                <el-input-number
                  v-model="armList.device[2].adjust"
                  :min="-360"
                  :max="360"
                  placeholder="本次伸缩增量"
                  :disabled="busy || !isReady"
                />
              </div>

              <span class="real-time-tag"
                >初始值: {{ armList.device[2].initialLocked ? armList.device[2].initial : '—' }}</span
              >
              <span class="real-time-tag"
                >当前实际值: {{ displayFeedback('telescopic', armList.device[2].current) }} · {{ fieldStatusLabel('telescopic') }}</span
              >
            </div>
          </div>
        </div>

        <div class="batch-controls">
          <el-button type="primary" :disabled="busy || !isReady || !hasPendingAdjustments" @click="confirmAdjustments">确认下发三轴调整</el-button>
          <span>输入为本次待提交增量，点击确认后按旋转、摆动、伸缩顺序执行。</span>
          <el-button v-if="!busy && !isReady" @click="openConfiguration">重新配置机械臂</el-button>
        </div>
        <div v-if="batchState" class="batch-progress">
          <el-alert :title="batchState.message" :type="batchState.status === 'completed' ? 'success' : 'warning'" :closable="false" />
          <p v-for="step in batchState.steps" :key="step.parameter_name">
            {{ axisLabels[step.parameter_name] }}：{{ step.position }}{{ step.parameter_name === 'telescopic' ? 'mm' : '°' }} · {{ stepLabels[step.status] || step.status }}
          </p>
          <el-button @click="pollBatch">刷新执行状态</el-button>
          <el-button v-if="batchState.id && ['queued', 'checking', 'executing'].includes(batchState.status)" type="warning" @click="interruptBatch">停止后续下发</el-button>
          <el-button v-if="batchState.id && batchState.status === 'uncertain'" type="warning" @click="acknowledgeBatch">{{ batchState.simulated ? '已核实模拟记录，关闭批次' : '已现场核实，关闭待确认批次' }}</el-button>
          <p>“停止后续下发”不停止正在运动的轴；需要立即停止时请使用全局急停。</p>
        </div>

        <div class="imu-panel">
          <div class="sensor-title">陀螺仪姿态与末端坐标反馈</div>
          <div class="imu-grid">
            <div class="imu-item">
              <span class="imu-label">摆动角</span>
              <span class="imu-value">{{ displayFeedback('swing_angle', imuFeedback.swingAngle) }}°</span>
              <small>{{ fieldStatusLabel('swing_angle') }}</small>
            </div>
            <div class="imu-item">
              <span class="imu-label">旋转角</span>
              <span class="imu-value">{{ displayFeedback('rotation_angle', imuFeedback.rotationAngle) }}°</span>
              <small>{{ fieldStatusLabel('rotation_angle') }}</small>
            </div>
            <div class="imu-item">
              <span class="imu-label">X</span>
              <span class="imu-value">{{ displayFeedback('x', imuFeedback.x) }} cm</span>
              <small>{{ fieldStatusLabel('x') }}</small>
            </div>
            <div class="imu-item">
              <span class="imu-label">Y</span>
              <span class="imu-value">{{ displayFeedback('y', imuFeedback.y) }} cm</span>
              <small>{{ fieldStatusLabel('y') }}</small>
            </div>
            <div class="imu-item">
              <span class="imu-label">Z</span>
              <span class="imu-value">{{ displayFeedback('z', imuFeedback.z) }} cm</span>
              <small>{{ fieldStatusLabel('z') }}</small>
            </div>
          </div>
        </div>

        <div class="sensor-panel">
          <div class="sensor-title">压力传感器实时反馈</div>
          <div class="sensor-value-box" v-if="loading">
            <span>{{ displayFeedback('pressure', armList.device[3].current) }} · {{ fieldStatusLabel('pressure') }}</span>
          </div>
          <div class="sensor-value-box" v-else>
            <span class="status-dot pulse"></span>
            <span class="value-text">等待数据接入...</span>
          </div>
        </div>
      </el-card>
      <el-card v-if="ackEvents.length" class="ack-card" shadow="never">
        <template #header>回执事件 · 不表示运动完成</template>
        <el-alert :title="ackEvents[0].text" :type="ackEvents[0].type" :closable="false" show-icon />
        <el-collapse>
          <el-collapse-item v-for="event in ackEvents" :key="event.id" :title="event.text" :name="event.id">
            <pre class="ack-raw">{{ event.raw }}</pre>
          </el-collapse-item>
        </el-collapse>
      </el-card>
    </div>

    <el-dialog
      class="initial-config-dialog"
      v-model="initDialogVisible"
      :title="isDebugMode ? '确认调试机械臂' : dialogMode === 'initial' ? '确认机械臂并下发图纸' : '重新下发图纸'"
      width="450px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="false"
    >
      <div class="dialog-intro">
        <div class="dialog-intro-icon">⌁</div>
        <div>
          <strong>{{ dialogMode === "initial" ? "建立本次微调会话" : "更新当前机械臂图纸" }}</strong>
          <p>{{ isDebugMode ? '完成机械臂确认后直接进入微调。真实或模拟由连接设置决定，当前配置不绑定图纸。' : dialogMode === "initial" ? "先确认需要参与本模块的机械臂，再统一下发目标图纸。" : "重新下发图纸只作用于当前机械臂。" }}</p>
        </div>
      </div>
      <el-form label-position="top" class="config-form">
        <el-form-item label="目标模块">
          <el-input :model-value="moduleDisplay" disabled />
        </el-form-item>
        <el-form-item label="参与机械臂" required>
          <div class="dialog-arm-picker">
            <div class="dialog-field-meta">
              <span>选择本次要操作的机械臂</span>
              <b>{{ draftInitConfig.unitRowIds.length }} / 5</b>
            </div>
            <el-checkbox-group
              v-model="draftInitConfig.unitRowIds"
              class="dialog-arm-grid"
              :max="5"
              :disabled="busy || dialogMode !== 'initial'"
            >
              <el-checkbox-button v-for="item in armIdList" :key="item.id" :label="item.id" class="dialog-arm-card">
                <span>机械臂 {{ armNumber(item.Unit_ID) }}</span>
                <small>Unit_ID {{ item.Unit_ID }}</small>
              </el-checkbox-button>
            </el-checkbox-group>
          </div>
        </el-form-item>
        <el-form-item v-if="!isDebugMode" label="目标图纸" required>
          <el-select v-model="draftInitConfig.drawingId" :disabled="busy" placeholder="请选择目标图纸" style="width: 100%">
            <el-option v-for="item in drawingList" :key="`${item.drawingSource || 'database'}:${item.drawingId}`" :label="item.drawingName" :value="Number(item.drawingId || 0)" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="busy" @click="handleDialogCancel">
          {{ dialogMode === "initial" ? "返回模块选择" : "取消" }}
        </el-button>
        <el-button type="primary" :loading="busy" :disabled="busy" @click="confirmInitConfig">{{ isDebugMode ? '确认机械臂并进入微调' : '确认并下发' }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onBeforeUnmount } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { ArrowLeft } from "@element-plus/icons-vue";
import {
  getFineTuningDrawingOptions,
  getUnitsByDeviceApi,
  getSensorsByUnitApi,
  createModule,
  sendCoordination,
  submitFineTuningBatch, getFineTuningBatch, getFineTuningBatchByRequest,
  getActiveFineTuningBatch, interruptFineTuningBatch, acknowledgeFineTuningBatch,
  type FineTuningBatch,
  saveFineTuningConfig,
} from "@/api/rosApi";
import { noRosDebug } from "@/api/noRosDebug";
import { getConnectionSettings } from '@/api/connectionSettings';
import { emptyFeedbackMarks, feedbackTimeouts, feedbackStatus, finiteFeedbackNumber, FEEDBACK_FIELDS, FEEDBACK_STATUS_LABELS, type FeedbackField } from '@/api/feedbackState';
import {
  armIndexFromUnitId,
  axisDeviceId,
  armLevelDeviceId,
  type AxisParameterName,
} from "@/api/deviceEncoding";

const router = useRouter();
// 每次建立会话前读取服务配置；模式变更后必须重新确认机械臂。
const isDebugMode = ref(false);
const drawingContextRevision = ref<number | null>(null);

// 数据准备完成后再打开配置弹窗，避免接口加载期间短暂显示空表单。
const initDialogVisible = ref(false);
const initConfig = reactive({
  deviceId: 0,
  unitId: 0,
  unitRowId: 0,
  sensorId: 0,
  drawingId: 0,
  drawingSource: 'database' as 'database' | 'builtin_mock',
});
const draftInitConfig = reactive({
  unitRowIds: [] as number[],
  unitRowId: 0,
  unitId: 0,
  drawingId: 0,
});
const dialogMode = ref<"initial" | "redraw">("initial");
const sharedDrawingId = ref(0);
const sharedDrawingSource = ref<'database' | 'builtin_mock'>('database');
const sharedDrawingViews = ref<Array<{ name: string; label: string; url: string }>>([]);

const loading = ref(false);
const busy = ref(false);
const batchState = ref<FineTuningBatch | null>(null);
const feedbackSimulated = ref(false);
const drawingSimulated = ref(false);
const confirmedConnectionRevision = ref<number | null>(null);
let batchTimer: ReturnType<typeof setInterval> | undefined;
let batchPolling = false;
let appliedSimulationId = '';
const axisLabels: Record<string, string> = { rotation: '旋转', swing: '摆动', telescopic: '伸缩' };
const stepLabels: Record<string, string> = { pending: '未下发', sent_unconfirmed: '已发送，等待运行和到位', completed: '已观测到完成', uncertain: '已发送，结果待核实' };
let feedbackSocket: WebSocket | null = null;
const armIdList = ref<any[]>([]);
const drawingList = ref<any[]>([]);
const pointCloudViews = ref<Array<{ name: string; label: string; url: string }>>([]);
const showPointCloudViews = ref(false);
const route = useRoute();
const moduleId = ref<number>(0);
const moduleDisplay = ref("");
const selectedArmRowId = ref(0);
const confirmedUnitIds = ref<number[]>([]);
const confirmedSeg = ref<number | null>(null);
const feedbackMarks = reactive(emptyFeedbackMarks());
const feedbackClock = ref(performance.now());
const feedbackConnected = ref(false);
const timeouts = feedbackTimeouts(import.meta.env);
let feedbackTimer: ReturnType<typeof setInterval> | undefined;
const ackEvents = ref<Array<{ id: number; text: string; type: 'info' | 'warning'; raw: string }>>([]);
let ackSequence = 0;
const fieldStatus = (field: FeedbackField) => feedbackStatus(
  feedbackMarks[field], feedbackClock.value,
  field === 'pressure' ? timeouts.pressure : adjustmentKeys.includes(field as AxisParameterName) ? timeouts.axis : timeouts.imu,
  feedbackConnected.value, noRosDebug || feedbackSimulated.value,
);
const fieldStatusLabel = (field: FeedbackField) => FEEDBACK_STATUS_LABELS[fieldStatus(field)];
const markReceived = (field: FeedbackField) => {
  feedbackClock.value = performance.now();
  feedbackMarks[field] = { receivedAt: feedbackClock.value, historical: false };
};
const displayFeedback = (field: FeedbackField, value: number) => feedbackMarks[field].receivedAt === null ? '—' : value.toFixed(2);
const armProfiles = reactive<Record<string, any>>({});
const activeProfile = computed(() =>
  initConfig.unitRowId ? armProfiles[String(initConfig.unitRowId)] || null : null
);
const isReady = computed(() =>
  !initDialogVisible.value &&
  Boolean(activeProfile.value?.configured) &&
  confirmedUnitIds.value.includes(Number(initConfig.unitId)) &&
  (isDebugMode.value || Number(activeProfile.value?.drawingId) > 0 || activeProfile.value?.drawingSource === 'builtin_mock')
);
const armList = reactive({
  id: 0,
  // deviceId 由 applyAxisEncoding 按 V2.1 三轴编码动态填充（1~15 轴级 / 21~25 臂级），禁止硬编码
  device: [
    { deviceId: 0, initial: 0.0, adjust: 0.0, current: 0.0, initialLocked: false, label: "底座旋转调整值" },
    { deviceId: 0, initial: 0.0, adjust: 0.0, current: 0.0, initialLocked: false, label: "摆动调整值" },
    { deviceId: 0, initial: 0.0, adjust: 0.0, current: 0.0, initialLocked: false, label: "伸缩杆调整值" },
    { deviceId: 0, initial: 0.0, current: 0.0 },
  ],
});
const imuFeedback = reactive({
  swingAngle: 0,
  rotationAngle: 0,
  x: 0,
  y: 0,
  z: 0,
});

const formatUnitOption = (item: any) => {
  const desc = item.UnitDescript ? ` - ${item.UnitDescript}` : "";
  return `机械臂 ${item.Unit_ID}${desc}`;
};

const armNumber = (unitId: number) => {
  const value = Number(unitId);
  if (value >= 1 && value <= 5) return value;
  if (value > 0 && value % 32 === 0) return value / 32;
  return value;
};

const adjustmentKeys: AxisParameterName[] = ["rotation", "swing", "telescopic"];
const hasPendingAdjustments = computed(() => armList.device.slice(0, 3).some(item => Number(item.adjust) !== 0));
// 反馈 device_id → 轴下标映射：按选中机械臂的 V2 轴号动态构建，见 rebuildFeedbackIndex
let feedbackDeviceIndex: Record<number, number> = {};
// 当前选中机械臂的臂级传感器（压力/IMU 共用）device_id 与压力传感器 sensor_ID
let armLevelId = 0;
let lastLoadedUnitRowId = 0;
const pressureSensorId = ref<number>(0);

const cloneDevices = () => armList.device.map((item: any) => ({ ...item }));

const saveActiveProfile = (force = false) => {
  if (!initConfig.unitRowId || !confirmedUnitIds.value.includes(Number(initConfig.unitId))) return;
  if (!isDebugMode.value && !initConfig.drawingId && initConfig.drawingSource !== 'builtin_mock') return;
  const existingProfile = armProfiles[String(initConfig.unitRowId)];
  if (!force && !existingProfile?.configured) return;
  armProfiles[String(initConfig.unitRowId)] = {
    unitRowId: Number(initConfig.unitRowId),
    unitId: Number(initConfig.unitId),
    drawingId: Number(initConfig.drawingId),
    drawingSource: initConfig.drawingSource,
    drawingSimulated: drawingSimulated.value,
    configured: true,
    device: cloneDevices(),
    imu: { ...imuFeedback },
    pressureSensorId: Number(pressureSensorId.value || 0),
    feedbackMarks: Object.fromEntries(FEEDBACK_FIELDS.map(field => [field, { ...feedbackMarks[field] }])),
    pointCloudViews: pointCloudViews.value.map((item) => ({ ...item })),
    showPointCloudViews: Boolean(showPointCloudViews.value),
    batch: batchState.value ? { ...batchState.value, steps: batchState.value.steps.map(step => ({ ...step })) } : null,
    ackEvents: ackEvents.value.map(event => ({ ...event })),
  };
};

const resetControlState = (preserveBatch = false) => {
  ackEvents.value = [];
  if (!preserveBatch) {
    batchState.value = null;
    if (batchTimer !== undefined) clearInterval(batchTimer);
    batchTimer = undefined;
  }
  armList.device.forEach((item: any, index: number) => {
    item.initial = 0;
    item.adjust = index < 3 ? 0 : undefined;
    item.current = 0;
    item.initialLocked = false;
  });
  Object.assign(imuFeedback, { swingAngle: 0, rotationAngle: 0, x: 0, y: 0, z: 0 });
  pressureSensorId.value = 0;
  initConfig.sensorId = 0;
  pointCloudViews.value = [];
  showPointCloudViews.value = false;
  loading.value = false;
  Object.assign(feedbackMarks, emptyFeedbackMarks());
};

const restoreArmProfile = (profile: any) => {
  ackEvents.value = (profile.ackEvents || []).map((event: any) => ({ ...event }));
  if (batchTimer !== undefined) clearInterval(batchTimer);
  batchTimer = undefined;
  batchState.value = profile.batch ? { ...profile.batch, steps: profile.batch.steps.map((step: any) => ({ ...step })) } : null;
  initConfig.unitRowId = Number(profile.unitRowId);
  initConfig.unitId = Number(profile.unitId);
  initConfig.drawingId = Number(profile.drawingId);
  initConfig.drawingSource = profile.drawingSource || 'database';
  drawingSimulated.value = Boolean(profile.drawingSimulated);
  armList.device.splice(0, armList.device.length, ...profile.device.map((item: any) => ({ ...item })));
  Object.assign(imuFeedback, profile.imu || {});
  pressureSensorId.value = Number(profile.pressureSensorId || 0);
  initConfig.sensorId = pressureSensorId.value;
  pointCloudViews.value = (profile.pointCloudViews || []).map((item: any) => ({ ...item }));
  showPointCloudViews.value = Boolean(profile.showPointCloudViews);
  applyAxisEncoding(initConfig.unitId);
  armList.id = initConfig.unitId;
  lastLoadedUnitRowId = initConfig.unitRowId;
  Object.assign(feedbackMarks, emptyFeedbackMarks());
  for (const field of FEEDBACK_FIELDS) {
    const saved = profile.feedbackMarks?.[field];
    if (saved?.receivedAt !== null && saved?.receivedAt !== undefined) {
      feedbackMarks[field] = { receivedAt: saved.receivedAt, historical: true };
    }
  }
  feedbackClock.value = performance.now();
  loading.value = feedbackMarks.pressure.receivedAt !== null;
};

// 依据机械臂 Unit_ID（32/64/96 → 臂1/2/3）计算 V2 轴号，填充三轴与臂级 deviceId
const applyAxisEncoding = (unitId: number) => {
  const armIndex = armIndexFromUnitId(unitId);
  const axisIds = adjustmentKeys.map((key) => axisDeviceId(armIndex, key));
  armList.device.forEach((item: any, index: number) => {
    item.deviceId = index < 3 ? axisIds[index] : armLevelDeviceId(armIndex);
  });
  armLevelId = armLevelDeviceId(armIndex);
  rebuildFeedbackIndex();
};

const rebuildFeedbackIndex = () => {
  feedbackDeviceIndex = {};
  armList.device.slice(0, 3).forEach((item: any, index: number) => {
    if (item.deviceId) {
      feedbackDeviceIndex[Number(item.deviceId)] = index;
    }
  });
};

// 拉取选中机械臂的传感器列表，取压力传感器的 sensor_ID 供配置保存使用
const loadSensorsForUnit = async (unitRowId: number) => {
  pressureSensorId.value = 0;
  try {
    const res: any = await getSensorsByUnitApi(unitRowId);
    const sensors: any[] = Array.isArray(res)
      ? res
      : Array.isArray(res?.data)
        ? res.data
        : [];
    const pressure =
      sensors.find((s) => String(s.sensordescript || "").includes("压力")) ||
      sensors.find((s) => Number(s.Unit_address) === 0);
    if (pressure) {
      pressureSensorId.value = Number(pressure.sensor_ID || 0);
    }
  } catch (err) {
    console.warn("获取传感器列表失败：", err);
  }
  initConfig.sensorId = pressureSensorId.value;
};

const togglePointCloudViews = () => {
  if (isDebugMode.value || busy.value) return;
  if (pointCloudViews.value.length === 0) {
    ElMessage.warning("暂无点云图，请确认点云服务已生成");
    return;
  }
  showPointCloudViews.value = !showPointCloudViews.value;
};

const updateAxisCurrent = (index: number, position: number) => {
  const axis = armList.device[index] as any;
  if (!axis.initialLocked) {
    axis.initial = position;
    axis.initialLocked = true;
  }
  axis.current = position;
  markReceived(adjustmentKeys[index]);
};

const applyMockInitialFeedback = () => {
  [0, 1, 2].forEach((index) => updateAxisCurrent(index, 0));
};

const applyImuFeedback = (feedback: any) => {
  const fields = { swing_angle: 'swingAngle', rotation_angle: 'rotationAngle', x: 'x', y: 'y', z: 'z' } as const;
  for (const [field, target] of Object.entries(fields)) {
    const value = finiteFeedbackNumber(feedback[field]);
    if (value === null || (Array.isArray(feedback.valid_fields) && !feedback.valid_fields.includes(field))) continue;
    imuFeedback[target as keyof typeof imuFeedback] = value;
    markReceived(field as FeedbackField);
  }
};

const getFeedbackWsUrl = () => {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/api/control/feedback/ws`;
};

const applyAck = (feedback: any) => {
  if (!isReady.value) return;
  const deviceId = finiteFeedbackNumber(feedback.device_id);
  const result = finiteFeedbackNumber(feedback.result);
  const command = finiteFeedbackNumber(feedback.ack_msg);
  if (deviceId === null || !Number.isInteger(deviceId) || result === null || !Number.isInteger(result) || command === null || !Number.isInteger(command)) return;
  const belongs = feedback.module_resolution === 'resolved' &&
    finiteFeedbackNumber(feedback.business_module_id) === Number(moduleId.value);
  if (feedback.module_resolution === 'resolved' && !belongs) return;
  if (feedbackDeviceIndex[deviceId] === undefined) return;
  const labels: Record<number, string> = { 0: '接受', 1: '拒绝：轴忙', 2: '拒绝：未绑定或基准无效', 3: '拒绝：参数越界', 4: '拒绝：轴故障', 5: '拒绝：急停锁存' };
  const scope = belongs ? `模块 ${moduleId.value} · 轴 ${deviceId}` : `归属待确认 · 原模块号 ${feedback.module_id} · 轴 ${deviceId}`;
  const description = labels[result] || `未知结果 ${result}`;
  ackEvents.value.unshift({
    id: ++ackSequence,
    text: `${scope}：收到${description}回执（MSG=${command}，detail=${feedback.detail ?? '未知'}）。来源及请求关联未确认，不表示运动完成。`,
    type: !belongs || result !== 0 ? 'warning' : 'info',
    raw: JSON.stringify(feedback, null, 2),
  });
  ackEvents.value = ackEvents.value.slice(0, 20);
};

const applyFeedback = (feedback: any) => {
  if (feedback?.data_type === 'config_changed') { connectionChanged(); return; }
  if (!feedback || feedback.data_type === "error") {
    feedbackConnected.value = false;
    if (feedback?.message) {
      console.warn("ROS 反馈订阅异常：", feedback.message);
    }
    return;
  }
  if (feedback.data_type === 'cmd_ack') {
    applyAck(feedback);
    return;
  }
  // 仅这些已核对的遥测话题使用 CAN SEG；均值和回执不能套用本规则。
  if (confirmedSeg.value === null || !confirmedUnitIds.value.includes(Number(initConfig.unitId))) return;
  if (feedback.module_id_space && feedback.module_id_space !== 'seg') return;
  if (finiteFeedbackNumber(feedback.module_id) !== confirmedSeg.value) return;
  feedbackSimulated.value = feedback.simulated === true;
  const position = finiteFeedbackNumber(feedback.position);
  if (
    feedback.data_type === "axis_encoder" ||
    feedback.data_type === "rotation_axis_encoder" ||
    feedback.data_type === "swing_axis_encoder" ||
    feedback.data_type === "telescope_axis_encoder"
  ) {
    if (position === null || feedback.position_valid === false) {
      return;
    }
    const index = feedbackDeviceIndex[Number(feedback.device_id)];
    const expectedTypes = ['rotation_axis_encoder', 'swing_axis_encoder', 'telescope_axis_encoder'];
    if (index !== undefined && (feedback.data_type === 'axis_encoder' || feedback.data_type === expectedTypes[index])) {
      updateAxisCurrent(index, position);
      feedbackConnected.value = true;
    }
    return;
  }

  if (feedback.data_type === "pressure_sensor") {
    if (Number(feedback.device_id) !== Number(armLevelId)) {
      return;
    }
    if (position === null || feedback.position_valid === false) {
      return;
    }
    armList.device[3].current = position;
    markReceived('pressure');
    loading.value = true;
    feedbackConnected.value = true;
    return;
  }

  if (feedback.data_type === "imu_pose") {
    if (Number(feedback.device_id) !== Number(armLevelId)) {
      return;
    }
    applyImuFeedback(feedback);
    feedbackConnected.value = true;
  }
};

const connectFeedbackSocket = () => {
  // 无 ROS 调试模式：不连接真实反馈 WebSocket，方便只调页面跳转和微调交互。
  if (noRosDebug) {
    feedbackConnected.value = false;
    loading.value = true;
    armList.device[3].current = 0.5;
    markReceived('pressure');
    applyMockInitialFeedback();
    applyImuFeedback({ swing_angle: 1.25, rotation_angle: -2.5, x: 12.3, y: 4.56, z: 7.89 });
    return;
  }

  if (feedbackSocket) {
    feedbackSocket.close();
  }

  feedbackSocket = new WebSocket(getFeedbackWsUrl());
  feedbackSocket.onopen = () => { feedbackConnected.value = true; };
  feedbackSocket.onmessage = (event) => {
    try {
      applyFeedback(JSON.parse(event.data));
    } catch (err) {
      console.warn("ROS 反馈解析失败：", err);
    }
  };
  feedbackSocket.onclose = () => {
    feedbackConnected.value = false;
    feedbackClock.value = performance.now();
    feedbackSocket = null;
  };
  feedbackSocket.onerror = () => { feedbackConnected.value = false; };
};

const openDrawingDialog = () => {
  if (isDebugMode.value || busy.value || !isReady.value) return;
  dialogMode.value = "redraw";
  draftInitConfig.unitRowIds = [Number(initConfig.unitRowId)];
  draftInitConfig.unitRowId = Number(initConfig.unitRowId || selectedArmRowId.value || armIdList.value[0]?.id || 0);
  draftInitConfig.unitId = Number(armIdList.value.find((item: any) => Number(item.id) === draftInitConfig.unitRowId)?.Unit_ID || 0);
  draftInitConfig.drawingId = Number(initConfig.drawingId || drawingList.value[0]?.drawingId || 0);
  initDialogVisible.value = true;
};

const handleDialogCancel = () => {
  if (busy.value) return;
  if (dialogMode.value === "redraw" && initConfig.unitRowId && activeProfile.value?.configured) {
    selectedArmRowId.value = Number(initConfig.unitRowId);
    initDialogVisible.value = false;
    return;
  }
  goBack();
};

const handleArmSwitch = async (rowId: number) => {
  if (busy.value || !isReady.value || Number(rowId) === Number(initConfig.unitRowId)) return;
  const target = armIdList.value.find((item: any) => Number(item.id) === Number(rowId));
  if (!target || !confirmedUnitIds.value.includes(Number(target.Unit_ID))) return;
  saveActiveProfile();
  const profile = armProfiles[String(rowId)];
  selectedArmRowId.value = Number(rowId);
  if (profile?.configured) {
    restoreArmProfile(profile);
    return;
  }
  // 尚未操作过的已确认臂继承本次模式及首次图纸（调试模式图纸为空）。
  // 机械臂切换是运行态状态切换，不重新打开初始化弹窗。
  resetControlState();
  initConfig.unitRowId = Number(rowId);
  initConfig.unitId = Number(target.Unit_ID);
  initConfig.drawingId = isDebugMode.value ? 0 : Number(sharedDrawingId.value);
  initConfig.drawingSource = isDebugMode.value ? 'database' : sharedDrawingSource.value;
  pointCloudViews.value = sharedDrawingViews.value.map((item) => ({ ...item }));
  applyAxisEncoding(initConfig.unitId);
  armList.id = initConfig.unitId;
  busy.value = true;
  try {
    await loadSensorsForUnit(initConfig.unitRowId);
    if (noRosDebug) connectFeedbackSocket();
    saveActiveProfile(true);
  } finally {
    busy.value = false;
  }
};

const confirmInitConfig = async () => {
  if (busy.value) return;
  const selectedRowIds = dialogMode.value === "initial"
    ? [...draftInitConfig.unitRowIds]
    : [Number(draftInitConfig.unitRowId)];
  if (selectedRowIds.length === 0 || selectedRowIds.length > 5) {
    ElMessage.warning("请选择 1-5 台机械臂");
    return;
  }
  const drawingChoice = drawingList.value.find(item => Number(item.drawingId || 0) === Number(draftInitConfig.drawingId));
  const builtinDrawing = drawingChoice?.drawingSource === 'builtin_mock';
  if (!isDebugMode.value && !draftInitConfig.drawingId && !builtinDrawing) {
    ElMessage.warning("必须选择一张图纸才能继续");
    return;
  }

  const selectedUnits = selectedRowIds
    .map((rowId) => armIdList.value.find((item: any) => Number(item.id) === Number(rowId)))
    .filter(Boolean);
  if (selectedUnits.length !== selectedRowIds.length) {
    ElMessage.warning("所选机械臂已不可用，请重新选择");
    return;
  }

  busy.value = true;
  try {
    let confirmedUnits = selectedUnits;
    if (dialogMode.value === "initial") {
      for (const unit of selectedUnits) {
        const active = await getActiveFineTuningBatch(Number(moduleId.value), Number(unit.Unit_ID));
        if (active.data) { await restoreBatch(unit, active.data); return; }
      }
      const qX = Number(route.query.x || 0);
      const qY = Number(route.query.y || 0);
      const moduleRes: any = await createModule({
        x: qX,
        y: qY,
        module_id: Number(moduleId.value),
        device_id: Number(initConfig.deviceId),
        unit_ids: selectedUnits.map((item: any) => Number(item.Unit_ID)),
        position: 0,
        ...(drawingContextRevision.value !== null ? { connection_revision: drawingContextRevision.value } : {}),
      });
      if (!moduleRes || moduleRes.code !== 200 || moduleRes.dispatch?.confirmed === false) {
        throw new Error(moduleRes?.message || moduleRes?.msg || "机械臂模块确认失败");
      }
      const confirmedIds = Array.isArray(moduleRes.data?.confirmations)
        ? moduleRes.data.confirmations.filter((item: any) => item.confirmed === true).map((item: any) => Number(item.unit_id))
        : selectedUnits.map((item: any) => Number(item.Unit_ID));
      confirmedUnits = selectedUnits.filter((item: any) => confirmedIds.includes(Number(item.Unit_ID)));
      if (confirmedUnits.length !== selectedUnits.length) {
        throw new Error("所选机械臂未全部确认成功，请重新确认");
      }
      const seg = finiteFeedbackNumber(moduleRes.data?.seg);
      if (!noRosDebug && (seg === null || !Number.isInteger(seg) || seg < 0 || seg > 14)) {
        throw new Error('模块确认响应缺少有效 SEG，无法核验反馈归属');
      }
      confirmedSeg.value = seg;
      confirmedConnectionRevision.value = typeof moduleRes.data?.connection_revision === 'number' ? moduleRes.data.connection_revision : null;
      confirmedUnitIds.value = confirmedUnits.map((item: any) => Number(item.Unit_ID));
      armIdList.value = confirmedUnits;
    }

    const drawingId = isDebugMode.value ? 0 : Number(draftInitConfig.drawingId);
    let firstDrawingResponse: any = null;
    if (!isDebugMode.value) {
      for (const unit of confirmedUnits) {
        const response: any = await sendCoordination({
          device_id: Number(initConfig.deviceId),
          module_id: Number(moduleId.value),
          unit_id: Number(unit.Unit_ID),
          unit_row_id: Number(unit.id),
          drawing_id: builtinDrawing ? null : drawingId,
          drawing_source: builtinDrawing ? 'builtin_mock' : 'database',
          ...(confirmedConnectionRevision.value !== null ? { connection_revision: confirmedConnectionRevision.value } : {}),
        });
        if (!response || response.code !== 200) {
          throw new Error(response?.message || response?.msg || `机械臂 ${unit.Unit_ID} 图纸下发失败`);
        }
        firstDrawingResponse ||= response;
      }
    }

    const activeUnit = confirmedUnits[0];
    if (dialogMode.value === "initial") {
      for (const key of Object.keys(armProfiles)) delete armProfiles[key];
      resetControlState();
      initConfig.unitRowId = Number(activeUnit.id);
      initConfig.unitId = Number(activeUnit.Unit_ID);
      selectedArmRowId.value = initConfig.unitRowId;
      applyAxisEncoding(initConfig.unitId);
      await loadSensorsForUnit(initConfig.unitRowId);
      if (noRosDebug) connectFeedbackSocket();
      lastLoadedUnitRowId = initConfig.unitRowId;
      armList.id = initConfig.unitId;
    }
    initConfig.drawingId = drawingId;
    initConfig.drawingSource = !isDebugMode.value && builtinDrawing ? 'builtin_mock' : 'database';
    drawingSimulated.value = firstDrawingResponse?.simulated === true;
    // 初次建立会话时，图纸才是所有已确认机械臂的共享默认值。
    // 重新下发只更新当前机械臂，避免影响尚未切换到的机械臂。
    if (dialogMode.value === "initial") {
      sharedDrawingId.value = drawingId;
      sharedDrawingSource.value = initConfig.drawingSource;
    }

    const viewLabels: Record<string, string> = { top: "俯视图", front: "正视图", side: "侧视图" };
    const timestamp = Date.now();
    const dispatchedViews = Object.entries(firstDrawingResponse?.views || {}).map(([name, url]) => ({
      name,
      label: viewLabels[name] || name,
      url: `${url}${String(url).includes("?") ? "&" : "?"}t=${timestamp}`,
    }));
    pointCloudViews.value = dispatchedViews;
    if (dialogMode.value === "initial") {
      sharedDrawingViews.value = dispatchedViews.map((item) => ({ ...item }));
    }
    showPointCloudViews.value = false;
    saveActiveProfile(true);
    initDialogVisible.value = false;
    if (!noRosDebug && !feedbackSocket) connectFeedbackSocket();
    ElMessage.success(isDebugMode.value
      ? `已确认 ${confirmedUnits.length} 台机械臂，进入无图纸调试模式`
      : `已确认 ${confirmedUnits.length} 台机械臂并完成图纸下发`);
  } catch (err: any) {
    console.error("机械臂确认或图纸下发失败：", err.response?.data || err);
    const detail = err.response?.data?.detail;
    ElMessage.error(typeof detail === 'string' ? detail : detail?.reason || err.message || "机械臂确认或图纸下发失败");
  } finally {
    busy.value = Boolean(batchState.value?.target_locked);
  }
};
const applyBatch = (batch: FineTuningBatch) => {
  if (batch.module_id !== Number(moduleId.value) || batch.unit_id !== Number(initConfig.unitId)) return;
  batchState.value = batch;
  busy.value = batch.target_locked;
  for (const step of batch.steps) {
    if (step.status !== 'completed') continue;
    const index = adjustmentKeys.indexOf(step.parameter_name as AxisParameterName);
    if (index < 0) continue;
    armList.device[index].adjust = 0;
    // 只有明确的无 ROS 模拟可本地更新模拟位置；真实实测仍只来自遥测。
    if (noRosDebug && batch.simulated && appliedSimulationId !== batch.id) {
      updateAxisCurrent(index, Number(armList.device[index].current) + step.position);
    }
  }
  if (batch.simulated) appliedSimulationId = batch.id;
  if (!batch.target_locked && batchTimer !== undefined) {
    clearInterval(batchTimer);
    batchTimer = undefined;
  }
  saveActiveProfile();
};

const pollBatch = async () => {
  if (batchPolling || !batchState.value || (noRosDebug && batchState.value.simulated)) return;
  const requestedBatch = batchState.value;
  const isCurrent = () => batchState.value === requestedBatch &&
    requestedBatch.module_id === Number(moduleId.value) && requestedBatch.unit_id === Number(initConfig.unitId);
  batchPolling = true;
  try {
    const result = requestedBatch.id
      ? await getFineTuningBatch(requestedBatch.id)
      : await getFineTuningBatchByRequest(requestedBatch.request_id);
    if (!isCurrent()) return;
    if (result.data) {
      if (result.data.request_id !== requestedBatch.request_id || (requestedBatch.id && result.data.id !== requestedBatch.id)) return;
      applyBatch(result.data);
    }
    else requestedBatch.message = '暂未找到提交记录，结果仍待核实；请勿重新提交增量';
  } catch {
    if (isCurrent()) requestedBatch.message = '执行状态查询失败；不会重发指令，请恢复连接后查询';
  } finally {
    batchPolling = false;
  }
};

const startBatchPolling = () => {
  if (batchTimer !== undefined) clearInterval(batchTimer);
  if (batchState.value?.target_locked) batchTimer = setInterval(() => { void pollBatch(); }, 1000);
};

const restoreBatch = async (unit: any, batch: FineTuningBatch) => {
  initConfig.unitRowId = Number(unit.id);
  initConfig.unitId = Number(unit.Unit_ID);
  selectedArmRowId.value = initConfig.unitRowId;
  confirmedSeg.value = batch.seg;
  confirmedUnitIds.value = [initConfig.unitId];
  applyAxisEncoding(initConfig.unitId);
  armList.id = initConfig.unitId;
  for (const step of batch.steps) {
    const index = adjustmentKeys.indexOf(step.parameter_name as AxisParameterName);
    if (index >= 0) armList.device[index].adjust = step.position;
  }
  initDialogVisible.value = false;
  applyBatch(batch);
  startBatchPolling();
  connectFeedbackSocket();
};

const readConnectionContext = async () => {
  const value = (await getConnectionSettings()).data;
  isDebugMode.value = value.drawing_mode === 'skip';
  drawingContextRevision.value = value.revision;
};

const openConfiguration = async () => {
  if (busy.value) return;
  busy.value = true;
  try {
    await readConnectionContext();
    const unitResult: any = await getUnitsByDeviceApi(Number(initConfig.deviceId));
    armIdList.value = Array.isArray(unitResult) ? unitResult : Array.isArray(unitResult.data) ? unitResult.data : [];
    const unit = armIdList.value.find(item => Number(item.id) === Number(initConfig.unitRowId)) || armIdList.value[0];
    if (!unit) { ElMessage.warning('当前模块没有可用机械臂'); return; }
    if (!isDebugMode.value) {
      const result = await getFineTuningDrawingOptions();
      drawingList.value = Array.isArray(result.data) ? result.data : [];
      if (!drawingList.value.length) { ElMessage.warning('请先导入可用图纸'); return; }
    }
    dialogMode.value = 'initial';
    draftInitConfig.unitRowIds = [Number(unit.id)];
    draftInitConfig.unitRowId = Number(unit.id);
    draftInitConfig.unitId = Number(unit.Unit_ID);
    draftInitConfig.drawingId = isDebugMode.value ? 0 : Number(drawingList.value[0].drawingId);
    initDialogVisible.value = true;
  } catch {
    ElMessage.error('加载新会话配置失败，请恢复连接后重试');
  } finally {
    busy.value = Boolean(batchState.value?.target_locked);
  }
};

const confirmAdjustments = async () => {
  if (busy.value || !isReady.value) return;
  const adjustments = adjustmentKeys.map((parameter_name, index) => ({ parameter_name, position: Number(armList.device[index].adjust) }));
  if (adjustments.some(item => !Number.isFinite(item.position))) {
    ElMessage.warning('请输入有效的微调增量');
    return;
  }
  const pending = adjustments.filter(item => item.position !== 0);
  if (!pending.length) { ElMessage.warning('没有待下发的非零调整'); return; }
  const requestId = globalThis.crypto?.randomUUID?.() || `batch_${Date.now()}_${Math.random().toString(36).slice(2)}`;
  batchState.value = { id: '', request_id: requestId, module_id: Number(moduleId.value), unit_id: Number(initConfig.unitId), seg: Number(confirmedSeg.value),
    status: 'submitting', message: '正在登记本次调整', target_locked: true, steps: pending.map(item => ({ ...item, device_id: 0, status: 'pending' })) };
  busy.value = true;
  try {
    const result = await submitFineTuningBatch({ request_id: requestId, module_id: Number(moduleId.value), unit_id: Number(initConfig.unitId), adjustments: pending,
      ...(confirmedConnectionRevision.value !== null ? { connection_revision: confirmedConnectionRevision.value } : {}) });
    applyBatch(result.data);
  } catch (error: any) {
    // 网络失败可能发生在服务已登记之后，保留请求号，查询而不重发。
    if (error.response?.status === 409) {
      try {
        const active = await getActiveFineTuningBatch(Number(moduleId.value), Number(initConfig.unitId));
        if (active.data) { applyBatch(active.data); startBatchPolling(); return; }
        batchState.value.target_locked = false;
        batchState.value.status = 'blocked';
        busy.value = false;
      } catch { /* 归属不明时继续保持锁定并查询原请求。 */ }
    }
    if (error.response?.status === 422 || error.response?.status === 401) {
      batchState.value.target_locked = false;
      batchState.value.status = 'blocked';
      busy.value = false;
    }
    batchState.value.message = error.response?.data?.detail || '提交结果待确认，请查询本次请求；不会自动重发';
  }
  startBatchPolling();
};

const interruptBatch = async () => {
  if (batchState.value?.id) applyBatch((await interruptFineTuningBatch(batchState.value.id)).data);
};

const acknowledgeBatch = async () => {
  if (!batchState.value?.id) return;
  try {
    await ElMessageBox.confirm(batchState.value.simulated
      ? '请核对模拟批次的已执行项与未执行项。此操作只关闭模拟记录，不修改真实设备急停或故障状态，也不会重发指令。'
      : '请先在现场确认该机械臂已停止，并核对已执行的增量。此操作只关闭 MES 待核实记录，不解除急停或轴故障，也不会重发指令。', batchState.value.simulated ? '模拟记录确认' : '现场核实确认', { type: 'warning' });
    const result = await acknowledgeFineTuningBatch(batchState.value.id);
    for (const step of result.data.steps) {
      const index = adjustmentKeys.indexOf(step.parameter_name as AxisParameterName);
      if (index >= 0 && step.status !== 'pending') armList.device[index].adjust = 0;
    }
    applyBatch(result.data);
  } catch { /* 取消或 API 错误时保持原锁定状态。 */ }
};

const handleSaveConfig = async () => {
  if (busy.value) return;
  if (!isReady.value) {
    ElMessage.warning(isDebugMode.value ? "请先完成机械臂确认" : "请先确认机械臂并完成图纸下发");
    return;
  }
  if (!noRosDebug && !pressureSensorId.value) {
    ElMessage.warning("当前机械臂缺少已登记的压力传感器，请检查设备信息后重新进入");
    return;
  }

  busy.value = true;
  try {
    const savedAt = performance.now();
    feedbackClock.value = savedAt;
    const payload = {
      module_id: Number(moduleId.value),
      device_id: Number(initConfig.deviceId),
      unit_id: Number(initConfig.unitId),
      sensor_id: Number(pressureSensorId.value),
      is_debug: isDebugMode.value,
      drawing_id: isDebugMode.value || initConfig.drawingSource === 'builtin_mock' ? null : Number(initConfig.drawingId),
      drawing_source: initConfig.drawingSource,
      ...(confirmedConnectionRevision.value !== null ? { connection_revision: confirmedConnectionRevision.value } : {}),
      x: feedbackMarks.x.receivedAt === null ? null : imuFeedback.x,
      y: feedbackMarks.y.receivedAt === null ? null : imuFeedback.y,
      z: feedbackMarks.z.receivedAt === null ? null : imuFeedback.z,
      feedback_state: Object.fromEntries(FEEDBACK_FIELDS.map(field => [field, {
        status: fieldStatus(field),
        age_ms: feedbackMarks[field].receivedAt === null ? null : Math.max(0, savedAt - feedbackMarks[field].receivedAt!),
      }])),
      devices: armList.device.map((item: any, index: number) => {
        const base = {
          device_id: Number(item.deviceId || 0),
          unit_id: Number(initConfig.unitId),
          parameter_name: index === 3 ? "pressure" : adjustmentKeys[index],
          label: item.label || "压力传感器",
          initial: index < 3 && item.initialLocked ? Number(item.initial) : null,
          adjust: Number(item.adjust || 0),
          current: feedbackMarks[index === 3 ? 'pressure' : adjustmentKeys[index]].receivedAt === null ? null : Number(item.current),
        };
        // 轴的 device_id 与传感器的 sensor_id 是两套编码：仅臂级压力项携带 sensor_id
        return index === 3
          ? { ...base, sensor_id: pressureSensorId.value || undefined }
          : base;
      }),
    };

    const res: any = await saveFineTuningConfig(payload);
    if (res && res.code === 200) {
      saveActiveProfile();
      ElMessage.success(noRosDebug ? "配置模拟保存完成（未写入数据库）" : isDebugMode.value ? "调试配置保存成功（未绑定图纸）" : "配置保存成功");
    } else {
      ElMessage.error(res?.message || res?.msg || "配置保存失败");
    }
  } catch (err: any) {
    console.error("配置保存失败：", err.response?.data || err);
    ElMessage.error(
      err.response?.data?.detail ||
        err.response?.data?.message ||
        "配置保存失败，请检查后端服务"
    );
  } finally {
    busy.value = false;
  }
};

// 返回模块管理页面
const goBack = () => {
  if (busy.value) return;
  router.push("/moduleManagement");
};

// ========== 6. 页面初始化 ==========
const connectionChanged = () => {
  initDialogVisible.value = false;
  confirmedSeg.value = null;
  confirmedConnectionRevision.value = null;
  confirmedUnitIds.value = [];
  for (const key of Object.keys(armProfiles)) delete armProfiles[key];
  Object.assign(feedbackMarks, emptyFeedbackMarks());
  feedbackConnected.value = false;
  feedbackSimulated.value = false;
  drawingSimulated.value = false;
  resetControlState(busy.value);
  if (feedbackSocket) { feedbackSocket.close(); feedbackSocket = null; }
  if (!busy.value) batchState.value = null;
  ElMessage.warning('连接设置已变更，请重新配置并确认机械臂');
};

onMounted(async () => {
  window.addEventListener?.('ros-connection-changed', connectionChanged);
  feedbackTimer = setInterval(() => { feedbackClock.value = performance.now(); }, 500);
  const qModuleId = route.query.module_id;
  const qDeviceId = route.query.device_id ?? route.query.Device_ID;
  const qX = route.query.x;
  const qY = route.query.y;

  if (qModuleId) {
    moduleId.value = parseInt(qModuleId as string);
  } else {
    ElMessage.warning("未获取到模块编号，请从模块管理页面进入");
    router.push("/moduleManagement");
    return;
  }

  const lockedDeviceId = qDeviceId ? Number(qDeviceId) : Number(moduleId.value);
  initConfig.deviceId = lockedDeviceId;
  moduleDisplay.value = qX && qY
    ? `模块 ${moduleId.value} (${qX},${qY})`
    : `模块 ${moduleId.value}`;

  try {
    await readConnectionContext();
    const unitRes: any = await getUnitsByDeviceApi(lockedDeviceId);

    const units = Array.isArray(unitRes)
      ? unitRes
      : Array.isArray(unitRes.data)
        ? unitRes.data
        : [];
    // 机械臂由微调页首次配置弹窗统一选择。忽略旧版本链接携带的 unit_ids，
    // 避免历史路由参数把可选机械臂过滤为空。
    const availableUnits = units.filter((item: any) => Number.isFinite(Number(item.id)));
    armIdList.value = availableUnits;
    for (const unit of availableUnits) {
      const active = await getActiveFineTuningBatch(Number(moduleId.value), Number(unit.Unit_ID));
      if (active.data) { await restoreBatch(unit, active.data); return; }
    }
    const drawingRes: any = isDebugMode.value ? { data: [] } : await getFineTuningDrawingOptions();
    const drawings = Array.isArray(drawingRes) ? drawingRes : Array.isArray(drawingRes.data) ? drawingRes.data : [];
    drawingList.value = drawings.filter((item: any) => Number.isFinite(Number(item.drawingId)));

    if (armIdList.value.length === 0) {
      ElMessage.warning("当前模块下没有可用机械臂，请先在设备信息管理中添加机械臂");
      router.push("/HardWorkPage");
      return;
    }

    if (!isDebugMode.value && drawingList.value.length === 0) {
      ElMessage.warning("暂无可用图纸，请先在图纸管理中导入图纸");
      router.push("/drawingManage");
      return;
    }

    initConfig.unitRowId = Number(armIdList.value[0].id);
    initConfig.unitId = Number(armIdList.value[0].Unit_ID);
    initConfig.drawingId = 0;
    selectedArmRowId.value = initConfig.unitRowId;
    // 按 V2 轴号编码填充三轴/臂级 deviceId，并拉取压力传感器 sensor_ID
    applyAxisEncoding(initConfig.unitId);
    lastLoadedUnitRowId = initConfig.unitRowId;
    await loadSensorsForUnit(initConfig.unitRowId);
    dialogMode.value = "initial";
    draftInitConfig.unitRowIds = [];
    draftInitConfig.unitRowId = initConfig.unitRowId;
    draftInitConfig.unitId = initConfig.unitId;
    draftInitConfig.drawingId = isDebugMode.value ? 0 : Number(drawingList.value[0].drawingId);
    armList.id = initConfig.unitId;
    connectFeedbackSocket();
    initDialogVisible.value = true;
  } catch (err: any) {
    console.error("初始化机械臂或图纸列表失败：", err.response?.data || err);
    ElMessage.error("初始化机械臂或图纸列表失败");
  }
});

onBeforeUnmount(() => {
  window.removeEventListener?.('ros-connection-changed', connectionChanged);
  if (batchTimer !== undefined) clearInterval(batchTimer);
  if (feedbackTimer !== undefined) clearInterval(feedbackTimer);
  if (feedbackSocket) {
    feedbackSocket.close();
    feedbackSocket = null;
  }
});
</script>


<style scoped>
.batch-controls { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin: 20px 0; }
.batch-controls span, .batch-progress p { color: #606266; font-size: 13px; }
.batch-progress { padding: 16px; border: 1px solid #e4e7ed; border-radius: 8px; }
.ack-card { width: min(100%, 980px); }
.ack-raw { white-space: pre-wrap; overflow-wrap: anywhere; }
.ack-card :deep(.el-collapse-item__header) { height: auto; min-height: 48px; line-height: 1.6; padding: 8px 0; }
.imu-item small { display: block; margin-top: 6px; color: #718096; font-size: 11px; }
.el-card__header{
  display: flex;
  justify-content: space-between;
}
.input-box {
  display: grid;
  grid-template-columns: 148px 150px;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.input-box :deep(.el-input-number) {
  width: min(150px, 100%);
}
.fine-tuning-container {
  overflow: auto;
  background:
    radial-gradient(circle at 88% 8%, rgba(37, 99, 235, 0.08), transparent 30%),
    #eef3f8;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.back-button {
  font-size: 14px;
}

.header-right {
  display: flex;
  justify-content: end;
  gap: 10px;
}

/* ========== 卡片样式 ========== */
.arm-list {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  margin-top: 24px;
  gap: 16px;
}

.main-control-card {
  width: min(100%, 900px);
  border-radius: 16px;
  border: 1px solid #dce6f0;
  box-shadow: 0 16px 36px rgba(15, 39, 67, 0.08) !important;
}

.runtime-toolbar {
  width: min(100%, 980px);
  box-sizing: border-box;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 18px;
  flex-wrap: wrap;
  padding: 14px 16px;
  border: 1px solid #d9e4ef;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.82);
  box-shadow: 0 8px 24px rgba(15, 39, 67, 0.06);
}

.runtime-context,
.runtime-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.runtime-context {
  color: #526274;
  font-size: 13px;
}

.runtime-context strong {
  color: #102a43;
  font-size: 15px;
}

.context-kicker {
  color: #718096;
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.context-divider {
  width: 1px;
  height: 18px;
  background: #d7e0e9;
}

.active-arm-chip {
  padding: 5px 10px;
  border: 1px solid #b8e3d6;
  border-radius: 999px;
  background: #ecfdf5;
  color: #087f5b;
  font-weight: 600;
}

.arm-switcher {
  width: 190px;
}

.pointcloud-card {
  width: min(100%, 980px);
  border-radius: 12px;
  border: none;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.05) !important;
}

.pointcloud-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.pointcloud-view {
  min-width: 0;
}

.pointcloud-title {
  color: #606266;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
}

.pointcloud-image {
  display: block;
  width: 100%;
  aspect-ratio: 16 / 10;
  object-fit: contain;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  background: #f5f7fa;
}

@media (max-width: 900px) {
  .pointcloud-grid {
    grid-template-columns: 1fr;
  }
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.control-heading {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  min-width: 0;
}

.control-caption {
  padding-left: 12px;
  border-left: 1px solid #d9e4ef;
  color: #718096;
  font-size: 12px;
  white-space: nowrap;
}

.header-text {
  font-weight: bold;
  font-size: 16px;
  color: #303133;
}

.config-form :deep(.el-form-item__label) {
  color: #425466;
  font-weight: 650;
}

.dialog-intro {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  margin-bottom: 20px;
  padding: 14px 16px;
  border: 1px solid #cfe4f5;
  border-radius: 12px;
  background: #f2f8fc;
}

.dialog-intro-icon {
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  border-radius: 9px;
  background: #0f5b78;
  color: #fff;
  font-size: 18px;
}

.dialog-intro strong {
  color: #153b50;
  font-size: 15px;
}

.dialog-intro p {
  margin: 4px 0 0;
  color: #6a7d8d;
  font-size: 12px;
  line-height: 1.5;
}

.dialog-arm-picker {
  width: 100%;
  padding: 12px;
  border: 1px solid #e1e8ef;
  border-radius: 12px;
  background: #f8fafc;
}

.dialog-field-meta {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
  color: #788797;
  font-size: 12px;
}

.dialog-field-meta b {
  color: #0f5b78;
}

.dialog-arm-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.dialog-arm-card {
  width: 100%;
  margin: 0 !important;
}

.dialog-arm-card :deep(.el-checkbox-button__inner) {
  display: flex;
  min-height: 60px;
  box-sizing: border-box;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  width: 100%;
  padding: 8px 10px;
  border: 1px solid #d7e1ea !important;
  border-radius: 9px !important;
  background: #fff;
  box-shadow: none !important;
  color: #425466;
  text-align: left;
}

.dialog-arm-card.is-checked :deep(.el-checkbox-button__inner) {
  border-color: #168aad !important;
  background: #e8f7fb;
  color: #0f5b78;
}

.dialog-arm-card small {
  margin-top: 3px;
  color: #8a9aab;
  font-size: 10px;
}

@media (max-width: 700px) {
  .dialog-arm-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.control-grid {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 10px 20px;
}

.control-item {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.label-box {
  display: grid;
  grid-template-columns: 310px 110px minmax(0, 1fr);
  align-items: center;
  gap: 12px;
  min-height: 40px;
}

.label-title {
  font-weight: 500;
  color: #606266;
  font-size: 14px;
  white-space: nowrap;
}

.real-time-tag {
  font-size: 13px;
  color: #64748b;
  background: #f4f4f5;
  padding: 4px 10px;
  border-radius: 4px;
  box-sizing: border-box;
  min-width: 0;
  line-height: 1.6;
  overflow-wrap: anywhere;
}

@media (max-width: 1100px) {
  .label-box {
    grid-template-columns: 110px minmax(0, 1fr);
    row-gap: 10px;
  }

  .input-box {
    grid-column: 1 / -1;
  }
}

@media (max-width: 480px) {
  .control-grid {
    padding-inline: 0;
  }

  .input-box {
    grid-template-columns: minmax(0, 1fr);
    gap: 8px;
  }

  .label-title {
    white-space: normal;
  }
}

.input-wrapper {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* 陀螺仪反馈面板 */
.imu-panel {
  margin-top: 34px;
  border: 1px solid var(--mes-border-light);
  border-radius: var(--mes-radius);
  padding: 18px 20px;
  background: #f8fafc;
}

.imu-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.imu-item {
  min-width: 0;
  border-radius: 6px;
  background: #fff;
  border: 1px solid #ebeef5;
  padding: 10px 8px;
  text-align: center;
}

.imu-label {
  display: block;
  color: #909399;
  font-size: 12px;
  margin-bottom: 6px;
}

.imu-value {
  display: block;
  color: #303133;
  font-size: 15px;
  font-weight: 600;
}

@media (max-width: 900px) {
  .imu-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .card-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .control-caption {
    padding-left: 0;
    border-left: 0;
  }

  .runtime-actions,
  .runtime-actions .arm-switcher,
  .runtime-actions .el-button {
    width: 100%;
  }
}

.sensor-panel {
  margin-top: 40px;
  background: linear-gradient(135deg, var(--mes-aside-bg-1), var(--mes-aside-bg-2));
  border-radius: var(--mes-radius);
  padding: 20px;
  color: #fff;
  text-align: center;
}

.sensor-title {
  font-size: 13px;
  color: #a8abb2;
  margin-bottom: 12px;
}

.sensor-value-box {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.value-text {
  font-size: 14px;
  letter-spacing: 1px;
}

/* 呼吸灯效果 */
.status-dot {
  width: 8px;
  height: 8px;
  background-color: #f56c6c;
  border-radius: 50%;
}

.pulse {
  animation: pulse-red 2s infinite;
}

@keyframes pulse-red {
  0% {
    transform: scale(0.95);
    box-shadow: 0 0 0 0 rgba(245, 108, 108, 0.7);
  }
  70% {
    transform: scale(1);
    box-shadow: 0 0 0 6px rgba(245, 108, 108, 0);
  }
  100% {
    transform: scale(0.95);
    box-shadow: 0 0 0 0 rgba(245, 108, 108, 0);
  }
}

.batch-bar {
  margin-top: 30px;
  display: flex;
  gap: 16px;
  justify-content: center;
}
</style>





