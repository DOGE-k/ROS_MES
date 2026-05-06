<template>
  <div class="fine-tuning-container">
    <!-- 顶部静态文字和按钮 -->
    <div class="header-bar">
      <div class="header-left">
        <el-button type="default" @click="goBack" class="back-button">
          &lt; Back
        </el-button>
        <span class="header-title">机械臂姿态微调与压力监控</span>
      </div>
    </div>
    <div class="arm-list">
      <el-card shadow="hover" class="main-control-card">
        <template #header>
          <div class="card-header">
            <span class="header-text"
              >核心机械臂控制单元 - 设备 {{ armList.id }}</span
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
                  >{{ armList.device[0].label }}(°)</span
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
                  >{{ armList.device[1].label }}(°)</span
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
      title="目标坐标下发"
      width="450px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="false"
    >
      <el-form label-width="100px">
        <el-form-item label="设备编号" required>
          <el-select
            v-model="initConfig.deviceId"
            placeholder="请选择机械臂"
            style="width: 100%"
          >
            <el-option
              v-for="item in armIdList"
              :key="item"
              :label="item"
              :value="item"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="X 坐标" required>
          <el-input-number
            v-model="initConfig.x"
            :step="10"
            controls-position="right"
            style="width: 100%"
            :disabled="coordinateDisable"
          />
        </el-form-item>
        <el-form-item label="Y 坐标" required>
          <el-input-number
            v-model="initConfig.y"
            :step="10"
            controls-position="right"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="Z 坐标" required>
          <el-input-number
            v-model="initConfig.z"
            :step="10"
            controls-position="right"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" @click="confirmInitConfig"
          >确定并关闭</el-button
        >
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import request from "@/utils/request";
 

const router = useRouter();
const coordinateDisable = ref(false)

// ========== 新增：初始化强制弹窗逻辑 ==========
const initDialogVisible = ref(true); // 默认 true，页面一进来就弹
const initConfig = reactive({
  deviceId: 0, // 可选设备编号列表
  x: 0,
  y: 0,
  z: 0,
});

var loading = ref(false);
const armIdList = ref<number[]>([]); // 从后端获取的机械臂编号列表
// ========== 1. 路由参数获取 ==========
const route = useRoute();
const moduleId = ref<number>(0); // 当前操作的模块编号
const armList = reactive({
  id: 0,
  device: [
    { deviceId: 0, initial: 0.0, adjust: 0.0, current: 0.0, label: "底座旋转调整值" },
    { deviceId: 0, initial: 0.0, adjust: 0.0, current: 0.0, label: "摆动调整值" },
    { deviceId: 0, initial: 0.0, adjust: 0.0, current: 0.0, label: "伸缩杆调整值" },
    { deviceId: 0, initial: 0.0, current: 0.0 },
  ],
});

const confirmInitConfig = () => {
  if (!initConfig.deviceId) {
    ElMessage.warning("必须选择一个设备编号才能继续");
    return;
  }

  coordinateDisable.value = true;

  const payload = {
    device_id: Number(initConfig.deviceId),
    module_id: Number(moduleId.value),
    x: Number(initConfig.x),
    y: Number(initConfig.y),
    z: Number(initConfig.z),
  };

  console.log("坐标下发提交数据：", payload);

  request
    .post("/coordination/", payload)
    .then((res: any) => {
      console.log("坐标下发返回：", res);

      if (res && res.code === 200) {
        ElMessage.success("初始参数下发成功！");
        initDialogVisible.value = false;
        armList.id = initConfig.deviceId;

        loading.value = true;
        coordinateDisable.value = false;
      } else {
        ElMessage.error(res?.message || res?.msg || "初始参数下发失败");
        coordinateDisable.value = false;
      }
    })
    .catch((err: any) => {
      console.error("坐标下发失败：", err.response?.data || err);
      ElMessage.error(
        err.response?.data?.detail ||
          err.response?.data?.message ||
          "坐标下发失败"
      );
      coordinateDisable.value = false;
    });
};

// ========== 3. 单个机械臂微调（核心接口） ==========
const sendSingleAdjust = async (value: number) => {
  console.log("ddddd", armList.device[value].adjust);
  loading.value = false;

  const adjustid = Number(initConfig.deviceId) + value + 1;

  try {
    const res: any = await request.post("/finetuning/", {
      module_id: moduleId.value,
      device_id: adjustid,
      position: armList.device[value].adjust,
    });

    if (res && res.code === 200) {
      ElMessage.success(`机械臂 ${armList.id} 微调成功`);

      if (Array.isArray(res.data)) {
        for (const i of res.data) {
          if (i.device_id == adjustid) {
            armList.device[value].current = i.position;
          } else {
            armList.device[3].current = i.position;
            loading.value = true;
          }
        }
      }

      armList.device[value].adjust = Number(armList.device[value].current || 0);
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
  if (!initConfig.deviceId) {
    ElMessage.warning("请先选择设备并完成初始坐标下发");
    return;
  }

  try {
    const payload = {
      module_id: Number(moduleId.value),
      device_id: Number(initConfig.deviceId),
      x: Number(initConfig.x),
      y: Number(initConfig.y),
      z: Number(initConfig.z),
      devices: armList.device.map((item: any, index: number) => ({
        device_id: index === 3 ? -1 : Number(initConfig.deviceId) + index + 1,
        label: item.label || "压力传感器",
        initial: Number(item.initial || 0),
        adjust: Number(item.adjust || 0),
        current: Number(item.current || 0),
      })),
    };

    const res: any = await request.post("/finetuning/config", payload);
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
onMounted(() => {
  const qModuleId = route.query.module_id;

  if (qModuleId) {
    moduleId.value = parseInt(qModuleId as string);
  } else {
    ElMessage.warning("未获取到模块编号，请从模块管理页面进入");
    router.push("/moduleManagement");
    return;
  }

  request
  .get("/hardware/")
  .then((res: any) => {
    const list = Array.isArray(res) ? res : res.data || [];

    if (list.length === 0) {
      ElMessage.warning("未获取到设备编号列表，请先添加机械臂信息");
      router.push("/HardWorkPage");
      return;
    }

    armIdList.value = list.map((item: any) => Number(item.id));
    initConfig.deviceId = armIdList.value[0];
  })
  .catch((err: any) => {
    console.error("请求设备编号列表失败：", err.response?.data || err);
    ElMessage.error("请求设备编号列表失败");
  });
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

.header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 10px;
  border-bottom: 1px solid #e4e7ed;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.back-button {
  font-size: 14px;
}

.header-title {
  font-size: 18px;
  font-weight: bold;
  color: #333;
}

.header-right {
  display: flex;
  justify-content: end;
  gap: 10px;
}

/* ========== 卡片美化样式 ========== */
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

/* 压力传感器黑盒样式 */
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
