<template>
  <div class="hardwork-page">
    <div class="page-header">
      <h2>设备信息管理</h2>
    </div>
    <div class="page-body">
      <div class="tree-panel">
        <div class="tree-header">
          <span class="tree-title">设备树</span>
          <el-button type="primary" size="small" @click="handleAddModel">新增型号</el-button>
        </div>
        <el-input
          v-model="filterText"
          placeholder="搜索设备..."
          size="small"
          clearable
          class="tree-filter"
        />
        <el-tree
          ref="treeRef"
          :data="treeData"
          :props="treeProps"
          :filter-node-method="filterNode"
          :highlight-current="true"
          :expand-on-click-node="true"
          node-key="id"
          @node-click="handleNodeClick"
          :default-expanded-keys="expandedKeys"
        >
          <template #default="{ node }">
            <span class="tree-node-label">
              {{ node.label }}
            </span>
          </template>
        </el-tree>
      </div>
      <div class="form-panel">
        <div v-if="!selectedNode" class="placeholder">
          <p>请从左侧设备树中选择一个节点</p>
        </div>
        <div v-else class="detail-form">
          <div class="form-header">
            <span class="form-title">
              <template v-if="selectedNode.type === 'model'">型号详情</template>
              <template v-else-if="selectedNode.type === 'device'">模块详情</template>
              <template v-else-if="selectedNode.type === 'unit'">机械臂详情</template>
              <template v-else>传感器详情</template>
            </span>
            <div class="form-actions">
              <el-button v-if="!isEditing" type="primary" size="small" @click="startEdit">编辑</el-button>
              <el-button v-if="isEditing" type="primary" size="small" @click="saveEdit">保存</el-button>
              <el-button v-if="isEditing" size="small" @click="cancelEdit">取消</el-button>
              <el-button
                v-if="selectedNode.type === 'model'"
                size="small"
                @click="showAddDialog('device')"
              >新增模块</el-button>
              <el-button
                v-if="selectedNode.type === 'device'"
                size="small"
                @click="showAddDialog('unit')"
              >新增机械臂</el-button>
              <el-button
                v-if="selectedNode.type === 'unit'"
                size="small"
                @click="showAddDialog('sensor')"
              >新增传感器</el-button>
              <el-button
                size="small"
                type="danger"
                plain
                @click="confirmDelete"
              >删除</el-button>
            </div>
          </div>
          <el-form
            :model="formData"
            label-width="105px"
            size="small"
            class="detail-el-form"
          >
            <template v-if="selectedNode.type === 'model'">
              <el-form-item label="型号ID">
                <el-input :model-value="formData.Model_ID" disabled />
              </el-form-item>
              <el-form-item label="型号名称">
                <el-input v-model="formData.Modelname" :disabled="!isEditing" />
              </el-form-item>
              <el-form-item label="型号描述">
                <el-input v-model="formData.Modeldescripte" :disabled="!isEditing" type="textarea" :rows="3" />
              </el-form-item>
              <el-form-item label="创建人">
                <el-input :model-value="formData.creater_id" disabled />
              </el-form-item>
              <el-form-item label="创建时间">
                <el-input :model-value="formData.Createtime" disabled />
              </el-form-item>
              <el-form-item label="备注">
                <el-input v-model="formData.Notes" :disabled="!isEditing" type="textarea" :rows="2" />
              </el-form-item>
            </template>
            <template v-else-if="selectedNode.type === 'device'">
              <el-form-item label="模块ID">
                <el-input :model-value="formData.Device_ID" disabled />
              </el-form-item>
              <el-form-item label="所属型号">
                <el-select v-model="formData.Model_ID" :disabled="!isEditing" style="width:100%">
                  <el-option
                    v-for="m in modelOptions"
                    :key="m.Model_ID"
                    :label="m.Modelname"
                    :value="m.Model_ID"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="模块坐标">
                <div style="display:flex;gap:8px;align-items:center">
                  <span>(</span>
                  <el-input-number v-model="formData.deviceCoordX" :disabled="!isEditing" :min="1" :max="15" controls-position="right" style="width:120px" />
                  <span>,</span>
                  <el-input-number v-model="formData.deviceCoordY" :disabled="!isEditing" :min="1" :max="15" controls-position="right" style="width:120px" />
                  <span>)</span>
                  <span style="color:#909399;font-size:12px;margin-left:4px">
                    二进制: {{ binaryAddress }}
                   </span>
                 </div>
                 <div v-if="isEditing && formData._coordDuplicate" style="color:#e6a23c;font-size:12px;margin-top:4px">
                   ⚠️ 该坐标的模块已存在
                 </div>
               </el-form-item>
              <el-form-item label="模块描述">
                <el-input v-model="formData.Devicedescript" :disabled="!isEditing" type="textarea" :rows="3" />
              </el-form-item>
              <el-form-item label="创建人">
                <el-input :model-value="formData.creater_id" disabled />
              </el-form-item>
              <el-form-item label="创建时间">
                <el-input :model-value="formData.Createtime" disabled />
              </el-form-item>
              <el-form-item label="备注">
                <el-input v-model="formData.Notes" :disabled="!isEditing" type="textarea" :rows="2" />
              </el-form-item>
            </template>
            <template v-else-if="selectedNode.type === 'unit'">
              <el-form-item label="机械臂ID">
                <el-input :model-value="formData.Unit_ID" disabled />
              </el-form-item>
              <el-form-item label="所属模块">
                <el-select v-model="formData.Device_ID" :disabled="!isEditing" style="width:100%">
                  <el-option
                    v-for="d in deviceOptions"
                    :key="d.Device_ID"
                    :label="'模块(' + ((d.DeviceAddress >> 4) & 0x0F) + ',' + (d.DeviceAddress & 0x0F) + ')'"
                    :value="d.Device_ID"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="机械臂名称">
                <el-input v-model="formData.UnitDescript" :disabled="!isEditing" />
              </el-form-item>
              <el-form-item label="创建人">
                <el-input :model-value="formData.creater_id" disabled />
              </el-form-item>
              <el-form-item label="创建时间">
                <el-input :model-value="formData.Createtime" disabled />
              </el-form-item>
              <el-form-item label="备注">
                <el-input v-model="formData.Notes" :disabled="!isEditing" type="textarea" :rows="2" />
              </el-form-item>
            </template>
            <template v-else-if="selectedNode.type === 'sensor'">
              <el-form-item label="传感器ID">
                <el-input :model-value="formData.sensor_ID" disabled />
              </el-form-item>
              <el-form-item label="所属机械臂">
                <el-select v-model="formData.unit_row_id" :disabled="!isEditing" style="width:100%">
                  <el-option
                    v-for="u in unitOptions"
                    :key="u.id"
                    :label="u.UnitDescript || '机械臂' + u.Unit_ID"
                    :value="u.id"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="传感器名称">
                <el-select v-model="formData.sensordescript" :disabled="!isEditing" style="width:100%" placeholder="请选择传感器类型" @change="onEditSensorNameChange">
                  <el-option
                    v-for="opt in editAvailableSensorOptions"
                    :key="opt.label"
                    :label="opt.label"
                    :value="opt.label"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="传感器地址">
                <el-input :model-value="formData.Unit_address" disabled />
              </el-form-item>
              <el-form-item label="是否启用">
                <el-switch
                  v-model="formData.IsRead"
                  :active-value="1"
                  :inactive-value="0"
                  :disabled="!isEditing"
                />
              </el-form-item>
              <el-form-item label="创建人">
                <el-input :model-value="formData.creater_id" disabled />
              </el-form-item>
              <el-form-item label="创建时间">
                <el-input :model-value="formData.Createtime" disabled />
              </el-form-item>
              <el-form-item label="备注">
                <el-input v-model="formData.Notes" :disabled="!isEditing" type="textarea" :rows="2" />
              </el-form-item>
            </template>
          </el-form>
        </div>
      </div>
    </div>

    <el-dialog
      v-model="addDialogVisible"
      :title="addDialogTitle"
      width="500px"
    >
      <el-form :model="addForm" label-width="100px" size="small">
        <template v-if="addTargetType === 'device'">
          <el-form-item label="所属型号">
            <el-input :model-value="selectedNode?.raw_id" disabled />
          </el-form-item>
          <el-form-item label="模块坐标">
            <div style="display:flex;gap:8px;align-items:center">
              <span>(</span>
              <el-input-number v-model="addForm.coordX" :min="1" :max="15" controls-position="right" style="width:120px" />
              <span>,</span>
              <el-input-number v-model="addForm.coordY" :min="1" :max="15" controls-position="right" style="width:120px" />
              <span>)</span>
              <span style="color:#909399;font-size:12px;margin-left:4px">
                二进制: {{ addCoordBinary }}
              </span>
            </div>
            <div v-if="addCoordDuplicate" style="color:#e6a23c;font-size:12px;margin-top:4px">
              ⚠️ 该坐标的模块已存在
            </div>
          </el-form-item>
          <el-form-item label="模块描述">
            <el-input v-model="addForm.Devicedescript" type="textarea" :rows="2" />
          </el-form-item>
        </template>
        <template v-else-if="addTargetType === 'unit'">
          <el-form-item label="所属模块">
            <el-input :model-value="selectedNode?.raw_id" disabled />
          </el-form-item>
          <el-form-item label="机械臂">
            <el-select v-model="addForm.Unit_ID" style="width:100%">
              <el-option
                v-for="opt in availableArmOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </el-form-item>
        </template>
        <template v-else-if="addTargetType === 'sensor'">
          <el-form-item label="所属机械臂">
            <el-input :model-value="selectedNode?.label" disabled />
          </el-form-item>
          <el-form-item label="传感器名称">
            <el-select v-model="addForm.sensordescript" style="width:100%" placeholder="请选择传感器类型" @change="onSensorNameChange">
              <el-option
                v-for="opt in availableSensorOptions"
                :key="opt.label"
                :label="opt.label"
                :value="opt.label"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="传感器地址">
            <el-input :model-value="addForm.Unit_address" disabled />
          </el-form-item>
          <el-form-item label="是否启用">
            <el-switch v-model="addForm.IsRead" :active-value="1" :inactive-value="0" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="addDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAdd" :disabled="addCoordDuplicate">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getDeviceTreeApi,
  getModelApi,
  getDeviceApi,
  getUnitApi,
  getSensorApi,
  createModelApi,
  updateModelApi,
  deleteModelApi,
  createDeviceApi,
  updateDeviceApi,
  deleteDeviceApi,
  createUnitApi,
  updateUnitApi,
  deleteUnitApi,
  createSensorApi,
  updateSensorApi,
  deleteSensorApi,
  getModelListApi,
  getDeviceListApi,
  getDevicesByModelApi,
  getUnitListApi,
  getSensorsByUnitApi,
  type TreeNode,
} from '@/api/rosApi'

