<template>
  <div class="user-manage-container">
    <el-card class="header-card">
      <h2 class="page-title">用户管理</h2>
    </el-card>
    <el-row :gutter="20" class="dashboard-row">
      <el-col :span="6">
        <el-card shadow="hover" class="data-card border-blue">
          <div class="card-header">
            <span class="card-title">用户总数</span>
            <el-icon class="card-icon" color="#409eff"><User /></el-icon>
          </div>
          <div class="card-value">{{ tableData.length }}</div>
          <div class="card-desc">系统注册用户总数</div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover" class="data-card border-green">
          <div class="card-header">
            <span class="card-title">管理员人数</span>
            <el-icon class="card-icon" color="#67c23a"><Avatar /></el-icon>
          </div>
          <div class="card-value success-text">{{ adminCount }}</div>
          <div class="card-desc">权限为管理员的账号数</div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover" class="data-card border-orange">
          <div class="card-header">
            <span class="card-title">正常账号</span>
            <el-icon class="card-icon" color="#e6a23c"><CircleCheck /></el-icon>
          </div>
          <div class="card-value warning-text">{{ normalCount }}</div>
          <div class="card-desc">当前状态正常的账号数</div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover" class="data-card border-red">
          <div class="card-header">
            <span class="card-title">锁定账号</span>
            <el-icon class="card-icon" color="#f56c6c"><Warning /></el-icon>
          </div>
          <div class="card-value danger-text">{{ lockedCount }}</div>
          <div class="card-desc">当前已被锁定的账号数</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="main-card">
      <div class="toolbar">
        <el-input
          v-model="searchKeyword"
          placeholder="请输入账号/用户名"
          clearable
          class="search-input"
          @keyup.enter="handleQuery"
        />
        <el-select v-model="searchTypeId" placeholder="全部角色" class="search-select" @change="handleQuery">
          <el-option label="全部角色" :value="0" />
          <el-option label="管理员" :value="1" />
          <el-option label="操作员" :value="2" />
        </el-select>
        <el-button type="primary" class="toolbar-btn query-btn" @click="handleQuery">查询</el-button>

        <el-divider direction="vertical" class="toolbar-divider" />

        <el-button type="primary" plain class="toolbar-btn" @click="handleAddUser">新增用户</el-button>
        <el-button type="success" plain class="toolbar-btn" @click="handleImport">批量导入</el-button>
        <el-button plain class="toolbar-btn" @click="handleExport">导出报表</el-button>
      </div>

      <el-table
        :data="tableData"
        border
        stripe
        v-loading="loading"
        style="width: 100%"
        class="user-table"
        :header-cell-style="{ backgroundColor: '#fafafa', color: '#333', fontWeight: 'bold' }"
      >
        <el-table-column type="index" label="序号" width="60" align="center" />
        <el-table-column prop="account" label="账号" width="130" />
        <el-table-column prop="username" label="用户名" width="130" />

        <el-table-column label="角色" width="120" align="center">
          <template #default="scope">
            <el-tag :type="scope.row.typeId === 1 ? 'danger' : 'info'" effect="light">
              {{ scope.row.typeLabel }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="状态" width="100" align="center">
          <template #default="scope">
            <el-tag v-if="!scope.row.isLock" type="success" size="small">正常</el-tag>
            <el-tag v-else type="danger" size="small" effect="dark">已锁定</el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="locktime" label="最后登录时间" width="180" align="center" />

        <el-table-column label="操作" min-width="260" align="center">
          <template #default="scope">
            <el-button size="small" type="primary" plain class="op-btn" @click="handleEdit(scope.row)">编辑</el-button>

            <el-button
              v-if="isAdmin && !scope.row.isLock && scope.row.typeId !== 1"
              size="small"
              type="danger"
              plain
              class="op-btn"
              @click="handleLock(scope.row)"
            >锁定</el-button>

            <el-button
              v-else-if="isAdmin && scope.row.typeId !== 1"
              size="small"
              type="success"
              plain
              class="op-btn"
              @click="handleUnlock(scope.row)"
            >解锁</el-button>

            <el-button
              v-if="isAdmin"
              size="small"
              type="warning"
              plain
              class="op-btn-long"
              @click="handleRoleChange(scope.row)"
            >修改权限</el-button>

            <el-button
              v-if="isAdmin"
              size="small"
              type="info"
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

    <el-dialog
      v-model="editDialogVisible"
      :title="isAdding ? '添加新用户' : '修改用户信息'"
      width="450px"
      append-to-body
      destroy-on-close
      @closed="resetEditForm"
    >
      <el-form :model="editForm" label-width="80px" style="padding: 10px 20px 0;">
        <el-form-item label="账号">
          <el-input v-model="editForm.account" :disabled="!isAdding" placeholder="请输入系统登录账号" />
          <p v-if="!isAdding" style="font-size: 12px; color: #999; margin: 5px 0 0;">账号作为唯一标识，不可修改</p>
        </el-form-item>

        <el-form-item label="用户名">
          <el-input v-model="editForm.username" placeholder="请输入显示的用户名" />
        </el-form-item>

        <el-form-item :label="isAdding ? '初始密码' : '重置密码'">
          <el-input
            v-model="editForm.password"
            type="password"
            :placeholder="isAdding ? '请输入登录密码' : '若不修改请留空'"
            show-password
          />
        </el-form-item>

        <el-form-item label="角色" v-if="isAdding">
          <el-select v-model="editForm.typeId" style="width: 100%;">
            <el-option :value="2" label="操作员" />
            <el-option :value="1" label="管理员" />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="editDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="submitLoading" @click="submitEdit">保存修改</el-button>
        </span>
      </template>
    </el-dialog>

    <el-dialog
      v-model="roleDialogVisible"
      title="权限级别调整"
      width="400px"
      append-to-body
    >
      <div style="padding: 10px 20px; text-align: center;">
        <p style="margin-bottom: 20px; color: #606266;">
          正在调整用户 <strong style="color: #409EFF;">{{ roleTarget.username }}</strong> 的系统权限
        </p>

        <el-radio-group v-model="roleTarget.typeId">
          <el-radio :value="2" border size="large">操作员</el-radio>
          <el-radio :value="1" border size="large">管理员</el-radio>
        </el-radio-group>

        <p style="margin-top: 20px; font-size: 12px; color: #f56c6c;">
          * 管理员拥有删除用户及修改系统配置的权限，请谨慎操作
        </p>
      </div>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="roleDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="roleLoading" @click="submitRoleUpdate">确认变更</el-button>
        </span>
      </template>
    </el-dialog>

    <el-dialog
      v-model="importDialogVisible"
      title="批量导入用户"
      width="500px"
      append-to-body
    >
      <div style="padding: 10px 20px;">
        <el-upload
          ref="uploadRef"
          drag
          :auto-upload="false"
          :limit="1"
          accept=".csv"
          :on-change="handleFileChange"
          :on-remove="handleFileRemove"
        >
          <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
          <div class="el-upload__text">
            将 CSV 文件拖到此处，或<em>点击上传</em>
          </div>
          <template #tip>
            <div class="el-upload__tip">
              CSV 表头需包含：username, password，可选 role（admin/operator）
            </div>
          </template>
        </el-upload>
      </div>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="importDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="importLoading" :disabled="!uploadFile" @click="submitImport">开始导入</el-button>
        </span>
      </template>
    </el-dialog>

    <el-dialog
      v-model="importResultVisible"
      title="导入结果"
      width="500px"
      append-to-body
    >
      <div style="padding: 10px 20px;">
        <el-result :icon="importResult.failCount > 0 ? 'warning' : 'success'">
          <template #title>
            成功 {{ importResult.successCount }} 条，失败 {{ importResult.failCount }} 条
          </template>
        </el-result>
        <div v-if="importResult.failList && importResult.failList.length > 0" style="margin-top: 10px;">
          <p style="color: #f56c6c; font-weight: bold;">失败详情：</p>
          <div v-for="(item, idx) in importResult.failList" :key="idx" style="font-size: 13px; color: #909399; margin: 4px 0;">
            第 {{ item.row }} 行：{{ item.reason }}
          </div>
        </div>
      </div>

      <template #footer>
        <el-button type="primary" @click="importResultVisible = false">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { User, Avatar, CircleCheck, Warning, UploadFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile, UploadInstance } from 'element-plus'
import request from '@/utils/request'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const router = useRouter()
const currentUserTypeId = ref(0)
const isAdmin = computed(() => currentUserTypeId.value === 1)

const adminCount = computed(() => tableData.value.filter(u => u.typeId === 1).length)
const normalCount = computed(() => tableData.value.filter(u => !u.isLock).length)
const lockedCount = computed(() => tableData.value.filter(u => u.isLock).length)

const fetchCurrentUserRole = async () => {
  try {
    const res = await request.get('/user/me')
    if (res.code === 200 && res.data) {
      currentUserTypeId.value = res.data.typeId || 0
      if (currentUserTypeId.value !== 1) {
        ElMessage.warning('无权访问用户管理页面')
        router.replace('/HardWorkPage')
      }
    }
  } catch {
    currentUserTypeId.value = 0
    router.replace('/login')
  }
}

const searchKeyword = ref('')
const searchTypeId = ref(0)
const loading = ref(false)

interface UserRow {
  id: number
  account: string
  username: string
  name: string
  typeId: number
  typeLabel: string
  headImage: string
  isLock: boolean
  birthday: string
  sex: number
  creatorId: number
  createtime: string
  locktime: string
  modifytime: string
  delFlag: boolean
  notes: string
}

const tableData = ref<UserRow[]>([])

const loadUsers = async () => {
  loading.value = true
  try {
    const params: Record<string, any> = { keyword: searchKeyword.value }
    if (searchTypeId.value) {
      params.type_id = searchTypeId.value
    }
    const res = await request.get('/user/', { params })
    if (res.code === 200) {
      tableData.value = res.data || []
    }
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await fetchCurrentUserRole()
  loadUsers()
})

const handleQuery = () => {
  loadUsers()
}

const editDialogVisible = ref(false)
const isAdding = ref(false)
const submitLoading = ref(false)
const editForm = reactive({
  id: 0,
  account: '',
  username: '',
  password: '',
  typeId: 2,
})

const resetEditForm = () => {
  editForm.id = 0
  editForm.account = ''
  editForm.username = ''
  editForm.password = ''
  editForm.typeId = 2
}

const handleAddUser = () => {
  isAdding.value = true
  resetEditForm()
  editDialogVisible.value = true
}

const handleEdit = (row: UserRow) => {
  isAdding.value = false
  editForm.id = row.id
  editForm.account = row.account
  editForm.username = row.username
  editForm.password = ''
  editForm.typeId = row.typeId
  editDialogVisible.value = true
}

const submitEdit = async () => {
  if (!editForm.account || !editForm.username) {
    ElMessage.error('账号和用户名不能为空')
    return
  }

  submitLoading.value = true
  try {
    if (isAdding.value) {
      if (!editForm.password || editForm.password.length < 6) {
        ElMessage.error('密码至少需要 6 位')
        submitLoading.value = false
        return
      }
      await request.post('/user/', {
        username: editForm.account,
        name: editForm.username,
        password: editForm.password,
        type_id: editForm.typeId,
      })
      ElMessage.success('用户创建成功')
    } else {
      const body: Record<string, any> = {
        username: editForm.account,
        name: editForm.username,
      }
      if (editForm.password) {
        body.password = editForm.password
      }
      await request.put(`/user/${editForm.id}`, body)
      ElMessage.success('信息更新成功')
    }
    editDialogVisible.value = false
    loadUsers()
  } finally {
    submitLoading.value = false
  }
}

const handleDelete = (row: UserRow) => {
  if (userStore.account === row.account) {
    ElMessage.warning('不能删除当前登录用户')
    return
  }
  if (row.account === 'admin') {
    ElMessage.warning('admin 账号不允许删除')
    return
  }

  ElMessageBox.confirm(`确定要删除用户 [${row.username}] 吗？`, '警告', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    try {
      await request.delete(`/user/${row.id}`)
      ElMessage.success('用户已成功删除')
      loadUsers()
    } catch {
      // 错误已由拦截器处理
    }
  }).catch(() => {})
}

