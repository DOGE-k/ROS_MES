import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import test from 'node:test';
import axios from 'axios';
import qs from 'qs';
import ts from 'typescript';

const script = ts.transpileModule(fs.readFileSync(new URL('../src/utils/request.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;

function setup(token = null) {
  const module = { exports: {} }, sent = [], redirects = [];
  vm.runInNewContext(script, {
    module, exports: module.exports, FormData,
    localStorage: { getItem: () => token, removeItem() {} },
    console: { error() {} },
    require(name) {
      if (name === 'axios') return { default: axios };
      if (name === 'qs') return { default: qs };
      if (name === '@/router') return { default: { replace: path => redirects.push(path) } };
      if (name === 'element-plus') return { ElMessage: { error() {} } };
      throw new Error(`Unexpected dependency ${name}`);
    },
  });
  const service = module.exports.default;
  service.defaults.adapter = async config => {
    sent.push(config);
    return { data: { code: 200 }, status: 200, statusText: 'OK', headers: {}, config };
  };
  return { service, sent, redirects };
}

test('all batch submission, recovery and operator actions carry the login token', async () => {
  const h = setup('isolated-test-token');
  for (const [method, url] of [
    ['post', '/control/finetuning/batches'],
    ['get', '/control/finetuning/batches/active'],
    ['get', '/control/finetuning/batches/by-request/request_001'],
    ['get', '/control/finetuning/batches/batch-id'],
    ['post', '/control/finetuning/batches/batch-id/interrupt'],
    ['post', '/control/finetuning/batches/batch-id/acknowledge'],
  ]) await h.service({ method, url });
  assert.equal(h.sent.length, 6);
  assert.ok(h.sent.every(config => config.headers.Authorization === 'Bearer isolated-test-token'));
});

test('a missing token blocks batch dispatch before transport and opens login', async () => {
  const h = setup();
  await assert.rejects(h.service({ method: 'post', url: '/control/finetuning/batches' }), /请先登录/);
  assert.equal(h.sent.length, 0);
  assert.deepEqual(h.redirects, ['/login']);
});

test('existing anonymous configuration and legacy fine-tuning calls remain compatible', async () => {
  const h = setup();
  for (const url of ['/finetuning/config', '/control/finetuning', '/module/']) {
    await h.service({ method: 'post', url });
  }
  assert.equal(h.sent.length, 3);
  assert.ok(h.sent.every(config => config.headers.Authorization === undefined));
  assert.equal(h.redirects.length, 0);
});
