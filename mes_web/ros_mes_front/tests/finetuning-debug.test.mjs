import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import test from 'node:test';
import { parse } from '@vue/compiler-sfc';
import ts from 'typescript';
import * as vue from 'vue';
import * as pinia from 'pinia';

// 执行实际组件和状态仓库；API/浏览器连接使用替身，不访问设备或项目数据库。
function evaluate(source, dependencies, globals = {}, bindings = '') {
  const script = ts.transpileModule(source.replaceAll('import.meta.env', '({})'), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
  }).outputText;
  const module = { exports: {} };
  vm.runInNewContext(script + '\n' + bindings, {
    module, exports: module.exports, ...globals,
    require(name) {
      if (name in dependencies) return dependencies[name];
      throw new Error(`Unexpected dependency: ${name}`);
    },
  });
  return module.exports;
}

const read = path => fs.readFileSync(new URL(path, import.meta.url), 'utf8');
const debugModule = evaluate(read('../src/stores/debugSettings.ts'), { vue, pinia });
const encoding = evaluate(read('../src/api/deviceEncoding.ts'), {});
const feedbackState = evaluate(read('../src/api/feedbackState.ts'), {});
const { descriptor } = parse(read('../src/components/Main/ModulePage/FineTuningPage.vue'));
const bindings = `Object.assign(module.exports, {
  isReady, busy, loading, initConfig, draftInitConfig, initDialogVisible,
  armList, armProfiles, armIdList, selectedArmRowId, imuFeedback, pointCloudViews,
  confirmInitConfig, handleArmSwitch, handleSaveConfig, confirmAdjustments,
  batchState, pollBatch, interruptBatch, acknowledgeBatch, openConfiguration, connectionChanged, resetControlState,
  applyFeedback, openDrawingDialog, togglePointCloudViews,
  confirmedSeg, feedbackMarks, feedbackClock, feedbackConnected, fieldStatus, displayFeedback, ackEvents,
});
Object.defineProperty(module.exports, 'isDebugMode', { get: () => isDebugMode.value });`;

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function batch(overrides = {}) {
  return { id: 'batch-test', request_id: 'request-test', module_id: 17, unit_id: 32, seg: 0,
    status: 'executing', target_locked: true, message: 'waiting', steps: [
      { parameter_name: 'rotation', device_id: 1, position: 2, status: 'sent_unconfirmed' },
      { parameter_name: 'swing', device_id: 2, position: 1, status: 'pending' },
    ], ...overrides };
}

function setup(t, options = {}) {
  const container = options.container || pinia.createPinia();
  pinia.setActivePinia(container);
  const settings = debugModule.useDebugSettingsStore(container);
  if (options.debug !== undefined) settings.skipDrawingBinding = options.debug;
  const calls = { drawings: 0, confirms: [], coordinates: [], saves: [], adjusts: [], events: [], sockets: [], polls: 0, interrupts: 0, acknowledgements: 0 };
  let latestBatch;
  const warnings = [], errors = [], navigations = [], mounted = [], unmounted = [];
  let now = 1000;
  const timers = new Map();
  const units = [{ id: 1, Unit_ID: 32 }, { id: 2, Unit_ID: 64 }];
  const api = {
    async getUnitsByDeviceApi() { return { data: units }; },
    async getDrawingListApi() {
      calls.drawings++;
      if (options.failDrawings) throw new Error('drawing service unavailable');
      return { data: options.noDrawings ? [] : options.drawings || [{ drawingId: 7, drawingName: 'drawing' }] };
    },
    async getSensorsByUnitApi(rowId) {
      return { data: options.noSensors ? [] : [{ id: 100 + rowId, sensor_ID: rowId * 32 + 17, Unit_address: 0 }] };
    },
    async createModule(payload) {
      calls.confirms.push(payload);
      calls.events.push('confirm');
      if (options.confirm) return options.confirm(payload);
      return { code: 200, data: { seg: options.seg ?? 0, confirmations: payload.unit_ids.map(unit_id => ({ unit_id, confirmed: true })) } };
    },
    async sendCoordination(payload) {
      calls.coordinates.push(payload);
      calls.events.push('drawing');
      if (options.coordinate) return options.coordinate(payload);
      return { code: 200, views: { front: '/api/coordination/views/front' } };
    },
    async submitFineTuningBatch(payload) {
      calls.adjusts.push(payload);
      if (options.adjust) return options.adjust(payload);
      latestBatch = { ...payload, id: 'test-batch', seg: 0, status: 'completed', message: 'completed', target_locked: false,
        simulated: Boolean(options.noRosDebug), steps: payload.adjustments.map(item => ({ ...item, device_id: 1, status: 'completed' })) };
      return { code: 200, data: latestBatch };
    },
    async getActiveFineTuningBatch(moduleId, unitId) { return { data: options.active ? options.active(moduleId, unitId) : null }; },
    async getFineTuningBatch(id) { calls.polls++; return { data: options.poll ? await options.poll(id) : latestBatch }; },
    async getFineTuningBatchByRequest(id) { calls.polls++; return { data: options.byRequest ? await options.byRequest(id) : latestBatch }; },
    async interruptFineTuningBatch() { calls.interrupts++; return { data: { ...latestBatch, ...options.batch, status: 'uncertain', target_locked: true, message: 'stopped' } }; },
    async acknowledgeFineTuningBatch() { calls.acknowledgements++; return { data: { ...latestBatch, ...options.batch, status: 'closed', target_locked: false, message: 'closed' } }; },
    async saveFineTuningConfig(payload) {
      calls.saves.push(payload);
      if (options.save) return options.save(payload);
      return { code: 200, data: { config: payload } };
    },
  };
  class FeedbackSocket {
    constructor(url) { this.url = url; calls.sockets.push(this); }
    close() { this.onclose?.(); }
    receive(data) { this.onmessage({ data: JSON.stringify(data) }); }
  }
  const scope = vue.effectScope();
  t.after(() => { unmounted.forEach(callback => callback()); scope.stop(); });
  const page = scope.run(() => evaluate(descriptor.scriptSetup.content, {
    vue: { ...vue, onMounted(callback) { mounted.push(callback); }, onBeforeUnmount(callback) { unmounted.push(callback); } },
    'vue-router': { useRoute: () => ({ query: { module_id: 17, device_id: 17, x: 1, y: 1 } }), useRouter: () => ({ push: target => navigations.push(target) }) },
    'element-plus': { ElMessageBox: { confirm: async () => { if (options.cancelAcknowledge) throw new Error('cancel'); } }, ElMessage: { success() {}, warning: text => warnings.push(text), error: text => errors.push(text) } },
    '@element-plus/icons-vue': { ArrowLeft: {} },
    '@/api/rosApi': { ...api, async getFineTuningDrawingOptions() {
      const result = await api.getDrawingListApi();
      return { data: options.drawingMode === 'mock' ? [{ drawingId: null, drawingName: '内置模拟图纸', drawingSource: 'builtin_mock' }, ...result.data] : result.data };
    } },
    '@/api/connectionSettings': { async getConnectionSettings() { return { data: { revision: 0, drawing_mode: settings.skipDrawingBinding ? 'skip' : options.drawingMode || 'real' } }; } },
    '@/api/noRosDebug': { noRosDebug: Boolean(options.noRosDebug) },
    '@/api/deviceEncoding': encoding,
    '@/api/feedbackState': feedbackState,
    '@/stores/debugSettings': debugModule,
  }, {
    window: { location: { protocol: 'http:', host: 'localhost' } },
    performance: { now: () => now },
    setInterval(callback) { const id = timers.size + 1; timers.set(id, callback); return id; },
    clearInterval(id) { timers.delete(id); },
    WebSocket: FeedbackSocket, console: { warn() {}, error() {}, log() {} },
  }, bindings));
  return { page, calls, settings, warnings, errors, navigations, timers,
    advance(milliseconds) { now += milliseconds; timers.forEach(callback => callback()); },
    elapseWithoutTimers(milliseconds) { now += milliseconds; },
    mount: () => mounted[0]() };
}

