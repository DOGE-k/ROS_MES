import { defineStore } from 'pinia';
import { ref } from 'vue';

// 跳过图纸只在本次打开应用有效；真实/模拟连接由后端页面配置独立管理。
export const useDebugSettingsStore = defineStore('debugSettings', () => {
  const skipDrawingBinding = ref(false);

  const reset = () => {
    skipDrawingBinding.value = false;
  };

  return { skipDrawingBinding, reset };
});
