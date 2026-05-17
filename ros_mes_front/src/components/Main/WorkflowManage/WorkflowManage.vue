<template>
  <div class="workflow-manage">
    <el-card class="header-card">
      <h2 class="page-title">工作流管理</h2>
    </el-card>

    <el-card class="tab-card">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="工作管理" name="work">
          <div class="tab-header">
            <el-button type="primary" @click="openCreateWorkDialog">新增工作</el-button>
          </div>
          <el-table :data="workList" border stripe v-loading="workLoading" style="margin-top: 16px">
            <el-table-column type="index" label="序号" width="60" />
            <el-table-column prop="Workname" label="工作名称" min-width="140" show-overflow-tooltip />
            <el-table-column label="绑定图纸" min-width="150" show-overflow-tooltip>
              <template #default="{ row }">{{ getDrawingLabel(row.Drawing_ID) }}</template>
            </el-table-column>
            <el-table-column label="绑定型号" min-width="140" show-overflow-tooltip>
              <template #default="{ row }">{{ getModelLabelByDevice(row.Device_id) }}</template>
            </el-table-column>
            <el-table-column label="绑定设备" min-width="150" show-overflow-tooltip>
              <template #default="{ row }">{{ getDeviceLabel(row.Device_id) }}</template>
            </el-table-column>
            <el-table-column label="绑定单元" min-width="150" show-overflow-tooltip>
              <template #default="{ row }">{{ getUnitLabel(row.unit_id) }}</template>
            </el-table-column>
            <el-table-column label="绑定传感器" min-width="150" show-overflow-tooltip>
              <template #default="{ row }">{{ getSensorLabel(row.sensor_id) }}</template>
            </el-table-column>
            <el-table-column prop="WorkDescript" label="工作描述" min-width="160" show-overflow-tooltip />
            <el-table-column prop="Createtime" label="创建时间" width="170" />
            <el-table-column label="操作" width="160" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openEditWorkDialog(row)">编辑</el-button>
                <el-popconfirm title="确定删除该工作吗？" @confirm="handleDeleteWork(row)">
                  <template #reference>
                    <el-button link type="danger">删除</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="工作流管理" name="workflow">
          <div class="tab-header">
            <el-button type="primary" @click="openCreateWorkflowDialog">新建工作流</el-button>
          </div>
          <el-table :data="workflowList" border stripe v-loading="workflowLoading" style="margin-top: 16px">
            <el-table-column type="index" label="序号" width="60" />
            <el-table-column prop="Workflowname" label="工作流名称" min-width="140" show-overflow-tooltip />
            <el-table-column prop="work_count" label="工作数量" width="100" />
            <el-table-column prop="WorkflowDescript" label="工作流描述" min-width="160" show-overflow-tooltip />
            <el-table-column prop="Createtime" label="创建时间" width="170" />
            <el-table-column label="操作" width="220" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openViewWorkflowDialog(row)">查看</el-button>
                <el-button link type="success" @click="openEditWorkflowDialog(row)">编辑</el-button>
                <el-popconfirm title="确定删除该工作流吗？" @confirm="handleDeleteWorkflow(row)">
                  <template #reference>
                    <el-button link type="danger">删除</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-dialog v-model="workDialogVisible" :title="workDialogTitle" width="640px" destroy-on-close>
      <el-form :model="workForm" label-width="120px">
        <el-form-item label="工作名称" required>
          <el-input v-model="workForm.Workname" placeholder="请输入工作名称" />
        </el-form-item>
        <el-form-item label="工作描述">
          <el-input v-model="workForm.WorkDescript" type="textarea" :rows="2" placeholder="请输入工作描述" />
        </el-form-item>
        <el-form-item label="绑定图纸" required>
          <el-select v-model="workForm.Drawing_ID" filterable clearable placeholder="请选择图纸" style="width: 100%">
            <el-option
              v-for="item in drawingOptions"
              :key="item.drawingId"
              :label="formatDrawingOption(item)"
              :value="item.drawingId"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="绑定型号" required>
          <el-select
            v-model="workForm.Model_ID"
            filterable
            clearable
            placeholder="请选择型号"
            style="width: 100%"
            @change="handleModelChange"
          >
            <el-option
              v-for="item in modelOptions"
              :key="item.Model_ID"
              :label="formatModelOption(item)"
              :value="item.Model_ID"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="绑定设备" required>
          <el-select
            v-model="workForm.Device_id"
            filterable
            clearable
            :disabled="!workForm.Model_ID"
            placeholder="请先选择型号"
            style="width: 100%"
            @change="handleDeviceChange"
          >
            <el-option
              v-for="item in deviceOptions"
              :key="item.Device_ID"
              :label="formatDeviceOption(item)"
              :value="item.Device_ID"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="绑定单元" required>
          <el-select
            v-model="workForm.unit_id"
            filterable
            clearable
            :disabled="!workForm.Device_id"
            placeholder="请先选择设备"
            style="width: 100%"
            @change="handleUnitChange"
          >
            <el-option
              v-for="item in unitOptions"
              :key="item.id"
              :label="formatUnitOption(item)"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="绑定传感器">
          <el-select
            v-model="workForm.sensor_id"
            filterable
            clearable
            :disabled="!workForm.unit_id"
            placeholder="请先选择单元"
            style="width: 100%"
          >
            <el-option
              v-for="item in sensorOptions"
              :key="item.id"
              :label="formatSensorOption(item)"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="workForm.Notes" type="textarea" :rows="3" placeholder="请输入备注信息" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="workDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveWork" :loading="workSaving">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="workflowDialogVisible" :title="workflowDialogTitle" width="700px" destroy-on-close>
      <el-form :model="workflowForm" label-width="120px">
        <el-form-item label="工作流名称" required>
          <el-input v-model="workflowForm.Workflowname" placeholder="请输入工作流名称" />
        </el-form-item>
        <el-form-item label="工作流描述">
          <el-input v-model="workflowForm.WorkflowDescript" type="textarea" :rows="2" placeholder="请输入工作流描述" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="workflowForm.Notes" type="textarea" :rows="3" placeholder="请输入备注信息" />
        </el-form-item>
        <el-form-item label="选择工作">
          <el-select
            v-model="selectedWorkIds"
            multiple
            filterable
            placeholder="请选择工作"
            style="width: 100%"
            @change="onWorkSelected"
          >
            <el-option
              v-for="w in allWorksForSelect"
              :key="w.Work_ID"
              :label="`[${w.Work_ID}] ${w.Workname}`"
              :value="w.Work_ID"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="执行顺序">
          <div class="seq-list">
            <div v-for="(item, idx) in orderedWorks" :key="item.Work_ID" class="seq-item">
              <span class="seq-index">第{{ idx + 1 }}步：</span>
              <span class="seq-name">{{ item.Workname }}</span>
              <div class="seq-actions">
                <el-button link type="primary" :disabled="idx === 0" @click="moveUp(idx)">上移</el-button>
                <el-button link type="primary" :disabled="idx === orderedWorks.length - 1" @click="moveDown(idx)">下移</el-button>
                <el-button link type="danger" @click="removeWork(idx)">移除</el-button>
              </div>
            </div>
            <el-empty v-if="orderedWorks.length === 0" description="请从上方选择工作" />
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="workflowDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveWorkflow" :loading="workflowSaving">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="detailVisible" title="工作流详情" width="760px" destroy-on-close>
      <div v-loading="detailLoading">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="工作流名称">{{ detailData.Workflowname }}</el-descriptions-item>
          <el-descriptions-item label="工作流描述">{{ detailData.WorkflowDescript || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ detailData.Createtime }}</el-descriptions-item>
          <el-descriptions-item label="备注">{{ detailData.Notes || '-' }}</el-descriptions-item>
        </el-descriptions>
        <h3 class="steps-title">包含的工作步骤</h3>
        <div v-for="(work, idx) in detailData.works" :key="work.Work_ID" class="step-card">
          <div class="step-header">第{{ idx + 1 }}步：{{ work.Workname }}</div>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="工作名称">{{ work.Workname }}</el-descriptions-item>
            <el-descriptions-item label="工作描述">{{ work.WorkDescript || '-' }}</el-descriptions-item>
            <el-descriptions-item label="图纸">{{ getDrawingLabel(work.Drawing_ID) }}</el-descriptions-item>
            <el-descriptions-item label="型号">{{ getModelLabelByDevice(work.Device_id) }}</el-descriptions-item>
            <el-descriptions-item label="设备">{{ getDeviceLabel(work.Device_id) }}</el-descriptions-item>
            <el-descriptions-item label="单元">{{ getUnitLabel(work.unit_id) }}</el-descriptions-item>
            <el-descriptions-item label="传感器">{{ getSensorLabel(work.sensor_id) }}</el-descriptions-item>
            <el-descriptions-item label="工作数据" :span="2">
              <pre class="data-pre">{{ work.data || '-' }}</pre>
            </el-descriptions-item>
            <el-descriptions-item label="备注" :span="2">{{ work.Notes || '-' }}</el-descriptions-item>
          </el-descriptions>
        </div>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import {
  createWorkApi,
  getWorkListApi,
  updateWorkApi,
  deleteWorkApi,
  createWorkflowApi,
  getWorkflowListApi,
  getWorkflowDetailApi,
  updateWorkflowApi,
  deleteWorkflowApi,
  getDrawingListApi,
  getModelListApi,
  getDevicesByModelApi,
  getDeviceListApi,
  getUnitsByDeviceApi,
  getUnitListApi,
  getSensorsByUnitApi,
  getSensorListApi,
} from '@/api/rosApi';
import type { DrawingItem, WorkItem, WorkflowItem } from '@/api/types';

