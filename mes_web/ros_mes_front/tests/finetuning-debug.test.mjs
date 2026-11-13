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
const drawingBaseline = evaluate(read('../src/api/drawingBaseline.ts'), {});
const { descriptor } = parse(read('../src/components/Main/ModulePage/FineTuningPage.vue'));
const bindings = `Object.assign(module.exports, {
  isReady, busy, loading, initConfig, draftInitConfig, initDialogVisible,
  armList, armProfiles, armIdList, selectedArmRowId, imuFeedback, pointCloudViews,
  confirmInitConfig, handleArmSwitch, handleSaveConfig, confirmAdjustments, calibrateMode,
  batchState, pollBatch, interruptBatch, acknowledgeBatch, openConfiguration, connectionChanged, resetControlState,
  applyFeedback, openDrawingDialog, togglePointCloudViews,
  confirmedSeg, feedbackMarks, feedbackClock, feedbackConnected, fieldStatus, displayFeedback, ackEvents,
  relativeAxisValue, displayAxisFeedback, axisFeedbackLabel, finetuningPreflightEnabled,
  drawingBaselines, activeDrawingBaseline, drawingBaselineLabel, displayDrawingReference,
  endSession, activeSession, resumedFromSession, tryResumeSession, persistSnapshot, drawingList, confirmedUnitIds,
  stopAxis, clearLocalStops, hasLocalStop, moduleHolds, localStopText, stopHolds, loadStopHolds, axisStopOptions,
});
Object.defineProperty(module.exports, 'isDebugMode', { get: () => isDebugMode.value });`;

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

// 内存版 Storage：lib.dom 的实现不参与测试，行为需与浏览器一致（含 key/index/length）
function memoryStorage(seed = {}) {
  const map = new Map(Object.entries(seed).map(([key, value]) => [key, String(value)]));
  return {
    getItem: key => (map.has(key) ? map.get(key) : null),
    setItem: (key, value) => { map.set(key, String(value)); },
    removeItem: key => { map.delete(key); },
    key: index => Array.from(map.keys())[index] ?? null,
    clear: () => map.clear(),
    get length() { return map.size; },
    dump: () => Object.fromEntries(map),
  };
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
  const calls = { drawings: 0, confirms: [], coordinates: [], saves: [], adjusts: [], events: [], sockets: [], polls: 0, interrupts: 0, acknowledgements: 0, sessions: 0, resumes: 0, closes: 0, stops: [], holdReads: 0, holdClears: [] };
  let latestBatch;
  const warnings = [], errors = [], messages = [], navigations = [], mounted = [], unmounted = [];
  let now = 1000;
  const timers = new Map();
  const timeouts = new Map(), windowEvents = new Map();
  let timeoutSequence = 0;
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
    async getActiveFineTuningBatch(moduleId, unitId) { return { data: options.active ? await options.active(moduleId, unitId) : null }; },
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
  // localStorage 存会话保持偏好，sessionStorage 存各臂界面快照
  const storage = () => {
    const map = new Map();
    return {
      getItem: key => (map.has(key) ? map.get(key) : null),
      setItem: (key, value) => { map.set(key, String(value)); },
      removeItem: key => { map.delete(key); },
      key: index => Array.from(map.keys())[index] ?? null,
      clear: () => map.clear(),
      get length() { return map.size; },
    };
  };
  const localStore = options.localStorage || storage();
  const snapshotStore = options.sessionStorage || storage();
  // 会话保持偏好从 localStorage 读取，因此 store 必须在本例的 Storage 上下文中求值
  const sessionModule = evaluate(read('../src/stores/fineTuningSession.ts'), { vue, pinia },
    { localStorage: localStore, sessionStorage: snapshotStore });
  const scope = vue.effectScope();
  t.after(() => { unmounted.forEach(callback => callback()); scope.stop(); });
  const page = scope.run(() => evaluate(descriptor.scriptSetup.content, {
    vue: { ...vue, onMounted(callback) { mounted.push(callback); }, onBeforeUnmount(callback) { unmounted.push(callback); } },
    'vue-router': { useRoute: () => ({ query: options.query || { module_id: 17, device_id: 17, x: 1, y: 1 } }), useRouter: () => ({ push: target => navigations.push(target) }) },
    'element-plus': { ElMessageBox: { confirm: async () => { if (options.cancelAcknowledge) throw new Error('cancel'); } }, ElMessage: { success: text => messages.push(['success', text]), info: text => messages.push(['info', text]), warning: text => warnings.push(text), error: text => errors.push(text) } },
    '@element-plus/icons-vue': { ArrowLeft: {} },
    '@/api/rosApi': { ...api, async getFineTuningDrawingOptions() {
      const result = await api.getDrawingListApi();
      return { data: options.drawingMode === 'mock' ? [{ drawingId: null, drawingName: '内置模拟图纸', drawingSource: 'builtin_mock' }, ...result.data] : result.data };
    } },
    '@/api/connectionSettings': { async getConnectionSettings() { return { data: {
      revision: 0, drawing_mode: settings.skipDrawingBinding ? 'skip' : options.drawingMode || 'real',
      finetuning_preflight_enabled: options.preflightEnabled,
    } }; } },
    '@/api/noRosDebug': { noRosDebug: Boolean(options.noRosDebug) },
    '@/api/session': {
      SESSION_REASON_LABELS: { closed: '已结束', superseded: '已被新的握手取代', connection_changed: '连接设置已变更', expired: '已超过保持时长', missing: '没有可续接的记录' },
      async getControlSession() {
        calls.sessions++;
        return { data: options.sessionState ? options.sessionState() : { session: null, latest: null, reason: null } };
      },
      async resumeControlSession(id) {
        calls.resumes++;
        return { data: options.resume ? options.resume(id) : { valid: false, reason: 'missing', session: null } };
      },
      async closeControlSession(id) { calls.closes++; return { data: { id } }; },
    },
    '@/api/localStop': {
      async requestLocalStop(payload) {
        calls.stops.push(payload);
        if (options.stop) return options.stop(payload);
        return { code: 200, message: '局部停指令已发送；设备是否停止待确认', data: {
          id: 1, mode: 'real', scope: payload.scope, module_id: payload.module_id,
          device_id: payload.device_id ?? null, state: 'sent', message: null,
          created_at: null, cleared_at: null, cleared_reason: null, active: true, simulated: false } };
      },
      async getLocalStopHolds() {
        calls.holdReads++;
        return { data: { mode: 'real', holds: options.holds ? options.holds() : [] } };
      },
      async clearLocalStopHolds(moduleId) {
        calls.holdClears.push(moduleId);
        return { data: { module_id: moduleId, cleared: 1 } };
      },
    },
    '@/stores/fineTuningSession': sessionModule,
    '@/api/deviceEncoding': encoding,
    '@/api/feedbackState': feedbackState,
    '@/api/drawingBaseline': drawingBaseline,
    '@/stores/debugSettings': debugModule,
  }, {
    window: { location: { protocol: 'http:', host: 'localhost' },
      addEventListener(name, callback) { windowEvents.set(name, callback); },
      removeEventListener(name) { windowEvents.delete(name); },
    },
    performance: { now: () => now },
    setInterval(callback) { const id = timers.size + 1; timers.set(id, callback); return id; },
    clearInterval(id) { timers.delete(id); },
    setTimeout(callback, delay = 0) {
      const id = ++timeoutSequence;
      timeouts.set(id, { callback, due: now + delay });
      return id;
    },
    clearTimeout(id) { timeouts.delete(id); },
    localStorage: localStore, sessionStorage: snapshotStore,
    WebSocket: FeedbackSocket, console: { warn() {}, error() {}, log() {} },
  }, bindings));
  return { page, calls, settings, warnings, errors, messages, navigations, timers, storages: { local: localStore, session: snapshotStore },
    sessionSettings: () => sessionModule.useFineTuningSessionStore(container),
    advance(milliseconds) { now += milliseconds; timers.forEach(callback => callback()); },
    elapseWithoutTimers(milliseconds) { now += milliseconds; },
    flushTimeouts() {
      for (const [id, timeout] of timeouts) {
        if (timeout.due > now) continue;
        timeouts.delete(id);
        timeout.callback();
      }
    },
    windowEvents,
    mount: () => mounted[0]() };
}

