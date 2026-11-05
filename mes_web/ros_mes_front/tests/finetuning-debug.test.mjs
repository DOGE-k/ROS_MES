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
  isDebugMode, isReady, busy, loading, initConfig, draftInitConfig, initDialogVisible,
  armList, armProfiles, armIdList, selectedArmRowId, imuFeedback, pointCloudViews,
  confirmInitConfig, handleArmSwitch, handleSaveConfig, sendSingleAdjust,
  applyFeedback, openDrawingDialog, togglePointCloudViews,
  confirmedSeg, feedbackMarks, feedbackClock, feedbackConnected, fieldStatus, displayFeedback, ackEvents,
});`;

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function setup(t, options = {}) {
  const container = options.container || pinia.createPinia();
  pinia.setActivePinia(container);
  const settings = debugModule.useDebugSettingsStore(container);
  if (options.debug !== undefined) settings.skipDrawingBinding = options.debug;
  const calls = { drawings: 0, confirms: [], coordinates: [], saves: [], adjusts: [], events: [], sockets: [] };
  const warnings = [], errors = [], navigations = [], mounted = [], unmounted = [];
  let now = 1000;
  const timers = new Map();
  const units = [{ id: 1, Unit_ID: 32 }, { id: 2, Unit_ID: 64 }];
  const api = {
    async getUnitsByDeviceApi() { return { data: units }; },
    async getDrawingListApi() {
      calls.drawings++;
      if (options.failDrawings) throw new Error('drawing service unavailable');
      return { data: options.noDrawings ? [] : [{ drawingId: 7, drawingName: 'drawing' }] };
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
    async sendFineTuning(payload) {
      calls.adjusts.push(payload);
      if (options.adjust) return options.adjust(payload);
      return { code: 200, data: [{ device_id: payload.device_id, parameter_name: payload.parameter_name, position: payload.position }, { type: 'pressure', position: 0 }] };
    },
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
    'element-plus': { ElMessage: { success() {}, warning: text => warnings.push(text), error: text => errors.push(text) } },
    '@element-plus/icons-vue': { ArrowLeft: {} },
    '@/api/rosApi': api,
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
  await h.page.sendSingleAdjust(0);
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
  await h.page.sendSingleAdjust(0);
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
  const first = h.page.sendSingleAdjust(0);
  await h.page.sendSingleAdjust(0);
  await h.page.handleArmSwitch(2);
  assert.equal(h.calls.adjusts.length, 1);
  assert.equal(h.page.initConfig.unitId, 32);
  pending.resolve({ code: 200, data: [{ device_id: 1, parameter_name: 'rotation', position: 2 }] });
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
  h.settings.skipDrawingBinding = false;
  await enter(h);
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