async function enter(harness, arms = [1]) {
  await harness.mount();
  harness.page.draftInitConfig.unitRowIds = arms;
  await harness.page.confirmInitConfig();
}

test('three inputs are drafts and one confirmation submits only changed axes in one batch', async t => {
  assert.equal(/@change="sendSingleAdjust/.test(descriptor.template.content), false);
  assert.match(descriptor.template.content, /@click="confirmAdjustments"/);
  const h = setup(t, { debug: true });
  await enter(h);
  h.page.armList.device[0].adjust = 2;
  h.page.armList.device[2].adjust = 0.5;
  assert.equal(h.calls.adjusts.length, 0);
  await h.page.confirmAdjustments();
  assert.equal(h.calls.adjusts.length, 1);
  const request = h.calls.adjusts[0];
  assert.equal(request.module_id, 17);
  assert.equal(request.unit_id, 32);
  assert.equal(request.adjustments.length, 2);
  assert.equal(request.adjustments[0].parameter_name, 'rotation');
  assert.equal(request.adjustments[1].parameter_name, 'telescopic');
  assert.equal(h.page.armList.device[0].adjust, 0);
});

test('zero and nonfinite increments cannot create a batch', async t => {
  const h = setup(t, { debug: true });
  await enter(h);
  await h.page.confirmAdjustments();
  h.page.armList.device[0].adjust = NaN;
  await h.page.confirmAdjustments();
  assert.equal(h.calls.adjusts.length, 0);
});

test('queued batch keeps target locked after HTTP success and polling does not resend', async t => {
  const h = setup(t, { debug: true, adjust: async () => ({ data: batch() }), poll: async () => batch() });
  await enter(h, [1, 2]);
  h.page.armList.device[0].adjust = 2;
  await h.page.confirmAdjustments();
  assert.equal(h.page.busy.value, true);
  await h.page.confirmAdjustments();
  await h.page.handleArmSwitch(2);
  await h.page.pollBatch();
  assert.equal(h.calls.adjusts.length, 1);
  assert.equal(h.page.initConfig.unitId, 32);
  assert.equal(h.page.armList.device[0].current, 0);
});

test('refresh restores an active batch without re-confirming hardware or dispatching drawings', async t => {
  const h = setup(t, { debug: false, failDrawings: true, active: (_, unitId) => unitId === 32 ? batch() : null });
  await h.mount();
  assert.equal(h.page.batchState.value.id, 'batch-test');
  assert.equal(h.page.busy.value, true);
  assert.equal(h.calls.confirms.length, 0);
  assert.equal(h.calls.coordinates.length, 0);
  assert.equal(h.calls.drawings, 0);
});

test('lost submission response retains request identity and queries instead of retrying', async t => {
  let submitted;
  const h = setup(t, { debug: true, adjust: async payload => { submitted = payload; throw new Error('connection lost'); },
    byRequest: id => batch({ request_id: id }) });
  await enter(h);
  h.page.armList.device[0].adjust = 2;
  await h.page.confirmAdjustments();
  assert.equal(h.page.busy.value, true);
  await h.page.confirmAdjustments();
  await h.page.pollBatch();
  assert.equal(h.page.batchState.value.request_id, submitted.request_id);
  assert.equal(h.calls.adjusts.length, 1);
  assert.equal(h.calls.polls, 1);
});

test('a restored completed batch can load drawings and begin a new configuration session', async t => {
  const h = setup(t, { debug: false, active: (_, unitId) => unitId === 32 ? batch() : null,
    poll: async () => batch({ status: 'completed', target_locked: false }) });
  await h.mount();
  assert.equal(h.calls.drawings, 0);
  await h.page.pollBatch();
  await h.page.openConfiguration();
  assert.equal(h.calls.drawings, 1);
  assert.equal(h.page.initDialogVisible.value, true);
  assert.equal(h.page.draftInitConfig.drawingId, 7);
  assert.equal(h.calls.adjusts.length, 0);
});

test('manual resolution clears sent uncertain values but retains unsent draft increments', async t => {
  const result = batch({ status: 'uncertain', steps: [
    { parameter_name: 'rotation', device_id: 1, position: 2, status: 'uncertain' },
    { parameter_name: 'swing', device_id: 2, position: 1, status: 'pending' },
  ] });
  const h = setup(t, { debug: true, active: (_, unitId) => unitId === 32 ? result : null, batch: result });
  await h.mount();
  await h.page.acknowledgeBatch();
  assert.equal(h.page.busy.value, false);
  assert.equal(h.page.armList.device[0].adjust, 0);
  assert.equal(h.page.armList.device[1].adjust, 1);
  assert.equal(h.calls.adjusts.length, 0);
});

test('settings are shared across pages, default off after reload, and reset on login/logout', () => {
  const container = pinia.createPinia();
  pinia.setActivePinia(container);
  const settings = debugModule.useDebugSettingsStore();
  assert.equal(settings.skipDrawingBinding, false);
  settings.skipDrawingBinding = true;
  assert.equal(debugModule.useDebugSettingsStore().skipDrawingBinding, true);
  assert.equal(debugModule.useDebugSettingsStore(pinia.createPinia()).skipDrawingBinding, false);

  const storage = new Map();
  const userModule = evaluate(read('../src/stores/user.ts'), { vue, pinia, './debugSettings': debugModule }, {
    localStorage: { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) },
  });
  const user = userModule.useUserStore(container);
  settings.skipDrawingBinding = true;
  user.clearUser();
  assert.equal(settings.skipDrawingBinding, false);
  settings.skipDrawingBinding = true;
  user.setUserInfo({ account: 'test', name: 'Test', typeId: 1, token: 'test', headImage: '', updateTime: '' });
  assert.equal(settings.skipDrawingBinding, false);
  assert.equal([...storage.keys()].some(key => /debug/i.test(key)), false);
});