async function enter(harness, arms = [1]) {
  await harness.mount();
  harness.page.draftInitConfig.unitRowIds = arms;
  await harness.page.confirmInitConfig();
}

function relativeBatch(payload, starts) {
  const parameters = ['rotation', 'swing', 'telescopic'];
  return batch({
    ...payload, id: payload.request_id, status: 'completed', target_locked: false,
    steps: payload.adjustments.map(item => ({
      ...item, device_id: (payload.unit_id / 32 - 1) * 3 + parameters.indexOf(item.parameter_name) + 1,
      status: 'completed', start_position: starts[item.parameter_name],
      expected_position: starts[item.parameter_name] + item.position,
    })),
  });
}

function drawingArmFeedback(harness, arm, positions) {
  const kinds = ['rotation_axis_encoder', 'swing_axis_encoder', 'telescope_axis_encoder'];
  positions.forEach((position, index) => harness.page.applyFeedback({
    module_id: 0, device_id: (arm - 1) * 3 + index + 1, data_type: kinds[index], position,
  }));
}

function drawingStillness(harness, arms, seconds = 10) {
  for (let second = 0; second < seconds; second++) {
    harness.elapseWithoutTimers(1000);
    for (const [arm, positions] of arms) drawingArmFeedback(harness, arm, positions);
    harness.advance(0);
  }
}

test('drawing motion settles for ten seconds and locks one baseline across consecutive relative commands', async t => {
  const h = setup(t, { adjust: async payload => ({ data: relativeBatch(payload,
    { rotation: h.page.armList.device[0].current }),
  }) });
  await enter(h);
  drawingArmFeedback(h, 1, [37.25, 4, 8]);
  drawingArmFeedback(h, 1, [47.25, 6, 9]);
  drawingStillness(h, [[1, [47.25, 6, 9]]], 9);
  assert.equal(h.page.activeDrawingBaseline.value.status, 'settling');
  assert.equal(h.page.displayDrawingReference(0), '—');
  drawingStillness(h, [[1, [47.25, 6, 9]]], 1);
  assert.equal(h.page.activeDrawingBaseline.value.status, 'locked');
  assert.equal(h.page.displayDrawingReference(0), '47.25');
  assert.equal(h.page.displayAxisFeedback(0), '0.00');
  h.page.armList.device[0].adjust = 10;
  await h.page.confirmAdjustments();
  drawingArmFeedback(h, 1, [57.25, 6, 9]);
  assert.equal(h.page.displayAxisFeedback(0), '10.00');
  h.page.armList.device[0].adjust = 10;
  await h.page.confirmAdjustments();
  drawingArmFeedback(h, 1, [67.25, 6, 9]);
  assert.equal(h.page.displayAxisFeedback(0), '20.00');
  assert.equal(h.page.displayDrawingReference(0), '47.25');
  await h.page.handleSaveConfig();
  const saved = h.calls.saves[0].devices[0];
  assert.equal(saved.initial, 47.25);
  assert.equal(saved.reference_position, 47.25);
  assert.equal(saved.reference_source, 'drawing_settled');
  assert.equal(saved.current, 20);
  assert.equal(saved.raw_current, 67.25);
  assert.equal(saved.requested_delta, 10);
});

test('drawing feedback during the HTTP request is collected for an initially unselected arm', async t => {
  const started = deferred(), response = deferred();
  const h = setup(t, { coordinate: async () => { started.resolve(); return response.promise; } });
  const entering = enter(h, [2]);
  await started.promise;
  drawingArmFeedback(h, 2, [10, 4, 8]);
  drawingArmFeedback(h, 2, [20, 6, 9]);
  drawingStillness(h, [[2, [20, 6, 9]]]);
  assert.equal(h.page.drawingBaselines['64'].motionObserved, true);
  assert.equal(h.page.drawingBaselines['64'].confirmed, false);
  assert.equal(h.page.drawingBaselines['64'].values, null);
  response.resolve({ code: 200, views: {} });
  await entering;
  assert.equal(h.page.initConfig.unitId, 64);
  assert.equal(h.page.activeDrawingBaseline.value.status, 'locked');
  assert.equal(h.page.displayDrawingReference(0), '20.00');
  assert.equal(h.page.armList.device[0].current, 20);
  assert.equal(h.page.displayAxisFeedback(0), '0.00');
});

test('all confirmed arms collect independent drawing baselines before being selected', async t => {
  const h = setup(t);
  await enter(h, [1, 2]);
  drawingArmFeedback(h, 1, [10, 4, 8]);
  drawingArmFeedback(h, 2, [30, 5, 9]);
  drawingArmFeedback(h, 1, [20, 6, 10]);
  drawingArmFeedback(h, 2, [40, 7, 11]);
  drawingStillness(h, [[1, [20, 6, 10]], [2, [40, 7, 11]]]);
  assert.equal(h.page.drawingBaselines['32'].values[0], 20);
  assert.equal(h.page.drawingBaselines['64'].values[0], 40);
  await h.page.handleArmSwitch(2);
  assert.equal(h.page.displayDrawingReference(0), '40.00');
  assert.equal(h.page.displayAxisFeedback(0), '0.00');
  await h.page.handleArmSwitch(1);
  assert.equal(h.page.displayDrawingReference(0), '20.00');
  assert.equal(h.calls.adjusts.length, 0);
});

