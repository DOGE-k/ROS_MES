<template>
  <div class="module-management">
    <div class="outer-table">
      <div class="title">模块管理与姿态调度</div>
      <div class="action-bar-restored">
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
          <el-button type="primary" class="lock-btn" @click="handleLockAndJump"
            >锁定并下发</el-button
          >
        </div>
        <div class="hint-text">
          系统锁定目标: X(十进制
          <span class="highlight">{{ selectedCell.x }}</span
          >) - Y(十进制 <span class="highlight">{{ selectedCell.y }}</span
          >)
        </div>
      </div>

      <!-- 8x8 模块矩阵 -->
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
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { ElMessage } from "element-plus";
import request from "@/utils/request";
import { useRouter } from "vue-router";
import { isNumber } from "element-plus/es/utils/types.mjs";

const router = useRouter();

// 矩阵数据 (8x8)
const matrixSize = 8;
const matrix = ref<any[]>([]);
const selectedCell = ref({ x: 1, y: 1 });

// 初始化矩阵
for (let y = 1; y <= matrixSize; y++) {
  const row = [];
  for (let x = 1; x <= matrixSize; x++) {
    row.push({ x, y });
  }
  matrix.value.push(row);
}

const xyToModuleId = (x: number, y: number): any => {
  const xBin = Number(x);
  const yBin = Number(y);
  if (xBin && yBin && xBin >= 1 && xBin <= 8 && yBin >= 1 && yBin <= 8) {
    return xBin * 16 + yBin;
  }
  return undefined;
};

const currentModuleId = computed(() =>
  xyToModuleId(inputX.value, inputY.value)
);

// ========== 替换刚才的 computed，使用更稳定的输入监听逻辑 ==========
// 1. 定义独立的输入框绑定值，不会再随便弹回去了
const inputX = ref(1);
const inputY = ref(1);

// 2. 监听下方矩阵点击：一旦格子变化，更新上方输入框
watch(
  selectedCell,
  (newVal) => {
    inputX.value = newVal.x;
    inputY.value = newVal.y;
  },
  { deep: true, immediate: true }
);

// 3. 监听 X 输入框的事件
const handleXChange = (val: number) => {
  console.log("X 输入事件触发，当前值:", val);
  selectedCell.value = { x: val, y: selectedCell.value.y };
  if (val < 1 || val > 8) {
    ElMessage.warning("请输入范围[1-8]内的值");
  }
};

// 4. 监听 Y 输入框的事件
const handleYChange = (val: number) => {
  selectedCell.value = { x: val, y: selectedCell.value.y };
  if (val < 1 || val > 8) {
    ElMessage.warning("请输入范围[1-8]内的值");
  }
};

// 点击矩阵格子（【修复】赋值为一个新对象，防止后续操作污染矩阵原数据）
const handleCellClick = (cell: any) => {
  selectedCell.value = { x: cell.x, y: cell.y };
};
// ========== 锁定并下发：跳转到微调页面 ==========
const handleLockAndJump = () => {
  const module_id = currentModuleId.value;
  if (module_id === undefined || module_id === null) {
    ElMessage.warning("未能获取到有效的模块编号");
    return;
  }
  request
    .post("/module", {
      params: {
        module_id,
        device_id: 0,
        position: 0
      },
    })
    .then((res: any) => {
      console.log(res)
      if (res && res.code === 200) {
        ElMessage.success(`模块 ${module_id} 已锁定，正在跳转微调页面...`);
        // 携带计算好的 module_id 跳转到微调页面
        router.push({ name: 'FineTuningPage' ,
          query: {
            module_id
          },
        })
      } else {
        ElMessage.error(res?.msg || "模块锁定失败，请重试");
      }
    })
    .catch((res: any) => {
      console.error("模块锁定异常:", res);
      ElMessage.error(res?.message || "请求失败，请检查后端服务");
      return;
    });
};
</script>

<style scoped>
.module-management {
  padding: 20px;
  background-color: #ffffff;
  border-radius: 10px;
  height: calc(100vh - 150px);
  overflow: auto;
}
.title {
  font-size: 20px;
  font-weight: bold;
  color: #333;
  margin-bottom: 10px;
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
  color: #409eff;
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
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 10px;
  background-color: #ffffff;
  display: inline-block;
}
.matrix-row {
  display: flex;
  gap: 5px;
  margin-bottom: 5px;
}
.matrix-cell {
  width: 70px;
  height: 50px;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  cursor: pointer;
  background-color: #f5f7fa;
  transition: all 0.2s ease;
}
.matrix-cell:hover {
  background-color: #ecf5ff;
  transform: translateY(-2px);
}
.matrix-cell.selected {
  background-color: #409eff;
  color: #fff;
  font-weight: bold;
}

/* 新增的还原截图样式 */
/* 新增的还原截图样式 (精修版) */
.action-bar-restored {
  background-color: #ffffff;
  padding: 16px 24px;
  border-radius: 8px;
  margin-bottom: 24px;
  border-left: 4px solid #409eff;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.05); /* 增加轻微阴影，更有质感 */
  display: flex;
  flex-direction: column;
  align-items: center; /* 内部元素居中 */
  gap: 12px;
  width: fit-content; /* 拒绝拉伸，宽度由内容撑开 */
  margin-left: auto;
  margin-right: auto; /* 整个面板整体居中 */
}

.input-row {
  display: flex;
  align-items: center;
  gap: 16px;
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
  color: #409eff;
  font-weight: bold;
  font-size: 14px;
}
</style>