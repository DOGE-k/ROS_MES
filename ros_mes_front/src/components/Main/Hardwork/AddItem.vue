<template>
  <el-dialog v-model="addDialogVisible" title="新增硬件" width="500px">
      <el-form
        :model="addForm"
        :rules="form"
        ref="addFormRef"
        label-width="100px"
      >
        <el-form-item label="硬件编号" prop="id">
          <el-input v-model="addForm.id" placeholder="唯一标识，不可重复" />
        </el-form-item>
        <el-form-item label="硬件名称" prop="deviceName">
          <el-input v-model="addForm.deviceName" />
        </el-form-item>
        <el-form-item label="硬件类型" prop="type">
          <el-select v-model="addForm.type" placeholder="请选择类型">
            <el-option label="机械臂" :value="1" />
            <el-option label="压力传感器" :value="2" />
            <el-option label="陀螺仪" :value="3" />
          </el-select>
        </el-form-item>
        <el-form-item label="规格" prop="spec">
          <el-input v-model="addForm.spec" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-radio-group v-model="addForm.status">
            <el-radio :label="1">正常</el-radio>
            <el-radio :label="0">故障</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="onClick">取消</el-button>
        <el-button type="primary" @click="submitAdd">确认新增</el-button>
      </template>
    </el-dialog>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue";
import { ElMessageBox, FormInstance, FormRules } from "element-plus";
import { computed } from "vue";
import request from "@/utils/request";

const props = defineProps({
  addDialogVisible: Boolean,
  hardwares: {
    type: Array,
    default: () => []
  }
});
const emit = defineEmits(["update:addDialogVisible","update:hardworks"]);
const typeOption = [
  { id: "1", label: "机械臂" },
  { id: "2", label: "压力传感器" },
];
const drawerVisible = computed({
  get() {
    return props.addDialogVisible;
  },
  set(value) {
    emit("update:addDialogVisible", value);
  },
});
const formLabelWidth = "80px";
let timer: any;

const table = ref(false);
const loading = ref(false);


// 新增弹窗相关
const addFormRef = ref<FormInstance>();
interface Hardware {
  id: number;
  deviceName: string;
  type: number;
  spec: string;
  status: number;
  updateTime: string;
  createTime: string;
}

const addForm = reactive<Hardware>({
  id: 0,
  deviceName: "",
  type: 1,
  spec: "",
  status: 1,
  updateTime: "",
  createTime: "",
});

// 新增表单校验规则（包含 id 唯一性校验）
const form: FormRules = {
  id: [
    { required: true, message: "请输入硬件编号", trigger: "blur" },
    {
      validator: (rule, value, callback) => {
        const exists = props.hardwares.some((item) => item.id === value);
        if (exists) {
          callback(new Error("硬件编号已存在"));
        } else {
          callback();
        }
      },
      trigger: "blur",
    },
  ],
  deviceName: [{ required: true, message: "请输入硬件名称", trigger: "blur" }],
  type: [{ required: true, message: "请选择硬件类型", trigger: "change" }],
  spec: [{ required: true, message: "请输入规格", trigger: "blur" }],
};

const onClick = async () => {
  loading.value = true;
    try{
      var res = await request.put("/hardware", {
      id: form.id,
      deviceName: form.deviceName,  
      type: form.type,
      spec: form.spec,
      status: form.status,
    });
    }catch(err){
      ElMessageBox.alert("添加失败,服务器未开启", "提示", {
        confirmButtonText: "确定"
      });
      loading.value = false;
      return;
    }
    if (res.code === 200) {
      ElMessageBox.alert("添加成功", "提示", {
        confirmButtonText: "确定",
      });
      res = await request.get("/hardware");
      emit("update:addDialogVisible", false);
      emit("update:hardworks", res.data);
    } else {
      ElMessageBox.alert("添加失败," + res.msg, "提示", {
        confirmButtonText: "确定"
      });
    }
    loading.value = false;
};

const handleClose = (done:any) => {
  if (loading.value) {
    return;
  }
  ElMessageBox.confirm("是否提交?")
    .then(() => {
      loading.value = true;
      timer = setTimeout(() => {
        done();
        setTimeout(() => {
          loading.value = false;
          drawerVisible.value = false;
        }, 400);
      }, 2000);
    })
    .catch(() => {
      done();
      drawerVisible.value = false;
    });
};

const cancelForm = () => {
  loading.value = false;
  drawerVisible.value = false;
  clearTimeout(timer);
};

const options = Array.from({ length: 2 }).map((_, idx) => ({
  value: `${idx}`,
  label: `${idx === 0 ? "正常" : "故障"}`,
}));
</script>