test('a drawing baseline stays unknown when feedback disappears and does not become a new dispatch gate', async t => {
  const h = setup(t, { preflightEnabled: false });
  await enter(h);
  drawingArmFeedback(h, 1, [10, 4, 8]);
  drawingArmFeedback(h, 1, [20, 6, 9]);
  h.advance(10000);
  assert.equal(h.page.activeDrawingBaseline.value.values, null);
  assert.equal(h.page.activeDrawingBaseline.value.stableSince, null);
  assert.equal(h.page.isReady.value, true);
  h.page.armList.device[0].adjust = 2;
  await h.page.confirmAdjustments();
  assert.equal(h.calls.adjusts.length, 1);
  assert.equal(h.page.displayAxisFeedback(0), '—');
  await h.page.handleSaveConfig();
  const saved = h.calls.saves[0].devices[0];
  assert.equal(saved.initial, null);
  assert.equal(saved.reference_position, null);
  assert.equal(saved.current, null);
  assert.equal(saved.raw_current, 20);
});

test('drawing redispatch starts a new observation generation for the confirmed arm scope', async t => {
  const h = setup(t);
  await enter(h, [1, 2]);
  drawingArmFeedback(h, 1, [10, 4, 8]);
  drawingArmFeedback(h, 2, [30, 5, 9]);
  drawingArmFeedback(h, 1, [20, 6, 10]);
  drawingArmFeedback(h, 2, [40, 7, 11]);
  drawingStillness(h, [[1, [20, 6, 10]], [2, [40, 7, 11]]]);
  const previous = h.page.drawingBaselines['32'].generation;
  h.page.openDrawingDialog();
  await h.page.confirmInitConfig();
  assert.notEqual(h.page.drawingBaselines['32'].generation, previous);
  assert.equal(h.page.drawingBaselines['32'].values, null);
  assert.equal(h.page.drawingBaselines['64'].values, null);
  assert.equal(h.calls.coordinates.length, 3);
});

test('failed drawing requests cannot freeze the positions observed during the request', async t => {
  const started = deferred(), response = deferred();
  const h = setup(t, { coordinate: async () => { started.resolve(); return response.promise; } });
  const entering = enter(h);
  await started.promise;
  drawingArmFeedback(h, 1, [10, 4, 8]);
  drawingArmFeedback(h, 1, [20, 6, 9]);
  drawingStillness(h, [[1, [20, 6, 9]]]);
  response.reject(new Error('drawing result unknown'));
  await entering;
  assert.equal(h.page.drawingBaselines['32'].status, 'failed');
  assert.equal(h.page.drawingBaselines['32'].values, null);
});

test('late drawing responses after connection changes cannot recreate an old fixed baseline', async t => {
  const started = deferred(), response = deferred();
  const h = setup(t, { coordinate: async () => { started.resolve(); return response.promise; } });
  const entering = enter(h);
  await started.promise;
  h.page.connectionChanged({ detail: { finetuning_preflight_enabled: false } });
  response.resolve({ code: 200, views: {} });
  await entering;
  assert.equal(Object.keys(h.page.drawingBaselines).length, 0);
  assert.equal(h.page.isReady.value, false);
});

for (const visited of [false, true]) {
  test(`drawing redispatch updates drawing identity for an ${visited ? 'already visited' : 'unvisited'} confirmed arm`, async t => {
    const h = setup(t, { drawings: [{ drawingId: 7, drawingName: 'first' }, { drawingId: 8, drawingName: 'second' }] });
    await enter(h, [1, 2]);
    if (visited) {
      await h.page.handleArmSwitch(2);
      await h.page.handleArmSwitch(1);
    }
    h.page.openDrawingDialog();
    h.page.draftInitConfig.drawingId = 8;
    await h.page.confirmInitConfig();
    await h.page.handleArmSwitch(2);
    assert.equal(h.page.initConfig.drawingId, 8);
    assert.equal(h.page.activeDrawingBaseline.value.drawingId, 8);
    await h.page.handleSaveConfig();
    assert.equal(h.calls.saves[0].drawing_id, 8);
  });
}

test('a late module confirmation cannot recreate binding or baseline after connection changes', async t => {
  const started = deferred(), confirmation = deferred();
  const h = setup(t, { confirm: async () => { started.resolve(); return confirmation.promise; } });
  const entering = enter(h);
  await started.promise;
  h.page.connectionChanged({ detail: { finetuning_preflight_enabled: false } });
  confirmation.resolve({ code: 200, data: { seg: 0,
    confirmations: [{ unit_id: 32, confirmed: true }], session: { id: 'late-session' },
  } });
  await entering;
  assert.equal(h.page.confirmedSeg.value, null);
  assert.equal(h.page.confirmedUnitIds.value.length, 0);
  assert.equal(h.page.activeSession.value, null);
  assert.equal(Object.keys(h.page.drawingBaselines).length, 0);
  assert.equal(h.calls.coordinates.length, 0);
});

test('old socket callbacks cannot interrupt a new drawing observation', async t => {
  const h = setup(t);
  await enter(h);
  const oldSocket = h.calls.sockets[0];
  h.page.connectionChanged({ detail: { finetuning_preflight_enabled: false } });
  await h.page.openConfiguration();
  h.page.draftInitConfig.unitRowIds = [1];
  await h.page.confirmInitConfig();
  const socket = h.calls.sockets.at(-1);
  const receive = positions => positions.forEach((position, index) => socket.receive({
    module_id: 0, device_id: index + 1,
    data_type: ['rotation_axis_encoder', 'swing_axis_encoder', 'telescope_axis_encoder'][index], position,
  }));
  receive([10, 4, 8]);
  receive([20, 6, 9]);
  const since = h.page.activeDrawingBaseline.value.stableSince;
  oldSocket.onclose();
  oldSocket.onerror();
  assert.equal(h.page.activeDrawingBaseline.value.stableSince, since);
  assert.equal(h.page.activeDrawingBaseline.value.samples[0].position, 20);
});

test('the fine-tuning page reads the preflight switch and defaults older responses to enabled', async t => {
  const legacy = setup(t, { debug: true });
  await enter(legacy);
  assert.equal(legacy.page.finetuningPreflightEnabled.value, true);
  const bypass = setup(t, { debug: true, preflightEnabled: false });
  await enter(bypass);
  assert.equal(bypass.page.finetuningPreflightEnabled.value, false);
  assert.match(descriptor.template.content, /微调下发前检查已关闭/);
  assert.match(descriptor.template.content, /运行、到位和空闲反馈/);
});