const handleLock = async (row: UserRow) => {
  ElMessageBox.confirm(`确定要锁定用户 [${row.username}] 吗？锁定后该用户将无法登录。`, '锁定用户', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    try {
      await request.put(`/user/${row.id}/lock`)
      ElMessage.success(`用户 [${row.username}] 已锁定`)
      loadUsers()
    } catch {
      // 错误已由拦截器处理
    }
  }).catch(() => {})
}

const handleUnlock = async (row: UserRow) => {
  ElMessageBox.confirm(`确定要解锁用户 [${row.username}] 吗？`, '解锁用户', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'info',
  }).then(async () => {
    try {
      await request.put(`/user/${row.id}/unlock`)
      ElMessage.success(`用户 [${row.username}] 已解锁`)
      loadUsers()
    } catch {
      // 错误已由拦截器处理
    }
  }).catch(() => {})
}

const roleDialogVisible = ref(false)
const roleLoading = ref(false)
const roleTarget = reactive({ id: 0, username: '', typeId: 2 })

const handleRoleChange = (row: UserRow) => {
  if (userStore.account === row.account) {
    ElMessage.warning('不能修改自己的权限')
    return
  }
  roleTarget.id = row.id
  roleTarget.username = row.username
  roleTarget.typeId = row.typeId
  roleDialogVisible.value = true
}

