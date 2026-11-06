import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import test from 'node:test';
import { parse } from '@vue/compiler-sfc';
import ts from 'typescript';
import * as vue from 'vue';

const read = path => fs.readFileSync(new URL(path, import.meta.url), 'utf8');
const { descriptor } = parse(read('../src/components/Main/UserManage/RosConnectionSettings.vue'));
const compile = source => ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const initial = () => ({ revision: 0, ros_mode: 'real', drawing_mode: 'real', emergency_mode: 'real',
  ros_url: 'ws://localhost:9010', drawing_ros_url: '', emergency_ros_url: '', pointcloud_url: 'http://localhost:5000' });

function setup(t, options = {}) {
  const mounted = [], calls = [], events = [], messages = [];
  let current = initial();
  const module = { exports: {} }, scope = vue.effectScope();
  t.after(() => scope.stop());
  scope.run(() => vm.runInNewContext(compile(descriptor.scriptSetup.content) + '\nObject.assign(module.exports, { config, draft, notice, changeMode, changeAddress });', {
    module, exports: module.exports,
    defineEmits: () => () => {},
    window: { dispatchEvent: event => events.push(event) }, CustomEvent: class { constructor(type, value) { this.type = type; this.detail = value.detail; } },
    require(name) {
      if (name === 'vue') return { ...vue, onMounted: callback => mounted.push(callback) };
      if (name === 'element-plus') return { ElMessage: { error: message => messages.push(message) } };
      if (name === '@/api/connectionSettings') return {
        async getConnectionSettings() { return { data: { ...current } }; },
        async changeConnectionSettings(revision, changes) {
          calls.push({ revision, changes });
          if (options.reject) {
            current = { ...current, revision: 5, ros_mode: 'mock' };
            throw { response: { data: { detail: 'config rejected' } } };
          }
          current = { ...current, ...changes, revision: revision + 1 };
          return { data: { ...current } };
        },
      };
      throw new Error(name);
    },
  }));
  return { page: module.exports, calls, events, messages, mount: () => mounted[0]() };
}

test('manual mode change applies one field and publishes the accepted configuration', async t => {
  const h = setup(t); await h.mount();
  await h.page.changeMode('ros_mode', 'mock');
  assert.equal(h.calls.length, 1);
  assert.equal(h.calls[0].changes.ros_mode, 'mock');
  assert.equal(h.page.config.value.drawing_mode, 'real');
  assert.equal(h.page.config.value.revision, 1);
  assert.equal(h.events[0].type, 'ros-connection-changed');
});

test('selecting real motion or drawing also selects real emergency control', async t => {
  const h = setup(t); await h.mount();
  await h.page.changeMode('ros_mode', 'mock');
  await h.page.changeMode('ros_mode', 'real');
  assert.equal(h.calls[1].changes.emergency_mode, 'real');
});

test('address edit sends the trimmed address without a save or test action', async t => {
  const h = setup(t); await h.mount();
  h.page.draft.ros_url = ' ws://192.0.2.10:9010 ';
  await h.page.changeAddress('ros_url');
  assert.equal(h.calls[0].changes.ros_url, 'ws://192.0.2.10:9010');
  assert.equal(h.page.config.value.ros_url, 'ws://192.0.2.10:9010');
});

test('rejected update restores server values and never publishes a false success', async t => {
  const h = setup(t, { reject: true }); await h.mount();
  await h.page.changeMode('drawing_mode', 'mock');
  assert.equal(h.page.config.value.revision, 5);
  assert.equal(h.page.config.value.drawing_mode, 'real');
  assert.equal(h.events.length, 0);
  assert.equal(h.calls.length, 1);
  assert.ok(h.messages.includes('config rejected'));
});

test('unchanged selections and unchanged addresses do not issue updates', async t => {
  const h = setup(t); await h.mount();
  await h.page.changeMode('ros_mode', 'real');
  await h.page.changeAddress('ros_url');
  assert.equal(h.calls.length, 0);
});

test('business APIs including mock batches still reach the real backend request layer', async () => {
  const calls = [], module = { exports: {} };
  vm.runInNewContext(compile(read('../src/api/rosApi.ts')), {
    module, exports: module.exports,
    require(name) {
      if (name === '../utils/request') return { default: config => { calls.push(config); return Promise.resolve({ data: null }); } };
      throw new Error(`Unexpected dependency ${name}`);
    },
  });
  const api = module.exports;
  await api.createModule({ unit_ids: [32] });
  await api.sendCoordination({ drawing_id: 7 });
  await api.submitFineTuningBatch({ request_id: 'request_001', module_id: 17, unit_id: 32, adjustments: [] });
  await api.getActiveFineTuningBatch(17, 32);
  await api.saveFineTuningConfig({ module_id: 17 });
  await api.getDeviceListApi();
  assert.deepEqual(calls.map(item => item.url), ['/module/', '/coordination/send', '/control/finetuning/batches',
    '/control/finetuning/batches/active', '/finetuning/config', '/device/']);
});