test('a sent batch without an initial position shows an unknown relative measurement and preserves raw feedback', async t => {
  const h = setup(t, { debug: true, preflightEnabled: false, adjust: async payload => ({ data: {
    ...relativeBatch(payload, { rotation: 12 }), finetuning_preflight_enabled: false,
    steps: payload.adjustments.map(item => ({ ...item, device_id: 1, status: 'completed',
      start_position: null, expected_position: null, observed_delta: null, deviation: null,
    })),
  } }) });
  await enter(h, [1, 2]);
  h.page.armList.device[0].adjust = 2;
  await h.page.confirmAdjustments();
  h.page.applyFeedback({ module_id: 0, device_id: 1, data_type: 'rotation_axis_encoder', position: 14 });
  assert.equal(h.page.relativeAxisValue(0), null);
  assert.equal(h.page.displayAxisFeedback(0), '—');
  assert.equal(h.page.axisFeedbackLabel(0), '缺少起点反馈');
  await h.page.handleSaveConfig();
  const saved = h.calls.saves[0].devices[0];
  assert.equal(saved.current, null);
  assert.equal(saved.reference_position, null);
  assert.equal(saved.raw_current, 14);
  assert.equal(saved.requested_delta, 2);
  assert.match(descriptor.template.content, /step\.observed_delta != null/);
  await h.page.handleArmSwitch(2);
  await h.page.handleArmSwitch(1);
  assert.equal(h.page.axisFeedbackLabel(0), '缺少起点反馈');
  assert.equal(h.calls.polls, 0);
});

test('preflight setting events update the displayed switch while clearing the old confirmation', async t => {
  const h = setup(t, { debug: true });
  await enter(h);
  h.page.connectionChanged({ detail: { finetuning_preflight_enabled: false } });
  assert.equal(h.page.finetuningPreflightEnabled.value, false);
  assert.equal(h.page.isReady.value, false);
  assert.equal(h.calls.adjusts.length, 0);
  h.page.connectionChanged({ detail: { finetuning_preflight_enabled: true } });
  assert.equal(h.page.finetuningPreflightEnabled.value, true);
});

test('relative motion uses each nonzero start while consecutive commands keep their increments', async t => {
  const h = setup(t, { debug: true, adjust: async payload => ({
    data: relativeBatch(payload, { rotation: h.page.armList.device[0].current }),
  }) });
  await enter(h);
  const receive = value => h.page.applyFeedback({
    module_id: 0, device_id: 1, data_type: 'rotation_axis_encoder', position: value,
  });
  receive(12);
  assert.equal(h.page.displayAxisFeedback(0), '—');
  assert.equal(h.page.axisFeedbackLabel(0), '等待本次下发');
  h.page.armList.device[0].adjust = 10;
  await h.page.confirmAdjustments();
  receive(22);
  assert.equal(h.page.displayAxisFeedback(0), '10.00');

  h.page.armList.device[0].adjust = 10;
  await h.page.confirmAdjustments();
  assert.equal(h.page.displayAxisFeedback(0), '—');
  assert.equal(h.page.axisFeedbackLabel(0), '等待本次反馈');
  receive(32);
  assert.equal(h.page.displayAxisFeedback(0), '10.00');
  h.page.armList.device[0].adjust = -3;
  await h.page.confirmAdjustments();
  receive(29);
  assert.equal(h.page.displayAxisFeedback(0), '-3.00');
  assert.deepEqual(h.calls.adjusts.map(item => item.adjustments[0].position), [10, 10, -3]);
  assert.equal(h.page.armList.device[0].current, 29);
  assert.match(descriptor.template.content, /本次实际转动/);
  assert.match(descriptor.template.content, /到位实际增量/);
});

test('configuration keeps each axis command and measurement after the inputs clear', async t => {
  const parameters = ['rotation', 'swing', 'telescopic'];
  const h = setup(t, { debug: true, adjust: async payload => ({ data: relativeBatch(payload,
    Object.fromEntries(parameters.map((name, index) => [name, h.page.armList.device[index].current]))),
  }) });
  await enter(h);
  const receive = (index, value) => h.page.applyFeedback({
    module_id: 0, device_id: index + 1,
    data_type: ['rotation_axis_encoder', 'swing_axis_encoder', 'telescope_axis_encoder'][index], position: value,
  });
  [12, 4, 8].forEach((value, index) => receive(index, value));
  h.page.armList.device[0].adjust = 10;
  await h.page.confirmAdjustments();
  receive(0, 21.5);
  h.page.armList.device[1].adjust = 2;
  h.page.armList.device[2].adjust = -0.5;
  await h.page.confirmAdjustments();
  receive(1, 6);
  receive(2, 7.5);
  assert.deepEqual([0, 1, 2].map(index => h.page.displayAxisFeedback(index)), ['9.50', '2.00', '-0.50']);
  assert.deepEqual(Array.from(h.page.armList.device.slice(0, 3), item => item.adjust), [0, 0, 0]);
  h.page.armList.device[0].adjust = 3;
  await h.page.handleSaveConfig();
  const devices = h.calls.saves[0].devices;
  assert.deepEqual(Array.from(devices.slice(0, 3), item => item.requested_delta), [10, 2, -0.5]);
  assert.ok(devices.every(item => !Object.hasOwn(item, 'adjust')));
  assert.equal(h.page.armList.device[0].adjust, 3);
  assert.deepEqual(Array.from(devices.slice(0, 3), item => item.current), [9.5, 2, -0.5]);
  assert.deepEqual(Array.from(devices.slice(0, 3), item => item.raw_current), [21.5, 6, 7.5]);
  assert.deepEqual(Array.from(devices.slice(0, 3), item => item.reference_position), [12, 4, 8]);
  assert.ok(devices.slice(0, 3).every(item => item.position_mode === 'relative'));
  assert.equal(devices[3].requested_delta, undefined);
});

test('queued batches wait for a sent reference and a fresh sample before showing relative motion', async t => {
  let result;
  const h = setup(t, { debug: true,
    adjust: async payload => {
      result = relativeBatch(payload, { rotation: 12 });
      result.status = 'queued';
      result.target_locked = true;
      result.steps[0].status = 'pending';
      return { data: result };
    },
    poll: async () => result,
  });
  await enter(h);
  h.page.applyFeedback({ module_id: 0, device_id: 1, data_type: 'rotation_axis_encoder', position: 12 });
  h.page.armList.device[0].adjust = 2;
  await h.page.confirmAdjustments();
  assert.equal(h.page.armList.device[0].requestedDelta, null);
  assert.equal(h.page.relativeAxisValue(0), null);
  result = { ...result, status: 'executing', steps: result.steps.map(step => ({ ...step, status: 'sent_unconfirmed' })) };
  await h.page.pollBatch();
  assert.equal(h.page.armList.device[0].requestedDelta, 2);
  assert.equal(h.page.displayAxisFeedback(0), '—');
  assert.equal(h.page.axisFeedbackLabel(0), '等待本次反馈');
  h.page.applyFeedback({ module_id: 0, device_id: 1, data_type: 'rotation_axis_encoder', position: 14 });
  assert.equal(h.page.displayAxisFeedback(0), '2.00');
});

