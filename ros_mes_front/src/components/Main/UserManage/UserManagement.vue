<template>
  <div class="user-manage-container">
    
    <el-row :gutter="20" class="dashboard-row">
      <el-col :span="6">
        <el-card shadow="hover" class="data-card border-blue">
          <div class="card-header">
            <span class="card-title">设备状态</span>
            <el-icon class="card-icon" color="#409eff"><Cpu /></el-icon>
          </div>
          <div class="card-value">36 / 40</div>
          <div class="card-desc">正常运行 / 总台数</div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover" class="data-card border-green">
          <div class="card-header">
            <span class="card-title">实时任务</span>
            <el-icon class="card-icon" color="#67c23a"><List /></el-icon>
          </div>
          <div class="card-value success-text">115</div>
          <div class="card-desc">当前进行中任务数量</div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover" class="data-card border-red">
          <div class="card-header">
            <span class="card-title">待处理故障</span>
            <el-icon class="card-icon" color="#f56c6c"><Warning /></el-icon>
          </div>
          <div class="card-value danger-text">0</div>
          <div class="card-desc">待确认告警数量</div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover" class="data-card border-orange">
          <div class="card-header">
            <span class="card-title">在线用户</span>
            <el-icon class="card-icon" color="#e6a23c"><User /></el-icon>
          </div>
          <div class="card-value warning-text">{{ onlineUserCount }}</div>
          <div class="card-desc">当前状态正常的用户总数</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="main-card">
      
      <div class="toolbar">
        <el-input 
          v-model="searchKeyword" 
          placeholder="请输入账号/姓名" 
          clearable 
          class="search-input"
        />
        
        <el-select v-model="searchRole" placeholder="全部角色" class="search-select">
          <el-option label="全部角色" value="" />
          <el-option label="管理员" value="admin" />
          <el-option label="操作员" value="operator" />
        </el-select>
        
        <el-button type="primary" class="toolbar-btn query-btn" @click="handleQuery">查询</el-button>

        <el-divider direction="vertical" class="toolbar-divider" />

        <el-button type="primary" plain class="toolbar-btn" @click="handleAddUser">新增用户</el-button>
        <el-button type="success" plain class="toolbar-btn" @click="handleImport">批量导入</el-button>
        <el-button plain class="toolbar-btn" @click="handleExport">导出报表</el-button>
      </div>

      <el-table 
        :data="displayData" 
        border 
        stripe 
        style="width: 100%" 
        class="user-table"
        :header-cell-style="{ backgroundColor: '#fafafa', color: '#333', fontWeight: 'bold' }"
      >
        <el-table-column type="index" label="序号" width="60" align="center" />
        <el-table-column prop="account" label="账号" width="130" />
        <el-table-column prop="username" label="用户名" width="130" />
        
        <el-table-column label="角色" width="120" align="center">
          <template #default="scope">
            <el-tag :type="scope.row.role === 'admin' ? 'danger' : 'info'" effect="light">
              {{ scope.row.role === 'admin' ? '管理员' : '操作员' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="状态" width="100" align="center">
          <template #default="scope">
            <el-tag v-if="scope.row.status === 0" type="success" size="small">正常</el-tag>
            <el-tag v-else type="danger" size="small" effect="dark">已锁定</el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="lastLogin" label="最后登录时间" width="180" align="center" />

        <el-table-column label="操作" min-width="260" align="center">
          <template #default="scope">
            <el-button size="small" type="primary" plain class="op-btn" @click="handleEdit(scope.row)">编辑</el-button>
            
            <el-button 
              v-if="scope.row.status === 0" 
              size="small" 
              type="danger" 
              plain 
              class="op-btn"
              @click="toggleStatus(scope.row)"
            >锁定</el-button>
            
            <el-button 
              v-else 
              size="small" 
              type="success" 
              plain 
              class="op-btn"
              @click="toggleStatus(scope.row)"
            >解锁</el-button>
            
            <el-button size="small" type="warning" plain class="op-btn-long" @click="handleRoleChange(scope.row)">修改权限</el-button>
            
            <el-button 
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
        <el-pagination
          background
          layout="prev, pager, next"
          :total="tableData.length"
        />
      </div>
      <el-dialog 
      v-model="editDialogVisible" 
      :title="isAdding ? '添加新用户' : '修改个人信息'"
      width="450px"
      append-to-body
      destroy-on-close
    >
      <el-form :model="currentUser" label-width="80px" style="padding: 10px 20px 0;">
        <el-form-item label="账号">
          <el-input v-model="currentUser.account" :disabled="!isAdding" placeholder="请输入系统登录账号" />
          <p v-if="!isAdding" style="font-size: 12px; color: #999; margin: 5px 0 0;">账号作为唯一标识，不可修改</p>
        </el-form-item>
        
        <el-form-item label="用户名">
          <el-input v-model="currentUser.username" placeholder="请输入显示的用户名" />
        </el-form-item>

        <el-form-item :label="isAdding ? '初始密码' : '重置密码'">
          <el-input 
            v-model="currentUser.password" 
            type="password" 
            :placeholder="isAdding ? '请输入登录密码' : '若不修改请留空'" 
            show-password 
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="editDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitEdit">保存修改</el-button>
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
          正在调整用户 <strong style="color: #409EFF;">{{ currentUser.username }}</strong> 的系统权限
        </p>
        
        <el-radio-group v-model="currentUser.role">
          <el-radio label="operator" border size="large">操作员</el-radio>
          <el-radio label="admin" border size="large">管理员</el-radio>
        </el-radio-group>
        
        <p style="margin-top: 20px; font-size: 12px; color: #f56c6c;">
          * 管理员拥有删除用户及修改系统配置的权限，请谨慎操作
        </p>
      </div>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="roleDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitRoleUpdate">确认变更</el-button>
        </span>
      </template>
    </el-dialog>
    </el-card>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive } from 'vue'
import { Cpu, List, Warning, User, Unlock, Lock} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

// --- 1. 搜索栏变量 ---
const searchKeyword = ref('')
const searchRole = ref('')

// --- 2. 弹窗控制与表单数据 ---
const editDialogVisible = ref(false)
const roleDialogVisible = ref(false)
const isAdding = ref(false) // 判断当前是“新增”还是“编辑”模式
const currentUser = reactive({
  id: 0,
  account: '',
  username: '',
  role: 'operator',
  status: 0,
  password: '',
  lastLogin: '' 
})

// --- 3. 原始数据源 ---
const tableData = ref([
  { id: 1, account: 'admin', username: '操作员A', role: 'admin', status: 0, lastLogin: '2026-04-25 10:00:00' },
  { id: 2, account: 'op_001', username: '操作员A', role: 'operator', status: 0, lastLogin: '2026-04-24 16:30:22' },
  { id: 3, account: 'op_002', username: '操作员B', role: 'operator', status: 1, lastLogin: '2026-04-20 09:15:00' },
  { id: 4, account: 'op_003', username: '操作员C', role: 'operator', status: 0, lastLogin: '2026-04-25 08:00:00' }
])

// --- 4. 计算属性 ---
const displayData = computed(() => {
  return tableData.value.filter(item => {
    // 使用 toLowerCase() 实现不区分大小写的模糊搜索
    const key = searchKeyword.value.toLowerCase()
    const matchKeyword = item.account.toLowerCase().includes(key) || 
                         item.username.toLowerCase().includes(key)
    const matchRole = searchRole.value === '' || item.role === searchRole.value
    return matchKeyword && matchRole
  })
})

//动态统计在线用户（状态为正常的用户）
const onlineUserCount = computed(() => {
  return tableData.value.filter(user => user.status === 0).length
})

// --- 5. 操作函数 ---

// 点击查询
const handleQuery = () => {
  // 因为我们用了 computed(displayData)，其实数据已经实时过滤了
  // 这里可以写一个反馈，让用户知道查询已执行
  ElMessage.success(`已根据关键词 [${searchKeyword.value}] 过滤数据`)
}

// 新增用户入口函数
const handleAddUser = () => {
  isAdding.value = true
  // 重置表单
  Object.assign(currentUser, { id: Date.now(), account: '', username: '', role: 'operator', status: 0, password: '' })
  editDialogVisible.value = true
}

//  批量导入 (先留个坑，实现点击反馈)
const handleImport = () => {
  ElMessageBox.alert('请选择符合 MES 标准格式的 Excel 文件进行上传', '批量导入', {
    confirmButtonText: '我知道了'
  })
}

//  导出报表
const handleExport = () => {
  ElMessage.warning('报表生成中，请稍后...')
}

// 编辑用户信息入口
const handleEdit = (row: any) => {
  isAdding.value = false
  Object.assign(currentUser, row)
  currentUser.password = '' // 编辑时密码初始留空
  editDialogVisible.value = true
}

// 保存/提交修改函数 (对应弹窗里的“保存”按钮)
const submitEdit = () => {
  if (!currentUser.account || !currentUser.username) {
    ElMessage.error('账号和用户名不能为空')
    return
  }

  if (isAdding.value) {
    // 新增逻辑
    tableData.value.push({ ...currentUser, lastLogin: '-' })
    ElMessage.success('用户创建成功')
  } else {
    // 编辑逻辑
    const index = tableData.value.findIndex(u => u.id === currentUser.id)
    if (index !== -1) {
      tableData.value[index] = { ...currentUser }
      ElMessage.success('信息更新成功')
    }
  }
  editDialogVisible.value = false
}

// 修改权限入口
const handleRoleChange = (row: any) => {
  Object.assign(currentUser, row)
  roleDialogVisible.value = true
}

// 提交权限修改
const submitRoleUpdate = () => {
  const user = tableData.value.find(u => u.id === currentUser.id)
  if (user) {
    user.role = currentUser.role
    ElMessage.success(`权限已变更为：${currentUser.role === 'admin' ? '管理员' : '操作员'}`)
    roleDialogVisible.value = false
  }
}

// 切换锁定
const toggleStatus = (row: any) => {
  const isLocking = row.status === 0
  row.status = isLocking ? 1 : 0
  ElMessage({
    message: `用户 [${row.username}] 已${isLocking ? '锁定' : '解锁'}`,
    type: isLocking ? 'warning' : 'success'
  })
}

// 删除
const handleDelete = (row: any) => {
  ElMessageBox.confirm(`确定要删除用户 [${row.username}] 吗？`, '警告', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(() => {
    tableData.value = tableData.value.filter(item => item.id !== row.id)
    ElMessage.success('用户已成功删除')
  }).catch(() => {})
}


</script>

<style scoped>
.user-manage-container {
  padding: 20px;
  background-color: #f5f7fa;
  min-height: calc(100vh - 60px);
}

/* 仪表盘卡片精修 */
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

/* 辅助颜色 */
.success-text { color: #67c23a; }
.danger-text { color: #f56c6c; }
.warning-text { color: #e6a23c; }

/* ================= 工具栏 (强制对齐与去偏移) ================= */
.main-card { border-radius: 8px; border: none; }
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px; /* 统一间距 */
  margin-bottom: 25px;
}

/* 强制清除 Element Plus 按钮默认的 margin-left 干扰 */
.toolbar :deep(.el-button) { margin-left: 0 !important; }

.search-input { width: 220px; }
.search-select { width: 130px; }

/* 顶部按钮统一样式：无图标，绝对居中 */
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

/* ================= 表格与按钮 (强制尺寸一致) ================= */
.user-table { margin-bottom: 20px; }

/* 锁定操作列按钮尺寸，确保 编辑/锁定/解锁 完全一样大 */
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

/* 修改权限文字多，略宽一点 */
.user-table :deep(.op-btn-long) {
  width: 90px;
  height: 28px;
  padding: 0 !important;
  justify-content: center;
  display: inline-flex;
  font-size: 13px;
  margin: 0 4px !important;
}

/* 分页对齐 */
.pagination-container {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  margin-top: 10px;
}
.total-text { font-size: 13px; color: #606266; margin-right: 15px; }
</style>