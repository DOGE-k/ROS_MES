import { defineStore } from "pinia";
import { ref } from "vue";

interface UserInfo {
  account: string;
  nickname?: string;
  role?: string;
  typeId?: number;
  name?: string;
  token: string;
  avatar?: string;
  headImage?: string;
  updateTime: string;
}

export const useUserStore = defineStore("user", () => {
  const account = ref(localStorage.getItem("account") || "");
  const nickname = ref(localStorage.getItem("nickname") || "");
  const role = ref(localStorage.getItem("role") || "");
  const token = ref(localStorage.getItem("token") || "");
  const avatar = ref(localStorage.getItem("avatar") || "");
  const updateTime = ref(localStorage.getItem("updateTime") || "");

  const setUserInfo = (data: UserInfo) => {
    account.value = data.account;
    nickname.value = data.nickname || data.name || data.account;
    role.value = data.typeId === 1 ? "admin" : (data.role || "");
    token.value = data.token;
    avatar.value = data.avatar || data.headImage || "";
    updateTime.value = data.updateTime;

    localStorage.setItem("account", data.account);
    localStorage.setItem("nickname", data.nickname || data.name || data.account);
    localStorage.setItem("role", data.typeId === 1 ? "admin" : (data.role || ""));
    localStorage.setItem("token", data.token);
    localStorage.setItem("avatar", data.avatar || data.headImage || "");
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
