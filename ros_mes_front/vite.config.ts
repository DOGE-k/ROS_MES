import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    // 配置 @ 别名（指向 src 目录）
    alias: {
      '@': path.resolve(__dirname, 'src')
    }
  },
  // 👇 👇 👇 核心：请求代理配置
  server: {
    host: '0.0.0.0', // 允许局域网访问
    port: 5173,      // 项目端口
    open: true,      // 自动打开浏览器
    proxy: {
      // 所有 /api 开头的请求都会被代理
      '/api': {
        target: 'http://127.0.0.1:8000', // 👈 你的后端真实地址
        changeOrigin: true               // 开启跨域
        
      }
    }
  }
})