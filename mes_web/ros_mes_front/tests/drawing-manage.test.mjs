import fs from 'node:fs';
import vm from 'node:vm';
import { File } from 'node:buffer';
import assert from 'node:assert/strict';
import test from 'node:test';
import { parse } from '@vue/compiler-sfc';
import ts from 'typescript';
import * as vue from 'vue';

// 运行实际组件脚本及 Vue 响应式逻辑；只替换 API 和消息提示，不连接真实后端。
const source = fs.readFileSync(new URL('../src/components/Main/DrawingManage/DrawingManage.vue', import.meta.url), 'utf8');
const { descriptor } = parse(source);
const script = ts.transpileModule(descriptor.scriptSetup.content, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
}).outputText;
const bindings = `Object.assign(module.exports, {
  currentPage, pageSize, total, pageDrawingList, loading, searchForm,
  fetchDrawingList, handleSearch, handleReset, handleDelete,
  openImportDialog, openReimportDialog, handleImport,
  importForm, importVisible, importing, currentFile,
  openEditDialog, handleEdit,
});`;
const flush = () => new Promise(resolve => setImmediate(resolve));
const rows = count => Array.from({ length: count }, (_, i) => ({
  drawingId: i + 1, drawingName: i < 2 ? 'target' : `drawing ${i + 1}`,
}));

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function setup(t, options = {}) {
  let records = rows(25);
  const queries = [];
  const imports = [];
  const errors = [];
  const api = {
    getDrawingListApi(params) {
      queries.push(params);
      if (options.list) return options.list(params);
      const data = params.keyword ? records.filter(row => row.drawingName.includes(params.keyword)) : [...records];
      return Promise.resolve({ code: 200, data });
    },
    async deleteDrawingApi(id) {
      records = records.filter(row => row.drawingId !== id);
      return { code: 200 };
    },
    async importDrawingApi(body) {
      imports.push(body);
      return options.import ? options.import(body) : { code: 200 };
    },
    async updateDrawingApi() { return { code: 200 }; },
  };
  const module = { exports: {} };
  const scope = vue.effectScope();
  t.after(() => scope.stop());
  scope.run(() => vm.runInNewContext(script + '\n' + bindings, {
    module, exports: module.exports, FormData,
    require(name) {
      if (name === 'vue') return { ...vue, onMounted() {} };
      if (name === '@/api/rosApi') return api;
      if (name === 'element-plus') return {
        ElMessage: { success() {}, warning() {}, error(message) { errors.push(message); } },
      };
      throw new Error(`Unexpected dependency: ${name}`);
    },
  }));
  return { page: module.exports, queries, imports, errors, setRecords(data) { records = data; } };
}

function selectImportFile(page) {
  page.importForm.drawingName = 'new drawing';
  page.currentFile.value = new File(['{}'], 'drawing.json', { type: 'application/json' });
}

test('25 drawings paginate as 10/10/5 and larger page size stays in range', async t => {
  const { page } = setup(t);
  await page.fetchDrawingList();
  assert.equal(page.total.value, 25);
  assert.equal(page.pageDrawingList.value.length, 10);
  page.currentPage.value = 3;
  assert.equal(page.pageDrawingList.value.length, 5);
  assert.equal(page.pageDrawingList.value[0].drawingId, 21);
  page.pageSize.value = 50;
  assert.equal(page.currentPage.value, 1);
  assert.equal(page.pageDrawingList.value.length, 25);
});

test('search and reset start on page 1; empty results keep a valid page', async t => {
  const { page, setRecords } = setup(t);
  await page.fetchDrawingList();
  page.currentPage.value = 3;
  page.searchForm.keyword = 'target';
  page.handleSearch();
  await flush();
  assert.equal(page.currentPage.value, 1);
  assert.equal(page.total.value, 2);
  page.handleReset();
  await flush();
  assert.equal(page.total.value, 25);
  assert.equal(page.currentPage.value, 1);
  setRecords([]);
  await page.fetchDrawingList();
  assert.equal(page.total.value, 0);
  assert.equal(page.currentPage.value, 1);
});

test('deleting the final row of the last page returns to the previous page', async t => {
  const { page, setRecords } = setup(t);
  setRecords(rows(21));
  await page.fetchDrawingList();
  page.currentPage.value = 3;
  await page.handleDelete({ drawingId: 21 });
  await flush();
  assert.equal(page.total.value, 20);
  assert.equal(page.currentPage.value, 2);
  assert.equal(page.pageDrawingList.value.length, 10);
});

