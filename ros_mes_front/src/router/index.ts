import { createRouter, createWebHistory } from "vue-router";
import routes from "./routes";

const router = createRouter({
  history: createWebHistory(),
  routes,
});

const whiteList = ["/login", "/register"];

router.beforeEach((to) => {
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