type SelectId = number | null;

const activeTab = ref('work');

const workLoading = ref(false);
const workList = ref<WorkItem[]>([]);
const workDialogVisible = ref(false);
const workDialogTitle = ref('新增工作');
const workSaving = ref(false);
const editingWorkId = ref<number | null>(null);

const workForm = reactive({
  Workname: '',
  WorkDescript: '',
  Drawing_ID: null as SelectId,
  Model_ID: null as SelectId,
  Device_id: null as SelectId,
  unit_id: null as SelectId,
  sensor_id: null as SelectId,
  Notes: '',
});

const drawingOptions = ref<DrawingItem[]>([]);
const modelOptions = ref<any[]>([]);
const allDeviceOptions = ref<any[]>([]);
const allUnitOptions = ref<any[]>([]);
const allSensorOptions = ref<any[]>([]);
const deviceOptions = ref<any[]>([]);
const unitOptions = ref<any[]>([]);
const sensorOptions = ref<any[]>([]);

const workflowLoading = ref(false);
const workflowList = ref<WorkflowItem[]>([]);
const workflowDialogVisible = ref(false);
const workflowDialogTitle = ref('新建工作流');
const workflowSaving = ref(false);
const editingWorkflowId = ref<number | null>(null);
const workflowForm = reactive({
  Workflowname: '',
  WorkflowDescript: '',
  Notes: '',
});
const allWorksForSelect = ref<WorkItem[]>([]);
const selectedWorkIds = ref<number[]>([]);
const orderedWorks = ref<WorkItem[]>([]);

