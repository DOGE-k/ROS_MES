<template>
  <div class="drawing-manage">
    <el-card class="header-card">
      <div class="header-row">
        <h2 class="page-title">图纸管理</h2>
        <el-button type="primary" @click="openImportDialog">导入 JSON 图纸数据</el-button>
      </div>
    </el-card>

    <div class="search-bar">
      <div class="search-inner">
        <el-input
          v-model="searchForm.keyword"
          placeholder="搜索图纸名称、描述或备注..."
          clearable
          class="search-input"
          @keyup.enter="handleSearch"
        >
          <template #prefix>
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#909399" stroke-width="2">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </template>
        </el-input>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
        <span class="total-tag">共 {{ drawingList.length }} 条记录</span>
      </div>
    </div>

    <div class="table-wrapper">
      <el-table :data="drawingList" border stripe v-loading="loading" empty-text="暂无图纸数据" class="drawing-table">
        <el-table-column prop="drawingId" label="ID" width="70" align="center" />
        <el-table-column prop="drawingName" label="图纸名称" min-width="140" show-overflow-tooltip />
        <el-table-column prop="drawingDescription" label="图纸描述" min-width="160" show-overflow-tooltip />
        <el-table-column prop="drawingFile" label="文件路径" min-width="200" show-overflow-tooltip />
        <el-table-column prop="createTime" label="创建时间" width="165" align="center" />
        <el-table-column prop="modifyTime" label="修改时间" width="165" align="center" />
        <el-table-column prop="notes" label="备注" min-width="140" show-overflow-tooltip />
        <el-table-column label="操作" width="280" fixed="right" align="center">
          <template #default="{ row }">
            <div class="action-btns">
              <el-button link type="primary" size="small" @click="openDetailDialog(row)">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:3px">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
                查看
              </el-button>
              <el-button link type="success" size="small" @click="openEditDialog(row)">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:3px">
                  <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
                  <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
                </svg>
                编辑
              </el-button>
              <el-button link type="warning" size="small" @click="openReimportDialog(row)">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:3px">
                  <polyline points="23 4 23 10 17 10" />
                  <path d="M20.49 15a9 9 0 11-2.12-9.36L23 10" />
                </svg>
                重导
              </el-button>
              <el-popconfirm title="确定删除该图纸吗？此操作不可恢复。" @confirm="handleDelete(row)">
                <template #reference>
                  <el-button link type="danger" size="small">
                    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:3px">
                      <polyline points="3 6 5 6 21 6" />
                      <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                    </svg>
                    删除
                  </el-button>
                </template>
              </el-popconfirm>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="importVisible" title="导入 JSON 图纸数据" width="720px" destroy-on-close class="styled-dialog">
      <el-form :model="importForm" label-width="100px" class="import-form">
        <el-form-item label="图纸名称" required>
          <el-input v-model="importForm.drawingName" placeholder="请输入图纸名称" maxlength="100" show-word-limit />
        </el-form-item>
        <el-form-item label="图纸描述">
          <el-input v-model="importForm.drawingDescription" type="textarea" :rows="2" placeholder="请输入图纸描述（可选）" maxlength="500" show-word-limit />
        </el-form-item>
        <el-form-item label="JSON 文件" required>
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            accept=".json"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
            class="file-upload"
          >
            <el-button type="primary" plain>
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:4px">
                <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="12" y1="18" x2="12" y2="12" />
                <line x1="9" y1="15" x2="15" y2="15" />
              </svg>
              选择 JSON 文件
            </el-button>
            <template #tip>
              <div class="upload-tip">仅支持 .json 格式文件</div>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item v-if="fileSummary.length > 0" label="文件信息">
          <div class="file-summary">
            <div v-for="(item, idx) in fileSummary" :key="idx" class="summary-item">
              <span class="summary-dot"></span>
              {{ item }}
            </div>
          </div>
        </el-form-item>
        <el-form-item v-if="jsonPreview" label="JSON 预览">
          <div class="json-preview-wrapper">
            <el-input
              v-model="jsonPreview"
              type="textarea"
              :rows="15"
              readonly
              class="json-preview-input"
            />
            <div v-if="jsonTruncated" class="json-truncated-tip">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:4px;vertical-align:-2px">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="16" x2="12" y2="12" />
                <line x1="12" y1="8" x2="12.01" y2="8" />
              </svg>
              当前仅展示部分 JSON 内容，完整文件将在导入后保存。
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="importVisible = false">取消</el-button>
        <el-button type="primary" @click="handleImport" :loading="importing">
          {{ importing ? '正在导入...' : '确认导入' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="detailVisible" title="图纸详情" width="820px" destroy-on-close class="styled-dialog detail-dialog">
      <div v-loading="detailLoading" class="detail-body">
        <el-descriptions :column="2" border class="detail-descriptions">
          <el-descriptions-item label="图纸ID" width="120">{{ detailData.drawingId }}</el-descriptions-item>
          <el-descriptions-item label="图纸名称">{{ detailData.drawingName }}</el-descriptions-item>
          <el-descriptions-item label="图纸描述" :span="2">
            <span class="desc-cell">{{ detailData.drawingDescription || '-' }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="文件路径" :span="2">
            <el-tag type="info" class="file-path-tag">{{ detailData.drawingFile }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="创建人ID">{{ detailData.creatorId }}</el-descriptions-item>
          <el-descriptions-item label="最新版本ID">{{ detailData.latestVersionId || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ detailData.createTime }}</el-descriptions-item>
          <el-descriptions-item label="修改时间">{{ detailData.modifyTime || '-' }}</el-descriptions-item>
          <el-descriptions-item label="备注" :span="2">
            <span class="desc-cell">{{ detailData.notes || '-' }}</span>
          </el-descriptions-item>
        </el-descriptions>
        <div v-if="detailJsonContent" class="detail-json-section">
          <div class="json-section-header">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#409eff" stroke-width="2" style="margin-right:6px">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            <span>JSON 文件内容预览</span>
          </div>
          <div class="json-preview-wrapper">
            <el-input
              v-model="detailJsonContent"
              type="textarea"
              :rows="12"
              readonly
              class="json-preview-input"
            />
            <div v-if="detailJsonTruncated" class="json-truncated-tip">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:4px;vertical-align:-2px">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="16" x2="12" y2="12" />
                <line x1="12" y1="8" x2="12.01" y2="8" />
              </svg>
              当前仅展示前 10000 个字符，完整文件已上传保存。
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editVisible" title="编辑图纸信息" width="520px" destroy-on-close class="styled-dialog">
      <el-form :model="editForm" label-width="100px">
        <el-form-item label="图纸名称" required>
          <el-input v-model="editForm.drawingName" placeholder="请输入图纸名称" maxlength="100" show-word-limit />
        </el-form-item>
        <el-form-item label="图纸描述">
          <el-input v-model="editForm.drawingDescription" type="textarea" :rows="3" placeholder="请输入图纸描述" maxlength="500" show-word-limit />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.notes" type="textarea" :rows="3" placeholder="请输入备注信息" maxlength="500" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="handleEdit" :loading="editing">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import type { UploadFile, UploadInstance } from 'element-plus';
import {
  getDrawingListApi,
  getDrawingFileContentApi,
  importDrawingApi,
  updateDrawingApi,
  deleteDrawingApi,
} from '@/api/rosApi';
import type { DrawingItem } from '@/api/types';

const loading = ref(false);
const drawingList = ref<DrawingItem[]>([]);

const searchForm = reactive({
  keyword: '',
});

const uploadRef = ref<UploadInstance>();

const importVisible = ref(false);
const importing = ref(false);
const importForm = reactive({
  drawingName: '',
  drawingDescription: '',
});
const currentFile = ref<File | null>(null);
const jsonPreview = ref('');
const jsonTruncated = ref(false);
const fileSummary = ref<string[]>([]);

const detailVisible = ref(false);
const detailLoading = ref(false);
const detailData = reactive<Partial<DrawingItem>>({});
const detailJsonContent = ref('');
const detailJsonTruncated = ref(false);

const editVisible = ref(false);
const editing = ref(false);
const editForm = reactive({
  drawingId: 0,
  drawingName: '',
  drawingDescription: '',
  notes: '',
});

const MAX_PREVIEW_CHARS = 5000;

function parseFileSummary(jsonObj: any): string[] {
  const fileInfo = jsonObj?.['文件信息'];
  if (!fileInfo) return [];
  const items: string[] = [];
  if (fileInfo['STP文件路径']) items.push('STP文件路径: ' + fileInfo['STP文件路径']);
  if (fileInfo['聚类阈值(mm)']) items.push('聚类阈值(mm): ' + fileInfo['聚类阈值(mm)']);
  if (fileInfo['总坐标点数量']) items.push('总坐标点数量: ' + fileInfo['总坐标点数量']);
  if (fileInfo['虚拟部件数量']) items.push('虚拟部件数量: ' + fileInfo['虚拟部件数量']);
  return items;
}

function handleFileChange(file: UploadFile) {
  const raw = file.raw as File;
  if (!raw) return;
  if (!raw.name.toLowerCase().endsWith('.json')) {
    ElMessage.warning('请选择 JSON 格式文件');
    uploadRef.value?.clearFiles();
    return;
  }
  currentFile.value = raw;
  const reader = new FileReader();
  reader.onload = (e) => {
    const text = e.target?.result as string;
    try {
      const jsonObj = JSON.parse(text);
      fileSummary.value = parseFileSummary(jsonObj);
      if (text.length > MAX_PREVIEW_CHARS) {
        jsonPreview.value = text.substring(0, MAX_PREVIEW_CHARS);
        jsonTruncated.value = true;
      } else {
        jsonPreview.value = text;
        jsonTruncated.value = false;
      }
    } catch {
      fileSummary.value = [];
      jsonPreview.value = text.substring(0, MAX_PREVIEW_CHARS);
      jsonTruncated.value = text.length > MAX_PREVIEW_CHARS;
    }
  };
  reader.readAsText(raw);
}

function handleFileRemove() {
  currentFile.value = null;
  jsonPreview.value = '';
  jsonTruncated.value = false;
  fileSummary.value = [];
}

function resetImportForm() {
  importForm.drawingName = '';
  importForm.drawingDescription = '';
  currentFile.value = null;
  jsonPreview.value = '';
  jsonTruncated.value = false;
  fileSummary.value = [];
  uploadRef.value?.clearFiles();
}

function openImportDialog() {
  resetImportForm();
  importVisible.value = true;
}

function openReimportDialog(row: DrawingItem) {
  resetImportForm();
  importForm.drawingName = row.drawingName;
  importForm.drawingDescription = row.drawingDescription || '';
  (importForm as any).drawingId = row.drawingId;
  importVisible.value = true;
}

async function handleImport() {
  if (!importForm.drawingName.trim()) {
    ElMessage.warning('请输入图纸名称');
    return;
  }
  if (!currentFile.value && !uploadRef.value?.uploadFiles?.length) {
    ElMessage.warning('请选择 JSON 文件');
    return;
  }

  importing.value = true;
  try {
    const formData = new FormData();
    formData.append('drawing_name', importForm.drawingName.trim());
    formData.append('drawing_description', importForm.drawingDescription.trim());
    const drawingId = (importForm as any).drawingId;
    if (drawingId) {
      formData.append('drawing_id', String(drawingId));
    }
    if (currentFile.value) {
      formData.append('file', currentFile.value);
    }

    const res = await importDrawingApi(formData);
    if (res.code === 200) {
      ElMessage.success(res.message || '导入成功');
      importVisible.value = false;
      delete (importForm as any).drawingId;
      fetchDrawingList();
    } else {
      ElMessage.error(res.message || '导入失败');
    }
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.message || '导入失败';
    ElMessage.error(msg);
  } finally {
    importing.value = false;
  }
}

async function fetchDrawingList(keyword?: string) {
  loading.value = true;
  try {
    const params: any = {};
    if (keyword && keyword.trim()) {
      params.keyword = keyword.trim();
    }
    const res = await getDrawingListApi(params);
    if (res.code === 200) {
      drawingList.value = res.data || [];
    }
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.message || '获取图纸列表失败';
    ElMessage.error(msg);
  } finally {
    loading.value = false;
  }
}

function handleSearch() {
  fetchDrawingList(searchForm.keyword);
}

function handleReset() {
  searchForm.keyword = '';
  fetchDrawingList();
}

async function openDetailDialog(row: DrawingItem) {
  detailVisible.value = true;
  detailLoading.value = true;
  detailJsonContent.value = '';
  detailJsonTruncated.value = false;
  Object.assign(detailData, row);

  try {
    const res = await getDrawingFileContentApi(row.drawingId);
    if (res.code === 200) {
      const fileData = res.data;
      detailJsonContent.value = fileData.content;
      detailJsonTruncated.value = fileData.truncated;
    }
  } catch {
    detailJsonContent.value = '';
  } finally {
    detailLoading.value = false;
  }
}

function openEditDialog(row: DrawingItem) {
  editForm.drawingId = row.drawingId;
  editForm.drawingName = row.drawingName;
  editForm.drawingDescription = row.drawingDescription || '';
  editForm.notes = row.notes || '';
  editVisible.value = true;
}

async function handleEdit() {
  if (!editForm.drawingName.trim()) {
    ElMessage.warning('请输入图纸名称');
    return;
  }

  editing.value = true;
  try {
    const formData = new FormData();
    formData.append('drawing_name', editForm.drawingName.trim());
    formData.append('drawing_description', editForm.drawingDescription.trim());
    formData.append('notes', editForm.notes.trim());

    const res = await updateDrawingApi(editForm.drawingId, formData);
    if (res.code === 200) {
      ElMessage.success('更新成功');
      editVisible.value = false;
      fetchDrawingList();
    } else {
      ElMessage.error(res.message || '更新失败');
    }
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.message || '更新失败';
    ElMessage.error(msg);
  } finally {
    editing.value = false;
  }
}

async function handleDelete(row: DrawingItem) {
  try {
    const res = await deleteDrawingApi(row.drawingId);
    if (res.code === 200) {
      ElMessage.success('删除成功');
      fetchDrawingList();
    } else {
      ElMessage.error(res.message || '删除失败');
    }
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.message || '删除失败';
    ElMessage.error(msg);
  }
}

onMounted(() => {
  fetchDrawingList();
});
</script>

<style scoped>
.drawing-manage {
  padding: 20px;
  min-height: calc(100vh - 100px);
}

.header-card {
  margin-bottom: 16px;
}

.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.page-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.search-bar {
  margin-bottom: 20px;
  background: #fff;
  border-radius: 12px;
  padding: 16px 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.search-inner {
  display: flex;
  align-items: center;
  gap: 12px;
}

.search-input {
  width: 360px;
}

.search-input :deep(.el-input__wrapper) {
  border-radius: 8px;
}

.total-tag {
  margin-left: auto;
  font-size: 13px;
  color: #909399;
}

.table-wrapper {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.drawing-table {
  border-radius: 8px;
}

.drawing-table :deep(.el-table__header th) {
  background: #f5f7fa;
  color: #606266;
  font-weight: 600;
}

.action-btns {
  display: flex;
  justify-content: center;
  gap: 2px;
}

/* File upload styling */
.file-upload {
  width: 100%;
}

.file-upload :deep(.el-upload) {
  display: inline-block;
}

.upload-tip {
  color: #909399;
  font-size: 12px;
  margin-top: 4px;
}

/* File summary styling */
.file-summary {
  background: #f0f9ff;
  border: 1px solid #b3d8f0;
  border-radius: 8px;
  padding: 12px 16px;
  line-height: 1.8;
  font-size: 13px;
  color: #303133;
  width: 100%;
}

.summary-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.summary-dot {
  width: 6px;
  height: 6px;
  background: #409eff;
  border-radius: 50%;
  flex-shrink: 0;
}

/* JSON preview */
.json-preview-wrapper {
  width: 100%;
}

.json-preview-input {
  overflow: auto;
}

.json-preview-input :deep(.el-textarea__inner) {
  height: 300px !important;
  max-height: 300px;
  overflow: auto;
  font-family: 'Courier New', Consolas, monospace;
  font-size: 12px;
  line-height: 1.5;
  resize: none;
  white-space: pre;
  word-break: break-all;
  background: #fafafa;
}

.json-truncated-tip {
  color: #e6a23c;
  font-size: 12px;
  margin-top: 8px;
  background: #fdf6ec;
  border: 1px solid #faecd8;
  border-radius: 6px;
  padding: 8px 12px;
}

/* Detail dialog */
.detail-dialog .detail-body {
  max-height: 70vh;
  overflow-y: auto;
}

.detail-dialog .desc-cell {
  word-break: break-all;
  white-space: pre-wrap;
  display: inline-block;
  max-width: 100%;
}

.file-path-tag {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.json-section-header {
  display: flex;
  align-items: center;
  margin: 20px 0 12px;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  padding-bottom: 8px;
  border-bottom: 2px solid #ecf5ff;
}

/* Dialog styling */
.styled-dialog :deep(.el-dialog__header) {
  padding: 20px 24px 16px;
  border-bottom: 1px solid #ebeef5;
  margin: 0;
}

.styled-dialog :deep(.el-dialog__title) {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.styled-dialog :deep(.el-dialog__body) {
  padding: 24px;
}

.styled-dialog :deep(.el-dialog__footer) {
  padding: 12px 24px 20px;
  border-top: 1px solid #ebeef5;
}

/* Import form */
.import-form :deep(.el-form-item__label) {
  font-weight: 500;
}
</style>
