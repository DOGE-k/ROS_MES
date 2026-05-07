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
import type { FormInstance, FormRules } from "element-plus";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  getHardwareList,
  createHardware,
  deleteHardware,
} from "@/api/rosApi";

// ---------- 前端页面使用的类型 ----------
interface Hardware {
  deviceId: string;
  deviceName: string;
  type: number;
  spec: string;
  status: number; // 1 正常，0 故障
  updateTime: string;
  createTime: string;
}

// ---------- 后端返回的数据类型 ----------
interface ApiHardware {
  id?: number | string;
  device_id?: number | string;
  hardware_id?: number | string;
  name?: string;
  hardware_name?: string;
  type?: string | number | null;
  hardware_type?: string | number | null;
  status?: string | number | null;
  description?: string | null;
  specification?: string | null;
  updated_at?: string | null;
  last_used_time?: string | null;
  create_time?: string | null;
}

// 表格数据
const hardwares = ref<Hardware[]>([]);

// 搜索表单
const searchForm = reactive({
  deviceId: "",
  deviceName: "",
  type: null as number | null,
  spec: "",
});

const typeMap: Record<number, string> = {
  1: "机械臂",
  2: "压力传感器",
  3: "陀螺仪",
};

const typeNameToValue = (type?: string | null): number => {
  if (type === "机械臂" || type === "1" || type === "robot") return 1;
  if (type === "压力传感器" || type === "2" || type === "pressure_sensor") return 2;
  if (type === "陀螺仪" || type === "3" || type === "gyroscope") return 3;
  return 1;
};

const statusToValue = (status?: string | null): number => {
  if (status === "normal" || status === "running" || status === "online" || status === "idle") {
    return 1;
  }

  if (status === "fault" || status === "error" || status === "offline") {
    return 0;
  }

  return 1;
};

const statusValueToBackend = (status: number): string => {
  return status === 1 ? "normal" : "fault";
};

// 新增弹窗相关
const addDialogVisible = ref(false);
const addFormRef = ref<FormInstance>();

const getEmptyAddForm = (): Hardware => ({
  deviceId: "",
  deviceName: "",
  type: 1,
  spec: "",
  status: 1,
  updateTime: "",
  createTime: "",
});

const addForm = reactive<Hardware>(getEmptyAddForm());

const resetAddForm = () => {
  Object.assign(addForm, getEmptyAddForm());
  addFormRef.value?.clearValidate();
};

// 新增表单校验规则
const addFormRules: FormRules = {
  deviceId: [
    { required: true, message: "请输入硬件编号", trigger: "blur" },
    {
      validator: (_rule, value, callback) => {
        const exists = hardwares.value.some(
          (item) => item.deviceId === String(value)
        );

        if (exists) {
          callback(new Error("硬件编号已存在"));
        } else {
          callback();
        }
      },
      trigger: "blur",
    },
  ],
  deviceName: [
    { required: true, message: "请输入硬件名称", trigger: "blur" },
  ],
  type: [
    { required: true, message: "请选择硬件类型", trigger: "change" },
  ],
};


const normalizeHardware = (item: ApiHardware): Hardware => {
  return {
    deviceId: String(item.device_id ?? item.hardware_id ?? item.id ?? ""),
    deviceName: String(item.hardware_name ?? item.name ?? ""),
    type: typeNameToValue(item.hardware_type ?? item.type),
    spec: String(item.specification ?? item.description ?? ""),
    status: statusToValue(item.status),
    updateTime: String(item.updated_at ?? item.last_used_time ?? ""),
    createTime: String(item.create_time ?? item.updated_at ?? ""),
  };
};

// 全量查询
const loadFromApi = async () => {
  try {
    const res: any = await getHardwareList();

    const list: ApiHardware[] = Array.isArray(res)
      ? res
      : Array.isArray(res.data)
        ? res.data
        : [];

    const tableList = list.map(normalizeHardware);

    hardwares.value = tableList;

    console.log("获取硬件列表成功，数据：", hardwares.value);

    return tableList;
  } catch (err: any) {
    console.error("获取硬件列表失败：", err.response?.data || err);
    ElMessage.error("获取硬件列表失败");
    return [];
  }
};

// 本地搜索：你的后端目前没有 /hardware/select，所以这里先在前端过滤
const handleSearch = async () => {
  const list = await loadFromApi();

  hardwares.value = list.filter((item) => {
    const matchDeviceId =
      !searchForm.deviceId ||
      item.deviceId.includes(String(searchForm.deviceId));

    const matchDeviceName =
      !searchForm.deviceName ||
      item.deviceName.includes(searchForm.deviceName);

    const matchType =
      searchForm.type === null || item.type === searchForm.type;

    const matchSpec =
      !searchForm.spec || item.spec.includes(searchForm.spec);

    return matchDeviceId && matchDeviceName && matchType && matchSpec;
  });
};

// 打开新增弹窗
const openAddDialog = () => {
  resetAddForm();
  addDialogVisible.value = true;
};

// 新增硬件
const addToApi = async (data: Hardware) => {
  const deviceId = Number(data.deviceId);

  if (Number.isNaN(deviceId)) {
    ElMessage.error("硬件编号必须是数字");
    return;
  }

  const payload = {
    device_id: deviceId,
    hardware_id: deviceId,
    name: data.deviceName.trim(),
    hardware_name: data.deviceName.trim(),
    type: typeMap[data.type] || String(data.type),
    hardware_type: typeMap[data.type] || String(data.type),
    status: statusValueToBackend(data.status),
    ip_address: "",
    description: data.spec || "",
    specification: data.spec || "",
  };

  console.log("新增硬件提交数据：", payload);

  try {
    const res: any = await createHardware(payload);

    console.log("新增硬件成功：", res);

    if (res && res.code === 200) {
      ElMessage.success("添加成功");
      addDialogVisible.value = false;
      await loadFromApi();
    } else {
      ElMessage.error(res?.message || res?.msg || "添加失败");
    }
  } catch (err: any) {
    console.error("添加硬件失败：", err.response?.data || err);
    ElMessage.error("添加失败");
  }
};

const submitAdd = async () => {
  try {
    await addFormRef.value?.validate();

    if (!addForm.deviceName.trim()) {
      ElMessage.error("请输入硬件名称");
      return;
    }

    addToApi({ ...addForm });
  } catch {
    ElMessage.error("请完善表单信息");
  }
};

// 删除硬件
const deleteFromApi = async (deviceId: string) => {
  try {
    const res: any = await deleteHardware(deviceId);

    console.log("删除硬件返回：", res);

    ElMessage.success("删除成功");
    await loadFromApi();
  } catch (err: any) {
    console.error("删除硬件失败：", err.response?.data || err);
    ElMessage.error("删除失败");
  }
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