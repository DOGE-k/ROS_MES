<template>
  <el-dialog
    v-model="visible"
    title="局部停（分级急停）"
    width="min(600px, 94vw)"
    append-to-body
  >
    <el-alert
      type="error"
      :closable="false"
      show-icon
      title="只停目标模块或整台机械臂，其他模块照常可用；不解除全局急停，也不代表设备已经停住。"
    />
    <el-alert
      v-if="backendMissing"
      type="warning"
      :closable="false"
      show-icon
      title="后端没有加载局部停接口（/control/stop/holds 返回 404），请用最新代码重启后端后再操作。"
    />

    <el-form label-width="76px" class="stop-form">
      <el-form-item label="模块">
        <el-select
          v-model="moduleId"
          placeholder="选择要停的模块"
          filterable
          :loading="loadingModules"
          style="width: 100%"
          @change="handleModuleChange"
        >
          <el-option v-for="item in modules" :key="item.id" :label="item.label" :value="item.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="停哪一级">
        <el-radio-group v-model="scope">
          <el-radio-button value="module">整模块</el-radio-button>
          <el-radio-button value="arm">整个机械臂</el-radio-button>
        </el-radio-group>
      </el-form-item>
      <el-form-item v-if="scope === 'arm'" label="机械臂">
        <el-select v-model="unitId" placeholder="选择要停的机械臂" style="width: 100%">
          <el-option v-for="item in units" :key="item.id" :label="item.label" :value="item.id" />
        </el-select>
      </el-form-item>
    </el-form>

    <div class="stop-actions">
      <el-button type="danger" :loading="sending" :disabled="!canSend" @click="sendStop">确认停{{ scopeLabel }}</el-button>
      <span class="stop-hint">臂停会停掉该臂的 3 根轴；设备侧是否锁存由固件决定，恢复运动前需现场确认。</span>
    </div>

    <div class="hold-list">
      <p class="hold-title">当前生效的局部停记录（{{ holds.length }}）</p>
      <p v-if="!holds.length" class="hold-empty">没有局部停记录</p>
      <ul v-else>
        <li v-for="hold in holds" :key="hold.id">
          <span>{{ describeHold(hold) }} · {{ hold.created_at || '时间未知' }}</span>
          <el-button size="small" :disabled="clearing" @click="clearHold(hold)">清除记录</el-button>
        </li>
      </ul>
      <p class="hold-empty">清除记录只恢复 MES 的下发能力，不发送解除或运动指令。</p>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';

import { getDeviceListApi, getUnitsByDeviceApi } from '@/api/rosApi';
import { getControlSession } from '@/api/session';
import { armIndexFromUnitId } from '@/api/deviceEncoding';
import {
  clearLocalStopHolds,
  getLocalStopHolds,
  requestLocalStop,
  type LocalStopHold,
} from '@/api/localStop';

// 侧栏底部与微调页共用同一个入口：任何页面都能停到模块或整台机械臂，不必先回到微调页。
const emit = defineEmits<{ (event: 'count', value: number): void }>();

const visible = ref(false);
const loadingModules = ref(false);
const sending = ref(false);
const clearing = ref(false);
const modules = ref<Array<{ id: number; label: string }>>([]);
const units = ref<Array<{ id: number; label: string }>>([]);
const holds = ref<LocalStopHold[]>([]);
const moduleId = ref<number | null>(null);
const scope = ref<'module' | 'arm'>('module');
const unitId = ref<number | null>(null);
// 读 /control/stop/holds 时带回的连接版本，随停指令一起提交，避免版本漂移后误操作
const connectionRevision = ref<number | null>(null);
// 后端是旧进程时 /control/stop/holds 会 404：提示重启，而不是只留一个空列表
const backendMissing = ref(false);

const scopeLabel = computed(() => (scope.value === 'module' ? '本模块' : '该机械臂'));
const armIndex = computed(() => (unitId.value ? armIndexFromUnitId(unitId.value) : 0));
const canSend = computed(() => {
  if (!moduleId.value) return false;
  return scope.value === 'module' || Boolean(armIndex.value);
});

const describeHold = (hold: LocalStopHold) => {
  if (hold.scope === 'module') return `模块 ${hold.module_id} · 整模块`;
  if (hold.scope === 'arm') return `模块 ${hold.module_id} · 臂 ${hold.device_id}`;
  return `模块 ${hold.module_id} · 单轴 device_id=${hold.device_id}`;
};

const refreshHolds = async () => {
  try {
    const res = await getLocalStopHolds();
    const data: any = res?.data || {};
    holds.value = Array.isArray(data.holds) ? data.holds : [];
    connectionRevision.value = typeof data.connection_revision === 'number' ? data.connection_revision : null;
    backendMissing.value = false;
  } catch (error: any) {
    // 读取失败时保留上一次记录，不清空提示，避免误以为锁已解除
    if (error?.response?.status === 404) backendMissing.value = true;
  }
  emit('count', holds.value.length);
};