test('debug initialization works with no drawings and does not request the drawing service', async t => {
  const h = setup(t, { debug: true, noDrawings: true, failDrawings: true });
  await h.mount();
  assert.equal(h.calls.drawings, 0);
  assert.equal(h.page.initDialogVisible.value, true);
  assert.equal(h.page.isReady.value, false);
  assert.equal(h.navigations.length, 0);
});

test('debug entry still confirms selected arms but never sends drawings or opens pointcloud views', async t => {
  const h = setup(t, { debug: true });
  await enter(h, [1, 2]);
  assert.deepEqual(Array.from(h.calls.confirms[0].unit_ids), [32, 64]);
  assert.equal(h.calls.coordinates.length, 0);
  assert.equal(h.page.isReady.value, true);
  assert.equal(h.page.initConfig.drawingId, 0);
  h.page.openDrawingDialog();
  h.page.togglePointCloudViews();
  assert.equal(h.page.initDialogVisible.value, false);
  assert.equal(h.page.pointCloudViews.value.length, 0);
  assert.equal(h.calls.sockets.length, 1);
});

test('confirmation failure leaves the dialog open and prevents movement and saving', async t => {
  const h = setup(t, { debug: true, confirm: async () => {
    throw { response: { data: { detail: { reason: 'ROS handshake timed out' } } } };
  } });
  await enter(h);
  assert.equal(h.page.isReady.value, false);
  assert.equal(h.page.initDialogVisible.value, true);
  await h.page.confirmAdjustments();
  await h.page.handleSaveConfig();
  assert.equal(h.calls.adjusts.length, 0);
  assert.equal(h.calls.saves.length, 0);
  assert.equal(h.errors[0], 'ROS handshake timed out');
});

test('an unconfirmed arm in a successful HTTP response cannot enable controls', async t => {
  const h = setup(t, { debug: true, confirm: async () => ({ code: 200, data: { confirmations: [{ unit_id: 32, confirmed: false }] } }) });
  await enter(h);
  assert.equal(h.page.isReady.value, false);
  assert.equal(Object.keys(h.page.armProfiles).length, 0);
});

test('normal mode still requires available drawings and a selected drawing', async t => {
  const missing = setup(t, { noDrawings: true });
  await missing.mount();
  assert.equal(missing.page.isDebugMode, false);
  assert.equal(missing.page.isReady.value, false);
  assert.ok(missing.navigations.some(path => /drawingmanage/i.test(path)));

  const h = setup(t);
  await h.mount();
  h.page.draftInitConfig.unitRowIds = [1];
  h.page.draftInitConfig.drawingId = 0;
  await h.page.confirmInitConfig();
  assert.equal(h.calls.confirms.length, 0);
  assert.equal(h.page.isReady.value, false);
});