const detailVisible = ref(false);
const detailLoading = ref(false);
const detailData = reactive<{
  Workflowname: string;
  WorkflowDescript: string;
  Createtime: string;
  Notes: string;
  works: any[];
}>({
  Workflowname: '',
  WorkflowDescript: '',
  Createtime: '',
  Notes: '',
  works: [],
});

function unwrapList(res: any): any[] {
  if (Array.isArray(res)) return res;
  if (Array.isArray(res?.data)) return res.data;
  return [];
}

function formatDeviceAddress(address: number | string | null | undefined) {
  const value = Number(address);
  if (!Number.isFinite(value)) return '-';
  return `(${(value >> 4) & 0x0f},${value & 0x0f})`;
}

function formatDrawingOption(item: any) {
  return `[${item.drawingId}] ${item.drawingName}`;
}

function formatModelOption(item: any) {
  return `[${item.Model_ID}] ${item.Modelname}`;
}

function formatDeviceOption(item: any) {
  const desc = item.Devicedescript ? ` - ${item.Devicedescript}` : '';
  return `[${item.Device_ID}] 模块${formatDeviceAddress(item.DeviceAddress)}${desc}`;
}

function formatUnitOption(item: any) {
  const desc = item.UnitDescript ? ` - ${item.UnitDescript}` : '';
  return `[${item.id}] 机械臂 ${item.Unit_ID}${desc}`;
}

function formatSensorOption(item: any) {
  const desc = item.sensordescript ? ` - ${item.sensordescript}` : '';
  return `[${item.id}] 传感器 ${item.sensor_ID}${desc}`;
}

function getDrawingLabel(id: number | null | undefined) {
  if (id == null) return '-';
  const item = drawingOptions.value.find(d => Number(d.drawingId) === Number(id));
  return item ? formatDrawingOption(item) : String(id);
}

function getModelLabelByDevice(deviceId: number | null | undefined) {
  if (deviceId == null) return '-';
  const device = allDeviceOptions.value.find(d => Number(d.Device_ID) === Number(deviceId));
  const modelId = device?.Model_ID;
  const model = modelOptions.value.find(m => Number(m.Model_ID) === Number(modelId));
  return model ? formatModelOption(model) : '-';
}

