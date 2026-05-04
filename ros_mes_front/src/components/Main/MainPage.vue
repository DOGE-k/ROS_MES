<template>
  <div class="common-layout" style="height:100%">
    <el-container style="height:100%">
       <el-aside :width="layoutStore.fold ? '64px' : '220px'" style="transition: width 0.3s ease;"><Aside></Aside></el-aside>
      <el-container>
        <el-main><router-view></router-view></el-main>
      </el-container>
    </el-container>
  </div>
</template>


<script lang="ts" setup>
import Aside from '../Main/AsidePage.vue';
import { useLayoutSettingStore } from '@/stores/layoutSetting';


const layoutStore = useLayoutSettingStore();
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
  /* margin: 0; */
  height: 60px;
}
</style>