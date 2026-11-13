<template>
  <section class="fine-tuning-session">
    <div class="session-row">
      <div class="session-copy">
        <h4>微调会话保持</h4>
        <p class="session-hint">
          开启后，微调页完成模块握手即登记一次会话。切到其他页面或刷新后可直接续接，
          <strong>不再向 ROS 发送模块确认握手</strong>（下位机无需断电重绑）。
        </p>
      </div>
      <el-switch
        :model-value="store.enabled"
        :loading="applying"
        active-text="开启"
        inactive-text="关闭"
        @update:model-value="handleToggle"
      />
    </div>

    <div class="session-row">
      <span class="session-label">保持时长</span>
      <el-select
        :model-value="store.ttlMinutes"
        class="ttl-select"
        :disabled="!store.enabled"
        @update:model-value="handleTtl"
      >
        <el-option v-for="item in SESSION_TTL_OPTIONS" :key="item.minutes" :label="item.label" :value="item.minutes" />
      </el-select>
      <span class="session-hint">从最后一次续接起算；超时后必须重新握手。</span>
    </div>

    <el-alert
      v-if="session"
      class="session-alert"
      type="success"
      :closable="false"
      :title="`进行中：模块 ${session.module_id}${moduleText} · 机械臂 ${unitText} · ${remainingText}`"
    >
      <p class="session-hint">续接按 MES 记录恢复，未经设备复核；结束会话只清除记录，不解绑设备、不发送任何指令。</p>
      <el-button size="small" :disabled="applying" @click="handleClose">结束会话</el-button>
    </el-alert>
    <el-alert
      v-else-if="latest"
      class="session-alert"
      type="info"
      :closable="false"
      :title="`上次会话已不可续接：${reasonText}；进入微调页需重新握手。`"
    />
    <p v-else-if="notice" class="session-hint">{{ notice }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { closeControlSession, getControlSession, SESSION_REASON_LABELS, type ControlSession } from '@/api/session';
import { SESSION_TTL_OPTIONS, useFineTuningSessionStore } from '@/stores/fineTuningSession';

const store = useFineTuningSessionStore();
const session = ref<ControlSession | null>(null);
const latest = ref<ControlSession | null>(null);
const reason = ref<string | null>(null);
const applying = ref(false);
const notice = ref('');

const moduleText = computed(() => (session.value?.x && session.value?.y ? ` (${session.value.x},${session.value.y})` : ''));
const unitText = computed(() => {
  const units = session.value?.unit_ids ?? [];
  return units.length ? units.map((item) => String(item)).join('、') : '—';
});
const reasonText = computed(() => SESSION_REASON_LABELS[reason.value || ''] || '已失效');
const remainingText = computed(() => {
  const expiresAt = session.value?.expires_at;
  if (!expiresAt) return '不限时';
  const left = new Date(expiresAt).getTime() - Date.now();
  if (!Number.isFinite(left) || left <= 0) return '即将失效';
  const minutes = Math.ceil(left / 60000);
  return minutes >= 60 ? `剩余约 ${Math.round(minutes / 60)} 小时` : `剩余约 ${minutes} 分钟`;
});

const load = async () => {
  if (!store.enabled) {
    session.value = null;
    latest.value = null;
    reason.value = null;
    notice.value = '';
    return;
  }
  try {
    const state = (await getControlSession(store.ttlSeconds)).data;
    session.value = state.session;
    latest.value = state.latest;
    reason.value = state.reason;
    notice.value = '';
  } catch {
    notice.value = '读取会话记录失败，请检查后端服务。';
  }
};

const handleToggle = async (value: boolean | string | number) => {
  applying.value = true;
  try {
    store.setEnabled(Boolean(value));
    if (!store.enabled) {
      store.clearSnapshot();
      ElMessage.info('已关闭会话保持；已登记的记录保留到有效期结束。');
    }
    await load();
  } finally {
    applying.value = false;
  }
};

const handleTtl = (value: number) => {
  store.setTtlMinutes(Number(value));
  void load();
};

const handleClose = async () => {
  if (!session.value) return;
  try {
    await ElMessageBox.confirm(
      '结束会话只清除 MES 的续接记录，不会解绑设备、不会发送任何指令。之后进入微调页需要重新握手。',
      '结束微调会话',
      { type: 'warning', confirmButtonText: '结束会话', cancelButtonText: '取消' },
    );
  } catch {
    return;
  }
  applying.value = true;
  try {
    await closeControlSession(session.value.id);
    store.clearSnapshot(session.value.id);
    ElMessage.success('已结束会话记录');
    await load();
  } catch {
    /* 请求失败已由拦截器提示，保留原状态 */
  } finally {
    applying.value = false;
  }
};

watch(() => store.enabled, () => { void load(); });
onMounted(load);
</script>

<style scoped>
.fine-tuning-session {
  border-top: 1px solid #e5e9ef;
  padding-top: 16px;
  margin-top: 8px;
}
.session-row {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.session-copy {
  flex: 1 1 320px;
  min-width: 0;
}
.session-copy h4 {
  margin: 0 0 4px;
  font-size: 14px;
  color: #303133;
}
.session-label {
  color: #606266;
  font-size: 13px;
  line-height: 32px;
}
.ttl-select {
  width: 140px;
}
.session-hint {
  margin: 0;
  color: #606266;
  font-size: 13px;
  line-height: 1.7;
}
.session-alert {
  margin-top: 4px;
}
.session-alert :deep(.el-alert__content) {
  width: 100%;
}
</style>
