import { defineStore } from "pinia";
import { ref } from "vue";

interface UserInfo {
  account: string;
  token: string;
  updateTime: string;
}

export const useUserStore = defineStore("user", () => {
  const account = ref(localStorage.getItem("account") || "");
  const token = ref(localStorage.getItem("token") || "");
  const updateTime = ref(localStorage.getItem("updateTime") || "");

  const setUserInfo = (data: UserInfo) => {
    account.value = data.account;
    token.value = data.token;
    updateTime.value = data.updateTime;

    localStorage.setItem("account", data.account);
    localStorage.setItem("token", data.token);
    localStorage.setItem("updateTime", data.updateTime);
  };

  const clearUser = () => {
    account.value = "";
    token.value = "";
    updateTime.value = "";

    localStorage.removeItem("account");
    localStorage.removeItem("token");
    localStorage.removeItem("updateTime");
  };

  const isLogin = () => {
    return Boolean(token.value || localStorage.getItem("token"));
  };

  return {
    account,
    token,
    updateTime,
    setUserInfo,
    clearUser,
    isLogin,
  };
});