function getDeviceLabel(id: number | null | undefined) {
  if (id == null) return '-';
  const item = allDeviceOptions.value.find(d => Number(d.Device_ID) === Number(id));
  return item ? formatDeviceOption(item) : String(id);
}

function getUnitLabel(id: number | null | undefined) {
  if (id == null) return '-';
  const item = allUnitOptions.value.find(u => Number(u.id) === Number(id));
  return item ? formatUnitOption(item) : String(id);
}

function getSensorLabel(id: number | null | undefined) {
  if (id == null) return '-';
  const item = allSensorOptions.value.find(s => Number(s.id) === Number(id));
  return item ? formatSensorOption(item) : String(id);
}

async function loadBaseOptions() {
  try {
    const [drawingRes, modelRes, deviceRes, unitRes, sensorRes] = await Promise.all([
      getDrawingListApi(),
      getModelListApi(),
      getDeviceListApi(),
      getUnitListApi(),
      getSensorListApi(),
    ]);
    drawingOptions.value = unwrapList(drawingRes) as DrawingItem[];
    modelOptions.value = unwrapList(modelRes);
    allDeviceOptions.value = unwrapList(deviceRes);
    allUnitOptions.value = unwrapList(unitRes);
    allSensorOptions.value = unwrapList(sensorRes);
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.message || '获取绑定选项失败';
    ElMessage.error(msg);
  }
}

async function loadDevicesByModel(modelId: SelectId) {
  deviceOptions.value = [];
  if (!modelId) return;
  try {
    const res = await getDevicesByModelApi(Number(modelId));
    deviceOptions.value = unwrapList(res);
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.message || '获取设备列表失败';
    ElMessage.error(msg);
  }
}

async function loadUnitsByDevice(deviceId: SelectId) {
  unitOptions.value = [];
  if (!deviceId) return;
  try {
    const res = await getUnitsByDeviceApi(Number(deviceId));
    unitOptions.value = unwrapList(res);
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.message || '获取机械臂单元失败';
    ElMessage.error(msg);
  }
}

async function loadSensorsByUnit(unitId: SelectId) {
  sensorOptions.value = [];
  if (!unitId) return;
  try {
    const res = await getSensorsByUnitApi(Number(unitId));
    sensorOptions.value = unwrapList(res);
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.message || '获取传感器列表失败';
    ElMessage.error(msg);
  }
}

function resetWorkForm() {
  workForm.Workname = '';
  workForm.WorkDescript = '';
  workForm.Drawing_ID = null;
  workForm.Model_ID = null;
  workForm.Device_id = null;
  workForm.unit_id = null;
  workForm.sensor_id = null;
  workForm.Notes = '';
  deviceOptions.value = [];
  unitOptions.value = [];
  sensorOptions.value = [];
  editingWorkId.value = null;
}

function handleModelChange() {
  workForm.Device_id = null;
  workForm.unit_id = null;
  workForm.sensor_id = null;
  unitOptions.value = [];
  sensorOptions.value = [];
  loadDevicesByModel(workForm.Model_ID);
}

function handleDeviceChange() {
  workForm.unit_id = null;
  workForm.sensor_id = null;
  sensorOptions.value = [];
  loadUnitsByDevice(workForm.Device_id);
}

function handleUnitChange() {
  workForm.sensor_id = null;
  loadSensorsByUnit(workForm.unit_id);
}

function openCreateWorkDialog() {
  resetWorkForm();
  workDialogTitle.value = '新增工作';
  workDialogVisible.value = true;
}

async function openEditWorkDialog(row: WorkItem) {
  resetWorkForm();
  workDialogTitle.value = '编辑工作';
  editingWorkId.value = row.Work_ID;
  workForm.Workname = row.Workname;
  workForm.WorkDescript = row.WorkDescript || '';
  workForm.Drawing_ID = row.Drawing_ID ?? null;
  workForm.Device_id = row.Device_id ?? null;
  workForm.unit_id = row.unit_id ?? null;
  workForm.sensor_id = row.sensor_id ?? null;
  workForm.Notes = row.Notes || '';

  const device = allDeviceOptions.value.find(d => Number(d.Device_ID) === Number(row.Device_id));
  workForm.Model_ID = device?.Model_ID ?? null;
  await loadDevicesByModel(workForm.Model_ID);
  await loadUnitsByDevice(workForm.Device_id);
  await loadSensorsByUnit(workForm.unit_id);
  workDialogVisible.value = true;
}

