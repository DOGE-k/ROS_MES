<template>
  <div class="profile-container">
    <el-row :gutter="20">
      
      <el-col :span="8">
        <el-card shadow="never" class="profile-card">
          <div class="avatar-section">
            <el-upload
              class="avatar-uploader"
              action="#" 
              :show-file-list="false"
              :auto-upload="false"
              accept="image/*"  :on-change="handleAvatarChange" >
              <el-avatar :size="120" :src="previewAvatar || userInfo.avatar" class="user-avatar" />
              <div class="avatar-mask">
                <el-icon><Plus /></el-icon>
                <span>更换头像</span>
              </div>
            </el-upload>
            <h2 class="user-name">{{ userInfo.username }}</h2>
            <el-tag :type="userInfo.role === 'admin' ? 'danger' : 'info'">
              {{ userInfo.role === 'admin' ? '系统管理员' : '一线操作员' }}
            </el-tag>
          </div>
          
          <el-divider />
          
          <div class="user-bio">
            <div class="bio-item">
              <el-icon><Postcard /></el-icon>
              <span>工号：{{ userInfo.account }}</span>
            </div>
            <div class="bio-item">
              <el-icon><Clock /></el-icon>
              <span>入职时间：2026-03-15</span>
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
                  <el-button type="primary" @click="saveBasicInfo">保存基本信息</el-button>
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
                  <el-button type="danger" @click="updatePassword">修改登录密码</el-button>
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
import { ref, reactive } from 'vue'
import { Plus, Postcard, Clock } from '@element-plus/icons-vue'
import { ElMessage, genFileId } from 'element-plus'
import type { UploadProps } from 'element-plus'

const activeTab = ref('info')

// 【新增核心变量】用来存放实时预览的 Base64 图片字符串，初始为空
const previewAvatar = ref('')

// 模拟当前登录用户数据 (保持不动)
const userInfo = reactive({
  account: 'KE_2026',
  username: '管理员',
  role: 'admin',
  phone: '138-xxxx-xxxx',
  email: 'xxxx@university.edu',
  avatar: 'https://cube.elemecdn.com/3/7c/3ea6beec64369c2642b92c6726f1epng.png'
})

// --- 【新增核心逻辑】文件状态改变时的钩子（选择文件后触发） ---
// 使用了 Element Plus 的 UploadProps['onChange'] 类型，防止 TS 报错
const handleAvatarChange: UploadProps['onChange'] = (uploadFile) => {
  console.log('文件已选择，准备生成预览:', uploadFile)

  // 1. 安全校验 (虽然 accept="image/*" 限制了，但 JS 再校验一次更稳)
  if (!uploadFile.raw?.type.startsWith('image/')) {
    ElMessage.error('上传文件必须是图片格式!')
    return // 停止执行
  }
  
  // 校验文件大小 (示例：不超过 2MB，MES 系统中头像不宜过大)
  if (uploadFile.raw.size / 1024 / 1024 > 2) {
    ElMessage.error('头像图片大小不能超过 2MB!')
    return // 停止执行
  }

  // 2. --- 纯前端预览魔法：FileReader ---
  // 既然后端还没好，我们就把图片读成 Base64 字符串直接塞给 <el-avatar>
  const reader = new FileReader()
  
  // 必须将 raw file 转换为 Blob 才能读取
  reader.readAsDataURL(uploadFile.raw as Blob)
  
  reader.onload = (e) => {
    // 读取成功后，将生成的 Base64 赋值给预览变量
    // 这个变量一变，template 里的 :src 就会瞬间响应
    previewAvatar.value = e.target?.result as string
    console.log('Base64 生成成功，预览已更新')
    ElMessage.success('头像预览已更新，记得保存修改哦')
  }
  
  reader.onerror = () => {
    ElMessage.error('图片读取失败，请重试')
  }
}

const securityForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})

// 修改这两个函数，在保存时同步预览图（可选，为了逻辑更闭环）
const saveBasicInfo = () => {
  // 如果有预览图，则在保存时更新回 userInfo
  if(previewAvatar.value) {
    userInfo.avatar = previewAvatar.value
  }
  ElMessage.success('个人资料及头像已全站同步更新')
}

const updatePassword = () => {
  if (securityForm.newPassword !== securityForm.confirmPassword) {
    ElMessage.error('两次输入的密码不一致')
    return
  }
  ElMessage.success('密码修改成功，请牢记新密码')
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