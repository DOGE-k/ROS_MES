<template>
  <div class="fine-tuning-container mes-page">
    <!-- 顶部标题和返回按钮 -->
    <div class="mes-page-header">
      <div class="header-left">
        <el-button @click="goBack" class="back-button" :icon="ArrowLeft" round>返回</el-button>
        <div>
          <h2 class="mes-page-title">机械臂姿态微调与压力监控</h2>
          <p class="mes-page-sub">在已确认的机械臂之间切换，实时调整姿态并查看传感器反馈</p>
        </div>
      </div>
    </div>
    <div class="arm-list">
      <div class="runtime-toolbar">
        <div class="runtime-context">
          <span class="context-kicker">运行状态</span>
          <strong>模块 {{ moduleId }}</strong>
          <span class="context-divider"></span>
          <span>当前机械臂</span>
          <span class="active-arm-chip">机械臂 {{ armNumber(initConfig.unitId) }}</span>
        </div>
        <div class="runtime-actions">
          <el-select v-model="selectedArmRowId" class="arm-switcher" :disabled="busy" placeholder="切换机械臂" @change="handleArmSwitch">
            <el-option v-for="item in armIdList" :key="item.id" :label="`机械臂 ${armNumber(item.Unit_ID)}`" :value="item.id" />
          </el-select>
          <el-button type="primary" plain :disabled="busy" @click="openDrawingDialog">
            {{ activeProfile?.drawingId ? "重新下发图纸" : "下发图纸" }}
          </el-button>
          <el-button type="primary" plain @click="togglePointCloudViews">
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
              <span class="control-caption">图纸 {{ activeProfile?.drawingId || "未下发" }}</span>
            </div>
            <el-button type="success" :disabled="busy || !activeProfile?.drawingId" @click="handleSaveConfig"
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
                  placeholder="顺时针为正"
                  :disabled="busy || !activeProfile?.drawingId"
                  @change="sendSingleAdjust(0)"
                  @enter="sendSingleAdjust(0)"
                />
              </div>

              <span class="real-time-tag"
                >初始值: {{ armList.device[0].initial }}</span
              >
              <span class="real-time-tag"
                >当前实际值: {{ armList.device[0].current }}</span
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
                  placeholder="顺时针为正"
                  :disabled="busy || !activeProfile?.drawingId"
                  @change="sendSingleAdjust(1)"
                />
              </div>

              <span class="real-time-tag"
                >初始值: {{ armList.device[1].initial }}</span
              >
              <span class="real-time-tag"
                >当前实际值: {{ armList.device[1].current }}</span
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
                  placeholder="顺时针为正"
                  :disabled="busy || !activeProfile?.drawingId"
                  @change="sendSingleAdjust(2)"
                />
              </div>

              <span class="real-time-tag"
                >初始值: {{ armList.device[2].initial }}</span
              >
              <span class="real-time-tag"
                >当前实际值: {{ armList.device[2].current }}</span
              >
            </div>
          </div>
        </div>

        <div class="imu-panel">
          <div class="sensor-title">陀螺仪姿态与末端坐标反馈</div>
          <div class="imu-grid">
            <div class="imu-item">
              <span class="imu-label">摆动角</span>
              <span class="imu-value">{{ formatFeedbackValue(imuFeedback.swingAngle) }}°</span>
            </div>
            <div class="imu-item">
              <span class="imu-label">旋转角</span>
              <span class="imu-value">{{ formatFeedbackValue(imuFeedback.rotationAngle) }}°</span>
            </div>
            <div class="imu-item">
              <span class="imu-label">X</span>
              <span class="imu-value">{{ formatFeedbackValue(imuFeedback.x) }} cm</span>
            </div>
            <div class="imu-item">
              <span class="imu-label">Y</span>
              <span class="imu-value">{{ formatFeedbackValue(imuFeedback.y) }} cm</span>
            </div>
            <div class="imu-item">
              <span class="imu-label">Z</span>
              <span class="imu-value">{{ formatFeedbackValue(imuFeedback.z) }} cm</span>
            </div>
          </div>
        </div>

        <div class="sensor-panel">
          <div class="sensor-title">压力传感器实时反馈</div>
          <div class="sensor-value-box" v-if="loading">
            <span>{{ armList.device[3].current }}</span>
          </div>
          <div class="sensor-value-box" v-else>
            <span class="status-dot pulse"></span>
            <span class="value-text">等待数据接入...</span>
          </div>
        </div>
      </el-card>
    </div>

    <el-dialog
      class="initial-config-dialog"
      v-model="initDialogVisible"
      :title="dialogMode === 'initial' ? '确认机械臂并下发图纸' : '重新下发图纸'"
      width="450px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="false"
    >
      <div class="dialog-intro">
        <div class="dialog-intro-icon">⌁</div>
        <div>
          <strong>{{ dialogMode === "initial" ? "建立本次微调会话" : "更新当前机械臂图纸" }}</strong>
          <p>{{ dialogMode === "initial" ? "先确认需要参与本模块的机械臂，再统一下发目标图纸。" : "重新下发图纸只作用于当前机械臂。" }}</p>
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
              :disabled="dialogMode !== 'initial'"
            >
              <el-checkbox-button v-for="item in armIdList" :key="item.id" :label="item.id" class="dialog-arm-card">
                <span>机械臂 {{ armNumber(item.Unit_ID) }}</span>
                <small>Unit_ID {{ item.Unit_ID }}</small>
              </el-checkbox-button>
            </el-checkbox-group>
          </div>
        </el-form-item>
        <el-form-item label="目标图纸" required>
          <el-select v-model="draftInitConfig.drawingId" placeholder="请选择目标图纸" style="width: 100%">
            <el-option v-for="item in drawingList" :key="item.drawingId" :label="item.drawingName" :value="item.drawingId" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="handleDialogCancel">
          {{ dialogMode === "initial" ? "返回模块选择" : "取消" }}
        </el-button>
        <el-button type="primary" :loading="busy" :disabled="busy" @click="confirmInitConfig">确认并下发</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onBeforeUnmount } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { ArrowLeft } from "@element-plus/icons-vue";
