import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import test from 'node:test';
import { parse } from '@vue/compiler-sfc';
import ts from 'typescript';
import * as vue from 'vue';

const { descriptor } = parse(fs.readFileSync(new URL('../src/components/Main/AsidePage.vue', import.meta.url), 'utf8'));
const script = ts.transpileModule(descriptor.scriptSetup.content, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;

function setup(t, options = {}) {
  const mounted = [], timers = [], messages = [];
  const calls = { stop: 0, release: 0 };
  const module = { exports: {} };
  const scope = vue.effectScope();
  t.after(() => scope.stop());
  scope.run(() => vm.runInNewContext(script + '\nObject.assign(module.exports, { triggerEmergency, resetEmergency, safetyState, isEmergencyActive, releasing, showEmergencyDetails, refreshSafetyState, connectionChanged, safetyNotice });', {
    module, exports: module.exports,
    setTimeout(callback, delay) { timers.push({ callback, delay }); return timers.length; }, clearTimeout() {},
    setInterval(callback, delay) { timers.push({ callback, delay }); return timers.length; }, clearInterval() {},
    require(name) {
      if (name === 'vue') return { ...vue, onMounted(callback) { mounted.push(callback); }, onBeforeUnmount() {} };
      if (name === 'vue-router') return { useRouter: () => ({ push() {} }), useRoute: () => ({ meta: {}, path: '/' }) };
      if (name === '@element-plus/icons-vue') return {};
      if (name === '@/stores/layoutSetting') return { useLayoutSettingStore: () => ({}) };
      if (name === '@/stores/user') return { useUserStore: () => ({ isAdmin: () => true }) };
      if (name === 'element-plus') return { ElMessage: Object.fromEntries(['info', 'warning', 'error'].map(key => [key, text => messages.push(text)])) };
      if (name === '@/api/rosApi') return {
    async getEmergencyStopState() { return { data: { state: options.state || 'clear', simulated: options.simulated === true } }; },
        async sendEmergencyStop() { calls.stop++; if (options.stop) return options.stop(); return { success: true }; },
        async releaseEmergencyStop() { calls.release++; if (options.release) return options.release(); return { success: true }; },
      };
      throw new Error(`Unexpected dependency ${name}`);
    },
  }));
  return { page: module.exports, calls, timers, messages, mount: () => mounted[0]() };
}

test('emergency remains active with no five-second auto-recovery timer', async t => {
  const h = setup(t);
  await h.page.triggerEmergency();
  assert.equal(h.calls.stop, 1);
  assert.equal(h.page.isEmergencyActive.value, true);
  assert.equal(h.page.safetyState.value, 'stop_sent');
  assert.equal(h.timers.some(timer => timer.delay === 5000), false);
});

test('failed release retains emergency overlay and reports failure', async t => {
  const h = setup(t, { release: async () => { throw new Error('release failed'); } });
  await h.page.triggerEmergency();
  await h.page.resetEmergency();
  assert.equal(h.calls.release, 1);
  assert.equal(h.page.isEmergencyActive.value, true);
  assert.equal(h.page.safetyState.value, 'stop_sent');
  assert.ok(h.messages.includes('release failed'));
});

test('release calls backend once and does not claim device release is confirmed', async t => {
  let resolve;
  const pending = new Promise(yes => { resolve = yes; });
  const h = setup(t, { release: () => pending });
  await h.page.triggerEmergency();
  const first = h.page.resetEmergency();
  await h.page.resetEmergency();
  assert.equal(h.calls.release, 1);
  resolve({ success: true });
  await first;
  assert.equal(h.page.safetyState.value, 'release_sent');
  assert.equal(h.page.isEmergencyActive.value, true);
  assert.equal(h.messages.some(text => text === '急停已解除'), false);
});

test('history restore retains interlock information without opening a fullscreen or sending commands', async t => {
  for (const state of ['stop_unknown', 'stop_sent', 'release_sent']) {
    const h = setup(t, { state });
    await h.mount();
    assert.equal(h.page.safetyState.value, state);
    assert.equal(h.page.isEmergencyActive.value, false);
    assert.equal(h.calls.stop + h.calls.release, 0);
  }
});

test('failed emergency request stays visibly unknown rather than silently returning to normal', async t => {
  const h = setup(t, { stop: async () => { throw new Error('stop failed'); } });
  await h.page.triggerEmergency();
  assert.equal(h.page.safetyState.value, 'stop_unknown');
  assert.equal(h.page.isEmergencyActive.value, true);
});


test('mock stop and release complete through backend results and close the overlay', async t => {
  const h = setup(t, { stop: async () => ({ success: true, simulated: true }), release: async () => ({ success: true, simulated: true }) });
  await h.page.triggerEmergency();
  assert.equal(h.page.isEmergencyActive.value, true);
  await h.page.resetEmergency();
  assert.equal(h.calls.release, 1);
  assert.equal(h.page.isEmergencyActive.value, false);
  assert.equal(h.page.safetyState.value, 'clear');
  assert.ok(h.messages.includes('模拟解除成功，未连接真实设备'));
});

test('mock simulation marker never turns a failed release into success', async t => {
  const h = setup(t, { simulated: true, release: async () => ({ success: false, simulated: true }) });
  await h.page.triggerEmergency();
  await h.page.resetEmergency();
  assert.equal(h.page.isEmergencyActive.value, true);
  assert.equal(h.page.safetyState.value, 'stop_sent');
});


test('opening history details is explicit and never sends a new stop', async t => {
  const h = setup(t, { state: 'stop_unknown' }); await h.mount();
  h.page.showEmergencyDetails();
  assert.equal(h.page.isEmergencyActive.value, true);
  assert.equal(h.calls.stop + h.calls.release, 0);
  assert.equal(h.page.safetyState.value, 'stop_unknown');
});

test('polling a changed historical record never forces the overlay open', async t => {
  const options = { state: 'clear' }, h = setup(t, options); await h.mount();
  options.state = 'stop_unknown';
  await h.page.refreshSafetyState();
  assert.equal(h.page.isEmergencyActive.value, false);
  assert.equal(h.page.safetyState.value, 'stop_unknown');
  assert.equal(h.calls.stop + h.calls.release, 0);
});

test('dismissed overlay stays dismissed after a pending release fails', async t => {
  let reject;
  const waiting = new Promise((_, no) => { reject = no; });
  const h = setup(t, { release: () => waiting }); await h.page.triggerEmergency();
  const request = h.page.resetEmergency();
  h.page.isEmergencyActive.value = false;
  reject(new Error('offline')); await request;
  assert.equal(h.page.isEmergencyActive.value, false);
  assert.equal(h.page.safetyState.value, 'stop_sent');
});
