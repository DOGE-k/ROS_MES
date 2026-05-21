<template>
  <div class="fine-tuning-container">
    <!-- 顶部标题和返回按钮 -->
    <el-card class="header-card">
      <div class="header-row">
        <div class="header-left">
          <el-button type="default" @click="goBack" class="back-button">
            &lt; Back
          </el-button>
          <h2 class="page-title">机械臂姿态微调与压力监控</h2>
        </div>
      </div>
    </el-card>
    <div class="arm-list">
      <el-card shadow="hover" class="main-control-card">
        <template #header>
          <div class="card-header">
            <span class="header-text"
              >核心机械臂控制单元 - 机械臂 {{ armList.id }}</span
            >
            <el-button type="success" @click="handleSaveConfig"
              >保存配置</el-button
            >
          </div>
        </template>
        <div class="control-grid">
          <div class="control-item">
            <div class="label-box">
              <div class="input-box">
                <span class="label-title"
                  >{{ armList.device[0].label }}(度)</span
                >
                <el-input-number
                  v-model="armList.device[0].adjust"
                  :min="-360"
                  :max="360"
                  placeholder="顺时针为正"
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
                  >{{ armList.device[1].label }}(度)</span
                >
                <el-input-number
                  v-model="armList.device[1].adjust"
                  :min="-360"
                  :max="360"
                  placeholder="顺时针为正"
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
      v-model="initDialogVisible"
      title="目标图纸下发"
      width="450px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="false"
    >
      <el-form label-width="100px">
        <el-form-item label="已选模块">
          <el-input :model-value="moduleDisplay" disabled />
        </el-form-item>
        <el-form-item label="机械臂" required>
          <el-select
            v-model="initConfig.unitRowId"
            placeholder="请选择机械臂"
            style="width: 100%"
          >
            <el-option
              v-for="item in armIdList"
              :key="item.id"
              :label="formatUnitOption(item)"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="图纸" required>
          <el-select
            v-model="initConfig.drawingId"
            placeholder="请选择图纸"
            style="width: 100%"
          >
            <el-option
              v-for="item in drawingList"
              :key="item.drawingId"
              :label="item.drawingName"
              :value="item.drawingId"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" @click="confirmInitConfig">确定并关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import {
  getDrawingListApi,
  getUnitsByDeviceApi,
  sendCoordination,
  sendFineTuning,
  saveFineTuningConfig,
} from "@/api/rosApi";

const router = useRouter();

// 页面进入后强制先完成目标图纸下发配置
const initDialogVisible = ref(true);
const initConfig = reactive({
  deviceId: 0,
  unitId: 0,
  unitRowId: 0,
  drawingId: 0,
});

var loading = ref(false);
let feedbackSocket: WebSocket | null = null;
const armIdList = ref<any[]>([]);
const drawingList = ref<any[]>([]);
const route = useRoute();
const moduleId = ref<number>(0);
const moduleDisplay = ref("");
const armList = reactive({
  id: 0,
  device: [
    { deviceId: 0, initial: 0.0, adjust: 0.0, current: 0.0, label: "底座旋转调整值" },
    { deviceId: 0, initial: 0.0, adjust: 0.0, current: 0.0, label: "摆动调整值" },
    { deviceId: 0, initial: 0.0, adjust: 0.0, current: 0.0, label: "伸缩杆调整值" },
    { deviceId: 0, initial: 0.0, current: 0.0 },
  ],
});

const formatUnitOption = (item: any) => {
  const desc = item.UnitDescript ? ` - ${item.UnitDescript}` : "";
  return `机械臂 ${item.Unit_ID}${desc}`;
};

const adjustmentKeys = ["rotation", "swing", "telescopic"];
const feedbackDeviceIndex: Record<number, number> = {
  33: 0,
  34: 1,
  35: 2,
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

  const position = Number(feedback.position);
  if (!Number.isFinite(position)) {
    return;
  }

  if (feedback.data_type === "axis_encoder") {
    const index = feedbackDeviceIndex[Number(feedback.device_id)];
    if (index !== undefined) {
      armList.device[index].current = position;
      loading.value = true;
    }
    return;
  }

  if (feedback.data_type === "pressure_sensor") {
    armList.device[3].current = position;
    loading.value = true;
  }
};

