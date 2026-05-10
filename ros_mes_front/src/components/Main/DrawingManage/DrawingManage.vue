<template>
  <div class="drawing-manage">
    <el-card class="header-card">
      <div class="header-row">
        <h2 class="page-title">图纸管理</h2>
        <el-button type="primary" @click="openImportDialog">导入 JSON 图纸数据</el-button>
      </div>
    </el-card>

    <el-card class="search-card">
      <el-form :model="searchForm" label-width="80px">
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="图纸名称">
              <el-input
                v-model="searchForm.keyword"
                placeholder="按图纸名称 / 描述搜索"
                clearable
                @keyup.enter="handleSearch"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item>
              <el-button type="primary" @click="handleSearch">查询</el-button>
              <el-button @click="handleReset">重置</el-button>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <el-card class="table-card">
      <el-table :data="drawingList" border stripe v-loading="loading">
        <el-table-column prop="drawingId" label="图纸ID" width="80" />
        <el-table-column prop="drawingName" label="图纸名称" min-width="140" show-overflow-tooltip />
        <el-table-column prop="drawingDescription" label="图纸描述" min-width="160" show-overflow-tooltip />
        <el-table-column prop="drawingFile" label="文件路径" min-width="200" show-overflow-tooltip />
        <el-table-column prop="createTime" label="创建时间" width="170" />
        <el-table-column prop="modifyTime" label="修改时间" width="170" />
        <el-table-column prop="notes" label="备注" min-width="160" show-overflow-tooltip />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetailDialog(row)">查看</el-button>
            <el-button link type="success" @click="openEditDialog(row)">编辑</el-button>
            <el-button link type="warning" @click="openReimportDialog(row)">重新导入</el-button>
            <el-popconfirm title="确定删除该图纸吗？" @confirm="handleDelete(row)">
              <template #reference>
                <el-button link type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="importVisible" title="导入 JSON 图纸数据" width="700px" destroy-on-close>
      <el-form :model="importForm" label-width="100px">
        <el-form-item label="图纸名称" required>
          <el-input v-model="importForm.drawingName" placeholder="请输入图纸名称" />
        </el-form-item>
        <el-form-item label="图纸描述">
          <el-input v-model="importForm.drawingDescription" type="textarea" :rows="2" placeholder="请输入图纸描述（可选）" />
        </el-form-item>
        <el-form-item label="JSON 文件" required>
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            accept=".json"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
          >
            <el-button type="primary">选择 JSON 文件</el-button>
          </el-upload>
        </el-form-item>
        <el-form-item v-if="fileSummary.length > 0" label="文件信息">
          <div class="file-summary">
            <div v-for="(item, idx) in fileSummary" :key="idx">{{ item }}</div>
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
              当前仅展示部分 JSON 内容，完整文件将在导入后保存。
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="importVisible = false">取消</el-button>
        <el-button type="primary" @click="handleImport" :loading="importing">确认导入</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="detailVisible" title="图纸详情" width="800px" destroy-on-close class="detail-dialog">
      <div v-loading="detailLoading" class="detail-body">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="图纸ID">{{ detailData.drawingId }}</el-descriptions-item>
          <el-descriptions-item label="图纸名称">{{ detailData.drawingName }}</el-descriptions-item>
          <el-descriptions-item label="图纸描述" :span="2">
            <span class="desc-cell">{{ detailData.drawingDescription || '-' }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="文件路径" :span="2">
            <span class="desc-cell">{{ detailData.drawingFile }}</span>
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
          <h4 class="json-section-title">JSON 文件内容预览</h4>
          <div class="json-preview-wrapper">
            <el-input
              v-model="detailJsonContent"
              type="textarea"
              :rows="12"
              readonly
              class="json-preview-input"
            />
            <div v-if="detailJsonTruncated" class="json-truncated-tip">
              当前仅展示前 10000 个字符，完整文件已上传保存。
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editVisible" title="编辑图纸信息" width="500px" destroy-on-close>
      <el-form :model="editForm" label-width="100px">
        <el-form-item label="图纸名称" required>
          <el-input v-model="editForm.drawingName" placeholder="请输入图纸名称" />
        </el-form-item>
        <el-form-item label="图纸描述">
          <el-input v-model="editForm.drawingDescription" type="textarea" :rows="2" placeholder="请输入图纸描述" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.notes" type="textarea" :rows="3" placeholder="请输入备注信息" />
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
  getDrawingDetailApi,
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
}

.header-card {
  margin-bottom: 16px;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.page-title {
  margin: 0;
  font-size: 18px;
  color: #303133;
}

.search-card {
  margin-bottom: 16px;
}

.search-card .el-form {
  margin-bottom: 0;
}

.table-card {
  min-height: 400px;
}

.file-summary {
  background: #f5f7fa;
  padding: 12px 16px;
  border-radius: 4px;
  line-height: 1.8;
  font-size: 13px;
  color: #303133;
}

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
}

.json-truncated-tip {
  color: #e6a23c;
  font-size: 12px;
  margin-top: 6px;
}

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

.json-section-title {
  margin: 16px 0 8px;
  font-size: 14px;
  color: #303133;
}
</style>