import {
  getDrawingListApi,
  getUnitsByDeviceApi,
  getSensorsByUnitApi,
  createModule,
  sendCoordination,
  sendFineTuning,
  saveFineTuningConfig,
} from "@/api/rosApi";
import { noRosDebug } from "@/api/noRosDebug";
import {
  armIndexFromUnitId,
  axisDeviceId,
  armLevelDeviceId,
  type AxisParameterName,
} from "@/api/deviceEncoding";

const router = useRouter();

// 数据准备完成后再打开配置弹窗，避免接口加载期间短暂显示空表单。
const initDialogVisible = ref(false);
const initConfig = reactive({
  deviceId: 0,
  unitId: 0,
  unitRowId: 0,
  sensorId: 0,
  drawingId: 0,
});
const draftInitConfig = reactive({
  unitRowIds: [] as number[],
  unitRowId: 0,
  unitId: 0,
  drawingId: 0,
});
const dialogMode = ref<"initial" | "redraw">("initial");
const sharedDrawingId = ref(0);
const sharedDrawingViews = ref<Array<{ name: string; label: string; url: string }>>([]);

const loading = ref(false);
const busy = ref(false);
let feedbackSocket: WebSocket | null = null;
const armIdList = ref<any[]>([]);
const drawingList = ref<any[]>([]);
const pointCloudViews = ref<Array<{ name: string; label: string; url: string }>>([]);
const showPointCloudViews = ref(false);
const route = useRoute();
const moduleId = ref<number>(0);
const moduleDisplay = ref("");
const selectedArmRowId = ref(0);
const armProfiles = reactive<Record<string, any>>({});
const activeProfile = computed(() =>
  initConfig.unitRowId ? armProfiles[String(initConfig.unitRowId)] || null : null
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
// 反馈 device_id → 轴下标映射：按选中机械臂的 V2 轴号动态构建，见 rebuildFeedbackIndex
let feedbackDeviceIndex: Record<number, number> = {};
// 当前选中机械臂的臂级传感器（压力/IMU 共用）device_id 与压力传感器 sensor_ID
let armLevelId = 0;
let lastLoadedUnitRowId = 0;
const pressureSensorId = ref<number>(0);

const cloneDevices = () => armList.device.map((item: any) => ({ ...item }));

const saveActiveProfile = (force = false) => {
  if (!initConfig.unitRowId || !initConfig.drawingId) return;
  const existingProfile = armProfiles[String(initConfig.unitRowId)];
  if (!force && !existingProfile?.configured) return;
  armProfiles[String(initConfig.unitRowId)] = {
    unitRowId: Number(initConfig.unitRowId),
    unitId: Number(initConfig.unitId),
    drawingId: Number(initConfig.drawingId),
    configured: true,
    device: cloneDevices(),
    imu: { ...imuFeedback },
    pressureSensorId: Number(pressureSensorId.value || 0),
    pointCloudViews: pointCloudViews.value.map((item) => ({ ...item })),
    showPointCloudViews: Boolean(showPointCloudViews.value),
  };
};

const resetControlState = () => {
  armList.device.forEach((item: any, index: number) => {
    item.initial = 0;
    item.adjust = index < 3 ? 0 : undefined;
    item.current = 0;
    item.initialLocked = false;
  });
  Object.assign(imuFeedback, { swingAngle: 0, rotationAngle: 0, x: 0, y: 0, z: 0 });
  pressureSensorId.value = 0;
  pointCloudViews.value = [];
  showPointCloudViews.value = false;
  loading.value = false;
};

const restoreArmProfile = (profile: any) => {
  initConfig.unitRowId = Number(profile.unitRowId);
  initConfig.unitId = Number(profile.unitId);
  initConfig.drawingId = Number(profile.drawingId);
  armList.device.splice(0, armList.device.length, ...profile.device.map((item: any) => ({ ...item })));
  Object.assign(imuFeedback, profile.imu || {});
  pressureSensorId.value = Number(profile.pressureSensorId || 0);
  pointCloudViews.value = (profile.pointCloudViews || []).map((item: any) => ({ ...item }));
  showPointCloudViews.value = Boolean(profile.showPointCloudViews);
  applyAxisEncoding(initConfig.unitId);
  armList.id = initConfig.unitId;
  lastLoadedUnitRowId = initConfig.unitRowId;
  loading.value = true;
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
      pressureSensorId.value = Number(pressure.sensor_ID || pressure.id || 0);
    }
  } catch (err) {
    console.warn("获取传感器列表失败：", err);
  }
  initConfig.sensorId = pressureSensorId.value;
};