const parseModules = (payload: any) => {
  const list = Array.isArray(payload?.data) ? payload.data : Array.isArray(payload) ? payload : [];
  return list
    .filter((item: any) => !item?.del_flag)
    .map((item: any) => {
      const id = Number(item?.Device_ID ?? item?.Module_ID ?? 0);
      const name = item?.Moduledescript || item?.Devicedescript || '';
      return { id, label: name ? `模块 ${id} · ${name}` : `模块 ${id}` };
    })
    .filter((item: { id: number }) => item.id > 0);
};

const handleModuleChange = async (value: number) => {
  unitId.value = null;
  units.value = [];
  if (!value) return;
  try {
    const res = await getUnitsByDeviceApi(value);
    const list = Array.isArray(res?.data) ? res.data : [];
    units.value = list
      .filter((item: any) => !item?.del_flag)
      .map((item: any) => ({ id: Number(item?.Unit_ID ?? 0), label: `机械臂 ${armIndexFromUnitId(Number(item?.Unit_ID ?? 0))}` }))
      .filter((item: { id: number }) => item.id > 0);
    unitId.value = units.value[0]?.id ?? null;
  } catch {
    ElMessage.error('获取机械臂列表失败，可先用整模块停');
  }
};

const preselectModule = async () => {
  try {
    const state = await getControlSession(null);
    const sessionModule = Number(state?.data?.session?.module_id || 0);
    if (sessionModule && modules.value.some(item => item.id === sessionModule)) {
      moduleId.value = sessionModule;
    } else if (modules.value.length === 1) {
      moduleId.value = modules.value[0].id;
    }
  } catch {
    // 没有会话记录时保持手动选择
  }
};

const loadModules = async () => {
  loadingModules.value = true;
  try {
    modules.value = parseModules(await getDeviceListApi());
  } catch {
    ElMessage.error('获取模块列表失败，请检查后端服务');
  } finally {
    loadingModules.value = false;
  }
};

const open = async () => {
  visible.value = true;
  await refreshHolds();
  if (!modules.value.length) {
    await loadModules();
  }
  if (!moduleId.value) {
    await preselectModule();
    if (moduleId.value) await handleModuleChange(moduleId.value);
  }
};

const sendStop = async () => {
  if (!canSend.value || sending.value) return;
  const label = scope.value === 'module' ? `模块 ${moduleId.value}` : `模块 ${moduleId.value} 臂 ${armIndex.value}`;
  try {
    await ElMessageBox.confirm(
      `确认停 ${label}？只停该目标，不解除全局急停；设备是否真的停住仍需现场确认。`,
      '局部停',
      { type: 'warning', confirmButtonText: '确认停', cancelButtonText: '取消' },
    );
  } catch {
    return;
  }
  sending.value = true;
  try {
    const res = await requestLocalStop({
      scope: scope.value,
      module_id: Number(moduleId.value),
      ...(scope.value === 'arm' ? { device_id: armIndex.value } : {}),
      ...(connectionRevision.value !== null ? { connection_revision: connectionRevision.value } : {}),
    });
    ElMessage.warning(res.message || '局部停已记录');
  } catch (error: any) {
    // 发送失败同样会留 MES 锁，刷新以显示真实记录
    if (error?.response?.status === 404) backendMissing.value = true;
    ElMessage.error(error?.response?.data?.detail || '局部停请求失败，请查看记录核实');
  } finally {
    sending.value = false;
    await refreshHolds();
  }
};

const clearHold = async (hold: LocalStopHold) => {
  if (clearing.value) return;
  try {
    await ElMessageBox.confirm(
      `清除 ${describeHold(hold)} 的记录？只恢复 MES 下发能力，不发送解除或运动指令。`,
      '清除局部停记录',
      { type: 'warning', confirmButtonText: '清除记录', cancelButtonText: '取消' },
    );
  } catch {
    return;
  }
  clearing.value = true;
  try {
    const res = await clearLocalStopHolds(hold.module_id);
    ElMessage.success(`已清除 ${res?.data?.cleared ?? 0} 条记录；未发送任何指令`);
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '清除失败，请稍后重试');
  } finally {
    clearing.value = false;
    await refreshHolds();
  }
};

let holdTimer: ReturnType<typeof setInterval> | undefined;
onMounted(() => {
  void refreshHolds();
  holdTimer = setInterval(() => { void refreshHolds(); }, 8000);
});
onBeforeUnmount(() => {
  if (holdTimer !== undefined) clearInterval(holdTimer);
  holdTimer = undefined;
});

defineExpose({ open });
</script>

<style scoped>
.stop-form {
  margin-top: 16px;
}

.stop-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 12px 0;
}

.stop-hint,
.hold-empty {
  color: #909399;
  font-size: 12px;
}

.hold-list {
  border-top: 1px solid #ebeef5;
  padding-top: 12px;
}

.hold-title {
  margin: 0 0 8px;
  color: #303133;
  font-size: 13px;
  font-weight: 500;
}

.hold-list ul {
  list-style: none;
  margin: 0 0 8px;
  padding: 0;
}

.hold-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 0;
  color: #606266;
  font-size: 13px;
}
</style>
