import { createRouter, createWebHistory } from "vue-router";
import routes from "./routes";

const router = createRouter({
  history: createWebHistory(),
  routes,
});

// 开发阶段：mock 模式下不检查登录
const isMock = import.meta.env.VITE_USE_MOCK === "true";

const whiteList = [
  "/login",
  "/register",
  "/RosTestPage",
];

router.beforeEach((to) => {
  if (isMock) {
    return true;
  }

  const token = localStorage.getItem("token");

  if (whiteList.includes(to.path)) {
    return true;
  }

  if (!token) {
    return "/login";
  }

  return true;
});

export default router;