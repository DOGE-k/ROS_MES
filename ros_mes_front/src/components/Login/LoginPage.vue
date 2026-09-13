<template>
  <div class="login-container">
    <!-- 左侧品牌区 -->
    <div class="brand-panel">
      <div class="brand-grid"></div>
      <div class="brand-content">
        <div class="brand-logo">
          <div class="brand-mark">
            <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <rect x="4" y="9" width="16" height="11" rx="2"/>
              <circle cx="9" cy="14.5" r="1.4" fill="currentColor" stroke="none"/>
              <circle cx="15" cy="14.5" r="1.4" fill="currentColor" stroke="none"/>
              <path d="M12 9V5"/>
              <circle cx="12" cy="3.6" r="1.4"/>
            </svg>
          </div>
          <span class="brand-name">ROS·MES</span>
        </div>

        <h1 class="brand-headline">智能制造执行系统</h1>
        <p class="brand-desc">基于 ROS 的机械臂集群调度与生产管理平台</p>

        <ul class="brand-features">
          <li>
            <span class="feature-icon">◈</span>
            <div>
              <p class="feature-title">设备全生命周期管理</p>
              <p class="feature-text">型号 / 模块 / 机械臂 / 传感器 四层设备树</p>
            </div>
          </li>
          <li>
            <span class="feature-icon">◈</span>
            <div>
              <p class="feature-title">工作流与任务调度</p>
              <p class="feature-text">图纸下发、工序编排、任务全程可追溯</p>
            </div>
          </li>
          <li>
            <span class="feature-icon">◈</span>
            <div>
              <p class="feature-title">实时姿态微调与监控</p>
              <p class="feature-text">编码器 / 压力 / 陀螺仪数据实时反馈</p>
            </div>
          </li>
        </ul>
      </div>
    </div>

    <!-- 右侧表单区 -->
    <div class="form-panel">
      <div class="login-box">
        <div class="card-header">
          <p class="title">{{ isLogin ? "欢迎登录" : "新用户注册" }}</p>
          <p class="subtitle">请使用操作员账号登录系统</p>
        </div>

        <el-form
          v-if="isLogin"
          ref="loginFormRef"
          :model="loginForm"
          :rules="formRules"
          label-width="0px"
          size="large"
        >
          <el-form-item prop="account">
            <el-input
              v-model="loginForm.account"
              placeholder="请输入操作员账号"
              prefix-icon="User"
              clearable
            />
          </el-form-item>

          <el-form-item prop="password">
            <el-input
              v-model="loginForm.password"
              type="password"
              placeholder="请输入密码"
              prefix-icon="Lock"
              show-password
              @keyup.enter="handleLogin"
            />
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              class="submit-btn"
              @click="handleLogin"
              :loading="loading"
              >登 录</el-button
            >
          </el-form-item>

          <div class="toggle-action">
            <el-link type="info" underline="never" @click="router.push('/register')"
              >没有账号？申请注册</el-link
            >
          </div>
        </el-form>
      </div>
      <p class="copyright">ROS MES System · 智能制造执行系统</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { ElMessage } from "element-plus"; // 引入消息提示组件
import router from "@/router";
import { useUserStore } from "@/stores/user";
import request from "@/utils/request";

const user = useUserStore();

// 1. 状态控制
const isLogin = ref(true); // true为登录页，false为注册页
const loading = ref(false); // 按钮的加载转圈状态

// 2. 获取表单的 DOM 引用（为了触发校验）
const loginFormRef = ref(null);
const registerFormRef = ref(null);

// 3. 数据绑定容器
const loginForm = reactive({
  account: "",
  password: "",
});

const registerForm = reactive({
  account: "",
  password: "",
  confirmPassword: "",
});

// 4. 自定义高级校验规则：检查两次密码是否一致
const validateConfirmPassword = (rule: any, value: string, callback: any) => {
  if (value === "") {
    callback(new Error("请再次输入密码以确认"));
  } else if (value !== registerForm.password) {
    callback(new Error("两次输入的密码不一致！"));
  } else {
    callback(); // 校验通过必须调用无参的 callback()
  }
};

