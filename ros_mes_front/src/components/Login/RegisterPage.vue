<template>
  <div class="register-container">
    <el-card class="register-card" shadow="hover">
      <div class="card-header">
        <p class="title">创建新账号</p>
      </div>

      <el-form
        ref="registerFormRef"
        :model="registerForm"
        :rules="registerRules"
        label-width="80px" 
      >
        <el-form-item prop="account" label="账号">
          <el-input
            v-model="registerForm.account"
            placeholder="请输入用户名"
            prefix-icon="User"
            clearable
          />
        </el-form-item>

        <el-form-item prop="password" label="密码">
          <el-input
            v-model="registerForm.password"
            type="password"
            placeholder="请输入密码"
            prefix-icon="Lock"
            show-password
          />
        </el-form-item>

        <el-form-item prop="repassword" label="确认密码">
          <el-input
            v-model="registerForm.repassword"
            type="password"
            placeholder="请再次输入密码"
            prefix-icon="Lock"
            show-password
          />
        </el-form-item>

        <el-form-item label-width="0">
          <el-button
            type="primary"
            class="submit-btn"
            @click="handleRegister"
            :loading="loading"
          >立即注册</el-button> 
          </el-form-item>

        <div class="toggle-action">
          <el-link type="primary" :underline="false" @click="$router.push('/login')">
            已有账号？去登录
          </el-link>
        </div>
      </el-form>
    </el-card>
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
                // 2. 【核心修改】真正向后端发起请求
                // 注意：这里发送的字段名要和后端定义的 Schema 一致（通常是 username 和 password）
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
/* 1. 容器：背景完全一致 */
.login-container, .register-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: linear-gradient(135deg, #1f2430 0%, #2b3243 100%);
}

/* 2. 卡片：宽度设为 440px，精致且不局促 */
.register-card {
  width: 440px; 
  border-radius: 12px;
  border: 1px solid #3d4556;
  background-color: #ffffff;
  padding: 35px 40px; /* 增加上下内边距，增加呼吸感 */
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
}

.card-header {
  text-align: center;
  margin-bottom: 35px;
}

/* 3. 标题：24px 粗体，这是最协调的字号 */
.title {
  margin: 0;
  font-size: 24px; 
  color: #303133;
  font-weight: 700;
  letter-spacing: 1px;
}

/* 4. 按钮：取消文字间距，显得更现代 */
.submit-btn {
  width: 100%;
  height: 42px;
  font-size: 16px;
  letter-spacing: 0px; 
  margin-top: 5px;
}

.toggle-action {
  text-align: center;
  margin-top: 20px;
}

/* 重点：深度选择器，确保输入框高度统一 */
:deep(.el-input__wrapper) {
  height: 40px;
}
</style>