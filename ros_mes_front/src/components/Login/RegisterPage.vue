<template>
  <div class="register-container">
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
        <h1 class="brand-headline">加入智能制造<br/>执行系统</h1>
        <p class="brand-desc">注册操作员账号，开始管理你的机械臂集群</p>
      </div>
    </div>

    <!-- 右侧表单区 -->
    <div class="form-panel">
      <div class="register-box">
        <div class="card-header">
          <p class="title">创建新账号</p>
          <p class="subtitle">注册成功后即可登录系统</p>
        </div>

        <el-form
          ref="registerFormRef"
          :model="registerForm"
          :rules="registerRules"
          label-width="0px"
          size="large"
        >
          <el-form-item prop="account">
            <el-input
              v-model="registerForm.account"
              placeholder="请输入用户名"
              prefix-icon="User"
              clearable
            />
          </el-form-item>

          <el-form-item prop="password">
            <el-input
              v-model="registerForm.password"
              type="password"
              placeholder="请输入密码（至少 6 位）"
              prefix-icon="Lock"
              show-password
            />
          </el-form-item>

          <el-form-item prop="repassword">
            <el-input
              v-model="registerForm.repassword"
              type="password"
              placeholder="请再次输入密码"
              prefix-icon="Lock"
              show-password
            />
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              class="submit-btn"
              @click="handleRegister"
              :loading="loading"
            >立即注册</el-button>
          </el-form-item>

          <div class="toggle-action">
            <el-link type="primary" :underline="false" @click="router.push('/login')">
              已有账号？去登录
            </el-link>
          </div>
        </el-form>
      </div>
      <p class="copyright">ROS MES System · 智能制造执行系统</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from "vue";
import { User, Lock } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { useRouter } from "vue-router";
import request from "../../utils/request";

const router = useRouter();
const loading = ref(false);
const registerFormRef = ref(null);

const registerForm = reactive({
  account: "",
  password: "",
  repassword: "",
});

// 确认密码校验规则
const validateConfirmPassword = (rule: any, value: string, callback: any) => {
  if (value === "") {
    callback(new Error("请再次输入密码"));
  } else if (value !== registerForm.password) {
    callback(new Error("两次输入的密码不一致！"));
  } else {
    callback();
  }
};

const registerRules = reactive({
  account: [{ required: true, message: "用户名不能为空", trigger: "blur" }],
  password: [
    { required: true, message: "密码不能为空", trigger: "blur" },
    { min: 6, message: "密码长度至少6位", trigger: "blur" }
  ],
  repassword: [{ validator: validateConfirmPassword, trigger: "blur" }],
});

const handleRegister = async () => {
  if (!registerFormRef.value) return;

  // @ts-ignore
  await registerFormRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true;
      try {
                // 向后端发起注册请求
                // 注意：这里发送的字段名要和后端定义的 Schema 一致（username 和 password）
                const res = await request.post("/register", {
                    username: registerForm.account,
                    password: registerForm.password
                });

                ElMessage.success("注册成功，请登录！");
                router.push("/login");
            } catch (error) {
                // 如果后端返回错误（比如用户名已存在），这里会自动处理
                console.error("注册失败：", error);
            } finally {
                loading.value = false;
            }
    }
  });
};
</script>

<style scoped>
/* ===== 布局：左右分栏（与登录页一致）===== */
.register-container {
  display: flex;
  height: 100vh;
  overflow: hidden;
  background: #fff;
}

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
  line-height: 1.4;
}

.brand-desc {
  margin: 0;
  font-size: 15px;
  color: #94a7c4;
  letter-spacing: 0.5px;
}

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

.register-box {
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
  letter-spacing: 2px;
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

:deep(.el-input__wrapper) {
  height: 44px;
  border-radius: 10px;
}

@media (max-width: 860px) {
  .brand-panel {
    display: none;
  }
  .form-panel {
    min-width: 0;
  }
}
</style>