test('normal mode confirms arms before dispatching drawings and saves the drawing association', async t => {
  const h = setup(t);
  await enter(h, [1, 2]);
  assert.deepEqual(h.calls.events, ['confirm', 'drawing', 'drawing']);
  assert.equal(h.page.isReady.value, true);
  await h.page.handleSaveConfig();
  assert.equal(h.calls.saves[0].is_debug, false);
  assert.equal(h.calls.saves[0].drawing_id, 7);
});

test('a failed drawing dispatch keeps normal controls disabled', async t => {
  const h = setup(t, { coordinate: async () => { throw new Error('pointcloud unavailable'); } });
  await enter(h);
  assert.equal(h.page.isReady.value, false);
  assert.equal(h.page.initDialogVisible.value, true);
  await h.page.handleSaveConfig();
  assert.equal(h.calls.saves.length, 0);
});

test('debug arm switching preserves independent state and uses the correct business sensor when saving', async t => {
  const h = setup(t, { debug: true });
  await enter(h, [1, 2]);
  h.calls.sockets[0].receive({ module_id: 0, data_type: 'rotation_axis_encoder', device_id: 1, position: 10 });
  h.calls.sockets[0].receive({ module_id: 0, data_type: 'pressure_sensor', device_id: 21, position: 2.5 });
  h.calls.sockets[0].receive({ module_id: 0, data_type: 'imu_pose', device_id: 21, x: 1.5, y: 2, z: 3 });
  h.page.armList.device[0].adjust = 3;
  await h.page.handleArmSwitch(2);
  assert.equal(h.page.isReady.value, true);
  assert.equal(h.page.initConfig.sensorId, 81);
  h.calls.sockets[0].receive({ module_id: 0, data_type: 'rotation_axis_encoder', device_id: 4, position: 20 });
  h.calls.sockets[0].receive({ module_id: 0, data_type: 'pressure_sensor', device_id: 21, position: 99 });
  assert.equal(h.page.armList.device[3].current, 0);
  await h.page.handleSaveConfig();
  assert.equal(h.calls.saves[0].sensor_id, 81);
  assert.equal(h.calls.saves[0].unit_id, 64);
  assert.equal(h.calls.saves[0].devices[0].device_id, 4);
  await h.page.handleArmSwitch(1);
  assert.equal(h.page.armList.device[0].current, 10);
  assert.equal(h.page.armList.device[0].adjust, 3);
  assert.equal(h.page.armList.device[3].current, 2.5);
  assert.equal(h.page.initConfig.sensorId, 49);
  await h.page.handleSaveConfig();
  assert.equal(h.calls.saves[1].is_debug, true);
  assert.equal(h.calls.saves[1].drawing_id, null);
  assert.equal(h.calls.saves[1].sensor_id, 49);
  assert.equal(h.calls.saves[1].x, 1.5);
});

test('saving blocks duplicate submissions, axis requests and target switching until completion', async t => {
  const pending = deferred();
  const h = setup(t, { debug: true, save: () => pending.promise });
  await enter(h, [1, 2]);
  const first = h.page.handleSaveConfig();
  await h.page.handleSaveConfig();
  await h.page.handleArmSwitch(2);
  await h.page.confirmAdjustments();
  assert.equal(h.calls.saves.length, 1);
  assert.equal(h.calls.adjusts.length, 0);
  assert.equal(h.page.initConfig.unitId, 32);
  pending.resolve({ code: 200 });
  await first;
  await h.page.handleArmSwitch(2);
  assert.equal(h.page.initConfig.unitId, 64);
});

test('command echoes cannot overwrite actual feedback and motion requests prevent target switching', async t => {
  const pending = deferred();
  const h = setup(t, { debug: true, adjust: () => pending.promise });
  await enter(h, [1, 2]);
  h.page.applyFeedback({ module_id: 0, data_type: 'rotation_axis_encoder', device_id: 1, position: 12 });
  h.page.armList.device[0].adjust = 2;
  const first = h.page.confirmAdjustments();
  await h.page.confirmAdjustments();
  await h.page.handleArmSwitch(2);
  assert.equal(h.calls.adjusts.length, 1);
  assert.equal(h.page.initConfig.unitId, 32);
  pending.resolve({ code: 200, data: { id: 'test-batch', request_id: h.calls.adjusts[0].request_id, module_id: 17, unit_id: 32,
    seg: 0, status: 'completed', target_locked: false, steps: [{ device_id: 1, parameter_name: 'rotation', position: 2, status: 'completed' }] } });
  await first;
  assert.equal(h.page.armList.device[0].current, 12);
  assert.equal(h.page.armList.device[0].initial, 12);
  h.calls.sockets[0].receive({ module_id: 0, data_type: 'rotation_axis_encoder', device_id: 1, position: 14 });
  assert.equal(h.page.armList.device[0].current, 14);
});

test('a missing registered pressure sensor prevents saving with a fabricated sensor number', async t => {
  const h = setup(t, { debug: true, noSensors: true });
  await enter(h);
  assert.equal(h.page.isReady.value, true);
  await h.page.handleSaveConfig();
  assert.equal(h.calls.saves.length, 0);
  assert.ok(h.warnings.some(text => text.includes('压力传感器')));
});

test('the current mode is fixed on entry and changed settings apply to the next entry', async t => {
  const container = pinia.createPinia();
  const h = setup(t, { container, debug: true });
  await enter(h);
  h.settings.skipDrawingBinding = false;
  assert.equal(h.page.isDebugMode, true);
  assert.equal(h.calls.drawings, 0);
  const next = setup(t, { container });
  await enter(next);
  assert.equal(next.page.isDebugMode, false);
  assert.equal(next.calls.drawings, 1);
  assert.equal(next.calls.coordinates.length, 1);
});

