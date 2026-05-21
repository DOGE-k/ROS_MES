<template>
  <div class="common-layout" style="height:100%">
    <el-container style="height:100%">
       <el-aside :width="layoutStore.fold ? '64px' : '220px'" style="transition: width 0.3s ease;"><Aside></Aside></el-aside>
      <el-container>
        <el-header class="main-header">
          <div class="header-left">
            <el-icon class="fold-icon" @click="layoutStore.toggleFold">
              <Fold v-if="!layoutStore.fold" />
              <Expand v-else />
            </el-icon>
          </div>
          <div class="header-right">
            <el-button
              type="success"
              size="small"
              :icon="Link"
              :loading="serialTesting"
              plain
              @click="handleTestSerial"
            >串口连接测试</el-button>
            <el-avatar :size="32" :src="userStore.avatar || ''" class="header-avatar">
              <el-icon><User /></el-icon>
            </el-avatar>
            <span class="header-nickname">{{ userStore.nickname || userStore.account }}</span>
            <el-button type="danger" size="small" plain @click="handleLogout">退出登录</el-button>
          </div>
        </el-header>
        <el-main><router-view></router-view></el-main>
      </el-container>
    </el-container>
  </div>
</template>


<script lang="ts" setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Fold, Expand, User, Link } from '@element-plus/icons-vue'
import Aside from '../Main/AsidePage.vue';
import { useLayoutSettingStore } from '@/stores/layoutSetting';
import { useUserStore } from '@/stores/user';
import { ElMessageBox, ElMessage } from 'element-plus';
import { testSerialConnection } from '@/api/rosApi';

const router = useRouter()
const layoutStore = useLayoutSettingStore();
const userStore = useUserStore();

const serialTesting = ref(false)

const handleTestSerial = async () => {
  serialTesting.value = true
  try {
    const res = await testSerialConnection()
    const data = res.data
    if (data.success && data.data?.connected) {
      ElMessage.success({
        message: data.data?.message || '串口连接测试成功',
        duration: 4000,
      })
    } else if (data.success) {
      ElMessage.warning({
        message: data.data?.message || '串口物理连接正常，未收到下位机响应',
        duration: 5000,
      })
    } else {
      ElMessage.error({
        message: data.data?.message || '串口连接测试失败',
        duration: 5000,
      })
    }
  } catch {
    ElMessage.error('串口连接测试请求失败，请检查网络连接或后端服务')
  } finally {
    serialTesting.value = false
  }
}

const handleLogout = async () => {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }

  userStore.clearUser()
  router.replace('/login')
}
</script>

<style>
.common-layout{
  height: 100%;
  width: 100%;
  background-color: #ffff;
}
.common-layout .el-container{
  background-color: #eff5f4;
  height: 100%;
}
.common-layout .el-header {
  padding: 0;
  height: 60px;
}

.main-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  padding: 0 20px;
}

.header-left {
  display: flex;
  align-items: center;
}

.fold-icon {
  font-size: 20px;
  cursor: pointer;
  color: #606266;
  transition: color 0.2s;
}

.fold-icon:hover {
  color: #409eff;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #606266;
  font-size: 14px;
}

.header-avatar {
  flex-shrink: 0;
}

.header-nickname {
  font-weight: 500;
}
</style>