async function handleSaveWork() {
  if (!workForm.Workname.trim()) {
    ElMessage.warning('请输入工作名称');
    return;
  }
  if (!workForm.Drawing_ID) {
    ElMessage.warning('请选择绑定图纸');
    return;
  }
  if (!workForm.Model_ID) {
    ElMessage.warning('请选择绑定型号');
    return;
  }
  if (!workForm.Device_id) {
    ElMessage.warning('请选择绑定设备');
    return;
  }
  if (!workForm.unit_id) {
    ElMessage.warning('请选择绑定单元');
    return;
  }

  workSaving.value = true;
  try {
    const payload = {
      Workname: workForm.Workname.trim(),
      WorkDescript: workForm.WorkDescript.trim(),
      Drawing_ID: workForm.Drawing_ID,
      Device_id: workForm.Device_id,
      unit_id: workForm.unit_id,
      sensor_id: workForm.sensor_id,
      Notes: workForm.Notes.trim(),
    };

    const res: any = editingWorkId.value
      ? await updateWorkApi(editingWorkId.value, payload)
      : await createWorkApi(payload);

    if (res.code === 200) {
      ElMessage.success(res.message || '保存成功');
      workDialogVisible.value = false;
      fetchWorkList();
    } else {
      ElMessage.error(res.message || '保存失败');
    }
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.message || '保存失败';
    ElMessage.error(msg);
  } finally {
    workSaving.value = false;
  }
}

async function handleDeleteWork(row: WorkItem) {
  try {
    const res = await deleteWorkApi(row.Work_ID);
    if (res.code === 200) {
      ElMessage.success('删除成功');
      fetchWorkList();
    } else {
      ElMessage.error(res.message || '删除失败');
    }
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.message || '删除失败';
    ElMessage.error(msg);
  }
}

async function fetchWorkList() {
  workLoading.value = true;
  try {
    const res = await getWorkListApi();
    if (res.code === 200) {
      workList.value = res.data || [];
    }
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.message || '获取工作列表失败';
    ElMessage.error(msg);
  } finally {
    workLoading.value = false;
  }
}

function resetWorkflowForm() {
  workflowForm.Workflowname = '';
  workflowForm.WorkflowDescript = '';
  workflowForm.Notes = '';
  selectedWorkIds.value = [];
  orderedWorks.value = [];
  editingWorkflowId.value = null;
}

function openCreateWorkflowDialog() {
  resetWorkflowForm();
  workflowDialogTitle.value = '新建工作流';
  fetchAllWorksForSelect();
  workflowDialogVisible.value = true;
}

function onWorkSelected(ids: number[]) {
  const currentIds = orderedWorks.value.map(w => w.Work_ID);
  const newIds = ids.filter(id => !currentIds.includes(id));
  for (const id of newIds) {
    const work = allWorksForSelect.value.find(w => w.Work_ID === id);
    if (work) orderedWorks.value.push({ ...work });
  }
  const keepIds = new Set(ids);
  orderedWorks.value = orderedWorks.value.filter(w => keepIds.has(w.Work_ID));
}

function moveUp(idx: number) {
  if (idx <= 0) return;
  const arr = orderedWorks.value;
  const temp = arr[idx];
  arr[idx] = arr[idx - 1];
  arr[idx - 1] = temp;
  orderedWorks.value = [...arr];
}

function moveDown(idx: number) {
  if (idx >= orderedWorks.value.length - 1) return;
  const arr = orderedWorks.value;
  const temp = arr[idx];
  arr[idx] = arr[idx + 1];
  arr[idx + 1] = temp;
  orderedWorks.value = [...arr];
}

function removeWork(idx: number) {
  orderedWorks.value.splice(idx, 1);
  selectedWorkIds.value = orderedWorks.value.map(w => w.Work_ID);
}

async function handleSaveWorkflow() {
  if (!workflowForm.Workflowname.trim()) {
    ElMessage.warning('请输入工作流名称');
    return;
  }
  if (orderedWorks.value.length === 0) {
    ElMessage.warning('请至少选择一个工作');
    return;
  }

  workflowSaving.value = true;
  try {
    const workIds = orderedWorks.value.map(w => w.Work_ID);
    const payload = {
      Workflowname: workflowForm.Workflowname.trim(),
      WorkflowDescript: workflowForm.WorkflowDescript.trim(),
      Notes: workflowForm.Notes.trim(),
      work_ids: JSON.stringify(workIds),
    };

    const res: any = editingWorkflowId.value
      ? await updateWorkflowApi(editingWorkflowId.value, payload)
      : await createWorkflowApi(payload);

    if (res.code === 200) {
      ElMessage.success(res.message || '保存成功');
      workflowDialogVisible.value = false;
      fetchWorkflowList();
    } else {
      ElMessage.error(res.message || '保存失败');
    }
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.message || '保存失败';
    ElMessage.error(msg);
  } finally {
    workflowSaving.value = false;
  }
}

