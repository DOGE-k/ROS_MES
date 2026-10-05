<script setup lang="ts">
import { ref } from "vue";
import { ElMessage } from "element-plus";
import {
  sendRosMessage,
  getRosStatus,
  createModule,
  sendCoordination,
  sendFineTuning,
} from "@/api/rosApi";

const msg = ref("前进");
const result = ref("");

// 测试用 ID 改为输入框可调（默认值为 V2 有效编码：模块18=(1,2)，device_id 1=一号臂旋转轴）
const testModuleId = ref(18);
const testDeviceId = ref(1);
const testUnitId = ref(32);
const testUnitRowId = ref(1);
const testDrawingId = ref(1);
const testParameter = ref<"rotation" | "swing" | "telescopic">("rotation");
const testPosition = ref(5);

const showResult = (data: any) => {
  result.value = JSON.stringify(data, null, 2);
};

const handleSend = async () => {
  const res = await sendRosMessage(msg.value);
  showResult(res);
  ElMessage.success(res.message || "发送成功");
};

const handleGetStatus = async () => {
  const res = await getRosStatus();
  showResult(res);
  ElMessage.success("获取状态成功");
};

const handleCreateModule = async () => {
  const res = await createModule({
    x: 1,
    y: 2,
    module_id: Number(testModuleId.value),
    device_id: Number(testDeviceId.value),
    position: 0,
  });

  showResult(res);
  ElMessage.success(res.message || "模块创建成功");
};

const handleCoordination = async () => {
  // 后端 /coordination/send 五元组必填
  const res = await sendCoordination({
    device_id: Number(testDeviceId.value),
    module_id: Number(testModuleId.value),
    unit_id: Number(testUnitId.value),
    unit_row_id: Number(testUnitRowId.value),
    drawing_id: Number(testDrawingId.value),
  });

  showResult(res);
  ElMessage.success(res.message || "坐标下发成功");
};

const handleFineTuning = async () => {
  // 后端 /control/finetuning：parameter_name 必填且 device_id ∈ 1~20
  const res = await sendFineTuning({
    module_id: Number(testModuleId.value),
    device_id: Number(testDeviceId.value),
    unit_id: Number(testUnitId.value),
    parameter_name: testParameter.value,
    position: Number(testPosition.value),
  });

  showResult(res);
  ElMessage.success(res.message || "微调成功");
};
</script>

<template>
  <div class="ros-test-page mes-page">
    <div class="mes-page-header">
      <div>
        <h2 class="mes-page-title">ROS API 前端 Mock 测试</h2>
        <p class="mes-page-sub">开发调试专用：模拟 ROS 消息下发与状态查询</p>
      </div>
    </div>
    <el-card>

      <div class="row">
        <span>消息：</span>
        <el-input v-model="msg" style="width: 260px" />

        <el-button type="primary" @click="handleSend">
          模拟发送 ROS 消息
        </el-button>

        <el-button type="success" @click="handleGetStatus">
          模拟获取 ROS 状态
        </el-button>
      </div>

      <div class="row">
        <span>module_id：</span>
        <el-input-number v-model="testModuleId" :min="17" :max="136" />
        <span>device_id：</span>
        <el-input-number v-model="testDeviceId" :min="1" :max="25" />
        <span>unit_id：</span>
        <el-input-number v-model="testUnitId" :min="32" :max="160" :step="32" />
        <span>unit_row_id：</span>
        <el-input-number v-model="testUnitRowId" :min="1" />
        <span>drawing_id：</span>
        <el-input-number v-model="testDrawingId" :min="1" />
      </div>

      <div class="row">
        <el-button @click="handleCreateModule">
          模拟创建模块
        </el-button>

        <el-button @click="handleCoordination">
          模拟下发坐标
        </el-button>
      </div>

      <div class="row">
        <span>parameter_name：</span>
        <el-select v-model="testParameter" style="width: 140px">
          <el-option label="rotation" value="rotation" />
          <el-option label="swing" value="swing" />
          <el-option label="telescopic" value="telescopic" />
        </el-select>
        <span>position：</span>
        <el-input-number v-model="testPosition" :min="-360" :max="360" />
        <el-button type="primary" @click="handleFineTuning">
          模拟微调下发
        </el-button>
      </div>

      <pre class="result">{{ result }}</pre>
    </el-card>
  </div>
</template>

<style scoped>
.row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.result {
  min-height: 220px;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 8px;
  white-space: pre-wrap;
}
</style>