const treeRef = ref()
const filterText = ref('')
const treeData = ref<TreeNode[]>([])
const selectedNode = ref<TreeNode | null>(null)
const isEditing = ref(false)
const expandedKeys = ref<string[]>([])

const treeProps = {
  children: 'children',
  label: 'label',
}

interface FormDataType {
  [key: string]: any
}

const formData = ref<FormDataType>({})
const formSnapshot = ref<FormDataType>({})

const modelOptions = ref<any[]>([])
const deviceOptions = ref<any[]>([])
const unitOptions = ref<any[]>([])

const addDialogVisible = ref(false)
const addTargetType = ref<'device' | 'unit' | 'sensor'>('device')
const addForm = ref<any>({})

const addDialogTitle = ref('')
const existingDevices = ref<any[]>([])
const allUnits = ref<any[]>([])
const existingSensorsInUnit = ref<any[]>([])

const ARM_OPTIONS = [
  { label: '一号机械臂', value: 32 },
  { label: '二号机械臂', value: 64 },
  { label: '三号机械臂', value: 96 },
]

const SENSOR_OPTIONS = [
  { label: '旋转电机', offset: 1, Unit_address: 1 },
  { label: '摆动电机', offset: 2, Unit_address: 2 },
  { label: '伸缩电机', offset: 3, Unit_address: 3 },
  { label: '旋转编码器', offset: 9, Unit_address: 1 },
  { label: '偏转编码器', offset: 10, Unit_address: 2 },
  { label: '伸缩编码器', offset: 11, Unit_address: 3 },
  { label: '压力传感器', offset: 17, Unit_address: 0 },
  { label: '陀螺仪传感器', offset: 18, Unit_address: 4 },
]

