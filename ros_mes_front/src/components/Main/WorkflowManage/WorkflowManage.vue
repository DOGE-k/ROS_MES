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
          <el-table :data="workList" border stripe v-loading="workLoading" style="margin-top: 16px;">
            <el-table-column type="index" label="序号" width="60" />
            <el-table-column prop="Workname" label="工作名称" min-width="140" show-overflow-tooltip />
            <el-table-column prop="Drawing_ID" label="绑定图纸" width="100">
              <template #default="{ row }">{{ row.Drawing_ID ?? '-' }}</template>
            </el-table-column>
            <el-table-column prop="Device_id" label="绑定设备" width="100">
              <template #default="{ row }">{{ row.Device_id ?? '-' }}</template>
            </el-table-column>
            <el-table-column prop="unit_id" label="绑定单元" width="100">
              <template #default="{ row }">{{ row.unit_id ?? '-' }}</template>
            </el-table-column>
            <el-table-column prop="sensor_id" label="绑定传感器" width="100">
              <template #default="{ row }">{{ row.sensor_id ?? '-' }}</template>
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
          <el-table :data="workflowList" border stripe v-loading="workflowLoading" style="margin-top: 16px;">
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

    <!-- 新增/编辑工作弹窗 -->
    <el-dialog v-model="workDialogVisible" :title="workDialogTitle" width="600px" destroy-on-close>
      <el-form :model="workForm" label-width="120px">
        <el-form-item label="工作名称" required>
          <el-input v-model="workForm.Workname" placeholder="请输入工作名称" />
        </el-form-item>
        <el-form-item label="工作描述">
          <el-input v-model="workForm.WorkDescript" type="textarea" :rows="2" placeholder="请输入工作描述" />
        </el-form-item>
        <el-form-item label="绑定图纸">
          <el-input v-model="workForm.Drawing_ID" placeholder="图纸ID" />
        </el-form-item>
        <el-form-item label="绑定设备">
          <el-input v-model="workForm.Device_id" placeholder="设备ID" />
        </el-form-item>
        <el-form-item label="绑定单元">
          <el-input v-model="workForm.unit_id" placeholder="单元ID" />
        </el-form-item>
        <el-form-item label="绑定传感器">
          <el-input v-model="workForm.sensor_id" placeholder="传感器ID" />
        </el-form-item>
        <el-form-item label="工作数据">
          <el-input v-model="workForm.data" type="textarea" :rows="4" placeholder="请输入 JSON 格式的工作数据" />
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

    <!-- 新建/编辑工作流弹窗 -->
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

    <!-- 查看工作流详情弹窗 -->
    <el-dialog v-model="detailVisible" title="工作流详情" width="700px" destroy-on-close>
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
            <el-descriptions-item label="图纸ID">{{ work.Drawing_ID ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="设备ID">{{ work.Device_id ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="单元ID">{{ work.unit_id ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="传感器ID">{{ work.sensor_id ?? '-' }}</el-descriptions-item>
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
import { ref, reactive, onMounted, computed } from 'vue';
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
} from '@/api/rosApi';
import type { WorkItem, WorkflowItem } from '@/api/types';

const activeTab = ref('work');

// ==================== 工作管理 ====================
const workLoading = ref(false);
const workList = ref<WorkItem[]>([]);

const workDialogVisible = ref(false);
const workDialogTitle = ref('新增工作');
const workSaving = ref(false);
const editingWorkId = ref<number | null>(null);
const workForm = reactive({
  Workname: '',
  WorkDescript: '',
  Drawing_ID: '',
  Device_id: '',
  unit_id: '',
  sensor_id: '',
  data: '',
  Notes: '',
});

function resetWorkForm() {
  workForm.Workname = '';
  workForm.WorkDescript = '';
  workForm.Drawing_ID = '';
  workForm.Device_id = '';
  workForm.unit_id = '';
  workForm.sensor_id = '';
  workForm.data = '';
  workForm.Notes = '';
  editingWorkId.value = null;
}

function openCreateWorkDialog() {
  resetWorkForm();
  workDialogTitle.value = '新增工作';
  workDialogVisible.value = true;
}

function openEditWorkDialog(row: WorkItem) {
  resetWorkForm();
  workDialogTitle.value = '编辑工作';
  editingWorkId.value = row.Work_ID;
  workForm.Workname = row.Workname;
  workForm.WorkDescript = row.WorkDescript || '';
  workForm.Drawing_ID = row.Drawing_ID != null ? String(row.Drawing_ID) : '';
  workForm.Device_id = row.Device_id != null ? String(row.Device_id) : '';
  workForm.unit_id = row.unit_id != null ? String(row.unit_id) : '';
  workForm.sensor_id = row.sensor_id != null ? String(row.sensor_id) : '';
  workForm.data = row.data || '';
  workForm.Notes = row.Notes || '';
  workDialogVisible.value = true;
}

function validateJson(str: string): boolean {
  if (!str || !str.trim()) return true
  try {
    JSON.parse(str)
    return true
  } catch {
    return false
  }
}

async function handleSaveWork() {
  if (!workForm.Workname.trim()) {
    ElMessage.warning('请输入工作名称')
    return
  }
  if (!validateJson(workForm.data)) {
    ElMessage.warning('工作数据不是合法的 JSON 格式')
    return
  }

  workSaving.value = true
  try {
    const data: any = {
      Workname: workForm.Workname.trim(),
      WorkDescript: workForm.WorkDescript.trim(),
      data: workForm.data,
      Notes: workForm.Notes.trim(),
    }
    if (workForm.Drawing_ID) {
      data.Drawing_ID = Number(workForm.Drawing_ID)
    }
    if (workForm.Device_id) {
      data.Device_id = Number(workForm.Device_id)
    }
    if (workForm.unit_id) {
      data.unit_id = Number(workForm.unit_id)
    }
    if (workForm.sensor_id) {
      data.sensor_id = Number(workForm.sensor_id)
    }

    let res: any
    if (editingWorkId.value) {
      res = await updateWorkApi(editingWorkId.value, data)
    } else {
      res = await createWorkApi(data)
    }

    if (res.code === 200) {
      ElMessage.success(res.message || '保存成功')
      workDialogVisible.value = false
      fetchWorkList()
    } else {
      ElMessage.error(res.message || '保存失败')
    }
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.message || '保存失败'
    ElMessage.error(msg)
  } finally {
    workSaving.value = false
  }
}

async function handleDeleteWork(row: WorkItem) {
  try {
    const res = await deleteWorkApi(row.Work_ID)
    if (res.code === 200) {
      ElMessage.success('删除成功')
      fetchWorkList()
    } else {
      ElMessage.error(res.message || '删除失败')
    }
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.message || '删除失败'
    ElMessage.error(msg)
  }
}

async function fetchWorkList() {
  workLoading.value = true
  try {
    const res = await getWorkListApi()
    if (res.code === 200) {
      workList.value = res.data || []
    }
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.message || '获取工作列表失败'
    ElMessage.error(msg)
  } finally {
    workLoading.value = false
  }
}

// ==================== 工作流管理 ====================
const workflowLoading = ref(false)
const workflowList = ref<WorkflowItem[]>([])

const workflowDialogVisible = ref(false)
const workflowDialogTitle = ref('新建工作流')
const workflowSaving = ref(false)
const editingWorkflowId = ref<number | null>(null)

const workflowForm = reactive({
  Workflowname: '',
  WorkflowDescript: '',
  Notes: '',
})

const allWorksForSelect = ref<WorkItem[]>([])
const selectedWorkIds = ref<number[]>([])
const orderedWorks = ref<WorkItem[]>([])

function resetWorkflowForm() {
  workflowForm.Workflowname = ''
  workflowForm.WorkflowDescript = ''
  workflowForm.Notes = ''
  selectedWorkIds.value = []
  orderedWorks.value = []
  editingWorkflowId.value = null
}

function openCreateWorkflowDialog() {
  resetWorkflowForm()
  workflowDialogTitle.value = '新建工作流'
  fetchAllWorksForSelect()
  workflowDialogVisible.value = true
}

function onWorkSelected(ids: number[]) {
  const currentIds = orderedWorks.value.map(w => w.Work_ID)
  const newIds = ids.filter(id => !currentIds.includes(id))
  for (const id of newIds) {
    const work = allWorksForSelect.value.find(w => w.Work_ID === id)
    if (work) {
      orderedWorks.value.push({ ...work })
    }
  }
  const keepIds = new Set(ids)
  orderedWorks.value = orderedWorks.value.filter(w => keepIds.has(w.Work_ID))
}

function moveUp(idx: number) {
  if (idx <= 0) return
  const arr = orderedWorks.value
  const temp = arr[idx]
  arr[idx] = arr[idx - 1]
  arr[idx - 1] = temp
  orderedWorks.value = [...arr]
}

function moveDown(idx: number) {
  if (idx >= orderedWorks.value.length - 1) return
  const arr = orderedWorks.value
  const temp = arr[idx]
  arr[idx] = arr[idx + 1]
  arr[idx + 1] = temp
  orderedWorks.value = [...arr]
}

function removeWork(idx: number) {
  const removed = orderedWorks.value[idx]
  orderedWorks.value.splice(idx, 1)
  selectedWorkIds.value = orderedWorks.value.map(w => w.Work_ID)
}

async function handleSaveWorkflow() {
  if (!workflowForm.Workflowname.trim()) {
    ElMessage.warning('请输入工作流名称')
    return
  }
  if (orderedWorks.value.length === 0) {
    ElMessage.warning('请至少选择一个工作')
    return
  }

  workflowSaving.value = true
  try {
    const workIds = orderedWorks.value.map(w => w.Work_ID)
    const data: any = {
      Workflowname: workflowForm.Workflowname.trim(),
      WorkflowDescript: workflowForm.WorkflowDescript.trim(),
      Notes: workflowForm.Notes.trim(),
      work_ids: JSON.stringify(workIds),
    }

    let res: any
    if (editingWorkflowId.value) {
      res = await updateWorkflowApi(editingWorkflowId.value, data)
    } else {
      res = await createWorkflowApi(data)
    }

    if (res.code === 200) {
      ElMessage.success(res.message || '保存成功')
      workflowDialogVisible.value = false
      fetchWorkflowList()
    } else {
      ElMessage.error(res.message || '保存失败')
    }
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.message || '保存失败'
    ElMessage.error(msg)
  } finally {
    workflowSaving.value = false
  }
}

async function openEditWorkflowDialog(row: WorkflowItem) {
  resetWorkflowForm()
  workflowDialogTitle.value = '编辑工作流'
  editingWorkflowId.value = row.Workflow_ID
  workflowForm.Workflowname = row.Workflowname
  workflowForm.WorkflowDescript = row.WorkflowDescript || ''
  workflowForm.Notes = row.Notes || ''

  await fetchAllWorksForSelect()

  try {
    const res = await getWorkflowDetailApi(row.Workflow_ID)
    if (res.code === 200) {
      const detail = res.data
      orderedWorks.value = (detail.works || []).map(w => ({
        Work_ID: w.Work_ID,
        Workname: w.Workname,
        WorkDescript: w.WorkDescript || '',
        Drawing_ID: w.Drawing_ID,
        Device_id: w.Device_id,
        unit_id: w.unit_id,
        sensor_id: w.sensor_id,
        data: w.data || '',
        creater_id: w.creater_id,
        Createtime: w.Createtime,
        Modifytime: w.Modifytime,
        del_flag: w.del_flag,
        Notes: w.Notes || '',
      }))
      orderedWorks.value.sort((a, b) => {
        const aSeq = (detail.works || []).find((dw: any) => dw.Work_ID === a.Work_ID)?.flow_seq || 0
        const bSeq = (detail.works || []).find((dw: any) => dw.Work_ID === b.Work_ID)?.flow_seq || 0
        return aSeq - bSeq
      })
      selectedWorkIds.value = orderedWorks.value.map(w => w.Work_ID)
    }
  } catch {
    // ignore
  }

  workflowDialogVisible.value = true
}

async function fetchAllWorksForSelect() {
  try {
    const res = await getWorkListApi()
    if (res.code === 200) {
      allWorksForSelect.value = res.data || []
    }
  } catch {
    // ignore
  }
}

async function handleDeleteWorkflow(row: WorkflowItem) {
  try {
    const res = await deleteWorkflowApi(row.Workflow_ID)
    if (res.code === 200) {
      ElMessage.success('删除成功')
      fetchWorkflowList()
    } else {
      ElMessage.error(res.message || '删除失败')
    }
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.message || '删除失败'
    ElMessage.error(msg)
  }
}

async function fetchWorkflowList() {
  workflowLoading.value = true
  try {
    const res = await getWorkflowListApi()
    if (res.code === 200) {
      workflowList.value = res.data || []
    }
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.message || '获取工作流列表失败'
    ElMessage.error(msg)
  } finally {
    workflowLoading.value = false
  }
}

// ==================== 查看工作流详情 ====================
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailData = reactive<{
  Workflowname: string
  WorkflowDescript: string
  Createtime: string
  Notes: string
  works: any[]
}>({
  Workflowname: '',
  WorkflowDescript: '',
  Createtime: '',
  Notes: '',
  works: [],
})

async function openViewWorkflowDialog(row: WorkflowItem) {
  detailVisible.value = true
  detailLoading.value = true
  detailData.Workflowname = ''
  detailData.WorkflowDescript = ''
  detailData.Createtime = ''
  detailData.Notes = ''
  detailData.works = []

  try {
    const res = await getWorkflowDetailApi(row.Workflow_ID)
    if (res.code === 200) {
      const d = res.data
      detailData.Workflowname = d.Workflowname
      detailData.WorkflowDescript = d.WorkflowDescript || ''
      detailData.Createtime = d.Createtime
      detailData.Notes = d.Notes || ''
      detailData.works = (d.works || []).sort((a: any, b: any) => a.flow_seq - b.flow_seq)
    }
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.message || '获取工作流详情失败'
    ElMessage.error(msg)
  } finally {
    detailLoading.value = false
  }
}

onMounted(() => {
  fetchWorkList()
  fetchWorkflowList()
})
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
  min-width: 60px;
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