test('relative references follow each arm and invalid samples keep their previous measurement and age', async t => {
  const h = setup(t, { debug: true, adjust: async payload => ({ data: relativeBatch(payload,
    { rotation: h.page.armList.device[0].current }),
  }) });
  await enter(h, [1, 2]);
  const receive = (deviceId, value) => h.page.applyFeedback({
    module_id: 0, device_id: deviceId, data_type: 'rotation_axis_encoder', position: value,
  });
  receive(1, 12);
  h.page.armList.device[0].adjust = 2;
  await h.page.confirmAdjustments();
  receive(1, 14);
  await h.page.handleArmSwitch(2);
  assert.equal(h.page.relativeAxisValue(0), null);
  receive(4, 50);
  h.page.armList.device[0].adjust = -3;
  await h.page.confirmAdjustments();
  receive(4, 47);
  assert.equal(h.page.displayAxisFeedback(0), '-3.00');
  await h.page.handleArmSwitch(1);
  assert.equal(h.page.displayAxisFeedback(0), '2.00');
  assert.match(h.page.axisFeedbackLabel(0), /历史缓存/);
  receive(1, 14);
  h.advance(59999);
  receive(1, null);
  receive(1, Infinity);
  assert.equal(h.page.displayAxisFeedback(0), '2.00');
  assert.equal(h.page.axisFeedbackLabel(0), '实时反馈');
  h.advance(1);
  assert.equal(h.page.axisFeedbackLabel(0), '数据已过期');
});

test('late submission responses after a connection change cannot restore the previous reference', async t => {
  const pending = deferred();
  const h = setup(t, { debug: true, adjust: () => pending.promise });
  await enter(h);
  h.page.armList.device[0].adjust = 2;
  const request = h.page.confirmAdjustments();
  const payload = h.calls.adjusts[0];
  h.page.connectionChanged();
  pending.resolve({ data: relativeBatch(payload, { rotation: 12 }) });
  await request;
  assert.equal(h.page.armList.device[0].referencePosition, null);
  assert.equal(h.page.displayAxisFeedback(0), '—');
});

test('a newer backend start waits for fresh telemetry instead of subtracting an older sample', async t => {
  const h = setup(t, { debug: true, adjust: async payload => ({ data: relativeBatch(payload, { rotation: 14 }) }) });
  await enter(h);
  const receive = value => h.page.applyFeedback({
    module_id: 0, device_id: 1, data_type: 'rotation_axis_encoder', position: value,
  });
  receive(12);
  h.page.armList.device[0].adjust = 10;
  await h.page.confirmAdjustments();
  assert.equal(h.page.relativeAxisValue(0), null);
  assert.equal(h.page.axisFeedbackLabel(0), '等待本次反馈');
  receive(14);
  assert.equal(h.page.displayAxisFeedback(0), '0.00');
  receive(24);
  assert.equal(h.page.displayAxisFeedback(0), '10.00');
});

for (const outcome of ['response', 'error']) {
  test(`a late 409 recovery ${outcome} cannot restore references after a connection change`, async t => {
    const recovery = deferred();
    const recoveryStarted = deferred();
    let recovering = false;
    const h = setup(t, { debug: true,
      adjust: async () => { recovering = true; throw { response: { status: 409 } }; },
      active: () => {
        if (!recovering) return null;
        recoveryStarted.resolve();
        return recovery.promise;
      },
    });
    await enter(h);
    h.page.armList.device[0].adjust = 2;
    const request = h.page.confirmAdjustments();
    await recoveryStarted.promise;
    h.page.connectionChanged();
    const oldMessage = h.page.batchState.value.message;
    if (outcome === 'response') recovery.resolve(relativeBatch(h.calls.adjusts[0], { rotation: 12 }));
    else recovery.reject(new Error('recovery unavailable'));
    await request;
    assert.equal(h.page.armList.device[0].referencePosition, null);
    assert.equal(h.page.displayAxisFeedback(0), '—');
    assert.equal(h.page.batchState.value.message, oldMessage);
  });
}

test('the legacy local simulation keeps each consecutive relative movement independent', async t => {
  const h = setup(t, { debug: true, noRosDebug: true,
    adjust: async payload => ({ data: { ...relativeBatch(payload, { rotation: h.page.armList.device[0].current }), simulated: true } }),
  });
  await enter(h);
  h.page.armList.device[0].adjust = 10;
  await h.page.confirmAdjustments();
  assert.equal(h.page.displayAxisFeedback(0), '10.00');
  h.page.armList.device[0].adjust = 10;
  await h.page.confirmAdjustments();
  assert.equal(h.page.displayAxisFeedback(0), '10.00');
  assert.equal(h.page.armList.device[0].current, 20);
});

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

test('manual refresh confirms the returned status instead of silently re-rendering', async t => {
  const h = setup(t, { debug: true, poll: async () => {
    const payload = h.calls.adjusts[0];
    return batch({ id: 'test-batch', request_id: payload.request_id, status: 'completed', target_locked: false,
      steps: payload.adjustments.map(item => ({ ...item, device_id: 1, status: 'completed' })) });
  } });
  await enter(h);
  h.page.armList.device[0].adjust = 2;
  await h.page.confirmAdjustments();
  h.messages.length = 0;

  await h.page.pollBatch(false);

  assert.equal(h.calls.polls, 1);
  assert.ok(h.messages.some(([level, text]) => level === 'success' && String(text).includes('本批次各轴已完成')));
});

test('out-of-tolerance arrival warns the operator but keeps dispatch available', async t => {
  assert.match(descriptor.template.content, /step\.warning/);
  const warning = '到位角 3.60 与期望 3.15 相差 +0.45（容差 0.2），仅提示，不阻止后续轴';
  const h = setup(t, { debug: true, adjust: async payload => ({ code: 200, data: {
    id: 'test-batch', request_id: payload.request_id, module_id: 17, unit_id: 32, seg: 0,
    status: 'completed', target_locked: false,
    message: '本批次各轴已观测到运行、目标到位和空闲反馈；1 个轴到位误差超出容差，已记录提示但未阻止下发',
    steps: payload.adjustments.map(item => ({ ...item, device_id: 1, status: 'completed', deviation: 0.45, warning })),
  } }) });
  await enter(h);
  h.page.armList.device[0].adjust = 2;
  await h.page.confirmAdjustments();

  // 批次不再因此锁住，可以继续下发
  assert.equal(h.page.busy.value, false);
  assert.equal(h.page.batchState.value.status, 'completed');
  assert.ok(h.warnings.some(text => String(text).includes('到位误差超出容差')));
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
  // 基准初始值固定为 0：实测值只更新 current，不能覆盖基准
  assert.equal(h.page.armList.device[0].initial, 0);
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
  h.advance(60000);
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
  assert.equal(h.page.fieldStatus('rotation'), 'current');
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
  // 下位机不回传初始值，基准固定 0，即使没有反馈也写 0 而不是 null
  assert.equal(first.devices[0].initial, 0);
  assert.equal(first.devices[0].current, null);
  assert.equal(first.devices[0].requested_delta, null);
  assert.equal(first.devices[3].current, null);
  assert.equal(first.x, null);
  assert.equal(first.feedback_state.pressure.status, 'waiting');
  h.page.applyFeedback({ module_id: 0, device_id: 1, data_type: 'rotation_axis_encoder', position: 0 });
  await h.page.handleArmSwitch(2);
  await h.page.handleArmSwitch(1);
  await h.page.handleSaveConfig();
  const second = h.calls.saves[1];
  assert.equal(second.devices[0].initial, 0);
  assert.equal(second.devices[0].current, null);
  assert.equal(second.devices[0].raw_current, 0);
  assert.equal(second.devices[0].position_mode, 'relative');
  assert.equal(second.devices[0].reference_position, null);
  assert.equal(second.feedback_state.rotation.status, 'history');
});

