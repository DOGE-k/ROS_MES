import { createRouter, createWebHistory } from 'vue-router'
import routes from './routes'
import {useUserStore} from "../stores/user";

const router = createRouter({
  history: createWebHistory(),
  routes
});


export default router