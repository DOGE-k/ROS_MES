import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import test from 'node:test';
import { parse } from '@vue/compiler-sfc';
import ts from 'typescript';
import * as vue from 'vue';

// 侧栏局部停面板：任何页面都能停到模块或单轴，模块列表/轴号/会话预选全部走真实逻辑，
// API 使用替身，不访问后端或设备。
const { descriptor } = parse(fs.readFileSync(new URL('../src/components/Main/LocalStopPanel.vue', import.meta.url), 'utf8'));
const script = ts.transpileModule(descriptor.scriptSetup.content, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;

function setup(t, options = {}) {
  const mounted = [], timers = [], messages = [], emits = [];
  const calls = { stops: [], clearModule: [], holdReads: 0, moduleReads: 0, unitReads: [] };
  let holds = options.holds || [];
  const module = { exports: {} };
  const scope = vue.effectScope();
  t.after(() => scope.stop());
  scope.run(() => vm.runInNewContext(`${script}
Object.assign(module.exports, {
  visible, modules, units, holds, moduleId, scope, unitId, armIndex, canSend,
  backendMissing, open, sendStop, clearHold, refreshHolds,
});`, {
    module, exports: module.exports,
    defineEmits: () => (event, value) => emits.push({ event, value }),
    defineExpose: () => {},
    setInterval(callback, delay) { timers.push({ callback, delay }); return timers.length; },
    clearInterval() {},
    require(name) {
      if (name === 'vue') return { ...vue, onMounted(callback) { mounted.push(callback); }, onBeforeUnmount() {} };
      if (name === 'element-plus') return {
        ElMessageBox: { confirm: async () => { if (options.cancel) throw new Error('cancel'); } },
        ElMessage: { success: text => messages.push(['success', text]), warning: text => messages.push(['warning', text]), error: text => messages.push(['error', text]) },
      };
      if (name === '@/api/rosApi') return {
        async getDeviceListApi() {
          calls.moduleReads++;
          return { data: options.modules || [{ Device_ID: 17, Moduledescript: '一号模块' }, { Device_ID: 18 }] };
        },
        async getUnitsByDeviceApi(deviceId) {
          calls.unitReads.push(deviceId);
          return { data: options.units || [{ Unit_ID: 32 }, { Unit_ID: 64 }] };
        },
      };
      if (name === '@/api/session') return {
        async getControlSession() {
          return { data: { session: options.session === undefined ? { module_id: 17 } : options.session, latest: null, reason: null } };
        },
      };
      if (name === '@/api/deviceEncoding') return {
        armIndexFromUnitId: unitId => (Number(unitId) === 64 ? 2 : 1),
        axisDeviceId: (armIndex, parameter) => (armIndex - 1) * 3 + { rotation: 1, swing: 2, telescopic: 3 }[parameter],
      };
      if (name === '@/api/localStop') return {
        async getLocalStopHolds() {
          calls.holdReads++;
          if (options.holdsError) throw options.holdsError;
          return { data: { mode: 'real', holds, connection_revision: 0 } };
        },
        async requestLocalStop(payload) {
          calls.stops.push(payload);
          if (options.stopError) throw options.stopError;
          return { code: 200, message: '模块 17 局部停指令已发送；设备是否停止待确认', data: { id: 1, module_id: payload.module_id } };
        },
        async clearLocalStopHolds(moduleId) {
          calls.clearModule.push(moduleId);
          holds = [];
          return { data: { module_id: moduleId, cleared: 1 } };
        },
      };
      throw new Error(`Unexpected dependency ${name}`);
    },
  }));
  return { page: module.exports, calls, messages, emits, timers, mount: () => mounted[0]() };
}

test('opening the panel preselects the fine-tuning session module and its arms', async t => {
  const h = setup(t, {});
  h.mount();
  await h.page.open();

  assert.equal(h.page.visible.value, true);
  assert.equal(h.page.modules.value.length, 2);
  assert.equal(h.page.moduleId.value, 17);
  assert.deepEqual(h.calls.unitReads, [17]);
  assert.equal(h.page.units.value.length, 2);
  assert.equal(h.page.unitId.value, 32);
  // 轮询到的记录数回传给侧栏徽标
  assert.deepEqual(h.emits.at(-1), { event: 'count', value: 0 });
});

test('module stop posts scope=module with the polled connection revision', async t => {
  const h = setup(t, {});
  h.mount();
  await h.page.open();
  await h.page.sendStop();

  assert.equal(h.calls.stops.length, 1);
  assert.equal(h.calls.stops[0].scope, 'module');
  assert.equal(h.calls.stops[0].module_id, 17);
  assert.equal(h.calls.stops[0].connection_revision, 0);
  assert.equal(h.calls.stops[0].device_id, undefined);
  assert.equal(h.messages[0][0], 'warning');
});

test('arm stop posts scope=arm with the arm index instead of an axis number', async t => {
  const h = setup(t, {});
  h.mount();
  await h.page.open();

  h.page.scope.value = 'arm';
  h.page.unitId.value = 64;
  assert.equal(h.page.armIndex.value, 2);
  assert.equal(h.page.canSend.value, true);

  await h.page.sendStop();

  assert.equal(h.calls.stops[0].scope, 'arm');
  assert.equal(h.calls.stops[0].module_id, 17);
  // device_id 传臂号 1~5，不是 V2 轴号
  assert.equal(h.calls.stops[0].device_id, 2);
});

test('without a module or arm the panel refuses to send', async t => {
  const h = setup(t, { modules: [], session: null });
  h.mount();
  await h.page.open();

  assert.equal(h.page.moduleId.value, null);
  assert.equal(h.page.canSend.value, false);
  await h.page.sendStop();
  assert.equal(h.calls.stops.length, 0);
});

test('holds are reported to the sidebar and cleared by module', async t => {
  const held = { id: 9, mode: 'real', scope: 'module', module_id: 17, device_id: null, state: 'sent',
    message: null, created_at: '2026-11-11 20:30:00', cleared_at: null, cleared_reason: null, active: true };
  const h = setup(t, { holds: [held] });
  h.mount();
  await h.page.refreshHolds();

  assert.equal(h.page.holds.value.length, 1);
  assert.deepEqual(h.emits.at(-1), { event: 'count', value: 1 });

  await h.page.clearHold(held);

  assert.deepEqual(h.calls.clearModule, [17]);
  assert.equal(h.page.holds.value.length, 0);
  assert.deepEqual(h.emits.at(-1), { event: 'count', value: 0 });
  assert.equal(h.messages.at(-1)[0], 'success');
});

test('a failed stop request keeps the refresh path so the MES lock is visible', async t => {
  const h = setup(t, { stopError: Object.assign(new Error('boom'), { response: { data: { detail: '局部停指令发送失败，MES 已锁定该目标' } } }) });
  h.mount();
  await h.page.open();
  await h.page.sendStop();

  assert.equal(h.calls.stops.length, 1);
  assert.equal(h.messages.at(-1)[0], 'error');
  assert.ok(h.calls.holdReads >= 2);
});

test('a backend without the local stop routes surfaces a restart hint', async t => {
  const h = setup(t, { holdsError: Object.assign(new Error('Not Found'), { response: { status: 404 } }) });
  h.mount();
  await h.page.open();

  assert.equal(h.page.backendMissing.value, true);
  assert.equal(h.page.holds.value.length, 0);
  // 模块列表仍可用：只缺局部停接口时不让整个弹窗不可用
  assert.equal(h.page.modules.value.length, 2);
});
