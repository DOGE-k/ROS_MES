<template>
  <div class="profile-container">
    <el-row :gutter="20">
      
      <el-col :span="8">
        <el-card shadow="never" class="profile-card">
          <div v-loading="loading" class="avatar-section">
            <el-upload
              class="avatar-uploader"
              action="#"
              :show-file-list="false"
              :auto-upload="false"
              accept=".png,.jpg,.jpeg,.gif,.webp"
              :on-change="handleAvatarChange">
              <el-avatar :size="120" :src="displayAvatar" class="user-avatar" />
              <div class="avatar-mask">
                <el-icon><Plus /></el-icon>
                <span>更换头像</span>
              </div>
            </el-upload>
            <h2 class="user-name">{{ userInfo.username || '未设置' }}</h2>
            <el-tag :type="userInfo.role === 'admin' ? 'danger' : 'info'">
              {{ userInfo.role === 'admin' ? '系统管理员' : userInfo.role === 'operator' ? '一线操作员' : userInfo.role }}
            </el-tag>
          </div>
          
          <el-divider />
          
          <div class="user-bio">
            <div class="bio-item">
              <el-icon><Postcard /></el-icon>
              <span>账号：{{ userInfo.account }}</span>
            </div>
            <div class="bio-item">
              <el-icon><Clock /></el-icon>
              <span>注册时间：{{ formatDate(userInfo.createdAt) }}</span>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="16">
        <el-card shadow="never" title="基础设置" class="form-card">
          <el-tabs v-model="activeTab">
            
            <el-tab-pane label="基本信息" name="info">
              <el-form :model="userInfo" label-width="100px" style="margin-top: 20px;">
                <el-form-item label="姓名">
                  <el-input v-model="userInfo.username" placeholder="请输入真实姓名" />
                </el-form-item>
                <el-form-item label="联系电话">
                  <el-input v-model="userInfo.phone" placeholder="请输入手机号" />
                </el-form-item>
                <el-form-item label="电子邮箱">
                  <el-input v-model="userInfo.email" placeholder="请输入常用邮箱" />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" :loading="saving" @click="saveBasicInfo">保存基本信息</el-button>
                </el-form-item>
              </el-form>
            </el-tab-pane>

            <el-tab-pane label="安全设置" name="security">
              <el-form :model="securityForm" label-width="100px" style="margin-top: 20px;">
                <el-form-item label="当前密码">
                  <el-input v-model="securityForm.oldPassword" type="password" show-password />
                </el-form-item>
                <el-form-item label="新密码">
                  <el-input v-model="securityForm.newPassword" type="password" show-password />
                </el-form-item>
                <el-form-item label="确认新密码">
                  <el-input v-model="securityForm.confirmPassword" type="password" show-password />
                </el-form-item>
                <el-form-item>
                  <el-button type="danger" :loading="changingPassword" @click="updatePassword">修改登录密码</el-button>
                </el-form-item>
              </el-form>
            </el-tab-pane>
            
          </el-tabs>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { Plus, Postcard, Clock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { UploadProps } from 'element-plus'
import request from '@/utils/request'

const activeTab = ref('info')
const loading = ref(true)
const saving = ref(false)
const changingPassword = ref(false)
const previewUrl = ref('')
const avatarFile = ref<File | null>(null)

const userInfo = reactive({
  id: 0,
  account: '',
  username: '',
  role: '',
  email: '',
  phone: '',
  avatar: '',
  createdAt: ''
})

const securityForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})

const displayAvatar = computed(() => {
  if (previewUrl.value) return previewUrl.value
  return userInfo.avatar || ''
})

onMounted(async () => {
  try {
    const res: any = await request.get('/user/me')
    if (res.code === 200) {
      const data = res.data
      userInfo.id = data.id
      userInfo.account = data.account
      userInfo.username = data.username
      userInfo.role = data.role
      userInfo.email = data.email || ''
      userInfo.phone = data.phone || ''
      userInfo.avatar = data.avatar || ''
      userInfo.createdAt = data.createdAt || ''
    }
  } catch {
  } finally {
    loading.value = false
  }
})

onUnmounted(() => {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
  }
})

const handleAvatarChange: UploadProps['onChange'] = (uploadFile) => {
  if (!uploadFile.raw) return

  if (!uploadFile.raw.type.startsWith('image/')) {
    ElMessage.error('上传文件必须是图片格式!')
    return
  }
  if (uploadFile.raw.size / 1024 / 1024 > 2) {
    ElMessage.error('头像图片大小不能超过 2MB!')
    return
  }

  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
  }

  avatarFile.value = uploadFile.raw
  previewUrl.value = URL.createObjectURL(uploadFile.raw)
}

const saveBasicInfo = async () => {
  saving.value = true
  try {
    if (avatarFile.value) {
      const fd = new FormData()
      fd.append('file', avatarFile.value)
      const uploadRes: any = await request.post('/user/avatar', fd)
      if (uploadRes.code === 200) {
        userInfo.avatar = uploadRes.data.avatar
        avatarFile.value = null
        URL.revokeObjectURL(previewUrl.value)
        previewUrl.value = ''
      }
    }

    const res: any = await request.put('/user/profile/me', {
      username: userInfo.username,
      email: userInfo.email,
      phone: userInfo.phone
    })
    if (res.code === 200) {
      ElMessage.success('个人资料已保存')
    }
  } catch {
  } finally {
    saving.value = false
  }
}

const updatePassword = async () => {
  if (!securityForm.oldPassword) {
    ElMessage.error('请输入当前密码')
    return
  }
  if (securityForm.newPassword !== securityForm.confirmPassword) {
    ElMessage.error('两次输入的密码不一致')
    return
  }
  if (securityForm.newPassword.length < 6) {
    ElMessage.error('新密码至少需要 6 位')
    return
  }
  changingPassword.value = true
  try {
    const res: any = await request.post('/user/password', {
      old_password: securityForm.oldPassword,
      new_password: securityForm.newPassword
    })
    if (res.code === 200) {
      ElMessage.success('密码修改成功，请牢记新密码')
      securityForm.oldPassword = ''
      securityForm.newPassword = ''
      securityForm.confirmPassword = ''
    }
  } catch {
  } finally {
    changingPassword.value = false
  }
}

function formatDate(dateStr: string): string {
  if (!dateStr) return '未知'
  return dateStr.substring(0, 10)
}
</script>

<style scoped>
.profile-container {
  padding: 20px;
  background-color: #f0f2f5;
  min-height: calc(100vh - 60px);
}

.profile-card {
  text-align: center;
  border: none;
  border-radius: 8px;
}

.avatar-section {
  padding: 20px 0;
  position: relative;
}

.avatar-uploader {
  cursor: pointer;
  position: relative;
  display: inline-block;
  border-radius: 50%;
  overflow: hidden;
}

.avatar-mask {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0,0,0,0.4);
  color: white;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  opacity: 0;
  transition: opacity 0.3s;
}

.avatar-uploader:hover .avatar-mask {
  opacity: 1;
}

.user-name {
  margin: 15px 0 10px;
  color: #303133;
}

.user-bio {
  text-align: left;
  padding: 10px 20px;
}

.bio-item {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  color: #606266;
  font-size: 14px;
}

.form-card {
  border: none;
  border-radius: 8px;
  min-height: 500px;
}

:deep(.el-tabs__item) {
  font-weight: bold;
}
</style>
