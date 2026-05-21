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
    module_id: 18,
    device_id: 1,
    position: 18,
  });

  showResult(res);
  ElMessage.success(res.message || "模块创建成功");
};

const handleCoordination = async () => {
  const res = await sendCoordination({
    module_id: 18,
    device_id: 1,
    x: 100,
    y: 200,
    z: 50,
  });

  showResult(res);
  ElMessage.success(res.message || "坐标下发成功");
};

const handleFineTuning = async (position: string) => {
  const res = await sendFineTuning({
    module_id: 18,
    device_id: 1,
    position,
  });

  showResult(res);
  ElMessage.success(res.message || "微调成功");
};
</script>

<template>
  <div class="ros-test-page">
    <el-card class="header-card">
      <h2 class="page-title">ROS API 前端 Mock 测试</h2>
    </el-card>
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
        <el-button @click="handleCreateModule">
          模拟创建模块
        </el-button>

        <el-button @click="handleCoordination">
          模拟下发坐标
        </el-button>

        <el-button @click="handleFineTuning('x+')">
          X+
        </el-button>

        <el-button @click="handleFineTuning('x-')">
          X-
        </el-button>

        <el-button @click="handleFineTuning('y+')">
          Y+
        </el-button>

        <el-button @click="handleFineTuning('y-')">
          Y-
        </el-button>
      </div>

      <pre class="result">{{ result }}</pre>
    </el-card>
  </div>
</template>

<style scoped>
.ros-test-page {
  padding: 20px;
}

.header-card {
  margin-bottom: 16px;
}

.page-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

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