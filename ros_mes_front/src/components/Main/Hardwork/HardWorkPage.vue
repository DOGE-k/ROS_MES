<template>
  <div class="container">
    <!-- 搜索表单 -->
    <el-form :model="searchForm" label-width="80px" style="max-width: 600px">
      <el-form-item label="硬件编号">
        <el-input
          v-model="searchForm.deviceId"
          placeholder="请输入硬件编号"
          clearable
        />
      </el-form-item>
      <el-form-item label="硬件名称">
        <el-input
          v-model="searchForm.deviceName"
          placeholder="请输入硬件名称"
          clearable
        />
      </el-form-item>
      <el-form-item label="硬件类型">
        <el-select v-model="searchForm.type" placeholder="请选择类型" clearable>
          <el-option label="机械臂" :value="1" />
          <el-option label="压力传感器" :value="2" />
          <el-option label="陀螺仪" :value="3" />
        </el-select>
      </el-form-item>
      <el-form-item label="规格">
        <el-input
          v-model="searchForm.spec"
          placeholder="请输入规格"
          clearable
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">搜索</el-button>
        <el-button type="success" @click="openAddDialog">+ 新增硬件</el-button>
      </el-form-item>
    </el-form>

    <!-- 硬件列表表格 -->
    <el-table :data="hardwares" border stripe style="width: 100%">
      <el-table-column prop="deviceId" label="硬件编号" width="150" align="center" />
      <el-table-column
        prop="deviceName"
        label="硬件名称"
        width="150"
        align="center"
      />
      <el-table-column prop="type" label="硬件类型" width="120" align="center">
        <template #default="{ row }">
          {{ typeMap[row.type] || "未知类型" }}
        </template>
      </el-table-column>
      <el-table-column prop="spec" label="规格" width="150" align="center" />
      <el-table-column prop="status" label="状态" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'danger'">
            {{ row.status === 1 ? "正常" : "故障" }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        prop="updateTime"
        label="最近使用时间"
        width="180"
        align="center"
      />
      <el-table-column
        prop="createTime"
        label="创建时间"
        width="180"
        align="center"
      />
      <el-table-column fixed="right" label="操作" width="120" align="center">
        <template #default="{ row }">
          <el-button link type="danger" size="small" @click="deleteRow(row)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新增硬件弹窗 -->
    <el-dialog v-model="addDialogVisible" title="新增硬件" width="500px">
      <el-form
        :model="addForm"
        :rules="addFormRules"
        ref="addFormRef"
        label-width="100px"
      >
        <el-form-item label="硬件编号" prop="deviceId">
           <el-input v-model="addForm.deviceId" placeholder="唯一标识，不可重复" />
        </el-form-item>
        <el-form-item label="硬件名称" prop="deviceName">
          <el-input v-model="addForm.deviceName" />
        </el-form-item>
        <el-form-item label="硬件类型" prop="type">
          <el-select v-model="addForm.type" placeholder="请选择类型">
            <el-option label="机械臂" :value="1" />
            <el-option label="压力传感器" :value="2" />
            <el-option label="陀螺仪" :value="3" />
          </el-select>
        </el-form-item>
        <el-form-item label="规格" prop="spec">
          <el-input v-model="addForm.spec" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-radio-group v-model="addForm.status">
            <el-radio :label="1">正常</el-radio>
            <el-radio :label="0">故障</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAdd">确认新增</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { ElMessage, ElMessageBox, FormInstance, FormRules } from "element-plus";
import request from "@/utils/request";
import { de } from "element-plus/es/locale/index.mjs";

// ---------- 类型定义 ----------
interface Hardware {
  deviceId: number;
  deviceName: string;
  type: number; // 1=机械臂, 2=压力传感器，3=陀螺仪
  spec: string;
  status: number; // 1=正常, 0=故障
  updateTime: string;
  createTime: string;
}

// 表格数据
const hardwares = ref<Hardware[]>([]);

// 搜索表单
const searchForm = reactive({
  deviceId: 0,
  deviceName: "",
  type: null as number | null,
  spec: "",
});

const typeMap = {
  1: "机械臂",
  2: "压力传感器",
  3: "陀螺仪", // 新增的第3个值
};

// 新增弹窗相关
const addDialogVisible = ref(false);
const addFormRef = ref<FormInstance>();
const addForm = reactive<Hardware>({
  deviceId: 0,
  deviceName: "",
  type: 1,
  spec: "",
  status: 1,
  updateTime: "",
  createTime: "",
});

// 新增表单校验规则（包含 deviceId 唯一性校验）
const addFormRules: FormRules = {
  deviceId: [
    { required: true, message: "请输入硬件编号", trigger: "blur" },
    {
      validator: (rule, value, callback) => {
        const exists = hardwares.value.some((item) => item.deviceId === value);
        if (exists) {
          callback(new Error("硬件编号已存在"));
        } else {
          callback();
        }
      },
      trigger: "blur",
    },
  ],
  deviceName: [{ required: true, message: "请输入硬件名称", trigger: "blur" }],
  type: [{ required: true, message: "请选择硬件类型", trigger: "change" }],
  spec: [{ required: false, message: "请输入规格", trigger: "blur" }],
};

// 全量查询
const loadFromApi = () => {
  request
    .get("/hardware")
    .then((res: any) => {
      console.log("获取硬件列表成功，数据：", res.data);
      hardwares.value = res.data;
    })
    .catch((err: any) => {
      ElMessage.error("获取硬件列表失败");
    });
};

// 模糊搜索
const searchFromApi = () => {
  request
    .get("/hardware/select", {
      params: {
        deviceId: searchForm.deviceId || undefined,
        deviceName: searchForm.deviceName || undefined,
        type: searchForm.type ?? undefined,
        spec: searchForm.spec || undefined,
      },
    })
    .then((res: any) => {
      hardwares.value = res.data;
    })
    .catch((err: any) => {
      ElMessage.error("搜索失败");
    });
};

// 新增硬件
const addToApi = (data: Hardware) => {
  request
    .post("/hardware", data)
    .then(() => {
      ElMessage.success("添加成功");
      addDialogVisible.value = false;
      loadFromApi(); // 刷新列表
    })
    .catch((err: any) => {
      console.log(err)
      if (err.response?.status === 400) {
        ElMessage.error("硬件编号已存在");
      } else {
        ElMessage.error("添加失败");
      }
    });
};

// 删除硬件
const deleteFromApi = (deviceId: number) => {
  request
    .delete("/hardware", { params: { deviceId } })
    .then(() => {
      ElMessage.success("删除成功");
      loadFromApi();
    })
    .catch((err: any) => {
      ElMessage.error("删除失败");
    });
};

const handleSearch = () => {
  searchFromApi();
};

const openAddDialog = () => {
  addDialogVisible.value = true;
};

const submitAdd = async () => {
  await addFormRef.value?.validate();
  const now = new Date();
  const newHardware: Hardware = {
    ...addForm
  };
  addToApi(newHardware);
  addDialogVisible.value = false;
};

const deleteRow = async (row: Hardware) => {
  ElMessageBox.confirm("确定删除该硬件吗？", "提示", { type: "warning" })
    .then(() => {
      deleteFromApi(row.deviceId);
    })
    .catch(() => {});
};

onMounted(() => {
  loadFromApi();
});
</script>

<style scoped>
.container {
  background-color: #ffffff;
  padding: 20px;
  border-radius: 10px;
  height: calc(100vh - 150px);
  display: flex;
  flex-direction: column;
  overflow: auto;
}
.container > :last-child {
  flex: 1;
}

/* 强制修正表格对齐问题 */
:deep(.el-table th.el-table__cell) {
  text-align: center !important;
}

:deep(.el-table td.el-table__cell) {
  text-align: center !important;
}

/* 修复表头和内容边框对不齐的对齐补丁 */
:deep(.el-table__header),
:deep(.el-table__body),
:deep(.el-table__footer) {
  width: 100% !important;
  table-layout: fixed !important;
}

/* 移除可能存在的默认内边距干扰 */
:deep(.el-table .cell) {
  padding: 0 !important;
  display: flex;
  justify-content: center;
  align-items: center;
}
</style>