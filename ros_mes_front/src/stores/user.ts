import { defineStore } from "pinia";
import { ref } from "vue";

interface UserInfo {
  account: string;
  role: string;
  token: string;
  updateTime: string;
}

export const useUserStore = defineStore("user", () => {
  const account = ref(localStorage.getItem("account") || "");
  const role = ref(localStorage.getItem("role") || "");
  const token = ref(localStorage.getItem("token") || "");
  const updateTime = ref(localStorage.getItem("updateTime") || "");

  const setUserInfo = (data: UserInfo) => {
    account.value = data.account;
    role.value = data.role || "";
    token.value = data.token;
    updateTime.value = data.updateTime;

    localStorage.setItem("account", data.account);
    localStorage.setItem("role", data.role || "");
    localStorage.setItem("token", data.token);
    localStorage.setItem("updateTime", data.updateTime);
  };

  const clearUser = () => {
    account.value = "";
    role.value = "";
    token.value = "";
    updateTime.value = "";

    localStorage.removeItem("account");
    localStorage.removeItem("role");
    localStorage.removeItem("token");
    localStorage.removeItem("updateTime");
  };

  const isLogin = () => {
    return Boolean(token.value || localStorage.getItem("token"));
  };

  const isAdmin = () => {
    return role.value === "admin" || localStorage.getItem("role") === "admin";
  };

  return {
    account,
    role,
    token,
    updateTime,
    setUserInfo,
    clearUser,
    isLogin,
    isAdmin,
  };
});