async function openEditWorkflowDialog(row: WorkflowItem) {
  resetWorkflowForm();
  workflowDialogTitle.value = '编辑工作流';
  editingWorkflowId.value = row.Workflow_ID;
  workflowForm.Workflowname = row.Workflowname;
  workflowForm.WorkflowDescript = row.WorkflowDescript || '';
  workflowForm.Notes = row.Notes || '';

  await fetchAllWorksForSelect();

  try {
    const res = await getWorkflowDetailApi(row.Workflow_ID);
    if (res.code === 200) {
      const detail = res.data;
      orderedWorks.value = (detail.works || []).map(w => ({ ...w }));
      orderedWorks.value.sort((a: any, b: any) => (a.flow_seq || 0) - (b.flow_seq || 0));
      selectedWorkIds.value = orderedWorks.value.map(w => w.Work_ID);
    }
  } catch {
    // Detail loading failure should not block editing base fields.
  }

  workflowDialogVisible.value = true;
}

async function fetchAllWorksForSelect() {
  try {
    const res = await getWorkListApi();
    if (res.code === 200) allWorksForSelect.value = res.data || [];
  } catch {
    // Ignore selector refresh errors; main table error handling covers the normal path.
  }
}

async function handleDeleteWorkflow(row: WorkflowItem) {
  try {
    const res = await deleteWorkflowApi(row.Workflow_ID);
    if (res.code === 200) {
      ElMessage.success('删除成功');
      fetchWorkflowList();
    } else {
      ElMessage.error(res.message || '删除失败');
    }
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.message || '删除失败';
    ElMessage.error(msg);
  }
}

async function fetchWorkflowList() {
  workflowLoading.value = true;
  try {
    const res = await getWorkflowListApi();
    if (res.code === 200) {
      workflowList.value = res.data || [];
    }
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.message || '获取工作流列表失败';
    ElMessage.error(msg);
  } finally {
    workflowLoading.value = false;
  }
}

async function openViewWorkflowDialog(row: WorkflowItem) {
  detailVisible.value = true;
  detailLoading.value = true;
  detailData.Workflowname = '';
  detailData.WorkflowDescript = '';
  detailData.Createtime = '';
  detailData.Notes = '';
  detailData.works = [];

  try {
    const res = await getWorkflowDetailApi(row.Workflow_ID);
    if (res.code === 200) {
      const d = res.data;
      detailData.Workflowname = d.Workflowname;
      detailData.WorkflowDescript = d.WorkflowDescript || '';
      detailData.Createtime = d.Createtime;
      detailData.Notes = d.Notes || '';
      detailData.works = (d.works || []).sort((a: any, b: any) => a.flow_seq - b.flow_seq);
    }
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.message || '获取工作流详情失败';
    ElMessage.error(msg);
  } finally {
    detailLoading.value = false;
  }
}

onMounted(async () => {
  await loadBaseOptions();
  fetchWorkList();
  fetchWorkflowList();
});
</script>

<style scoped>
.workflow-manage {
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

.tab-card {
  min-height: 400px;
}

.tab-header {
  display: flex;
  justify-content: flex-start;
}

.seq-list {
  width: 100%;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 8px;
  min-height: 80px;
}

.seq-item {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid #ebeef5;
}

.seq-item:last-child {
  border-bottom: none;
}

.seq-index {
  font-weight: bold;
  min-width: 70px;
  color: #409eff;
}

.seq-name {
  flex: 1;
}

.seq-actions {
  white-space: nowrap;
}

.steps-title {
  margin: 20px 0 12px;
  font-size: 16px;
  color: #303133;
}

.step-card {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 16px;
  margin-bottom: 12px;
  background: #fafafa;
}

.step-header {
  font-size: 15px;
  font-weight: bold;
  color: #409eff;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #ebeef5;
}

.data-pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 12px;
  background: #f5f7fa;
  padding: 8px;
  border-radius: 4px;
  max-height: 120px;
  overflow-y: auto;
}
</style>
