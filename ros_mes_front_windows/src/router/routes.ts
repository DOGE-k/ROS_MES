import LoginPage from "../components/Login/LoginPage.vue";
import MainPage from "../components/Main/MainPage.vue";
import DashboardPage from "../components/Main/Dashboard/DashboardPage.vue";
import HardWorkPage from "../components/Main/Hardwork/HardWorkPage.vue";
import FineTuningPage from "../components/Main/ModulePage/FineTuningPage.vue";
import ModuleManagement from "../components/Main/ModulePage/ModuleManagement.vue";
import RegisterPage from "../components/Login/RegisterPage.vue";
import DrawingManage from "../components/Main/DrawingManage/DrawingManage.vue";
import TaskManage from "../components/Main/TaskManage/TaskManage.vue";
import UserManagement from "../components/Main/UserManage/UserManagement.vue";
import Profile from '../components/Main/UserManage/Profile.vue'
import RosTestPage from "../components/Main/RosTestPage.vue";
import WorkflowManage from "../components/Main/WorkflowManage/WorkflowManage.vue";
const routes = [
  {
    path: '/login',
    name: 'Login',
    component: LoginPage
  },
  {
    path: '/register',
    name: 'Register',
    component: RegisterPage
  },
  {
    path: '/',
    name: 'Main',
    component: MainPage,
    redirect: '/Dashboard',  // 默认显示首页仪表盘
    children: [
      {
        path: '/Dashboard',
        name: 'Dashboard',
        component: DashboardPage,
        meta: {
          activeMenu: '/Dashboard'
        }
      },
      {
        path: '/HardWorkPage',
        name: 'HardWorkPage',
        component: HardWorkPage,
        meta: {
          activeMenu: '/HardWorkPage'
        }
      },
      {
        path: '/ModuleManagement',
        name: 'ModuleManagement',
        component: ModuleManagement,
        meta: {
          // 模块管理菜单的激活key
          activeMenu: '/ModuleManagement'
        }
      },
      {
        path: '/FineTuningPage',
        name: 'FineTuningPage',
        component: FineTuningPage,
        meta: {
          // 关键：微调页也绑定模块管理的激活key
          activeMenu: '/ModuleManagement'
        }
      },
      {
        path: '/DrawingManage',
        name: 'DrawingManage',
        component: DrawingManage,
        meta: {
          activeMenu: '/DrawingManage'
        }
      },
      {
        path: '/TaskManagement',
        name: 'TaskManagement',
        component: TaskManage,
        meta: {
          activeMenu: '/TaskManagement'
        }
      },
      {
        path: '/UserManagement',
        name: 'UserManagement',
        component: UserManagement,
        meta: {
          activeMenu: '/UserManagement',
          requiresAdmin: true,
        }
      },
      {
        path: '/Profile',
        name: 'Profile',
        component: Profile,
      },
      {
        path: "/RosTestPage",
        name: "RosTestPage",
        component: RosTestPage,
        meta: {
          activeMenu: "/RosTestPage",
        },
      },
      {
        path: '/WorkflowManage',
        name: 'WorkflowManage',
        component: WorkflowManage,
        meta: {
          activeMenu: '/WorkflowManage'
        }
      },
    ]
  }
]



export default routes