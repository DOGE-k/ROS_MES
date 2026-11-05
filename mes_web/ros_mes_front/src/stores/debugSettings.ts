import { defineStore } from 'pinia';
import { ref } from 'vue';

// 仅本次打开应用有效；刷新后重新创建状态，不改变无 ROS 模拟开关。
export const useDebugSettingsStore = defineStore('debugSettings', () => {
  const skipDrawingBinding = ref(false);

  const reset = () => {
    skipDrawingBinding.value = false;
  };

  return { skipDrawingBinding, reset };
});
