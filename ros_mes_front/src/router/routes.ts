import LoginPage from "../components/Login/LoginPage.vue";
import MainPage from "../components/Main/MainPage.vue";
import HardWorkPage from "../components/Main/Hardwork/HardWorkPage.vue";
import FineTuningPage from "../components/Main/ModulePage/FineTuningPage.vue";
import ModuleManagement from "../components/Main/ModulePage/ModuleManagement.vue";
import RegisterPage from "../components/Login/RegisterPage.vue";
import UserManagement from "../components/Main/UserManage/UserManagement.vue";
import Profile from '../components/Main/UserManage/Profile.vue'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: LoginPage
  },
  {
    path: '/register', // 2. 给注册页分配路径
    name: 'Register',
    component: RegisterPage
  },
  {
    path: '/',
    name: 'Main',
    component: MainPage,
    redirect: '/HardWorkPage',  // 默认显示硬件信息管理页面
    children: [
      {
        path: '/HardWorkPage',
        name: 'HardWorkPage',
        component: HardWorkPage,
        meta: {
          // 设备信息管理菜单的激活key
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
        path: '/UserManagement',
        name: 'UserManagement',
        component: UserManagement,
        meta: {
          activeMenu: '/UserManagement' // 用于让侧边栏高亮
        }
      },
      {
        path: '/Profile',
        name: 'Profile',
        component: Profile,
        meta: { activeMenu: '/Profile' }
      },
    ]
  }
]



export default routes