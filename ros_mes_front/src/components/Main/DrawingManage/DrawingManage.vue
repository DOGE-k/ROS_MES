<template>
  <div class="drawing-manage-container">
    <el-row :gutter="20" class="dashboard-row">
      <el-col :span="6">
        <el-card shadow="hover" class="data-card border-blue">
          <div class="card-header">
            <span class="card-title">图纸总数</span>
            <el-icon class="card-icon" color="#409eff"><Document /></el-icon>
          </div>
          <div class="card-value">{{ tableData.length }}</div>
          <div class="card-desc">已上传图纸数量</div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover" class="data-card border-green">
          <div class="card-header">
            <span class="card-title">包含JSON数据</span>
            <el-icon class="card-icon" color="#67c23a"><DataAnalysis /></el-icon>
          </div>
          <div class="card-value success-text">{{ hasJsonCount }}</div>
          <div class="card-desc">含点云参数的图纸数</div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover" class="data-card border-orange">
          <div class="card-header">
            <span class="card-title">已上传文件</span>
            <el-icon class="card-icon" color="#e6a23c"><Files /></el-icon>
          </div>
          <div class="card-value warning-text">{{ hasFileCount }}</div>
          <div class="card-desc">关联了点云文件的图纸数</div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover" class="data-card border-purple">
          <div class="card-header">
            <span class="card-title">今日新增</span>
            <el-icon class="card-icon" color="#9b59b6"><TrendCharts /></el-icon>
          </div>
          <div class="card-value purple-text">{{ todayCount }}</div>
          <div class="card-desc">今日新上传图纸数量</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="main-card">
      <div class="toolbar">
        <el-input
          v-model="searchKeyword"
          placeholder="请输入图纸名称"
          clearable
          class="search-input"
        />
        <el-button type="primary" class="toolbar-btn query-btn" @click="handleQuery">查询</el-button>

        <el-divider direction="vertical" class="toolbar-divider" />

        <el-button type="primary" class="toolbar-btn" @click="handleImport">
          <el-icon style="margin-right: 4px;"><Upload /></el-icon>
          导入图纸
        </el-button>
      </div>

      <el-table
        :data="displayData"
        border
        stripe
        style="width: 100%"
        class="drawing-table"
        :header-cell-style="{ backgroundColor: '#fafafa', color: '#333', fontWeight: 'bold' }"
      >
        <el-table-column type="index" label="序号" width="60" align="center" />
        <el-table-column prop="name" label="图纸名称" min-width="180" />

        <el-table-column label="JSON数据" min-width="200" align="center">
          <template #default="scope">
            <el-button
              v-if="scope.row.jsonData && scope.row.jsonData !== '{}'"
              size="small"
              type="success"
              plain
              @click="showJsonDetail(scope.row)"
            >
              查看JSON
            </el-button>
            <el-tag v-else type="info" size="small">无数据</el-tag>
          </template>
        </el-table-column>

        <el-table-column label="关联文件" width="100" align="center">
          <template #default="scope">
            <el-tag v-if="scope.row.filePath" type="primary" size="small">是</el-tag>
            <el-tag v-else type="info" size="small">否</el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="createdAt" label="创建时间" width="180" align="center" />

        <el-table-column label="操作" width="200" align="center">
          <template #default="scope">
            <el-button size="small" type="primary" plain class="op-btn" @click="handleEdit(scope.row)">编辑</el-button>
            <el-button
              size="small"
              type="danger"
              plain
              class="op-btn"
              @click="handleDelete(scope.row)"
            >删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-container">
        <span class="total-text">共 {{ tableData.length }} 条数据</span>
      </div>
    </el-card>

    <!-- 导入/编辑对话框 -->
    <el-dialog
      v-model="importDialogVisible"
      :title="isEditing ? '编辑图纸' : '导入图纸'"
      width="600px"
      append-to-body
      destroy-on-close
    >
      <el-form :model="formData" label-width="100px" style="padding: 10px 20px 0;">
        <el-form-item label="图纸名称">
          <el-input v-model="formData.name" placeholder="请输入图纸名称" />
        </el-form-item>

        <el-form-item label="点云文件">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
            accept=".pcd,.ply,.las,.laz,.xyz,.bin,.txt"
          >
            <el-button type="primary" plain>
              <el-icon style="margin-right: 4px;"><Upload /></el-icon>
              选择文件
            </el-button>
            <template #tip>
              <div class="el-upload__tip" style="font-size: 12px; color: #909399;">
                支持 .pcd .ply .las .xyz 等点云格式
              </div>
            </template>
          </el-upload>
        </el-form-item>

        <el-form-item label="JSON数据">
          <el-input
            v-model="formData.jsonData"
            type="textarea"
            :rows="8"
            placeholder='请输入JSON格式数据，例如：{"points": 1024, "resolution": "0.01mm"}'
          />
          <p style="font-size: 12px; color: #909399; margin: 4px 0 0;">
            导入点云图时，前端会自动显示并保存JSON数据内容
          </p>
        </el-form-item>
      </el-form>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="importDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitImport" :loading="submitting">
            {{ isEditing ? '保存修改' : '确认导入' }}
          </el-button>
        </span>
      </template>
    </el-dialog>

    <!-- JSON详情对话框 -->
    <el-dialog
      v-model="jsonDialogVisible"
      title="JSON数据详情"
      width="600px"
      append-to-body
      destroy-on-close
    >
      <div style="padding: 0 10px;">
        <p style="font-size: 14px; color: #606266; margin-bottom: 10px;">
          图纸：<strong style="color: #409eff;">{{ jsonDetailTitle }}</strong>
        </p>
        <el-input
          :model-value="formattedJson"
          type="textarea"
          :rows="12"
          readonly
        />
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="jsonDialogVisible = false">关闭</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  Document,
  DataAnalysis,
  Files,
  TrendCharts,
  Upload,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadInstance, UploadFile } from 'element-plus'