test('existing no-ROS simulation remains independent and can simulate saving without registered sensors', async t => {
  const h = setup(t, { debug: true, noRosDebug: true, noSensors: true });
  await enter(h);
  assert.equal(h.calls.sockets.length, 0);
  assert.equal(h.page.armList.device[3].current, 0.5);
  assert.equal(h.page.loading.value, true);
  await h.page.handleSaveConfig();
  assert.equal(h.calls.saves.length, 1);
  assert.equal(h.calls.saves[0].is_debug, true);
  assert.equal(h.calls.saves[0].drawing_id, null);
});

test('real entry requires the confirmed SEG instead of guessing it from the business module', async t => {
  const h = setup(t, { debug: true, confirm: async () => ({ code: 200, data: { confirmations: [{ unit_id: 32, confirmed: true }] } }) });
  await enter(h);
  assert.equal(h.page.isReady.value, false);
  assert.ok(h.errors.some(text => text.includes('SEG')));
});

test('foreign modules, wrong arm/type and missing module cannot update actual values', async t => {
  const h = setup(t, { debug: true, seg: 3 });
  await enter(h, [1, 2]);
  const receive = payload => h.calls.sockets[0].receive({ module_id: 3, device_id: 1, data_type: 'rotation_axis_encoder', position: 9, ...payload });
  receive({ module_id: 7 });
  receive({ module_id: 17 });
  receive({ module_id: null });
  receive({ module_id_space: 'business' });
  receive({ device_id: 4 });
  receive({ data_type: 'swing_axis_encoder' });
  assert.equal(h.page.fieldStatus('rotation'), 'waiting');
  assert.equal(h.page.displayFeedback('rotation', 0), '—');
  receive({ position: 0 });
  assert.equal(h.page.fieldStatus('rotation'), 'current');
  assert.equal(h.page.displayFeedback('rotation', 0), '0.00');
});

test('missing, invalid and nonfinite samples do not overwrite or refresh actual zero', async t => {
  const h = setup(t, { debug: true });
  await enter(h);
  const receive = position => h.page.applyFeedback({ module_id: 0, device_id: 1, data_type: 'rotation_axis_encoder', position });
  receive(0);
  h.advance(6000);
  for (const value of [null, undefined, '', false, [], 'invalid', NaN, Infinity]) receive(value);
  assert.equal(h.page.armList.device[0].current, 0);
  assert.equal(h.page.fieldStatus('rotation'), 'stale');
  assert.equal(h.page.fieldStatus('swing'), 'waiting');
});

test('axis, pressure and each IMU component have independent validity and freshness', async t => {
  const h = setup(t, { debug: true });
  await enter(h);
  h.page.applyFeedback({ module_id: 0, device_id: 1, data_type: 'rotation_axis_encoder', position: 12 });
  assert.equal(h.page.loading.value, false);
  assert.equal(h.page.fieldStatus('pressure'), 'waiting');
  h.page.applyFeedback({ module_id: 0, device_id: 21, data_type: 'pressure_sensor', position: 0 });
  h.page.applyFeedback({ module_id: 0, device_id: 21, data_type: 'imu_pose', x: 4, y: null, z: 'invalid', swing_angle: 0 });
  assert.equal(h.page.fieldStatus('x'), 'current');
  assert.equal(h.page.fieldStatus('y'), 'waiting');
  assert.equal(h.page.fieldStatus('z'), 'waiting');
  assert.equal(h.page.fieldStatus('swing_angle'), 'current');
  h.advance(6000);
  assert.equal(h.page.fieldStatus('rotation'), 'stale');
  assert.equal(h.page.fieldStatus('x'), 'stale');
  assert.equal(h.page.fieldStatus('pressure'), 'current');
  h.advance(5000);
  assert.equal(h.page.fieldStatus('pressure'), 'stale');
  h.page.applyFeedback({ module_id: 0, device_id: 21, data_type: 'imu_pose', x: 0, valid_fields: ['x'] });
  assert.equal(h.page.fieldStatus('x'), 'current');
  assert.equal(h.page.imuFeedback.x, 0);
  assert.equal(h.page.fieldStatus('swing_angle'), 'stale');
});

test('restored caches are historical until a new valid sample, and disconnect expires current samples', async t => {
  const h = setup(t, { debug: true });
  await enter(h, [1, 2]);
  const sample = { module_id: 0, device_id: 1, data_type: 'rotation_axis_encoder', position: 12 };
  h.page.applyFeedback(sample);
  await h.page.handleArmSwitch(2);
  await h.page.handleArmSwitch(1);
  assert.equal(h.page.fieldStatus('rotation'), 'history');
  assert.equal(h.page.armList.device[0].current, 12);
  h.page.applyFeedback(sample);
  assert.equal(h.page.fieldStatus('rotation'), 'current');
  h.calls.sockets[0].close();
  assert.equal(h.page.fieldStatus('rotation'), 'stale');
  assert.equal(h.page.armList.device[0].current, 12);
});