test('refresh after editing or deleting uses the submitted search, not unfinished input', async t => {
  const { page, queries } = setup(t);
  page.searchForm.keyword = 'target';
  page.handleSearch();
  await flush();
  page.searchForm.keyword = 'unfinished input';
  page.openEditDialog({ drawingId: 1, drawingName: 'target' });
  await page.handleEdit();
  await flush();
  assert.equal(queries.at(-1).keyword, 'target');
  await page.handleDelete({ drawingId: 1 });
  await flush();
  assert.equal(queries.at(-1).keyword, 'target');
  assert.equal(page.total.value, 1);
});

test('a slow earlier query cannot overwrite the latest result', async t => {
  const requests = [deferred(), deferred()];
  const { page } = setup(t, { list: () => requests.shift().promise });
  const [first, second] = [...requests];
  const oldRequest = page.fetchDrawingList();
  const newRequest = page.fetchDrawingList();
  second.resolve({ code: 200, data: [{ drawingId: 2 }] });
  await newRequest;
  first.resolve({ code: 200, data: [{ drawingId: 1 }] });
  await oldRequest;
  assert.equal(page.pageDrawingList.value[0].drawingId, 2);
});

test('an earlier request finishing does not stop the latest loading indicator', async t => {
  const requests = [deferred(), deferred()];
  const [first, second] = [...requests];
  const { page } = setup(t, { list: () => requests.shift().promise });
  const oldRequest = page.fetchDrawingList();
  const newRequest = page.fetchDrawingList();
  first.resolve({ code: 200, data: [] });
  await oldRequest;
  assert.equal(page.loading.value, true);
  second.resolve({ code: 200, data: rows(1) });
  await newRequest;
  assert.equal(page.loading.value, false);
});

test('a stale request failure cannot replace the latest state or add a component error', async t => {
  const requests = [deferred(), deferred()];
  const [first, second] = [...requests];
  const { page, errors } = setup(t, { list: () => requests.shift().promise });
  const oldRequest = page.fetchDrawingList();
  const newRequest = page.fetchDrawingList();
  second.resolve({ code: 200, data: rows(1) });
  await newRequest;
  first.reject(new Error('old request failed'));
  await oldRequest;
  assert.equal(page.total.value, 1);
  assert.equal(page.loading.value, false);
  assert.equal(errors.length, 0);
});

test('a current request failure preserves the last successful list and reports the error', async t => {
  let fail = false;
  const { page, errors } = setup(t, { list: async () => {
    if (fail) throw new Error('current request failed');
    return { code: 200, data: rows(1) };
  } });
  await page.fetchDrawingList();
  fail = true;
  await page.fetchDrawingList();
  assert.equal(page.total.value, 1);
  assert.equal(page.loading.value, false);
  assert.equal(errors[0], 'current request failed');
});

test('cancel reimport then open a new import does not send the old drawing ID', async t => {
  const { page, imports } = setup(t);
  page.openReimportDialog({ drawingId: 42, drawingName: 'existing drawing' });
  page.importVisible.value = false;
  page.openImportDialog();
  selectImportFile(page);
  await page.handleImport();
  assert.equal(imports[0].get('drawing_id'), null);
});

test('a new import returns to page 1 to show the newest drawings', async t => {
  const { page, imports } = setup(t);
  await page.fetchDrawingList();
  page.currentPage.value = 3;
  page.openImportDialog();
  selectImportFile(page);
  await page.handleImport();
  await flush();
  assert.equal(imports[0].get('drawing_id'), null);
  assert.equal(page.currentPage.value, 1);
});

test('reimport sends the selected drawing ID and retains the current page', async t => {
  const { page, imports } = setup(t);
  await page.fetchDrawingList();
  page.currentPage.value = 3;
  page.openReimportDialog({ drawingId: 42, drawingName: 'existing drawing' });
  selectImportFile(page);
  await page.handleImport();
  await flush();
  assert.equal(imports[0].get('drawing_id'), '42');
  assert.equal(page.currentPage.value, 3);
});

test('repeated clicks while importing only send one write request', async t => {
  const pending = deferred();
  const { page, imports } = setup(t, { import: () => pending.promise });
  page.openImportDialog();
  selectImportFile(page);
  const first = page.handleImport();
  const second = page.handleImport();
  const count = imports.length;
  pending.resolve({ code: 200 });
  await Promise.all([first, second]);
  assert.equal(count, 1);
});
