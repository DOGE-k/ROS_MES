import { defineStore } from 'pinia';
import { ref } from 'vue';

export const useLayoutSettingStore = defineStore('layoutSetting', () => {
    // 菜单折叠状态: false=展开, true=收起
    const fold = ref(false);

    const toggleFold = () => {
        fold.value = !fold.value;
    };

    const setFold = (value: boolean) => {
        fold.value = value;
    };

    return { fold, toggleFold, setFold };
});