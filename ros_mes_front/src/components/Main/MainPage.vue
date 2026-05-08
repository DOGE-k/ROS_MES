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
            <el-icon><User /></el-icon>
            <span class="header-account">{{ userStore.account }}</span>
            <el-button type="danger" size="small" plain @click="handleLogout">退出登录</el-button>
          </div>
        </el-header>
        <el-main><router-view></router-view></el-main>
      </el-container>
    </el-container>
  </div>
</template>


<script lang="ts" setup>
import { useRouter } from 'vue-router'
import { Fold, Expand, User } from '@element-plus/icons-vue'
import Aside from '../Main/AsidePage.vue';
import { useLayoutSettingStore } from '@/stores/layoutSetting';
import { useUserStore } from '@/stores/user';
import { ElMessageBox } from 'element-plus';

const router = useRouter()
const layoutStore = useLayoutSettingStore();
const userStore = useUserStore();

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

.header-account {
  font-weight: 500;
}
</style>