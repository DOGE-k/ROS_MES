<template>
  <router-view/>
</template>

<script>
export default {
  name: 'App'
}
</script>

<style>
html,body{
  margin: 0;
  padding:0;
  box-sizing: border-box;
  width: 100%;
  height: 100%;
}
#app {
  width: 100%;
  height: 100%;
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: #2c3e50;
  overflow: auto;
}

/* 全局容器：锁死视口高度 */
/* .dashboard-container {
  height: 100vh;
  width: 100vw;
  background-color: #f0f2f5;
  position: relative;
  overflow: hidden !important; 
}

.right-layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: #f0f2f5;
  overflow: hidden !important;
}

.global-header {
  background-color: #ffffff;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  align-items: center;
  padding: 0 20px;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
  z-index: 10;
  flex-shrink: 0;
}
.toggle-btn {
  cursor: pointer;
  color: #606266;
  display: flex;
  align-items: center;
  transition: color 0.3s;
} */


</style>
