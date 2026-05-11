<template>
  <div class="task-manage">
    <el-card class="header-card">
      <div class="header-row">
        <h2 class="page-title">任务管理</h2>
      </div>
    </el-card>

    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-label">任务总数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card stat-running">
          <div class="stat-value">{{ stats.running }}</div>
          <div class="stat-label">运行中</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card stat-paused">
          <div class="stat-value">{{ stats.paused }}</div>
          <div class="stat-label">暂停 / 阻塞</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card stat-finished">
          <div class="stat-value">{{ stats.finished }}</div>
          <div class="stat-label">已结束</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="search-card">
      <el-form :model="searchForm" label-width="80px">
        <el-row :gutter="16">
          <el-col :span="6">
            <el-form-item label="任务名称">
              <el-input v-model="searchForm.keyword" placeholder="按任务名称搜索" clearable @keyup.enter="handleSearch" />
            </el-form-item>
          </el-col>
          <el-col :span="4">
            <el-form-item label="状态">
              <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 100%">
                <el-option label="全部" value="" />
                <el-option label="就绪" value="0" />
                <el-option label="运行中" value="1" />
                <el-option label="已暂停" value="2" />
                <el-option label="已结束" value="3" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="4">
            <el-form-item label="图纸">
              <el-select v-model="searchForm.drawing_id" placeholder="全部" clearable style="width: 100%">
                <el-option label="全部" :value="null" />
                <el-option v-for="d in drawingOptions" :key="d.drawingId" :label="d.drawingName" :value="d.drawingId" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="4">
            <el-form-item label="工作流">
              <el-select v-model="searchForm.workflow_id" placeholder="全部" clearable style="width: 100%">
                <el-option label="全部" :value="null" />
                <el-option v-for="w in workflowOptions" :key="w.Workflow_ID" :label="w.Workflowname" :value="w.Workflow_ID" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item>
              <el-button type="primary" @click="handleSearch">查询</el-button>
              <el-button @click="handleReset">重置</el-button>
              <el-button type="success" @click="openCreateDialog">新建任务</el-button>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <el-card class="table-card">
      <el-table :data="taskList" border stripe v-loading="loading">
        <el-table-column type="index" label="序号" width="60" />
        <el-table-column prop="Taskname" label="任务名称" min-width="140" show-overflow-tooltip />
        <el-table-column prop="Taskdescripte" label="任务描述" min-width="160" show-overflow-tooltip />
        <el-table-column prop="DrawingName" label="绑定图纸" min-width="120" show-overflow-tooltip />
        <el-table-column label="绑定工作流" min-width="140">
          <template #default="{ row }">
            <div>{{ row.WorkflowName || '未绑定' }}</div>
            <div v-if="row.WorksSubset && row.WorksSubset.length" class="works-subset-indicator">
              <el-tag size="small" type="info">包含 {{ row.WorksSubset.length }} 个工作</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="AssigneeName" label="分配人员" min-width="100" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.Status)" size="small">
              {{ statusLabel(row.Status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="Createtime" label="创建时间" width="170" />
        <el-table-column label="操作" width="340" fixed="right">
          <template #default="{ row }">
            <template v-if="row.Status === '0'">
              <el-button link type="primary" @click="handleStart(row)">启动</el-button>
              <el-button link type="success" @click="openEditDialog(row)">编辑</el-button>
              <el-popconfirm title="确定删除该任务吗？" @confirm="handleDelete(row)">
                <template #reference>
                  <el-button link type="danger">删除</el-button>
                </template>
              </el-popconfirm>
            </template>
            <template v-else-if="row.Status === '1'">
              <el-button link type="warning" @click="handlePause(row)">暂停</el-button>
              <el-button link type="danger" @click="handleFinish(row)">结束</el-button>
              <el-button link type="primary" @click="openProgressDialog(row)">查看进度</el-button>
            </template>
            <template v-else-if="row.Status === '2'">
              <el-button link type="primary" @click="handleResume(row)">唤醒</el-button>
              <el-button link type="warning" @click="handleDispatch(row)">调度</el-button>
              <el-button link type="danger" @click="handleFinish(row)">结束</el-button>
              <el-button link type="primary" @click="openProgressDialog(row)">查看进度</el-button>
              <el-button link type="success" @click="openEditDialog(row)">编辑</el-button>
              <el-popconfirm title="确定删除该任务吗？" @confirm="handleDelete(row)">
                <template #reference>
                  <el-button link type="danger">删除</el-button>
                </template>
              </el-popconfirm>
            </template>
            <template v-else-if="row.Status === '3'">
              <el-button link type="primary" @click="openProgressDialog(row)">查看进度</el-button>
              <el-popconfirm title="确定删除该任务吗？" @confirm="handleDelete(row)">
                <template #reference>
                  <el-button link type="danger">删除</el-button>
                </template>
              </el-popconfirm>
            </template>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="formVisible" :title="isEditing ? '编辑任务' : '新建任务'" width="700px" destroy-on-close>
      <el-form :model="taskForm" label-width="100px" ref="formRef">
        <el-form-item label="任务名称" required>
          <el-input v-model="taskForm.Taskname" placeholder="请输入任务名称" />
        </el-form-item>
        <el-form-item label="任务描述">
          <el-input v-model="taskForm.Taskdescripte" type="textarea" :rows="2" placeholder="请输入任务描述（可选）" />
        </el-form-item>
        <el-form-item label="绑定工作流">
          <el-select v-model="taskForm.Workflow_ID" placeholder="请选择工作流" clearable style="width: 100%" @change="onWorkflowChange">
            <el-option v-for="w in workflowOptions" :key="w.Workflow_ID" :label="w.Workflowname" :value="w.Workflow_ID" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="selectedWorks.length > 0" label="工作子集">
          <div class="works-subset-panel">
            <div class="works-subset-header">该工作流包含以下工作（共 {{ selectedWorks.length }} 项）</div>
            <el-table :data="selectedWorks" border stripe size="small" max-height="200">
              <el-table-column type="index" label="序号" width="50" />
              <el-table-column prop="flow_seq" label="执行顺序" width="80" />
              <el-table-column prop="Workname" label="工作名称" min-width="120" />
              <el-table-column prop="WorkDescript" label="工作描述" min-width="160" show-overflow-tooltip />
            </el-table>
          </div>
        </el-form-item>
        <el-form-item label="绑定图纸">
          <el-select v-model="taskForm.Drawing_ID" placeholder="请选择图纸" clearable style="width: 100%">
            <el-option v-for="d in drawingOptions" :key="d.drawingId" :label="d.drawingName" :value="d.drawingId" />
          </el-select>
        </el-form-item>
        <el-form-item label="分配人员">
          <el-select v-model="taskForm.TaskAssignment_id" placeholder="请选择分配人员" clearable style="width: 100%">
            <el-option v-for="u in userOptions" :key="u.id" :label="u.name || u.username" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="taskForm.Notes" type="textarea" :rows="3" placeholder="备注信息（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">确认</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="progressVisible" title="查看任务进度" width="900px" destroy-on-close>
      <template v-if="currentTask">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="任务名称">{{ currentTask.Taskname }}</el-descriptions-item>
          <el-descriptions-item label="当前状态">
            <el-tag :type="statusType(currentTask.Status)" size="small">
              {{ statusLabel(currentTask.Status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="绑定图纸">{{ currentTask.DrawingName || '未绑定' }}</el-descriptions-item>
          <el-descriptions-item label="绑定工作流">{{ currentTask.WorkflowName || '未绑定' }}</el-descriptions-item>
          <el-descriptions-item label="分配人员">{{ currentTask.AssigneeName || '未分配' }}</el-descriptions-item>
        </el-descriptions>

        <div v-if="currentTask.WorksSubset && currentTask.WorksSubset.length" class="section-block">
          <h4 class="section-title">工作子集（{{ currentTask.WorksSubset.length }} 项）</h4>
          <el-table :data="currentTask.WorksSubset" border stripe size="small" max-height="200">
            <el-table-column type="index" label="序号" width="50" />
            <el-table-column prop="flow_seq" label="执行顺序" width="80" />
            <el-table-column prop="Workname" label="工作名称" min-width="140" />
            <el-table-column prop="WorkDescript" label="工作描述" min-width="200" show-overflow-tooltip />
          </el-table>
        </div>

        <div class="section-block">
          <h4 class="section-title">工件执行记录</h4>
          <el-card shadow="never" class="piece-form-card">
            <el-form :model="pieceForm" label-width="100px" size="small">
              <el-row :gutter="16">
                <el-col :span="12">
                  <el-form-item label="识别码">
                    <el-input v-model="pieceForm.piece_code" placeholder="唯一识别码，如 P202605100001" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="编码类型">
                    <el-select v-model="pieceForm.code_type" placeholder="请选择" style="width: 100%">
                      <el-option label="二维码" value="二维码" />
                      <el-option label="序列号" value="序列号" />
                      <el-option label="RFID" value="RFID" />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>
              <el-row :gutter="16">
                <el-col :span="8">
                  <el-form-item label="抓取时间">
                    <el-date-picker v-model="pieceForm.grab_time" type="datetime" placeholder="选择抓取时间" style="width: 100%" value-format="YYYY-MM-DD HH:mm:ss" />
                  </el-form-item>
                </el-col>
                <el-col :span="16">
                  <el-form-item label="检测结果">
                    <el-select v-model="pieceForm.detect_result" placeholder="请选择" style="width: 100%">
                      <el-option label="合格" value="合格" />
                      <el-option label="不合格" value="不合格" />
                      <el-option label="待复检" value="待复检" />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>
              <el-form-item label="工装坐标">
                <el-row :gutter="8">
                  <el-col :span="8">
                    <el-input v-model.number="pieceForm.fixture_position.x" placeholder="X">
                      <template #prefix>X</template>
                    </el-input>
                  </el-col>
                  <el-col :span="8">
                    <el-input v-model.number="pieceForm.fixture_position.y" placeholder="Y">
                      <template #prefix>Y</template>
                    </el-input>
                  </el-col>
                  <el-col :span="8">
                    <el-input v-model.number="pieceForm.fixture_position.z" placeholder="Z">
                      <template #prefix>Z</template>
                    </el-input>
                  </el-col>
                </el-row>
              </el-form-item>
              <el-form-item label="机械臂轨迹">
                <el-input v-model="pieceForm.robot_track" placeholder="轨迹数据或文件路径（可选）" />
              </el-form-item>
              <el-form-item label="操作人员">
                <el-input v-model="pieceForm.operator" placeholder="操作人员姓名" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" size="small" @click="handleAddPieceRecord" :loading="pieceSaving">添加工件记录</el-button>
              </el-form-item>
            </el-form>
          </el-card>
        </div>

        <div class="section-block">
          <h4 class="section-title">任务跟踪记录</h4>
          <el-table :data="tracingList" border stripe v-loading="tracingLoading" max-height="400">
            <el-table-column prop="operate_time" label="操作时间" width="170" />
            <el-table-column label="操作类型" width="120">
              <template #default="{ row }">
                {{ operateTypeLabel(row.operate_type) }}
              </template>
            </el-table-column>
            <el-table-column prop="OperatorName" label="操作人员" width="120" />
            <el-table-column label="备注" min-width="200" show-overflow-tooltip>
              <template #default="{ row }">
                <div v-if="isJsonString(row.Notes)" class="json-notes">
                  <pre>{{ formatJson(row.Notes) }}</pre>
                </div>
                <span v-else>{{ row.Notes }}</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </template>
    </el-dialog>

    <el-dialog v-model="dispatchVisible" title="任务调度" width="420px" destroy-on-close>
      <p v-if="runningTaskName" style="margin-bottom: 12px;">
        当前存在运行中的任务：<strong>{{ runningTaskName }}</strong>，将自动暂停该任务。
      </p>
      <p v-else style="margin-bottom: 12px; color: #67c23a;">
        当前没有运行中的任务，可以直接调度。
      </p>
      <p>确认调度任务 <strong>{{ dispatchTaskName }}</strong> 进入流水线？</p>
      <template #footer>
        <el-button @click="dispatchVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmDispatch" :loading="dispatching">确认调度</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getTaskListApi,
  createTaskApi,
  updateTaskApi,
  deleteTaskApi,
  startTaskApi,
  pauseTaskApi,
  resumeTaskApi,
  finishTaskApi,
  dispatchTaskApi,
  getTaskTracingApi,
  addTaskProgressApi,
  getTaskWorksApi,
  getDrawingListApi,
  getWorkflowListApi,
  getUserListApi,
} from '@/api/rosApi'
import type { TaskItem, TaskTracingItem, WorkSubsetItem } from '@/api/types'

const loading = ref(false)
const saving = ref(false)
const tracingLoading = ref(false)
const dispatching = ref(false)
const pieceSaving = ref(false)
const taskList = ref<TaskItem[]>([])
const tracingList = ref<TaskTracingItem[]>([])
const drawingOptions = ref<any[]>([])
const workflowOptions = ref<any[]>([])
const userOptions = ref<any[]>([])
const selectedWorks = ref<WorkSubsetItem[]>([])

const searchForm = reactive({
  keyword: '',
  status: '',
  drawing_id: null as number | null,
  workflow_id: null as number | null,
})

const stats = reactive({
  total: 0,
  running: 0,
  paused: 0,
  finished: 0,
})

const formVisible = ref(false)
const isEditing = ref(false)
const editingId = ref<number | null>(null)

const taskForm = reactive({
  Taskname: '',
  Taskdescripte: '',
  Workflow_ID: null as number | null,
  Drawing_ID: null as number | null,
  TaskAssignment_id: null as number | null,
  Notes: '',
})

const progressVisible = ref(false)
const currentTask = ref<TaskItem | null>(null)

const dispatchVisible = ref(false)
const dispatchTaskId = ref<number>(0)
const dispatchTaskName = ref('')
const runningTaskName = ref('')

const pieceForm = reactive({
  piece_code: '',
  code_type: '二维码',
  grab_time: '',
  fixture_position: { x: 0, y: 0, z: 0 },
  robot_track: '',
  detect_result: '合格',
  operator: '',
})

function statusType(status: string): string {
  switch (status) {
    case '0': return 'info'
    case '1': return 'success'
    case '2': return 'warning'
    case '3': return ''
    default: return 'info'
  }
}

function statusLabel(status: string): string {
  switch (status) {
    case '0': return '就绪'
    case '1': return '运行中'
    case '2': return '已暂停'
    case '3': return '已结束'
    default: return '未知'
  }
}

function operateTypeLabel(type: number): string {
  switch (type) {
    case 0: return '启动任务'
    case 1: return '暂停任务'
    case 2: return '唤醒任务'
    case 3: return '结束任务'
    case 4: return '进度记录'
    case 5: return '任务调度'
    case 6: return '删除任务'
    default: return `操作(${type})`
  }
}

function isJsonString(str: string): boolean {
  if (!str) return false
  try {
    const obj = JSON.parse(str)
    return typeof obj === 'object'
  } catch {
    return false
  }
}

function formatJson(str: string): string {
  try {
    return JSON.stringify(JSON.parse(str), null, 2)
  } catch {
    return str
  }
}

async function fetchTaskList() {
  loading.value = true
  try {
    const params: Record<string, any> = {}
    if (searchForm.keyword) params.keyword = searchForm.keyword
    if (searchForm.status !== '' && searchForm.status !== null) params.status = searchForm.status
    if (searchForm.drawing_id) params.drawing_id = searchForm.drawing_id
    if (searchForm.workflow_id) params.workflow_id = searchForm.workflow_id
    const res = await getTaskListApi(params)
    if (res.code === 200) {
      taskList.value = res.data || []
      calcStats()
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || err?.message || '获取任务列表失败')
  } finally {
    loading.value = false
  }
}

function calcStats() {
  const list = taskList.value
  stats.total = list.length
  stats.running = list.filter(t => t.Status === '1').length
  stats.paused = list.filter(t => t.Status === '2').length
  stats.finished = list.filter(t => t.Status === '3').length
}

async function fetchDrawings() {
  try {
    const res = await getDrawingListApi()
    if (res.code === 200) {
      drawingOptions.value = res.data || []
    }
  } catch {
    // TODO: 图纸接口不可用时使用普通输入框
  }
}

async function fetchWorkflows() {
  try {
    const res = await getWorkflowListApi()
    if (res.code === 200) {
      workflowOptions.value = res.data || []
    }
  } catch {
    // TODO: 工作流接口不可用时使用普通输入框
  }
}

async function fetchUsers() {
  try {
    const res = await getUserListApi()
    if (res.code === 200) {
      userOptions.value = res.data || []
    }
  } catch {
    // TODO: 用户列表接口不可用时使用普通输入框
  }
}

function handleSearch() {
  fetchTaskList()
}

function handleReset() {
  searchForm.keyword = ''
  searchForm.status = ''
  searchForm.drawing_id = null
  searchForm.workflow_id = null
  fetchTaskList()
}

async function onWorkflowChange(workflowId: number | null) {
  selectedWorks.value = []
  if (!workflowId) return
  try {
    const res = await getWorkflowListApi()
    // TODO: 如果有工作流详情接口返回工作子集，改为使用详情接口
    const workflowDetail = res.data?.find((w: any) => w.Workflow_ID === workflowId)
    if (workflowDetail && (workflowDetail as any).works) {
      selectedWorks.value = (workflowDetail as any).works.map((w: any) => ({
        Work_ID: w.Work_ID,
        Workname: w.Workname,
        WorkDescript: w.WorkDescript || '',
        flow_seq: w.flow_seq || 0,
      }))
    }
  } catch {
    // 工作流详情接口不可用时静默处理
  }
}

function resetPieceForm() {
  const now = new Date()
  const pad = (n: number) => n.toString().padStart(2, '0')
  const ts = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
  const seq = now.getFullYear().toString() +
    pad(now.getMonth() + 1) +
    pad(now.getDate()) +
    pad(now.getHours()) +
    pad(now.getMinutes()) +
    pad(now.getSeconds())
  pieceForm.piece_code = `P${seq}`
  pieceForm.code_type = '二维码'
  pieceForm.grab_time = ts
  pieceForm.fixture_position = { x: 0, y: 0, z: 0 }
  pieceForm.robot_track = ''
  pieceForm.detect_result = '合格'
  pieceForm.operator = ''
}

function openCreateDialog() {
  isEditing.value = false
  editingId.value = null
  taskForm.Taskname = ''
  taskForm.Taskdescripte = ''
  taskForm.Workflow_ID = null
  taskForm.Drawing_ID = null
  taskForm.TaskAssignment_id = null
  taskForm.Notes = ''
  selectedWorks.value = []
  formVisible.value = true
}

function openEditDialog(row: TaskItem) {
  isEditing.value = true
  editingId.value = row.Task_ID
  taskForm.Taskname = row.Taskname
  taskForm.Taskdescripte = row.Taskdescripte || ''
  taskForm.Workflow_ID = row.Workflow_ID
  taskForm.Drawing_ID = row.Drawing_ID
  taskForm.TaskAssignment_id = row.TaskAssignment_id
  taskForm.Notes = row.Notes || ''
  selectedWorks.value = row.WorksSubset || []
  formVisible.value = true
}

async function handleSave() {
  if (!taskForm.Taskname || !taskForm.Taskname.trim()) {
    ElMessage.warning('任务名称不能为空')
    return
  }
  saving.value = true
  try {
    if (isEditing.value && editingId.value) {
      const res = await updateTaskApi(editingId.value, { ...taskForm })
      if (res.code === 200) {
        ElMessage.success('更新任务成功')
        formVisible.value = false
        fetchTaskList()
      }
    } else {
      const res = await createTaskApi({ ...taskForm })
      if (res.code === 200) {
        ElMessage.success('创建任务成功')
        formVisible.value = false
        fetchTaskList()
      }
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || err?.message || '操作失败')
  } finally {
    saving.value = false
  }
}

async function handleStart(row: TaskItem) {
  try {
    const res = await startTaskApi(row.Task_ID)
    if (res.code === 200) {
      ElMessage.success('任务已启动')
      fetchTaskList()
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || err?.message || '启动失败')
  }
}

async function handlePause(row: TaskItem) {
  try {
    const res = await pauseTaskApi(row.Task_ID)
    if (res.code === 200) {
      ElMessage.success('任务已暂停')
      fetchTaskList()
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || err?.message || '暂停失败')
  }
}

async function handleResume(row: TaskItem) {
  try {
    const res = await resumeTaskApi(row.Task_ID)
    if (res.code === 200) {
      ElMessage.success('任务已唤醒')
      fetchTaskList()
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || err?.message || '唤醒失败')
  }
}

async function handleFinish(row: TaskItem) {
  try {
    const res = await finishTaskApi(row.Task_ID)
    if (res.code === 200) {
      ElMessage.success('任务已结束')
      fetchTaskList()
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || err?.message || '结束失败')
  }
}

async function handleDelete(row: TaskItem) {
  try {
    const res = await deleteTaskApi(row.Task_ID)
    if (res.code === 200) {
      ElMessage.success('删除任务成功')
      fetchTaskList()
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || err?.message || '删除失败')
  }
}

async function openProgressDialog(row: TaskItem) {
  currentTask.value = row
  progressVisible.value = true
  tracingLoading.value = true
  tracingList.value = []
  resetPieceForm()
  try {
    const [tracingRes, worksRes] = await Promise.all([
      getTaskTracingApi(row.Task_ID),
      getTaskWorksApi(row.Task_ID),
    ])
    if (tracingRes.code === 200) {
      tracingList.value = tracingRes.data || []
    }
    if (worksRes.code === 200) {
      if (currentTask.value) {
        currentTask.value.WorksSubset = worksRes.data || []
      }
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || err?.message || '获取进度数据失败')
  } finally {
    tracingLoading.value = false
  }
}

async function handleAddPieceRecord() {
  if (!pieceForm.piece_code) {
    ElMessage.warning('请输入工件识别码')
    return
  }
  if (!currentTask.value) return
  pieceSaving.value = true
  try {
    const payload = {
      piece_code: pieceForm.piece_code,
      code_type: pieceForm.code_type,
      grab_time: pieceForm.grab_time,
      fixture_position: pieceForm.fixture_position,
      robot_track: pieceForm.robot_track,
      detect_result: pieceForm.detect_result,
      operator: pieceForm.operator,
    }
    const res = await addTaskProgressApi(currentTask.value.Task_ID, {
      Notes: JSON.stringify(payload),
    })
    if (res.code === 200) {
      ElMessage.success('工件记录已添加')
      resetPieceForm()
      const tracingRes = await getTaskTracingApi(currentTask.value.Task_ID)
      if (tracingRes.code === 200) {
        tracingList.value = tracingRes.data || []
      }
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || err?.message || '添加记录失败')
  } finally {
    pieceSaving.value = false
  }
}

async function handleDispatch(row: TaskItem) {
  dispatchTaskId.value = row.Task_ID
  dispatchTaskName.value = row.Taskname
  runningTaskName.value = ''
  const running = taskList.value.find(t => t.Status === '1')
  if (running) {
    runningTaskName.value = running.Taskname
  }
  dispatchVisible.value = true
}

async function confirmDispatch() {
  dispatching.value = true
  try {
    const res = await dispatchTaskApi(dispatchTaskId.value)
    if (res.code === 200) {
      ElMessage.success('任务调度成功')
      dispatchVisible.value = false
      fetchTaskList()
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || err?.message || '调度失败')
  } finally {
    dispatching.value = false
  }
}

onMounted(() => {
  fetchTaskList()
  fetchDrawings()
  fetchWorkflows()
  fetchUsers()
})
</script>

<style scoped>
.task-manage {
  padding: 20px;
}

.header-card {
  margin-bottom: 16px;
}

.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.page-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.stat-row {
  margin-bottom: 16px;
}

.stat-card {
  text-align: center;
}

.stat-card .stat-value {
  font-size: 32px;
  font-weight: 700;
  color: #303133;
}

.stat-card .stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 4px;
}

.stat-running .stat-value {
  color: #67c23a;
}

.stat-paused .stat-value {
  color: #e6a23c;
}

.stat-finished .stat-value {
  color: #909399;
}

.search-card {
  margin-bottom: 16px;
}

.works-subset-panel {
  width: 100%;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 10px;
  background: #fafafa;
}

.works-subset-header {
  font-size: 13px;
  color: #606266;
  margin-bottom: 8px;
  font-weight: 500;
}

.works-subset-indicator {
  margin-top: 2px;
}

.section-block {
  margin-top: 20px;
}

.section-title {
  margin: 0 0 10px;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.piece-form-card {
  margin-bottom: 10px;
}

.json-notes pre {
  background: #f5f7fa;
  padding: 8px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}
</style>