const availableArmOptions = computed(() => {
  const parentDeviceId = selectedNode.value?.raw_id
  if (!parentDeviceId) return ARM_OPTIONS
  return ARM_OPTIONS.filter(opt => !allUnits.value.some(
    u => u.Unit_ID === opt.value && u.Device_ID === parentDeviceId
  ))
})

const availableSensorOptions = computed(() => {
  const unitRowId = selectedNode.value?.raw_id
  if (!unitRowId) return SENSOR_OPTIONS
  return SENSOR_OPTIONS.filter(opt => !existingSensorsInUnit.value.some(
    s => s.sensordescript === opt.label
  ))
})

const editAvailableSensorOptions = computed(() => {
  if (selectedNode.value?.type !== 'sensor') return SENSOR_OPTIONS
  const currentSensorId = selectedNode.value?.sensor_type
  return SENSOR_OPTIONS.filter(opt => {
    const existing = existingSensorsInUnit.value.find(
      s => s.sensordescript === opt.label
    )
    if (existing && existing.sensor_ID === currentSensorId) return true
    return !existing
  })
})

const binaryAddress = computed(() => {
  const x = formData.value.deviceCoordX ?? 0
  const y = formData.value.deviceCoordY ?? 0
  const addr = (x << 4) | y
  // 检查编辑时是否与其他设备地址冲突
  if (isEditing.value && selectedNode.value?.type === 'device') {
    formData.value._coordDuplicate = deviceOptions.value.some(
      d => d.DeviceAddress === addr && d.Device_ID !== selectedNode.value?.raw_id
    )
  }
  return addr.toString(2).padStart(8, '0')
})