test('calibration mode marks the saved snapshot as a zeroing value in the database remark', async t => {
  const h = setup(t, { debug: true });
  await enter(h);
  // 基准初始值固定 0：反馈只更新实测值
  h.page.applyFeedback({ module_id: 0, device_id: 1, data_type: 'rotation_axis_encoder', position: 12 });
  assert.equal(h.page.armList.device[0].current, 12);
  assert.equal(h.page.armList.device[0].initial, 0);

  await h.page.handleSaveConfig();
  assert.equal(h.calls.saves[0].calibrated, false);
  assert.equal(h.calls.saves[0].notes, null);
  assert.equal(h.calls.saves[0].devices[0].initial, 0);

  h.page.calibrateMode.value = true;
  await h.page.handleSaveConfig();
  assert.equal(h.calls.saves[1].calibrated, true);
  assert.match(h.calls.saves[1].notes, /^校零：机械臂 1/);
  assert.match(h.calls.saves[1].notes, /人工下发归位后保存/);
  // 保存成功后自动熄灭，避免下一组微调值被误标
  assert.equal(h.page.calibrateMode.value, false);

  await h.page.handleSaveConfig();
  assert.equal(h.calls.saves[2].calibrated, false);
  assert.equal(h.calls.saves[2].notes, null);
});

