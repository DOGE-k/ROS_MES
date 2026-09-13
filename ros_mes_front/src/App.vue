<template>
  <el-config-provider :locale="locale">
    <router-view/>
  </el-config-provider>
</template>

<script setup>
import zhCn from 'element-plus/es/locale/lang/zh-cn'

const locale = zhCn
</script>

<style>
#app {
  width: 100%;
  height: 100%;
  overflow: auto;
}
</style>