const connectFeedbackSocket = () => {
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

const confirmInitConfig = async () => {
  const selectedUnit = armIdList.value.find(
    (item: any) => Number(item.id) === Number(initConfig.unitRowId)
  );

  if (!selectedUnit) {
    ElMessage.warning("必须选择一个机械臂才能继续");
    return;
  }

  if (!initConfig.drawingId) {
    ElMessage.warning("必须选择一张图纸才能继续");
    return;
  }

  initConfig.unitId = Number(selectedUnit.Unit_ID);

  const payload = {
    device_id: Number(initConfig.deviceId),
    module_id: Number(moduleId.value),
    unit_id: Number(selectedUnit.Unit_ID),
    unit_row_id: Number(selectedUnit.id),
    drawing_id: Number(initConfig.drawingId),
  };

  console.log("目标图纸下发提交数据：", payload);

  try {
    const res: any = await sendCoordination(payload);

    console.log("目标图纸下发返回：", res);

    if (res && res.code === 200) {
      ElMessage.success("目标图纸下发成功");
      initDialogVisible.value = false;
      armList.id = initConfig.unitId;
      loading.value = true;
    } else {
      ElMessage.error(res?.message || res?.msg || "目标图纸下发失败");
    }
  } catch (err: any) {
    console.error("目标图纸下发失败：", err.response?.data || err);
    ElMessage.error(
      err.response?.data?.detail ||
        err.response?.data?.message ||
        "目标图纸下发失败，请检查后端服务"
    );
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
      device_id: Number(initConfig.deviceId),
      unit_id: Number(initConfig.unitId),
      unit_row_id: Number(initConfig.unitRowId),
      parameter_name: parameterName,
      position: adjustValue,
    });

    console.log("微调返回：", res);

    if (res && res.code === 200) {
      ElMessage.success(`机械臂 ${armList.id} 微调成功`);

      if (Array.isArray(res.data)) {
        for (const i of res.data) {
          if (i.parameter_name === parameterName || Number(i.device_id) === Number(initConfig.deviceId)) {
            armList.device[value].current = Number(i.position);
          } else {
            armList.device[3].current = Number(i.position);
            loading.value = true;
          }
        }
      }

      else if (res.data && res.data.position !== undefined) {
        armList.device[value].current = Number(res.data.position);
      }

      else {
        armList.device[value].current = adjustValue;
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
      unit_row_id: Number(initConfig.unitRowId),
      drawing_id: Number(initConfig.drawingId),
      devices: armList.device.map((item: any, index: number) => ({
        device_id: Number(initConfig.deviceId),
        unit_id: Number(initConfig.unitId),
        unit_row_id: Number(initConfig.unitRowId),
        parameter_name: index === 3 ? "pressure" : adjustmentKeys[index],
        label: item.label || "压力传感器",
        initial: Number(item.initial || 0),
        adjust: Number(item.adjust || 0),
        current: Number(item.current || 0),
      })),
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

    armIdList.value = units.filter((item: any) => Number.isFinite(Number(item.id)));
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
    initConfig.drawingId = Number(drawingList.value[0].drawingId);
    armList.id = initConfig.unitId;
    connectFeedbackSocket();
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
  padding: 30px;
  background-color: #fff;
  border-radius: 10px;
  height: calc(100vh - 150px);
  overflow: auto;
}

.header-card {
  margin-bottom: 16px;
}

.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.back-button {
  font-size: 14px;
}

.page-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.header-right {
  display: flex;
  justify-content: end;
  gap: 10px;
}

/* ========== 卡片样式 ========== */
.arm-list {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}

.main-control-card {
  width: 750px;
  border-radius: 12px;
  border: none;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.05) !important;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-text {
  font-weight: bold;
  font-size: 16px;
  color: #303133;
}

.control-grid {
  display: flex;
  flex-direction: column;
  gap: 30px;
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

/* 压力传感器面板 */
.sensor-panel {
  margin-top: 40px;
  background: #2b3243;
  border-radius: 8px;
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