test('saving refreshes the age/status clock even if the browser has throttled timers', async t => {
  const h = setup(t, { debug: true });
  await enter(h);
  h.page.applyFeedback({ module_id: 0, device_id: 1, data_type: 'rotation_axis_encoder', position: 2 });
  h.elapseWithoutTimers(60000);
  await h.page.handleSaveConfig();
  assert.equal(h.calls.saves[0].feedback_state.rotation.status, 'stale');
  assert.equal(h.calls.saves[0].feedback_state.rotation.age_ms, 60000);
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

// ========== 会话保持与续接 ==========
const SESSION_SETTINGS = { 'mes.finetuning.session.settings': JSON.stringify({ enabled: true, ttlMinutes: 30 }) };
const heldSession = overrides => ({
  id: 'session-1', module_id: 17, device_id: 17, x: 1, y: 1, seg: 3,
  unit_ids: [32, 64], connection_revision: 0, ...overrides,
});
const snapshotOf = (rowId = 1) => ({
  selectedArmRowId: rowId,
  armProfiles: {
    [rowId]: {
      unitRowId: rowId, unitId: 32, drawingId: 0, drawingSource: 'database', drawingSimulated: false, configured: true,
      device: [
        { deviceId: 1, initial: 10, adjust: 1.5, current: 12, initialLocked: true, label: '底座旋转调整值' },
        { deviceId: 2, initial: 2, adjust: 0, current: 2, initialLocked: true, label: '摆动调整值' },
        { deviceId: 3, initial: 3, adjust: 0, current: 3, initialLocked: true, label: '伸缩杆调整值' },
        { deviceId: 21, initial: 0, current: 0.4 },
      ],
      imu: { swingAngle: 1, rotationAngle: 2, x: 0, y: 0, z: 0 },
      pressureSensorId: 49, feedbackMarks: {}, pointCloudViews: [], showPointCloudViews: false, batch: null, ackEvents: [],
    },
  },
});

test('valid held session resumes without sending module confirm', async t => {
  const session = heldSession();
  const h = setup(t, {
    debug: true,
    localStorage: memoryStorage(SESSION_SETTINGS),
    sessionState: () => ({ session, latest: session, reason: null }),
    resume: () => ({ valid: true, reason: null, session }),
  });

  await h.mount();

  assert.equal(h.calls.confirms.length, 0);
  assert.equal(h.calls.resumes, 1);
  assert.equal(h.page.initDialogVisible.value, false);
  assert.equal(h.page.confirmedSeg.value, 3);
  assert.deepEqual(Array.from(h.page.confirmedUnitIds.value), [32, 64]);
  assert.equal(h.page.resumedFromSession.value, true);
  assert.equal(h.page.activeSession.value.id, 'session-1');
  assert.equal(h.page.armIdList.value.length, 2);
});

test('resume restores per-arm snapshot values and stays locked out of a new handshake', async t => {
  const session = heldSession();
  const snapshotStore = memoryStorage({ 'mes.finetuning.session.snapshot.session-1': JSON.stringify(snapshotOf(1)) });
  const h = setup(t, {
    debug: true,
    localStorage: memoryStorage(SESSION_SETTINGS),
    sessionStorage: snapshotStore,
    sessionState: () => ({ session, latest: session, reason: null }),
    resume: () => ({ valid: true, reason: null, session }),
  });

  await h.mount();

  assert.equal(h.calls.confirms.length, 0);
  assert.equal(h.page.selectedArmRowId.value, 1);
  assert.equal(h.page.armList.device[0].adjust, 1.5);
  assert.equal(h.page.armList.device[0].initial, 10);
  assert.equal(h.page.armProfiles['1'].configured, true);
  assert.equal(h.page.displayAxisFeedback(0), '—');
  assert.equal(h.page.axisFeedbackLabel(0), '等待本次下发');
});

test('session snapshots preserve the latest measured relative motion and restore it as historical', async t => {
  const h = setup(t, { debug: true, adjust: async payload => ({ data: relativeBatch(payload, { rotation: 12 }) }) });
  await enter(h);
  const receive = value => h.page.applyFeedback({
    module_id: 0, device_id: 1, data_type: 'rotation_axis_encoder', position: value,
  });
  receive(12);
  h.page.armList.device[0].adjust = 2;
  await h.page.confirmAdjustments();
  receive(14);
  h.page.applyFeedback({ module_id: 0, device_id: 21, data_type: 'imu_pose', x: 12, rotation_angle: 3 });
  h.page.activeSession.value = heldSession({ seg: 0 });
  h.sessionSettings().setEnabled(true);
  h.page.persistSnapshot();
  const snapshotText = h.storages.session.getItem('mes.finetuning.session.snapshot.session-1');
  const stored = JSON.parse(snapshotText);
  assert.equal(stored.armProfiles['1'].device[0].current, 14);
  assert.equal(stored.armProfiles['1'].device[0].referencePosition, 12);
  assert.equal(stored.armProfiles['1'].device[0].requestedDelta, 2);
  assert.equal(stored.armProfiles['1'].device[0].referenceReady, true);
  assert.equal(stored.armProfiles['1'].imu.x, 12);

  const session = heldSession({ seg: 0 });
  const resumed = setup(t, { debug: true,
    localStorage: memoryStorage(SESSION_SETTINGS),
    sessionStorage: memoryStorage({ 'mes.finetuning.session.snapshot.session-1': snapshotText }),
    sessionState: () => ({ session, latest: session, reason: null }),
    resume: () => ({ valid: true, reason: null, session }),
  });
  await resumed.mount();
  assert.equal(resumed.page.displayAxisFeedback(0), '2.00');
  assert.match(resumed.page.axisFeedbackLabel(0), /历史缓存/);
  assert.equal(resumed.page.imuFeedback.x, 12);
  assert.equal(resumed.page.imuFeedback.rotationAngle, 3);
  await resumed.page.handleSaveConfig();
  assert.equal(resumed.calls.saves[0].devices[0].current, 2);
  assert.equal(resumed.calls.saves[0].devices[0].requested_delta, 2);
  assert.equal(resumed.calls.saves[0].devices[0].raw_current, 14);
  assert.equal(resumed.calls.saves[0].devices[0].reference_position, 12);
});

test('locked drawing baselines survive session resume with their measured cumulative offset', async t => {
  const h = setup(t, { adjust: async payload => ({ data: relativeBatch(payload, { rotation: 20 }) }) });
  await enter(h);
  drawingArmFeedback(h, 1, [10, 4, 8]);
  drawingArmFeedback(h, 1, [20, 6, 9]);
  drawingStillness(h, [[1, [20, 6, 9]]]);
  h.page.armList.device[0].adjust = 3;
  await h.page.confirmAdjustments();
  drawingArmFeedback(h, 1, [23, 6, 9]);
  const session = heldSession({ seg: 0, connection_revision: null });
  h.page.activeSession.value = session;
  h.sessionSettings().setEnabled(true);
  h.page.persistSnapshot();
  const snapshotText = h.storages.session.getItem('mes.finetuning.session.snapshot.session-1');
  const resumed = setup(t, {
    localStorage: memoryStorage(SESSION_SETTINGS),
    sessionStorage: memoryStorage({ 'mes.finetuning.session.snapshot.session-1': snapshotText }),
    sessionState: () => ({ session, latest: session, reason: null }),
    resume: () => ({ valid: true, reason: null, session }),
  });
  await resumed.mount();
  assert.equal(resumed.page.activeDrawingBaseline.value.status, 'locked');
  assert.equal(resumed.page.displayDrawingReference(0), '20.00');
  assert.equal(resumed.page.displayAxisFeedback(0), '3.00');
  assert.match(resumed.page.axisFeedbackLabel(0), /历史缓存/);
  await resumed.page.handleSaveConfig();
  assert.equal(resumed.calls.saves[0].devices[0].initial, 20);
  assert.equal(resumed.calls.saves[0].devices[0].reference_source, 'drawing_settled');
});

test('continuous telemetry and page hiding persist the latest fixed drawing baseline', async t => {
  const h = setup(t);
  await enter(h);
  drawingArmFeedback(h, 1, [10, 4, 8]);
  drawingArmFeedback(h, 1, [20, 6, 9]);
  drawingStillness(h, [[1, [20, 6, 9]]]);
  h.page.activeSession.value = heldSession({ seg: 0, connection_revision: null });
  h.sessionSettings().setEnabled(true);
  for (let sample = 0; sample < 6; sample++) {
    h.elapseWithoutTimers(100);
    drawingArmFeedback(h, 1, [20, 6, 9]);
    await vue.nextTick();
  }
  h.flushTimeouts();
  const key = 'mes.finetuning.session.snapshot.session-1';
  let saved = JSON.parse(h.storages.session.getItem(key));
  assert.equal(saved.drawingBaselines['32'].values[0], 20);
  assert.equal(saved.armProfiles['1'].device[0].current, 20);
  drawingArmFeedback(h, 1, [23, 6, 9]);
  h.windowEvents.get('pagehide')();
  saved = JSON.parse(h.storages.session.getItem(key));
  assert.equal(saved.drawingBaselines['32'].values[0], 20);
  assert.equal(saved.armProfiles['1'].device[0].current, 23);
});

test('unfinished drawing baselines restart the full ten-second observation after a refresh', async t => {
  const h = setup(t);
  await enter(h);
  drawingArmFeedback(h, 1, [10, 4, 8]);
  drawingArmFeedback(h, 1, [20, 6, 9]);
  drawingStillness(h, [[1, [20, 6, 9]]], 4);
  const session = heldSession({ seg: 0, connection_revision: null });
  h.page.activeSession.value = session;
  h.sessionSettings().setEnabled(true);
  h.page.persistSnapshot();
  const snapshotText = h.storages.session.getItem('mes.finetuning.session.snapshot.session-1');
  const resumed = setup(t, {
    localStorage: memoryStorage(SESSION_SETTINGS),
    sessionStorage: memoryStorage({ 'mes.finetuning.session.snapshot.session-1': snapshotText }),
    sessionState: () => ({ session, latest: session, reason: null }),
    resume: () => ({ valid: true, reason: null, session }),
  });
  await resumed.mount();
  assert.equal(resumed.page.activeDrawingBaseline.value.stableSince, null);
  drawingArmFeedback(resumed, 1, [20, 6, 9]);
  drawingStillness(resumed, [[1, [20, 6, 9]]], 6);
  assert.equal(resumed.page.activeDrawingBaseline.value.values, null);
  drawingStillness(resumed, [[1, [20, 6, 9]]], 4);
  assert.equal(resumed.page.displayDrawingReference(0), '20.00');
});

test('completed legacy snapshots refresh relative results without clearing new drafts', async t => {
  const session = heldSession();
  const oldWarning = '到位角 14.45 与期望 14.00 相差 +0.45';
  const cached = snapshotOf();
  cached.armProfiles['1'].batch = batch({ id: 'old-batch', request_id: 'old-request',
    status: 'completed', target_locked: false, message: `轴 1 已观测到运行、到位及空闲；${oldWarning}`,
    steps: [{ parameter_name: 'rotation', device_id: 1, position: 2, status: 'completed',
      expected_position: 14, observed_angle: 14.45, warning: oldWarning }],
  });
  const pending = deferred();
  const h = setup(t, { debug: true,
    localStorage: memoryStorage(SESSION_SETTINGS),
    sessionStorage: memoryStorage({ 'mes.finetuning.session.snapshot.session-1': JSON.stringify(cached) }),
    sessionState: () => ({ session, latest: session, reason: null }),
    resume: () => ({ valid: true, reason: null, session }),
    poll: () => pending.promise,
  });
  await h.mount();
  assert.equal(h.calls.polls, 1);
  assert.equal(h.page.armList.device[0].requestedDelta, 2);
  assert.equal(h.page.batchState.value.steps[0].warning, undefined);
  assert.equal(h.page.batchState.value.message, '正在读取历史批次的相对运动结果');
  h.page.armList.device[0].adjust = 3;
  pending.resolve({ ...cached.armProfiles['1'].batch, message: '历史相对结果已读取', steps: [{
    ...cached.armProfiles['1'].batch.steps[0], start_position: 12, observed_delta: 2.45,
    warning: '本次实际转动 2.45°，指令增量 2.00°，相差 +0.45°',
  }] });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.page.armList.device[0].adjust, 3);
  assert.equal(h.page.armList.device[0].referencePosition, 12);
  assert.equal(h.page.batchState.value.steps[0].observed_delta, 2.45);
  assert.match(h.page.batchState.value.steps[0].warning, /本次实际转动/);
});

test('resume is refused when the requested module differs from the held session', async t => {
  const session = heldSession({ module_id: 18 });
  const h = setup(t, {
    debug: true,
    localStorage: memoryStorage(SESSION_SETTINGS),
    sessionState: () => ({ session, latest: session, reason: null }),
    resume: () => ({ valid: true, reason: null, session }),
  });

  await h.mount();

  // 记录仍会滑动有效期，但绝不套用到另一个模块上
  assert.equal(h.page.initDialogVisible.value, true);
  assert.equal(h.page.resumedFromSession.value, false);
  assert.equal(h.page.activeSession.value, null);
});

test('explicit session link with expired record warns and falls back to handshake', async t => {
  const h = setup(t, {
    debug: true,
    query: { module_id: 17, device_id: 17, x: 1, y: 1, session: 'session-1' },
    localStorage: memoryStorage(SESSION_SETTINGS),
    sessionState: () => ({ session: null, latest: heldSession(), reason: 'expired' }),
    resume: () => ({ valid: false, reason: 'expired', session: null }),
  });

  await h.mount();

  assert.equal(h.calls.confirms.length, 0);
  assert.equal(h.page.initDialogVisible.value, true);
  assert.ok(h.warnings.some(text => String(text).includes('已超过保持时长')));
});

test('session API is untouched when session hold is off', async t => {
  const h = setup(t, { debug: true });

  await h.mount();

  assert.equal(h.calls.sessions, 0);
  assert.equal(h.calls.resumes, 0);
  assert.equal(h.page.initDialogVisible.value, true);
});

test('handshake registers session and persists a local snapshot for the next visit', async t => {
  const session = heldSession({ seg: 0 });
  const snapshotStore = memoryStorage();
  const h = setup(t, {
    debug: true,
    localStorage: memoryStorage(SESSION_SETTINGS),
    sessionStorage: snapshotStore,
    confirm: payload => ({
      code: 200,
      data: {
        seg: 0,
        connection_revision: 0,
        session: { ...session, unit_ids: payload.unit_ids },
        confirmations: payload.unit_ids.map(unit_id => ({ unit_id, confirmed: true })),
      },
    }),
  });

  await enter(h);
  assert.equal(h.page.activeSession.value.id, 'session-1');

  h.page.persistSnapshot();
  const saved = JSON.parse(snapshotStore.getItem('mes.finetuning.session.snapshot.session-1'));
  assert.equal(saved.confirmedSeg, 0);
  assert.ok(saved.armProfiles[String(h.page.initConfig.unitRowId)].configured);
});

test('ending the session closes the record and drops the local snapshot', async t => {
  const session = heldSession();
  const snapshotStore = memoryStorage({ 'mes.finetuning.session.snapshot.session-1': JSON.stringify(snapshotOf(1)) });
  const h = setup(t, {
    debug: true,
    localStorage: memoryStorage(SESSION_SETTINGS),
    sessionStorage: snapshotStore,
    sessionState: () => ({ session, latest: session, reason: null }),
    resume: () => ({ valid: true, reason: null, session }),
  });

  await h.mount();
  await h.page.endSession();

  assert.equal(h.calls.closes, 1);
  assert.equal(h.page.activeSession.value, null);
  assert.equal(h.page.resumedFromSession.value, false);
  assert.equal(snapshotStore.getItem('mes.finetuning.session.snapshot.session-1'), null);
});

// ========== 局部停（分级急停） ==========
test('local stop state stays visible on the fine-tuning page', () => {
  // 模块停已统一到侧栏底部急停区，本页只保留与轴上下文相关的单轴停和状态提示
  assert.match(descriptor.template.content, /@click="stopAxis\(item\.index\)"/);
  assert.match(descriptor.template.content, /局部停生效中/);
  assert.equal(/停本模块/.test(descriptor.template.content), false);
});

test('axis stop posts the axis number derived from unit and parameter', async t => {
  const h = setup(t, { debug: true });
  await enter(h);

  await h.page.stopAxis(1);

  assert.equal(h.calls.stops.length, 1);
  assert.equal(h.calls.stops[0].scope, 'axis');
  assert.equal(h.calls.stops[0].device_id, 2);
  assert.equal(h.calls.stops[0].module_id, 17);
});

test('held module blocks submissions until the record is cleared', async t => {
  const held = { id: 7, mode: 'real', scope: 'module', module_id: 17, device_id: null, state: 'sent',
    message: null, created_at: null, cleared_at: null, cleared_reason: null, active: true };
  const h = setup(t, { debug: true, holds: () => [held] });
  await enter(h);
  await h.page.loadStopHolds();

  assert.equal(h.page.hasLocalStop.value, true);
  h.page.armList.device[0].adjust = 2;
  await h.page.confirmAdjustments();

  assert.equal(h.calls.adjusts.length, 0);
  assert.ok(h.warnings.some(text => String(text).includes('局部停')));
});

test('clearing local stop records unlocks the module', async t => {
  const held = { id: 8, mode: 'real', scope: 'axis', module_id: 17, device_id: 2, state: 'sent',
    message: null, created_at: null, cleared_at: null, cleared_reason: null, active: true };
  let holds = [held];
  const h = setup(t, { debug: true, holds: () => holds });
  await enter(h);
  await h.page.loadStopHolds();
  assert.equal(h.page.hasLocalStop.value, true);

  holds = [];
  await h.page.clearLocalStops();
  await h.page.loadStopHolds();

  assert.deepEqual(h.calls.holdClears, [17]);
  assert.equal(h.page.hasLocalStop.value, false);
  h.page.armList.device[0].adjust = 1;
  await h.page.confirmAdjustments();
  assert.equal(h.calls.adjusts.length, 1);
});

test('holds of another module never block the current one', async t => {
  const other = { id: 9, mode: 'real', scope: 'module', module_id: 18, device_id: null, state: 'sent',
    message: null, created_at: null, cleared_at: null, cleared_reason: null, active: true };
  const h = setup(t, { debug: true, holds: () => [other] });
  await enter(h);
  await h.page.loadStopHolds();

  assert.equal(h.page.hasLocalStop.value, false);
  h.page.armList.device[0].adjust = 1;
  await h.page.confirmAdjustments();
  assert.equal(h.calls.adjusts.length, 1);
});
