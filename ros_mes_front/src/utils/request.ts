import axios from "axios";
import qs from "qs";
import router from "@/router";
import { ElMessage } from "element-plus";

const service = axios.create({
  baseURL: "/api",
  timeout: 15000,
  headers: {
    "Content-Type": "application/json;charset=utf-8",
  },
});

const whiteList = ["/login", "/register"];

service.interceptors.request.use(
  (config) => {
    const url = config.url || "";

    if (url.includes("/login")) {
      config.data = qs.stringify(config.data);
      config.headers["Content-Type"] = "application/x-www-form-urlencoded";
    } else {
      config.headers["Content-Type"] = "application/json;charset=utf-8";
    }

    const isWhiteApi = whiteList.some((item) => url.includes(item));

    if (!isWhiteApi) {
      const token = localStorage.getItem("token");

      if (!token) {
        ElMessage.error("请先登录");
        router.replace("/login");
        return Promise.reject(new Error("请先登录"));
      }
      console.log("当前请求：", config.url, "当前 token：", token);
      config.headers["Authorization"] = `Bearer ${token}`;
    }

    return config;
  },
  (error) => Promise.reject(error)
);

service.interceptors.response.use(
  (res) => res.data,
  (error) => {
    const status = error.response?.status;
    const detail = error.response?.data?.detail;
    const message = error.response?.data?.message;

    if (status === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("account");
      localStorage.removeItem("updateTime");

      ElMessage.error("登录已过期，请重新登录");
      router.replace("/login");
    } else if (detail || message) {
      ElMessage.error(detail || message);
    }

    return Promise.reject(error);
  }
);

export default service;