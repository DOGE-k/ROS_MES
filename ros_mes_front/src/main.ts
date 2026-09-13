//前端入口
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
// 注意：全局设计系统必须在 Element Plus 样式之后引入，才能覆盖其主题变量
import './style.css'
import App from './App.vue'
import router from './router'
import { createPinia } from 'pinia'

const pinia = createPinia()
createApp(App).use(router).use(ElementPlus).use(pinia).mount('#app')
