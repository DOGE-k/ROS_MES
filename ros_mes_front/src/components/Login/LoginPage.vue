<template>
  <div class="login-container">
    <el-card class="login-card" shadow="hover">
      <div class="card-header">
        <p class="title">{{ isLogin ? "系统登录" : "新用户注册" }}</p>
      </div>

      <el-form
        v-if="isLogin"
        ref="loginFormRef"
        :model="loginForm"
        :rules="formRules"
        label-width="0px"
      >
        <el-form-item prop="account" label="账号" label-width="50px">
          <el-input
            v-model="loginForm.account"
            placeholder="请输入操作员账号"
            prefix-icon="User"
            clearable
          />
        </el-form-item>

        <el-form-item prop="password" label="密码" label-width="50px">
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

      <!--      <el-form-->
      <!--        v-else-->
      <!--        ref="registerFormRef"-->
      <!--        :model="registerForm"-->
      <!--        :rules="formRules"-->
      <!--        label-width="0px"-->
      <!--      >-->
      <!--        <el-form-item prop="account">-->
      <!--          <el-input-->
      <!--            v-model="registerForm.account"-->
      <!--            placeholder="设置操作员账号"-->
      <!--            prefix-icon="User"-->
      <!--            clearable-->
      <!--          />-->
      <!--        </el-form-item>-->

      <!--        <el-form-item prop="password">-->
      <!--          <el-input-->
      <!--            v-model="registerForm.password"-->
      <!--            type="password"-->
      <!--            placeholder="设置高强度密码"-->
      <!--            prefix-icon="Lock"-->
      <!--            show-password-->
      <!--          />-->
      <!--        </el-form-item>-->

      <!--        <el-form-item prop="confirmPassword">-->
      <!--          <el-input-->
      <!--            v-model="registerForm.confirmPassword"-->
      <!--            type="password"-->
      <!--            placeholder="再次确认密码"-->
      <!--            prefix-icon="Lock"-->
      <!--            show-password-->
      <!--          />-->
      <!--        </el-form-item>-->

      <!--        <el-alert-->
      <!--          title="注意：注册后需管理员审核通过方可登录"-->
      <!--          type="warning"-->
      <!--          show-icon-->
      <!--          :closable="false"-->
      <!--          class="audit-alert"-->
      <!--        />-->

      <!--        <el-form-item>-->
      <!--          <el-button-->
      <!--            type="success"-->
      <!--            class="submit-btn"-->
      <!--            :loading="loading"-->
      <!--            >提交注册申请</el-button-->
      <!--          >-->
      <!--        </el-form-item>-->

      <!--        <div class="toggle-action">-->
      <!--          <el-link type="info" underline="never" @click="isLogin = true"-->
      <!--            >返回登录</el-link-->
      <!--          >-->
      <!--        </div>-->
      <!--      </el-form>-->
      <!--    -->
    </el-card>
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

    console.log("登录返回：", response);

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
/* 1. 容器：背景完全一致 */
.login-container, .register-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: linear-gradient(135deg, #1f2430 0%, #2b3243 100%);
}

/* 2. 卡片：宽度设为 440px，精致且不局促 */
.login-card{
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
```