test('unknown measurements save as null and historical measurements retain their status', async t => {
  const h = setup(t, { debug: true });
  await enter(h, [1, 2]);
  await h.page.handleSaveConfig();
  const first = h.calls.saves[0];
  assert.equal(first.devices[0].initial, null);
  assert.equal(first.devices[0].current, null);
  assert.equal(first.devices[3].current, null);
  assert.equal(first.x, null);
  assert.equal(first.feedback_state.pressure.status, 'waiting');
  h.page.applyFeedback({ module_id: 0, device_id: 1, data_type: 'rotation_axis_encoder', position: 0 });
  await h.page.handleArmSwitch(2);
  await h.page.handleArmSwitch(1);
  await h.page.handleSaveConfig();
  const second = h.calls.saves[1];
  assert.equal(second.devices[0].initial, 0);
  assert.equal(second.devices[0].current, 0);
  assert.equal(second.feedback_state.rotation.status, 'history');
});

test('saving refreshes the age/status clock even if the browser has throttled timers', async t => {
  const h = setup(t, { debug: true });
  await enter(h);
  h.page.applyFeedback({ module_id: 0, device_id: 1, data_type: 'rotation_axis_encoder', position: 2 });
  h.elapseWithoutTimers(6000);
  await h.page.handleSaveConfig();
  assert.equal(h.calls.saves[0].feedback_state.rotation.status, 'stale');
  assert.equal(h.calls.saves[0].feedback_state.rotation.age_ms, 6000);
});

test('ACK events show acceptance/rejection without changing measurements or retrying a command', async t => {
  const h = setup(t, { debug: true });
  await enter(h);
  const ack = { data_type: 'cmd_ack', module_id: 0, device_id: 1, ack_msg: 1, result: 0, detail: 0,
    module_resolution: 'resolved', business_module_id: 17, module_candidates: [17], raw: { module_id: 0 } };
  h.page.applyFeedback(ack);
  assert.match(h.page.ackEvents.value[0].text, /收到接受回执/);
  assert.match(h.page.ackEvents.value[0].text, /不表示运动完成/);
  assert.equal(h.page.fieldStatus('rotation'), 'waiting');
  h.page.applyFeedback({ ...ack, module_id: 17, result: 3, detail: 1 });
  assert.match(h.page.ackEvents.value[0].text, /拒绝：参数越界/);
  h.page.applyFeedback({ ...ack, ack_msg: 4, result: 3 });
  assert.match(h.page.ackEvents.value[0].text, /MSG=4/);
  assert.doesNotMatch(h.page.ackEvents.value[0].text, /本次微调/);
  assert.equal(h.calls.adjusts.length, 0);
  assert.equal(h.page.isReady.value, true);
});

test('ACK history belongs to its arm and a new initial configuration clears all previous arm ACKs', async t => {
  const h = setup(t, { debug: true }); await enter(h, [1, 2]);
  const ack = { data_type: 'cmd_ack', module_id: 0, device_id: 1, ack_msg: 1, result: 0, detail: 0,
    module_resolution: 'resolved', business_module_id: 17 };
  h.page.applyFeedback(ack);
  const firstArmText = h.page.ackEvents.value[0].text;
  await h.page.handleArmSwitch(2);
  assert.equal(h.page.ackEvents.value.length, 0);
  h.page.applyFeedback({ ...ack, device_id: 4, result: 1 });
  const secondArmText = h.page.ackEvents.value[0].text;
  assert.match(secondArmText, /轴 4.*轴忙/);
  await h.page.handleArmSwitch(1);
  assert.equal(h.page.ackEvents.value.length, 1);
  assert.equal(h.page.ackEvents.value[0].text, firstArmText);
  await h.page.handleArmSwitch(2);
  assert.equal(h.page.ackEvents.value.length, 1);
  assert.equal(h.page.ackEvents.value[0].text, secondArmText);
  await h.page.openConfiguration();
  h.page.draftInitConfig.unitRowIds = [1, 2];
  await h.page.confirmInitConfig();
  assert.equal(h.page.initConfig.unitId, 32);
  assert.equal(h.page.ackEvents.value.length, 0);
  await h.page.handleArmSwitch(2);
  assert.equal(h.page.ackEvents.value.length, 0);
  assert.equal(h.calls.adjusts.length, 0);
});

test('foreign ACKs are isolated while ambiguous or legacy ACKs stay explicitly unattributed', async t => {
  const h = setup(t, { debug: true });
  await enter(h);
  const ack = { data_type: 'cmd_ack', module_id: 1, device_id: 1, ack_msg: 1, result: 0, detail: 0 };
  h.page.applyFeedback({ ...ack, module_resolution: 'resolved', business_module_id: 18 });
  h.page.applyFeedback({ ...ack, device_id: 4, module_resolution: 'resolved', business_module_id: 17 });
  assert.equal(h.page.ackEvents.value.length, 0);
  h.page.applyFeedback({ ...ack, module_resolution: 'ambiguous', module_candidates: [1, 17], business_module_id: null });
  assert.match(h.page.ackEvents.value[0].text, /归属待确认/);
  assert.match(h.page.ackEvents.value[0].raw, /module_candidates/);
  for (let index = 0; index < 25; index++) h.page.applyFeedback(ack);
  assert.equal(h.page.ackEvents.value.length, 20);
  assert.match(h.page.ackEvents.value[0].text, /归属待确认/);
  assert.equal(h.calls.adjusts.length, 0);
});

test('freshness policy overrides are validated and simulation is always explicitly marked', async t => {
  assert.deepEqual(JSON.parse(JSON.stringify(feedbackState.feedbackTimeouts({ VITE_ROS_AXIS_STALE_MS: 900, VITE_ROS_PRESSURE_STALE_MS: -1, VITE_ROS_IMU_STALE_MS: 'invalid' }))), { axis: 900, pressure: 10000, imu: 5000 });
  const h = setup(t, { debug: true, noRosDebug: true });
  await enter(h);
  h.advance(99999);
  assert.equal(h.page.fieldStatus('rotation'), 'simulated');
  assert.equal(h.page.fieldStatus('pressure'), 'simulated');
});


