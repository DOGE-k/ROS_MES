import { defineStore } from "pinia";
import { ref } from "vue";
import type { LoginResponse } from "@/api/types";

export const useUserStore = defineStore("user", () => {
  const account = ref(localStorage.getItem("account") || "");
  const nickname = ref(localStorage.getItem("nickname") || "");
  const role = ref(localStorage.getItem("role") || "");
  const token = ref(localStorage.getItem("token") || "");
  const avatar = ref(localStorage.getItem("avatar") || "");
  const updateTime = ref(localStorage.getItem("updateTime") || "");

  // 入参为登录接口返回的 data，字段见《ROS_MES_前后端接口字段文档》5.1
  const setUserInfo = (data: LoginResponse) => {
    account.value = data.account;
    nickname.value = data.name || data.account;
    role.value = data.typeId === 1 ? "admin" : "";
    token.value = data.token;
    avatar.value = data.headImage || "";
    updateTime.value = data.updateTime;

    localStorage.setItem("account", data.account);
    localStorage.setItem("nickname", data.name || data.account);
    localStorage.setItem("role", data.typeId === 1 ? "admin" : "");
    localStorage.setItem("token", data.token);
    localStorage.setItem("avatar", data.headImage || "");
    localStorage.setItem("updateTime", data.updateTime);
  };

  const clearUser = () => {
    account.value = "";
    nickname.value = "";
    role.value = "";
    token.value = "";
    avatar.value = "";
    updateTime.value = "";

    localStorage.removeItem("account");
    localStorage.removeItem("nickname");
    localStorage.removeItem("role");
    localStorage.removeItem("token");
    localStorage.removeItem("avatar");
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
    nickname,
    role,
    token,
    avatar,
    updateTime,
    setUserInfo,
    clearUser,
    isLogin,
    isAdmin,
  };
});
