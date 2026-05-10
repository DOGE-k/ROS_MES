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

const whiteList = [
  "/login",
  "/register",
  "/send_ros",
  "/get_ros_status",
  "/hardware",
  "/module",
  "/coordination",
  "/finetuning",
];

service.interceptors.request.use(
  (config) => {
    const url = config.url || "";

    if (url.includes("/login")) {
      config.data = qs.stringify(config.data);
      config.headers["Content-Type"] = "application/x-www-form-urlencoded";
    } else if (config.data instanceof FormData) {
      delete config.headers["Content-Type"];
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
    } else {
      ElMessage.error("请求失败，请检查 API 服务是否启动");
    }

    return Promise.reject(error);
  }
);

export default service;