const submitRoleUpdate = async () => {
  roleLoading.value = true
  try {
    await request.put(`/user/${roleTarget.id}/role`, { type_id: roleTarget.typeId })
    ElMessage.success(`权限已变更为：${roleTarget.typeId === 1 ? '管理员' : '操作员'}`)
    roleDialogVisible.value = false
    loadUsers()
  } finally {
    roleLoading.value = false
  }
}

const importDialogVisible = ref(false)
const importLoading = ref(false)
const importResultVisible = ref(false)
const importResult = reactive({ successCount: 0, failCount: 0, failList: [] as any[] })
const uploadFile = ref<File | null>(null)
const uploadRef = ref<UploadInstance>()

const handleImport = () => {
  uploadFile.value = null
  uploadRef.value?.clearFiles()
  importDialogVisible.value = true
}

const handleFileChange = (file: UploadFile) => {
  uploadFile.value = file.raw || null
}

const handleFileRemove = () => {
  uploadFile.value = null
}

const submitImport = async () => {
  if (!uploadFile.value) {
    ElMessage.warning('请先选择 CSV 文件')
    return
  }

  importLoading.value = true
  try {
    const formData = new FormData()
    formData.append('file', uploadFile.value)
    const response = await fetch('/api/user/import', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${userStore.token}`,
      },
      body: formData,
    })
    const res = await response.json()
    if (res.code === 200) {
      importResult.successCount = res.data.successCount
      importResult.failCount = res.data.failCount
      importResult.failList = res.data.failList || []
      importDialogVisible.value = false
      importResultVisible.value = true
      loadUsers()
    } else {
      ElMessage.error(res.message || res.detail || '导入失败')
    }
  } catch {
    ElMessage.error('导入失败，请检查网络连接')
  } finally {
    importLoading.value = false
  }
}

const handleExport = async () => {
  try {
    const response = await fetch('/api/user/export', {
      headers: {
        Authorization: `Bearer ${userStore.token}`,
      },
    })
    if (!response.ok) {
      const err = await response.json()
      ElMessage.error(err.detail || '导出失败')
      return
    }
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'users_export.csv'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    ElMessage.success('报表导出成功')
  } catch {
    ElMessage.error('导出失败，请检查网络连接')
  }
}
</script>

<style scoped>
.user-manage-container {
  padding: 20px;
  background-color: #f5f7fa;
  min-height: calc(100vh - 60px);
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

.dashboard-row { margin-bottom: 20px; }
.data-card { border: none; border-radius: 8px; transition: all 0.3s; }
.data-card:hover { transform: translateY(-3px); }
.border-blue { border-top: 4px solid #409eff; }
.border-green { border-top: 4px solid #67c23a; }
.border-red { border-top: 4px solid #f56c6c; }
.border-orange { border-top: 4px solid #e6a23c; }

.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
.card-title { font-size: 14px; color: #606266; font-weight: bold; }
.card-icon { font-size: 22px; }
.card-value { font-size: 26px; font-weight: bold; color: #303133; margin-bottom: 8px; }
.card-desc { font-size: 12px; color: #909399; }

.success-text { color: #67c23a; }
.danger-text { color: #f56c6c; }
.warning-text { color: #e6a23c; }

.main-card { border-radius: 8px; border: none; }
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 25px;
}

.toolbar :deep(.el-button) { margin-left: 0 !important; }

.search-input { width: 220px; }
.search-select { width: 130px; }

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

.user-table { margin-bottom: 20px; }

.user-table :deep(.op-btn) {
  width: 72px;
  height: 28px;
  padding: 0 !important;
  justify-content: center;
  align-items: center;
  display: inline-flex;
  font-size: 13px;
  margin: 0 4px !important;
}

.user-table :deep(.op-btn-long) {
  width: 90px;
  height: 28px;
  padding: 0 !important;
  justify-content: center;
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