const addCoordBinary = computed(() => {
  const x = addForm.value.coordX ?? 0
  const y = addForm.value.coordY ?? 0
  const addr = (x << 4) | y
  return addr.toString(2).padStart(8, '0')
})

const addCoordDuplicate = computed(() => {
  if (addTargetType.value !== 'device') return false
  const x = addForm.value.coordX ?? 0
  const y = addForm.value.coordY ?? 0
  const addr = (x << 4) | y
  return existingDevices.value.some(d => d.DeviceAddress === addr)
})

function getSensorId(unitId: number, sensorLabel: string) {
  const opt = SENSOR_OPTIONS.find(o => o.label === sensorLabel)
  return opt ? unitId + opt.offset : unitId
}

function findNodePath(nodes: TreeNode[], targetId: string, path: string[] = []): string[] | null {
  for (const node of nodes) {
    const nextPath = [...path, node.id]
    if (node.id === targetId) return nextPath
    const childPath = node.children ? findNodePath(node.children, targetId, nextPath) : null
    if (childPath) return childPath
  }
  return null
}

async function reloadTreeAndFocus(targetId?: string) {
  await loadTree()
  if (!targetId) return
  const path = findNodePath(treeData.value, targetId)
  if (!path) return
  expandedKeys.value = path.slice(0, -1)
  await nextTick()
  for (const key of expandedKeys.value) {
    treeRef.value?.getNode(key)?.expand()
  }
  treeRef.value?.setCurrentKey(targetId)
}

watch(filterText, (val) => {
  treeRef.value?.filter(val)
})

function filterNode(value: string, data: any) {
  if (!value) return true
  return data.label.toLowerCase().includes(value.toLowerCase())
}

async function loadTree() {
  try {
    const res = await getDeviceTreeApi()
    treeData.value = res.data || []
  } catch {
    ElMessage.error('加载设备树失败')
  }
}

async function loadModelOptions() {
  try {
    const res = await getModelListApi()
    modelOptions.value = res.data || []
  } catch {
    modelOptions.value = []
  }
}

async function loadDeviceOptions() {
  try {
    const res = await getDeviceListApi()
    deviceOptions.value = res.data || []
  } catch {
    deviceOptions.value = []
  }
}

async function loadUnitOptions() {
  try {
    const res = await getUnitListApi()
    unitOptions.value = res.data || []
  } catch {
    unitOptions.value = []
  }
}

async function handleNodeClick(node: TreeNode) {
  selectedNode.value = node
  isEditing.value = false
  try {
    if (node.type === 'model') {
      const res = await getModelApi(node.raw_id)
      formData.value = res.data || {}
    } else if (node.type === 'device') {
      const res = await getDeviceApi(node.raw_id)
      formData.value = res.data || {}
      const addr = formData.value.DeviceAddress || 0
      formData.value.deviceCoordX = (addr >> 4) & 0x0F
      formData.value.deviceCoordY = addr & 0x0F
    } else if (node.type === 'unit') {
      const res = await getUnitApi(node.raw_id)
      formData.value = res.data || {}
    } else if (node.type === 'sensor') {
      const res = await getSensorApi(node.raw_id)
      formData.value = res.data || {}
      const unitRowId = formData.value.unit_row_id
      if (unitRowId) {
        getSensorsByUnitApi(unitRowId).then(r => {
          existingSensorsInUnit.value = r.data || []
        }).catch(() => {
          existingSensorsInUnit.value = []
        })
      }
    }
    formSnapshot.value = JSON.parse(JSON.stringify(formData.value))
  } catch {
    ElMessage.error('获取详情失败')
  }
}