import {
  getDrawingList,
  createDrawing,
  updateDrawing,
  deleteDrawing,
} from '@/api/rosApi'
import type { DrawingItem } from '@/api/types'

const searchKeyword = ref('')
const importDialogVisible = ref(false)
const jsonDialogVisible = ref(false)
const isEditing = ref(false)
const editingId = ref<number | null>(null)
const submitting = ref(false)
const uploadRef = ref<UploadInstance>()
const selectedFile = ref<File | null>(null)

const formData = ref({
  name: '',
  jsonData: '',
})

const jsonDetailTitle = ref('')
const formattedJson = ref('')

const tableData = ref<DrawingItem[]>([])

const displayData = computed(() => {
  const key = searchKeyword.value.toLowerCase()
  if (!key) return tableData.value
  return tableData.value.filter(item => item.name.toLowerCase().includes(key))
})

const hasJsonCount = computed(() =>
  tableData.value.filter(item => item.jsonData && item.jsonData !== '{}').length
)

const hasFileCount = computed(() =>
  tableData.value.filter(item => item.filePath).length
)

const todayCount = computed(() => {
  const today = new Date().toISOString().slice(0, 10)
  return tableData.value.filter(item => {
    if (!item.createdAt) return false
    return item.createdAt.slice(0, 10) === today
  }).length
})

const loadData = async () => {
  try {
    const res = await getDrawingList()
    if (res.code === 200) {
      tableData.value = [...(res.data || [])]
    }
  } catch {
    ElMessage.error('获取图纸列表失败')
  }
}

loadData()

const handleFileChange = (uploadFile: UploadFile) => {
  if (uploadFile.raw) {
    selectedFile.value = uploadFile.raw
  }
}

const handleFileRemove = () => {
  selectedFile.value = null
}

const handleQuery = () => {
  ElMessage.success(`已根据关键词 [${searchKeyword.value}] 过滤数据`)
}

