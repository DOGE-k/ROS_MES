import { defineStore } from "pinia";
import {ref} from "vue";

export const useUserStore = defineStore('user', () => {
    // const userinfo = ref({
    //     account : '',
    //     password : '',
    //     token: '',
    //     updateToken: ''
    // })
    //
    // const setUserInfo = (data: any) =>{
    //     userinfo.value = data
    // }
    // return { userinfo, setUserInfo }

    const account = ref('');
    const token = ref('');
    const updateTime = ref('');

    const setUserInfo = (data: { account: string; token: string; updateTime: string }) => {
        account.value = data.account;
        token.value = data.token;
        updateTime.value = data.updateTime;
        // 同步到 localStorage
        localStorage.setItem('token', data.token);
        localStorage.setItem('account', data.account);
        localStorage.setItem('updateTime', data.updateTime);
    };

    const clearUser = () => {
        account.value = '';
        token.value = '';
        updateTime.value = '';
        localStorage.removeItem('token');
        localStorage.removeItem('account');
        localStorage.removeItem('updateTime');
    };


    const isTokenExpired = () => {
        if (!updateTime.value) return true;
        const now = Date.now();
        const last = new Date(updateTime.value).getTime();
        const threeDays = 3 * 24 * 60 * 60 * 1000;
        return now - last > threeDays;
    };

    return { account, token, updateTime, setUserInfo, clearUser, isTokenExpired };
})