function startEdit() {
  formSnapshot.value = JSON.parse(JSON.stringify(formData.value))
  isEditing.value = true
}

function cancelEdit() {
  formData.value = JSON.parse(JSON.stringify(formSnapshot.value))
  isEditing.value = false
}

async function saveEdit() {
  if (!selectedNode.value) return
  const node = selectedNode.value
  try {
    if (node.type === 'model') {
      await updateModelApi(node.raw_id, {
        Modelname: formData.value.Modelname,
        Modeldescripte: formData.value.Modeldescripte,
        Notes: formData.value.Notes,
      })
    } else if (node.type === 'device') {
      const x = formData.value.deviceCoordX ?? 0
      const y = formData.value.deviceCoordY ?? 0
      await updateDeviceApi(node.raw_id, {
        Model_ID: formData.value.Model_ID,
        DeviceAddress: (x << 4) | y,
        Devicedescript: formData.value.Devicedescript,
        Notes: formData.value.Notes,
      })
    } else if (node.type === 'unit') {
      await updateUnitApi(node.raw_id, {
        Device_ID: formData.value.Device_ID,
        UnitDescript: formData.value.UnitDescript,
        Notes: formData.value.Notes,
      })
    } else if (node.type === 'sensor') {
      const selectedUnit = unitOptions.value.find(u => u.id === formData.value.unit_row_id)
      const sensorId = getSensorId(selectedUnit?.Unit_ID || formData.value.Unit_ID || 0, formData.value.sensordescript)
      await updateSensorApi(node.raw_id, {
        sensor_ID: sensorId,
        Device_ID: selectedUnit?.Device_ID || formData.value.Device_ID || node.device_id || 0,
        Unit_ID: selectedUnit?.Unit_ID || 0,
        unit_row_id: formData.value.unit_row_id,
        sensordescript: formData.value.sensordescript,
        Unit_address: formData.value.Unit_address,
        IsRead: formData.value.IsRead,
        Notes: formData.value.Notes,
      })
    }
    ElMessage.success('保存成功')
    isEditing.value = false
    formSnapshot.value = JSON.parse(JSON.stringify(formData.value))
    await reloadTreeAndFocus(node.id)
  } catch {
    ElMessage.error('保存失败')
  }
}

async function confirmDelete() {
  if (!selectedNode.value) return
  const node = selectedNode.value
  const labels: Record<string, string> = { model: '型号', device: '模块', unit: '机械臂', sensor: '传感器' }
  try {
    await ElMessageBox.confirm(`确定删除该${labels[node.type]}吗？`, '确认删除', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    if (node.type === 'model') {
      await deleteModelApi(node.raw_id)
    } else if (node.type === 'device') {
      await deleteDeviceApi(node.raw_id)
    } else if (node.type === 'unit') {
      await deleteUnitApi(node.raw_id)
    } else if (node.type === 'sensor') {
      await deleteSensorApi(node.raw_id)
    }
    ElMessage.success('删除成功')
    selectedNode.value = null
    formData.value = {}
    isEditing.value = false
    await loadTree()
  } catch {
    ElMessage.error('删除失败')
  }
}

function handleAddModel() {
  ElMessageBox.prompt('请输入型号名称', '新增型号', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    inputPattern: /\S+/,
    inputErrorMessage: '型号名称不能为空',
  }).then(async ({ value }) => {
    try {
      await createModelApi({ Modelname: value })
      ElMessage.success('新增型号成功')
      await loadTree()
    } catch {
      ElMessage.error('新增型号失败')
    }
  }).catch(() => {})
}