// 5. 核心校验规则字典 (与 prop 属性一一对应)
const formRules = reactive({
  account: [{ required: true, message: "操作员账号不能为空", trigger: "blur" }],
  password: [{ required: true, message: "密码不能为空", trigger: "blur" }],
});

// 6. 登录按钮点击事件
const handleLogin = async () => {
  if (!loginForm.account || !loginForm.password) {
    ElMessage.error("请输入账号和密码");
    return;
  }

  loading.value = true;

  try {
    const response: any = await request.post("/login", {
      username: loginForm.account,
      password: loginForm.password,
    });

    if (response.code !== 200) {
      ElMessage.error(response.message || "登录失败");
      return;
    }

    user.setUserInfo(response.data);

    ElMessage.success("登录成功");
    router.replace("/");
  } catch (error: any) {
    const errMsg =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      "登录请求失败，请稍后再试";

    ElMessage.error(errMsg);
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
/* ===== 布局：左右分栏 ===== */
.login-container {
  display: flex;
  height: 100vh;
  overflow: hidden;
  background: #fff;
}

/* ===== 左侧品牌区 ===== */
.brand-panel {
  position: relative;
  flex: 1.15;
  min-width: 0;
  background:
    radial-gradient(ellipse 80% 60% at 70% 20%, rgba(59, 130, 246, 0.25), transparent),
    linear-gradient(160deg, #0b1626 0%, #12233c 60%, #0e1f36 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px;
}

/* 工业网格纹理 */
.brand-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(148, 167, 196, 0.07) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148, 167, 196, 0.07) 1px, transparent 1px);
  background-size: 44px 44px;
  mask-image: radial-gradient(ellipse 90% 80% at 50% 40%, #000 30%, transparent 100%);
}

.brand-content {
  position: relative;
  max-width: 460px;
}

.brand-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 48px;
}

.brand-mark {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 24px rgba(37, 99, 235, 0.5);
}

.brand-name {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 2px;
}

.brand-headline {
  margin: 0 0 12px;
  font-size: 34px;
  font-weight: 700;
  letter-spacing: 1px;
  line-height: 1.3;
}

.brand-desc {
  margin: 0 0 44px;
  font-size: 15px;
  color: #94a7c4;
  letter-spacing: 0.5px;
}

.brand-features {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.brand-features li {
  display: flex;
  gap: 14px;
  align-items: flex-start;
}

.feature-icon {
  color: #60a5fa;
  font-size: 15px;
  line-height: 22px;
}

.feature-title {
  margin: 0 0 2px;
  font-size: 15px;
  font-weight: 600;
  color: #e2e8f0;
}

.feature-text {
  margin: 0;
  font-size: 13px;
  color: #7d90ad;
}

/* ===== 右侧表单区 ===== */
.form-panel {
  flex: 1;
  min-width: 420px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #fff;
  position: relative;
  padding: 40px;
}

.login-box {
  width: 360px;
  max-width: 100%;
}

.card-header {
  margin-bottom: 32px;
}

.title {
  margin: 0 0 6px;
  font-size: 26px;
  color: var(--mes-text-title, #0f172a);
  font-weight: 700;
  letter-spacing: 0.5px;
}

.subtitle {
  margin: 0;
  font-size: 14px;
  color: var(--mes-text-sub, #64748b);
}

.submit-btn {
  width: 100%;
  height: 44px;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 6px;
  margin-top: 4px;
  background: linear-gradient(90deg, #2563eb, #1d4ed8);
  border: none;
}

.submit-btn:hover {
  background: linear-gradient(90deg, #3b82f6, #2563eb);
}

.toggle-action {
  text-align: center;
  margin-top: 18px;
}

.copyright {
  position: absolute;
  bottom: 20px;
  font-size: 12px;
  color: var(--mes-text-faint, #94a3b8);
  letter-spacing: 1px;
}

/* 输入框高度统一 */
:deep(.el-input__wrapper) {
  height: 44px;
  border-radius: 10px;
}

/* 窄屏隐藏品牌区 */
@media (max-width: 860px) {
  .brand-panel {
    display: none;
  }
  .form-panel {
    min-width: 0;
  }
}
</style>