test('backend simulated batches keep polling rather than using frontend-only completion', async t => {
  const h = setup(t, { debug: true, adjust: async () => ({ data: batch({ simulated: true }) }),
    poll: async () => batch({ simulated: true, status: 'completed', target_locked: false }) });
  await enter(h);
  h.page.armList.device[0].adjust = 2;
  await h.page.confirmAdjustments();
  await h.page.pollBatch();
  assert.equal(h.calls.polls, 1);
  assert.equal(h.page.busy.value, false);
});

test('backend mock telemetry is displayed as simulated and cannot be confused with real feedback', async t => {
  const h = setup(t, { debug: true }); await enter(h);
  h.page.applyFeedback({ data_type: 'rotation_axis_encoder', module_id: 0, module_id_space: 'seg', device_id: 1,
    position: 2, position_valid: true, simulated: true });
  assert.equal(h.page.fieldStatus('rotation'), 'simulated');
});

test('changing connections invalidates the old arm session and sends no movement', async t => {
  const h = setup(t, { debug: true }); await enter(h);
  assert.equal(h.page.isReady.value, true);
  h.page.connectionChanged();
  assert.equal(h.page.isReady.value, false);
  assert.equal(h.page.confirmedSeg.value, null);
  assert.equal(h.calls.adjusts.length, 0);
});


test('empty business drawing library can use the backend builtin mock option and save without inventing a drawing ID', async t => {
  const h = setup(t, { drawingMode: 'mock', noDrawings: true }); await enter(h);
  assert.equal(h.page.isReady.value, true);
  assert.equal(h.calls.coordinates[0].drawing_id, null);
  assert.equal(h.calls.coordinates[0].drawing_source, 'builtin_mock');
  assert.equal(h.navigations.length, 0);
  await h.page.handleSaveConfig();
  assert.equal(h.calls.saves[0].drawing_id, null);
  assert.equal(h.calls.saves[0].drawing_source, 'builtin_mock');
  assert.equal(h.calls.saves[0].is_debug, false);
});

test('redraw cancellation and arm switching preserve builtin drawing source', async t => {
  const h = setup(t, { drawingMode: 'mock', noDrawings: true }); await enter(h, [1, 2]);
  h.page.selectedArmRowId.value = 2; await h.page.handleArmSwitch(2);
  assert.equal(h.page.initConfig.drawingSource, 'builtin_mock');
  assert.equal(h.page.isReady.value, true);
  h.page.openDrawingDialog();
  assert.equal(h.page.initDialogVisible.value, true);
});

test('switching arms displays only that arm batch and restores each completed record on return', async t => {
  const h = setup(t, { debug: true, adjust: async payload => ({ data: batch({
    ...payload, id: `completed-${payload.unit_id}`, status: 'completed', target_locked: false,
    message: `completed arm ${payload.unit_id}`,
    steps: payload.adjustments.map(item => ({ ...item, device_id: 1, status: 'completed' })),
  }) }) });
  await enter(h, [1, 2]);
  h.page.armList.device[0].adjust = 2;
  await h.page.confirmAdjustments();
  assert.equal(h.page.batchState.value.unit_id, 32);
  await h.page.handleArmSwitch(2);
  assert.equal(h.page.batchState.value, null);
  h.page.armList.device[1].adjust = 3;
  await h.page.confirmAdjustments();
  assert.equal(h.page.batchState.value.unit_id, 64);
  await h.page.handleArmSwitch(1);
  assert.equal(h.page.batchState.value.id, 'completed-32');
  assert.equal(h.page.batchState.value.steps[0].parameter_name, 'rotation');
  assert.equal(h.page.batchState.value.steps[0].position, 2);
  await h.page.handleArmSwitch(2);
  assert.equal(h.page.batchState.value.id, 'completed-64');
  assert.equal(h.page.batchState.value.steps[0].parameter_name, 'swing');
  assert.equal(h.page.batchState.value.steps[0].position, 3);
  assert.equal(h.calls.adjusts.length, 2);
});

test('switching to an already configured arm with no batch clears the previous arm record', async t => {
  const h = setup(t, { debug: true }); await enter(h, [1, 2]);
  await h.page.handleArmSwitch(2);
  await h.page.handleArmSwitch(1);
  h.page.armList.device[0].adjust = 2;
  await h.page.confirmAdjustments();
  assert.equal(h.page.batchState.value.unit_id, 32);
  await h.page.handleArmSwitch(2);
  assert.equal(h.page.batchState.value, null);
  assert.equal(h.page.busy.value, false);
  await h.page.handleArmSwitch(1);
  assert.equal(h.page.batchState.value.unit_id, 32);
  assert.equal(h.calls.adjusts.length, 1);
});