function showAddDialog(type: 'device' | 'unit' | 'sensor') {
  addTargetType.value = type
  const titles: Record<string, string> = { device: '新增模块', unit: '新增机械臂', sensor: '新增传感器' }
  addDialogTitle.value = titles[type]
  addForm.value = {}
  if (type === 'device') {
    addForm.value.coordX = 1
    addForm.value.coordY = 1
    const modelId = selectedNode.value?.raw_id
    if (modelId) {
      getDevicesByModelApi(modelId).then(res => {
        existingDevices.value = res.data || []
      }).catch(() => {
        existingDevices.value = []
      })
    } else {
      existingDevices.value = []
    }
  } else if (type === 'unit') {
    addForm.value.Unit_ID = availableArmOptions.value.length > 0 ? availableArmOptions.value[0].value : null
    getUnitListApi().then(res => {
      allUnits.value = res.data || []
    }).catch(() => {
      allUnits.value = []
    })
    addForm.value.UnitDescript = ''
  } else if (type === 'sensor') {
    const unitRowId = selectedNode.value?.raw_id ?? 0
    getSensorsByUnitApi(unitRowId).then(res => {
      existingSensorsInUnit.value = res.data || []
    }).catch(() => {
      existingSensorsInUnit.value = []
    })
    addForm.value.sensordescript = ''
    addForm.value.Unit_address = 0
    addForm.value.IsRead = 1
    addForm.value.unit_row_id = unitRowId
    addForm.value.Unit_ID = (selectedNode.value as any)?.arm_type || 0
    addForm.value.Device_ID = (selectedNode.value as any)?.device_id || 0
  }
  addDialogVisible.value = true
}

function onSensorNameChange(label: string) {
  const opt = SENSOR_OPTIONS.find(o => o.label === label)
  if (opt) {
    addForm.value.Unit_address = opt.Unit_address
  }
}

function onEditSensorNameChange(label: string) {
  const opt = SENSOR_OPTIONS.find(o => o.label === label)
  if (opt) {
    formData.value.Unit_address = opt.Unit_address
  }
}

async function submitAdd() {
  if (!selectedNode.value) return
  const parent = selectedNode.value
  let focusId = parent.id
  try {
    if (addTargetType.value === 'device') {
      const x = addForm.value.coordX ?? 1
      const y = addForm.value.coordY ?? 1
      const res = await createDeviceApi({
        Model_ID: parent.raw_id,
        DeviceAddress: (x << 4) | y,
        Devicedescript: addForm.value.Devicedescript || '',
      })
      focusId = `device-${res.data.Device_ID}`
    } else if (addTargetType.value === 'unit') {
      const armName = ARM_OPTIONS.find(o => o.value === addForm.value.Unit_ID)?.label || ''
      const res = await createUnitApi({
        Unit_ID: addForm.value.Unit_ID,
        Device_ID: parent.raw_id,
        UnitDescript: armName,
      })
      focusId = `unit-${res.data.id}`
    } else if (addTargetType.value === 'sensor') {
      const sensorId = getSensorId(addForm.value.Unit_ID, addForm.value.sensordescript)
      const res = await createSensorApi({
        sensor_ID: sensorId,
        Device_ID: addForm.value.Device_ID,
        Unit_ID: addForm.value.Unit_ID,
        unit_row_id: addForm.value.unit_row_id,
        sensordescript: addForm.value.sensordescript || '',
        Unit_address: addForm.value.Unit_address ?? 0,
        IsRead: addForm.value.IsRead ?? 1,
      })
      focusId = `sensor-${res.data.id}`
    }
    ElMessage.success('新增成功')
    addDialogVisible.value = false
    await reloadTreeAndFocus(focusId)
  } catch {
    ElMessage.error('新增失败')
  }
}

onMounted(async () => {
  await loadTree()
  loadModelOptions()
  loadDeviceOptions()
  loadUnitOptions()
})
</script>

<style scoped>
.hardwork-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 16px;
  background: #f5f7fa;
}

.page-header {
  margin-bottom: 16px;
}
.page-header h2 {
  margin: 0;
  font-size: 20px;
  color: #303133;
}

.page-body {
  flex: 1;
  display: flex;
  gap: 16px;
  overflow: hidden;
}

.tree-panel {
  width: 300px;
  min-width: 280px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  padding: 12px;
  overflow: auto;
}

.tree-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.tree-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.tree-filter {
  margin-bottom: 8px;
}

.tree-node-label {
  display: inline-block;
  min-width: 0;
  cursor: default;
  user-select: none;
}

.form-panel {
  flex: 1;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  padding: 16px;
  overflow: auto;
}

.placeholder {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 200px;
  color: #909399;
  font-size: 14px;
}

.form-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #ebeef5;
}

.form-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.form-actions {
  display: flex;
  gap: 6px;
}

.detail-el-form {
  max-width: 600px;
}
</style>