const formatFeedbackValue = (value: number) => Number(value || 0).toFixed(2);

const togglePointCloudViews = () => {
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
};

const applyMockInitialFeedback = () => {
  [0, 1, 2].forEach((index) => updateAxisCurrent(index, 0));
};

const applyImuFeedback = (feedback: any) => {
  imuFeedback.swingAngle = Number(feedback.swing_angle || 0);
  imuFeedback.rotationAngle = Number(feedback.rotation_angle || 0);
  imuFeedback.x = Number(feedback.x || 0);
  imuFeedback.y = Number(feedback.y || 0);
  imuFeedback.z = Number(feedback.z || 0);
};

const getFeedbackWsUrl = () => {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/api/control/feedback/ws`;
};

const applyFeedback = (feedback: any) => {
  if (!feedback || feedback.data_type === "error") {
    if (feedback?.message) {
      console.warn("ROS 反馈订阅异常：", feedback.message);
    }
    return;
  }

  // V2.1 伸缩轴契约：ROS 回传 0.01mm，后端归一化时附加 position_mm（毫米），
  // 伸缩轴显示优先取毫米值；旋转/摆动仍为度，直接用 position
  const rawPosition = Number(feedback.position);
  const positionMm = Number(feedback.position_mm);
  const position =
    feedback.data_type === "telescope_axis_encoder" && Number.isFinite(positionMm)
      ? positionMm
      : rawPosition;
  if (
    feedback.data_type === "axis_encoder" ||
    feedback.data_type === "rotation_axis_encoder" ||
    feedback.data_type === "swing_axis_encoder" ||
    feedback.data_type === "telescope_axis_encoder"
  ) {
    if (!Number.isFinite(position)) {
      return;
    }
    const index = feedbackDeviceIndex[Number(feedback.device_id)];
    if (index !== undefined) {
      updateAxisCurrent(index, position);
      loading.value = true;
    }
    return;
  }

  if (feedback.data_type === "pressure_sensor") {
    if (Number(feedback.device_id) !== Number(armLevelId)) {
      return;
    }
    if (!Number.isFinite(position)) {
      return;
    }
    armList.device[3].current = position;
    loading.value = true;
    return;
  }

  if (feedback.data_type === "imu_pose") {
    if (Number(feedback.device_id) !== Number(armLevelId)) {
      return;
    }
    applyImuFeedback(feedback);
  }
};

const connectFeedbackSocket = () => {
  // 无 ROS 调试模式：不连接真实反馈 WebSocket，方便只调页面跳转和微调交互。
  if (noRosDebug) {
    loading.value = true;
    armList.device[3].current = 0.5;
    applyMockInitialFeedback();
    imuFeedback.swingAngle = 1.25;
    imuFeedback.rotationAngle = -2.5;
    imuFeedback.x = 12.3;
    imuFeedback.y = 4.56;
    imuFeedback.z = 7.89;
    return;
  }

  if (feedbackSocket) {
    feedbackSocket.close();
  }

  feedbackSocket = new WebSocket(getFeedbackWsUrl());
  feedbackSocket.onmessage = (event) => {
    try {
      applyFeedback(JSON.parse(event.data));
    } catch (err) {
      console.warn("ROS 反馈解析失败：", err);
    }
  };
  feedbackSocket.onclose = () => {
    feedbackSocket = null;
  };
};

const openDrawingDialog = () => {
  dialogMode.value = "redraw";
  draftInitConfig.unitRowIds = [Number(initConfig.unitRowId)];
  draftInitConfig.unitRowId = Number(initConfig.unitRowId || selectedArmRowId.value || armIdList.value[0]?.id || 0);
  draftInitConfig.unitId = Number(armIdList.value.find((item: any) => Number(item.id) === draftInitConfig.unitRowId)?.Unit_ID || 0);
  draftInitConfig.drawingId = Number(initConfig.drawingId || drawingList.value[0]?.drawingId || 0);
  initDialogVisible.value = true;
};

const handleDialogCancel = () => {
  if (dialogMode.value === "redraw" && initConfig.unitRowId && activeProfile.value?.drawingId) {
    selectedArmRowId.value = Number(initConfig.unitRowId);
    initDialogVisible.value = false;
    return;
  }
  goBack();
};

const handleArmSwitch = async (rowId: number) => {
  if (busy.value || Number(rowId) === Number(initConfig.unitRowId)) return;
  const target = armIdList.value.find((item: any) => Number(item.id) === Number(rowId));
  if (!target) return;
  saveActiveProfile();
  const profile = armProfiles[String(rowId)];
  selectedArmRowId.value = Number(rowId);
  if (profile?.configured) {
    restoreArmProfile(profile);
    return;
  }
  // 切换到本次已确认但尚未操作过的机械臂时，直接继承首次下发的图纸。
  // 机械臂切换是运行态状态切换，不重新打开初始化弹窗。
  resetControlState();
  initConfig.unitRowId = Number(rowId);
  initConfig.unitId = Number(target.Unit_ID);
  initConfig.drawingId = Number(sharedDrawingId.value || drawingList.value[0]?.drawingId || 0);
  pointCloudViews.value = sharedDrawingViews.value.map((item) => ({ ...item }));
  applyAxisEncoding(initConfig.unitId);
  armList.id = initConfig.unitId;
  busy.value = true;
  try {
    await loadSensorsForUnit(initConfig.unitRowId);
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
  if (!draftInitConfig.drawingId) {
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
      const qX = Number(route.query.x || 0);
      const qY = Number(route.query.y || 0);
      const moduleRes: any = await createModule({
        x: qX,
        y: qY,
        module_id: Number(moduleId.value),
        device_id: Number(initConfig.deviceId),
        unit_ids: selectedUnits.map((item: any) => Number(item.Unit_ID)),
        position: 0,
      });
      if (!moduleRes || moduleRes.code !== 200) {
        throw new Error(moduleRes?.message || moduleRes?.msg || "机械臂模块确认失败");
      }
      const confirmedIds = Array.isArray(moduleRes.data?.confirmations)
        ? moduleRes.data.confirmations.map((item: any) => Number(item.unit_id))
        : selectedUnits.map((item: any) => Number(item.Unit_ID));
      confirmedUnits = selectedUnits.filter((item: any) => confirmedIds.includes(Number(item.Unit_ID)));
      if (confirmedUnits.length === 0) {
        throw new Error("没有机械臂确认成功");
      }
      armIdList.value = confirmedUnits;
    }

    const drawingId = Number(draftInitConfig.drawingId);
    let firstDrawingResponse: any = null;
    for (const unit of confirmedUnits) {
      const response: any = await sendCoordination({
        device_id: Number(initConfig.deviceId),
        module_id: Number(moduleId.value),
        unit_id: Number(unit.Unit_ID),
        unit_row_id: Number(unit.id),
        drawing_id: drawingId,
      });
      if (!response || response.code !== 200) {
        throw new Error(response?.message || response?.msg || `机械臂 ${unit.Unit_ID} 图纸下发失败`);
      }
      firstDrawingResponse ||= response;
    }

    const activeUnit = confirmedUnits[0];
    if (dialogMode.value === "initial") {
      resetControlState();
      initConfig.unitRowId = Number(activeUnit.id);
      initConfig.unitId = Number(activeUnit.Unit_ID);
      selectedArmRowId.value = initConfig.unitRowId;
      applyAxisEncoding(initConfig.unitId);
      await loadSensorsForUnit(initConfig.unitRowId);
      lastLoadedUnitRowId = initConfig.unitRowId;
      armList.id = initConfig.unitId;
      loading.value = true;
    }
    initConfig.drawingId = drawingId;
    // 初次建立会话时，图纸才是所有已确认机械臂的共享默认值。
    // 重新下发只更新当前机械臂，避免影响尚未切换到的机械臂。
    if (dialogMode.value === "initial") {
      sharedDrawingId.value = drawingId;
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
    ElMessage.success(`已确认 ${confirmedUnits.length} 台机械臂并完成图纸下发`);
  } catch (err: any) {
    console.error("机械臂确认或图纸下发失败：", err.response?.data || err);
    ElMessage.error(err.response?.data?.detail || err.message || "机械臂确认或图纸下发失败");
  } finally {
    busy.value = false;
  }
};
// 单个机械臂微调：不改变 Unit_ID，只记录参数名和调整值
const sendSingleAdjust = async (value: number) => {
  const adjustValue = Number(armList.device[value].adjust);

  console.log("微调值：", adjustValue);
  loading.value = false;

  const parameterName = adjustmentKeys[value] || `adjust_${value}`;

  try {
    const res: any = await sendFineTuning({
      module_id: Number(moduleId.value),
      device_id: Number(armList.device[value].deviceId),
      unit_id: Number(initConfig.unitId),
      parameter_name: parameterName,
      position: adjustValue,
    });

    console.log("微调返回：", res);

    if (res && res.code === 200) {
      ElMessage.success(`机械臂 ${armList.id} 微调成功`);

      if (Array.isArray(res.data)) {
        for (const i of res.data) {
          if (i.type === "imu_pose") {
            applyImuFeedback(i);
          } else if (i.parameter_name === parameterName || Number(i.device_id) === Number(armList.device[value].deviceId)) {
            updateAxisCurrent(value, Number(i.position));
          } else {
            armList.device[3].current = Number(i.position);
            loading.value = true;
          }
        }
      }

      else if (res.data && res.data.position !== undefined) {
        updateAxisCurrent(value, Number(res.data.position));
      }

      else {
        updateAxisCurrent(value, adjustValue);
      }

      armList.device[value].adjust = Number(armList.device[value].current);
    } else {
      ElMessage.error(res?.message || res?.msg || "微调失败");
    }
  } catch (err: any) {
    console.error("微调失败：", err.response?.data || err);
    ElMessage.error(
      err.response?.data?.detail ||
        err.response?.data?.message ||
        "请求失败，请检查后端服务"
    );
  }
};

const handleSaveConfig = async () => {
  if (
    initConfig.deviceId === null ||
    initConfig.deviceId === undefined
  ) {
    ElMessage.warning("请先选择机械臂并完成目标图纸下发");
    return;
  }

  try {
    const payload = {
      module_id: Number(moduleId.value),
      device_id: Number(initConfig.deviceId),
      unit_id: Number(initConfig.unitId),
      sensor_id: Number(initConfig.sensorId),
      drawing_id: Number(initConfig.drawingId),
      devices: armList.device.map((item: any, index: number) => {
        const base = {
          device_id: Number(item.deviceId || 0),
          unit_id: Number(initConfig.unitId),
          parameter_name: index === 3 ? "pressure" : adjustmentKeys[index],
          label: item.label || "压力传感器",
          initial: Number(item.initial || 0),
          adjust: Number(item.adjust || 0),
          current: Number(item.current || 0),
        };
        // 轴的 device_id 与传感器的 sensor_id 是两套编码：仅臂级压力项携带 sensor_id
        return index === 3
          ? { ...base, sensor_id: pressureSensorId.value || undefined }
          : base;
      }),
    };

    const res: any = await saveFineTuningConfig(payload);
    if (res && res.code === 200) {
      ElMessage.success("配置保存成功");
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
  }
};

// 返回模块管理页面
const goBack = () => {
  router.push("/moduleManagement");
};

// ========== 6. 页面初始化 ==========
onMounted(async () => {
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
    const [unitRes, drawingRes]: any[] = await Promise.all([
      getUnitsByDeviceApi(lockedDeviceId),
      getDrawingListApi(),
    ]);

    const units = Array.isArray(unitRes)
      ? unitRes
      : Array.isArray(unitRes.data)
        ? unitRes.data
        : [];
    const drawings = Array.isArray(drawingRes)
      ? drawingRes
      : Array.isArray(drawingRes.data)
        ? drawingRes.data
        : [];

    // 机械臂由微调页首次配置弹窗统一选择。忽略旧版本链接携带的 unit_ids，
    // 避免历史路由参数把可选机械臂过滤为空。
    const availableUnits = units.filter((item: any) => Number.isFinite(Number(item.id)));
    armIdList.value = availableUnits;
    drawingList.value = drawings.filter((item: any) => Number.isFinite(Number(item.drawingId)));

    if (armIdList.value.length === 0) {
      ElMessage.warning("当前模块下没有可用机械臂，请先在设备信息管理中添加机械臂");
      router.push("/HardWorkPage");
      return;
    }

    if (drawingList.value.length === 0) {
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
    draftInitConfig.drawingId = Number(drawingList.value[0].drawingId);
    armList.id = initConfig.unitId;
    connectFeedbackSocket();
    initDialogVisible.value = true;
  } catch (err: any) {
    console.error("初始化机械臂或图纸列表失败：", err.response?.data || err);
    ElMessage.error("初始化机械臂或图纸列表失败");
  }
});

onBeforeUnmount(() => {
  if (feedbackSocket) {
    feedbackSocket.close();
    feedbackSocket = null;
  }
});
</script>


<style scoped>
.el-card__header{
  display: flex;
  justify-content: space-between;
}
.input-box {
  display: flex;
  flex-direction: row;
  gap: 12px;
  flex-grow: 1;
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
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.label-title {
  font-weight: 500;
  color: #606266;
  font-size: 14px;
}

.real-time-tag {
  font-size: 13px;
  color: #909399;
  background: #f4f4f5;
  padding: 4px 10px;
  border-radius: 4px;
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