test('a new initial configuration clears prior arm profiles and shares its newly dispatched drawing', async t => {
  let session = 1;
  const h = setup(t, { drawings: [{ drawingId: 7, drawingName: 'first drawing' }, { drawingId: 9, drawingName: 'new drawing' }],
    coordinate: async payload => ({ code: 200, views: {
    front: `/session-${session}/drawing-${payload.drawing_id}/front`,
  } }) });
  await enter(h, [1, 2]);
  await h.page.handleArmSwitch(2);
  h.page.armList.device[0].adjust = 2;
  await h.page.confirmAdjustments();
  assert.equal(h.page.batchState.value.unit_id, 64);
  assert.equal(h.page.armProfiles['2'].drawingId, 7);
  await h.page.handleArmSwitch(1);

  session = 2;
  await h.page.openConfiguration();
  h.page.draftInitConfig.unitRowIds = [1, 2];
  h.page.draftInitConfig.drawingId = 9;
  await h.page.confirmInitConfig();
  assert.equal(h.page.isReady.value, true);
  assert.equal(h.page.initConfig.drawingId, 9);
  assert.equal(h.page.batchState.value, null);
  assert.equal(h.calls.coordinates.length, 4);
  await h.page.handleArmSwitch(2);
  assert.equal(h.page.initConfig.unitId, 64);
  assert.equal(h.page.initConfig.drawingId, 9);
  assert.equal(h.page.armProfiles['2'].drawingId, 9);
  assert.equal(h.page.batchState.value, null);
  assert.match(h.page.pointCloudViews.value[0].url, /session-2\/drawing-9\/front/);
  assert.equal(h.page.armList.device[0].current, 0);
  assert.equal(h.page.armList.device[0].adjust, 0);
  assert.equal(h.calls.adjusts.length, 1);
});

for (const target of ['same arm', 'another arm']) {
  for (const outcome of ['success', 'empty', 'error']) {
    test(`a late ${outcome} query cannot overwrite a new batch on ${target}`, async t => {
      const pending = deferred();
      let submissions = 0;
      const h = setup(t, { debug: true, poll: () => pending.promise, adjust: async payload => {
        submissions++;
        return { data: batch({
          ...payload, id: `batch-${submissions}`, status: submissions === 1 ? 'completed' : 'executing',
          target_locked: submissions !== 1, message: `batch ${submissions}`,
          steps: payload.adjustments.map(item => ({ ...item, device_id: 1, status: submissions === 1 ? 'completed' : 'pending' })),
        }) };
      } });
      await enter(h, [1, 2]);
      h.page.armList.device[0].adjust = 2;
      await h.page.confirmAdjustments();
      const previous = h.page.batchState.value;
      const polling = h.page.pollBatch();
      if (target === 'another arm') await h.page.handleArmSwitch(2);
      h.page.armList.device[0].adjust = 3;
      await h.page.confirmAdjustments();
      const current = h.page.batchState.value;
      assert.equal(current.id, 'batch-2');
      assert.equal(h.page.busy.value, true);
      if (outcome === 'error') pending.reject(new Error('late old query failed'));
      else pending.resolve(outcome === 'success' ? previous : null);
      await polling;
      assert.equal(h.page.batchState.value, current);
      assert.equal(h.page.batchState.value.id, 'batch-2');
      assert.equal(h.page.batchState.value.message, 'batch 2');
      assert.equal(h.page.batchState.value.unit_id, target === 'same arm' ? 32 : 64);
      assert.equal(h.page.busy.value, true);
      assert.equal(h.page.armList.device[0].adjust, 3);
      assert.equal(h.calls.adjusts.length, 2);
      assert.equal(h.calls.polls, 1);
    });
  }
}

for (const outcome of ['empty', 'error']) {
  test(`a late ${outcome} query after changing to an arm with no batch leaves its context empty`, async t => {
    const pending = deferred();
    const h = setup(t, { debug: true, poll: () => pending.promise });
    await enter(h, [1, 2]);
    h.page.armList.device[0].adjust = 2;
    await h.page.confirmAdjustments();
    const polling = h.page.pollBatch();
    await h.page.handleArmSwitch(2);
    assert.equal(h.page.batchState.value, null);
    if (outcome === 'error') pending.reject(new Error('old arm query failed'));
    else pending.resolve(null);
    await polling;
    assert.equal(h.page.batchState.value, null);
    assert.equal(h.page.busy.value, false);
    assert.equal(h.page.initConfig.unitId, 64);
    assert.equal(h.calls.adjusts.length, 1);
  });
}

test('resetting control context clears the old batch record and its polling timer', async t => {
  const h = setup(t, { debug: true, adjust: async () => ({ data: batch() }) });
  await enter(h);
  const baseTimers = h.timers.size;
  h.page.armList.device[0].adjust = 2;
  await h.page.confirmAdjustments();
  assert.equal(h.page.batchState.value.id, 'batch-test');
  assert.equal(h.timers.size, baseTimers + 1);
  h.page.resetControlState();
  assert.equal(h.page.batchState.value, null);
  assert.equal(h.timers.size, baseTimers);
  assert.equal(h.calls.adjusts.length, 1);
});

test('both angular inputs use a 0.01-degree step and two decimal places', () => {
  const inputs = [...descriptor.template.content.matchAll(/<el-input-number\b[^>]*\/>/g)].map(match => match[0]);
  assert.equal(inputs.length, 3);
  for (const input of inputs.slice(0, 2)) {
    assert.match(input, /:step="0\.01"/);
    assert.match(input, /:precision="2"/);
  }
  assert.doesNotMatch(inputs[2], /:step=|:precision=/);
});

test('0.01-degree angular increments reach batch submission without truncation', async t => {
  const h = setup(t, { debug: true });
  await enter(h);
  h.page.armList.device[0].adjust = 0.01;
  h.page.armList.device[1].adjust = -0.01;
  await h.page.confirmAdjustments();
  assert.deepEqual(Array.from(h.calls.adjusts[0].adjustments, item => ({ ...item })), [
    { parameter_name: 'rotation', position: 0.01 },
    { parameter_name: 'swing', position: -0.01 },
  ]);
});
