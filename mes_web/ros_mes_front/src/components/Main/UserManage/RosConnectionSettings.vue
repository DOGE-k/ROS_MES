<template>
  <div v-loading="loading || applying" class="connection-settings">
    <el-alert v-if="!config" title="连接设置尚未加载，请检查后端连接。" type="warning" :closable="false" />
    <template v-else>
      <p class="settings-hint">逐项手动选择。选择后自动应用；地址修改后按回车或移出输入框生效，对当前服务生效。</p>
      <el-form label-position="top" :disabled="applying">
        <section>
          <el-form-item label="ROS 通信与微调">
            <el-radio-group :model-value="config.ros_mode" @update:model-value="value => changeMode('ros_mode', value)">
              <el-radio-button value="mock">模拟</el-radio-button><el-radio-button value="real">真实</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="ROS 连接地址">
            <el-input v-model="draft.ros_url" :disabled="config.ros_mode === 'mock'" placeholder="ws://主机地址:9010" @change="changeAddress('ros_url')" />
          </el-form-item>
          <el-form-item label="微调下发前检查">
            <el-switch
              :model-value="config.finetuning_preflight_enabled"
              :disabled="applying"
              active-text="开启"
              inactive-text="关闭"
              @update:model-value="changePreflightCheck"
            />
          </el-form-item>
          <p class="settings-hint">开启时等待实时轴状态和有效位置。关闭后可发送当前轴，系统继续等待运行、到位和空闲反馈。缺少回传时约 1 分钟转为待核实。切换此设置后需重新确认机械臂。</p>
        </section>
        <section>
          <el-form-item label="图纸处理方式">
            <el-radio-group :model-value="config.drawing_mode" @update:model-value="value => changeMode('drawing_mode', value)">
              <el-radio-button value="skip">不使用图纸</el-radio-button>
              <el-radio-button value="mock">模拟下发</el-radio-button><el-radio-button value="real">真实下发</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <p v-if="config.drawing_mode === 'mock'" class="settings-hint">微调页可直接使用内置模拟图纸，无需导入正式图纸。</p>
          <p v-if="config.drawing_mode === 'skip'" class="settings-hint">只确认机械臂，不选择或下发图纸，直接进行微调。</p>
          <el-form-item v-if="config.drawing_mode === 'real'" label="图纸 ROS 地址">
            <el-input v-model="draft.drawing_ros_url" placeholder="留空共用 ROS 连接地址" @change="changeAddress('drawing_ros_url')" />
          </el-form-item>
          <el-form-item v-if="config.drawing_mode === 'real'" label="三视图服务地址">
            <el-input v-model="draft.pointcloud_url" placeholder="http://主机地址:5000" @change="changeAddress('pointcloud_url')" />
          </el-form-item>
        </section>
        <section>
          <el-form-item label="急停与解除">
            <el-radio-group :model-value="config.emergency_mode" @update:model-value="value => changeMode('emergency_mode', value)">
              <el-radio-button value="mock" :disabled="config.ros_mode === 'real' || config.drawing_mode === 'real'">模拟</el-radio-button>
              <el-radio-button value="real">真实</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="急停 ROS 地址">
            <el-input v-model="draft.emergency_ros_url" :disabled="config.emergency_mode === 'mock'" placeholder="留空共用 ROS 连接地址" @change="changeAddress('emergency_ros_url')" />
          </el-form-item>
        </section>
      </el-form>
      <p class="settings-hint">真实微调或图纸下发会同时启用真实急停。模拟结果只用于调试，真实连接失败不会转为模拟成功。</p>
      <p v-if="notice" role="status" class="settings-notice">{{ notice }}</p>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, reactive } from 'vue';
import { ElMessage } from 'element-plus';
import { getConnectionSettings, changeConnectionSettings, type ConnectionSettings, type ConnectionMode } from '@/api/connectionSettings';

const config = ref<ConnectionSettings | null>(null);
const draft = reactive({ ros_url: '', drawing_ros_url: '', emergency_ros_url: '', pointcloud_url: '' });
const loading = ref(true), applying = ref(false), notice = ref('');
const emit = defineEmits<{ changed: [config: ConnectionSettings] }>();
const accept = (value: ConnectionSettings) => {
  const accepted = { ...value, finetuning_preflight_enabled: value.finetuning_preflight_enabled !== false };
  config.value = accepted;
  for (const key of Object.keys(draft) as (keyof typeof draft)[]) draft[key] = value[key];
  return accepted;
};
const load = async () => {
  try { accept((await getConnectionSettings()).data); }
  catch { notice.value = '读取连接设置失败'; }
  finally { loading.value = false; }
};
const apply = async (changes: Partial<ConnectionSettings>) => {
  if (!config.value || applying.value) return;
  applying.value = true;
  try {
    const value = (await changeConnectionSettings(config.value.revision, changes)).data;
    const accepted = accept(value);
    notice.value = '设置已应用；新操作使用当前配置，未自动下发任何任务。';
    window.dispatchEvent(new CustomEvent('ros-connection-changed', { detail: accepted }));
    emit('changed', accepted);
  } catch (error: any) {
    notice.value = error.response?.data?.detail || '应用失败，继续使用原配置';
    ElMessage.error(notice.value);
    await load();
  } finally { applying.value = false; }
};
const changeMode = (key: 'ros_mode' | 'drawing_mode' | 'emergency_mode', value: unknown) => {
  if (!config.value || !(['mock', 'real'].includes(String(value)) || (key === 'drawing_mode' && value === 'skip')) || config.value[key] === value) return;
  const changes: Partial<ConnectionSettings> = {};
  if (key === 'drawing_mode') changes.drawing_mode = value as ConnectionMode | 'skip';
  else changes[key] = value as ConnectionMode;
  if (key !== 'emergency_mode' && value === 'real') changes.emergency_mode = 'real';
  return apply(changes);
};
const changeAddress = (key: keyof typeof draft) => {
  if (config.value && draft[key].trim() !== config.value[key]) return apply({ [key]: draft[key].trim() });
};
const changePreflightCheck = (value: unknown) => {
  if (!config.value || typeof value !== 'boolean' || config.value.finetuning_preflight_enabled === value) return;
  return apply({ finetuning_preflight_enabled: value });
};
onMounted(load);
</script>

<style scoped>
.connection-settings section { border-bottom: 1px solid #e5e9ef; margin-bottom: 20px; }
.connection-settings :deep(.el-form-item) { margin-bottom: 16px; }
.settings-hint { color: #606266; line-height: 1.7; font-size: 13px; }
.settings-notice { color: #327653; font-size: 13px; }
</style>
