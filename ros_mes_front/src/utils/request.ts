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

const timeLimit = 3 * 24 * 60 * 60 * 1000;

service.interceptors.request.use(
  function (config) {

    if (config.url === "/login" || config.url?.includes("login")) {
        // 登录接口：必须转成表单格式满足 FastAPI OAuth2 规范
        config.data = qs.stringify(config.data);
        config.headers["Content-Type"] = "application/x-www-form-urlencoded";
    } else {
        // 非登录接口：统统使用 JSON 格式（覆盖掉之前的配置）
        // 这里不需要 qs.stringify
        config.headers["Content-Type"] = "application/json;charset=utf-8";
    }
    
    if (config.url != "/user" && config.url != "/login") {
      var token = localStorage.getItem("token");
      if (!token) {
        router.push("/login");
        ElMessage.error("请先登录");
        router.replace("/login");
        return Promise.reject(new Error("请先登录"));
      }
      var nowtime = new Date();
      var updateToken = new Date(token.slice(12));
      var diffMs = Math.abs(nowtime.getTime() - updateToken.getTime());
      if (diffMs > timeLimit) {
        router.push("/login");
        ElMessage.error("Token过期，请重新登录");
        router.replace("/login");
        return Promise.reject(new Error("Token过期，请重新登录"));
      }
      config.headers["Authorization"] = `Bearer ${token}`;
    }

    return config;
  },
  function (error) {
    return Promise.reject(error);
  },
);

// 响应拦截
service.interceptors.response.use(
  (res) => res.data,
  (err) => Promise.reject(err),
);
export default service;