const handleImport = () => {
  isEditing.value = false
  editingId.value = null
  formData.value = { name: '', jsonData: '' }
  selectedFile.value = null
  importDialogVisible.value = true
}

const handleEdit = (row: DrawingItem) => {
  isEditing.value = true
  editingId.value = row.id
  formData.value = {
    name: row.name,
    jsonData: row.jsonData || '',
  }
  selectedFile.value = null
  importDialogVisible.value = true
}

const showJsonDetail = (row: DrawingItem) => {
  jsonDetailTitle.value = row.name
  try {
    const parsed = JSON.parse(row.jsonData || '{}')
    formattedJson.value = JSON.stringify(parsed, null, 2)
  } catch {
    formattedJson.value = row.jsonData || ''
  }
  jsonDialogVisible.value = true
}

const submitImport = async () => {
  if (!formData.value.name.trim()) {
    ElMessage.error('图纸名称不能为空')
    return
  }

  let jsonToSave = formData.value.jsonData.trim()
  if (jsonToSave) {
    try {
      JSON.parse(jsonToSave)
    } catch {
      ElMessage.error('JSON 格式不正确')
      return
    }
  } else {
    jsonToSave = '{}'
  }

  submitting.value = true
  try {
    const fd = new FormData()
    fd.append('name', formData.value.name.trim())
    fd.append('json_data', jsonToSave)
    if (selectedFile.value) {
      fd.append('file', selectedFile.value)
    }

    if (isEditing.value && editingId.value) {
      await updateDrawing(editingId.value, fd)
      ElMessage.success('图纸更新成功')
    } else {
      await createDrawing(fd)
      ElMessage.success('图纸导入成功')
    }

    importDialogVisible.value = false
    await loadData()
  } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || '操作失败'
      ElMessage.error(msg)
    } finally {
    submitting.value = false
  }
}

const handleDelete = (row: DrawingItem) => {
  ElMessageBox.confirm(`确定要删除图纸 [${row.name}] 吗？`, '警告', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    try {
      await deleteDrawing(row.id)
      ElMessage.success('图纸已成功删除')
      await loadData()
    } catch {
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}
</script>

<style scoped>
.drawing-manage-container {
  padding: 20px;
  background-color: #f5f7fa;
  min-height: calc(100vh - 60px);
}

.dashboard-row { margin-bottom: 20px; }
.data-card { border: none; border-radius: 8px; transition: all 0.3s; }
.data-card:hover { transform: translateY(-3px); }
.border-blue { border-top: 4px solid #409eff; }
.border-green { border-top: 4px solid #67c23a; }
.border-orange { border-top: 4px solid #e6a23c; }
.border-purple { border-top: 4px solid #9b59b6; }

.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
.card-title { font-size: 14px; color: #606266; font-weight: bold; }
.card-icon { font-size: 22px; }
.card-value { font-size: 26px; font-weight: bold; color: #303133; margin-bottom: 8px; }
.card-desc { font-size: 12px; color: #909399; }

.success-text { color: #67c23a; }
.warning-text { color: #e6a23c; }
.purple-text { color: #9b59b6; }

.main-card { border-radius: 8px; border: none; }
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 25px;
}

.toolbar :deep(.el-button) { margin-left: 0 !important; }

.search-input { width: 220px; }

.toolbar-btn {
  height: 34px;
  padding: 0 18px !important;
  display: inline-flex;
  justify-content: center;
  align-items: center;
  font-size: 14px;
  letter-spacing: 1px;
}
.query-btn { min-width: 80px; }
.toolbar-divider { height: 20px; margin: 0 5px; border-color: #dcdfe6; }

.drawing-table { margin-bottom: 20px; }

.drawing-table :deep(.op-btn) {
  width: 72px;
  height: 28px;
  padding: 0 !important;
  justify-content: center;
  align-items: center;
  display: inline-flex;
  font-size: 13px;
  margin: 0 4px !important;
}

.pagination-container {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  margin-top: 10px;
}
.total-text { font-size: 13px; color: #606266; margin-right: 15px; }
</style>
