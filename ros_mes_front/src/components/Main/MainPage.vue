<template>
  <div class="common-layout">
    <el-container class="layout-root">
       <el-aside :width="layoutStore.fold ? '64px' : '220px'" class="layout-aside"><Aside></Aside></el-aside>
      <el-container class="layout-body">
        <el-header class="main-header">
          <div class="header-left">
            <el-icon class="fold-icon" @click="layoutStore.toggleFold">
              <Fold v-if="!layoutStore.fold" />
              <Expand v-else />
            </el-icon>
            <span class="header-title">{{ pageTitle }}</span>
          </div>
          <div class="header-right">
            <el-button
              type="success"
              size="small"
              :icon="Link"
              :loading="serialTesting"
              plain
              round
              @click="handleTestSerial"
            >串口连接测试</el-button>

            <el-divider direction="vertical" class="header-divider" />

            <el-dropdown trigger="click" @command="handleUserCommand">
              <div class="user-chip">
                <el-avatar :size="30" :src="userStore.avatar || ''" class="header-avatar">
                  <el-icon><User /></el-icon>
                </el-avatar>
                <span class="header-nickname">{{ userStore.nickname || userStore.account }}</span>
                <el-icon class="chip-arrow"><ArrowDown /></el-icon>
              </div>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="profile">
                    <el-icon><Setting /></el-icon>个人中心
                  </el-dropdown-item>
                  <el-dropdown-item divided command="logout">
                    <el-icon><SwitchButton /></el-icon>退出登录
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </el-header>
        <el-main class="layout-main">
          <router-view v-slot="{ Component }">
            <transition name="fade-slide" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>


<script lang="ts" setup>
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Fold, Expand, User, Link, ArrowDown, Setting, SwitchButton } from '@element-plus/icons-vue'
import Aside from '../Main/AsidePage.vue';
import { useLayoutSettingStore } from '@/stores/layoutSetting';
import { useUserStore } from '@/stores/user';
import { ElMessageBox, ElMessage } from 'element-plus';
import { testSerialConnection } from '@/api/rosApi';

const router = useRouter()
const route = useRoute()
const layoutStore = useLayoutSettingStore();
const userStore = useUserStore();

const routeTitles: Record<string, string> = {
  '/Dashboard': '首页仪表盘',
  '/HardWorkPage': '设备信息管理',
  '/ModuleManagement': '模块管理',
  '/FineTuningPage': '姿态微调',
  '/DrawingManage': '图纸管理',
  '/WorkflowManage': '工作流管理',
  '/TaskManagement': '任务管理',
  '/UserManagement': '用户管理',
  '/Profile': '个人中心',
  '/RosTestPage': 'ROS 联调测试',
}

const pageTitle = computed(() => routeTitles[route.path] || '')

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

const handleUserCommand = (command: string | number | object) => {
  if (command === 'profile') {
    router.push('/Profile')
  } else if (command === 'logout') {
    handleLogout()
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
.common-layout {
  height: 100%;
  width: 100%;
}

.common-layout .layout-root {
  height: 100%;
}

.common-layout .layout-aside {
  transition: width 0.3s ease;
  overflow: hidden;
}

.common-layout .layout-body {
  height: 100%;
  background: var(--mes-bg);
}

.common-layout .el-header {
  padding: 0;
  height: 60px;
}

.main-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--mes-border);
  padding: 0 20px;
  position: sticky;
  top: 0;
  z-index: 10;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.fold-icon {
  font-size: 20px;
  cursor: pointer;
  color: var(--mes-text-sub);
  transition: color 0.2s, transform 0.2s;
  padding: 6px;
  border-radius: 8px;
}

.fold-icon:hover {
  color: var(--mes-primary);
  background: var(--el-color-primary-light-9);
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--mes-text-title);
  letter-spacing: 0.3px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--mes-text-main);
  font-size: 14px;
}

.header-divider {
  height: 18px;
}

.user-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px 4px 4px;
  border-radius: 999px;
  cursor: pointer;
  transition: background 0.2s;
  outline: none;
}

.user-chip:hover {
  background: var(--mes-bg);
}

.header-avatar {
  flex-shrink: 0;
  border: 2px solid #fff;
  box-shadow: 0 0 0 1px var(--mes-border);
}

.header-nickname {
  font-weight: 600;
  color: var(--mes-text-title);
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chip-arrow {
  font-size: 12px;
  color: var(--mes-text-faint);
}

.layout-main {
  padding: 0;
  overflow: auto;
}
</style>
