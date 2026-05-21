<template>
  <div class="dashboard-container">
    <div class="page-header">
      <h1 class="page-title">首页仪表盘</h1>
      <p class="page-subtitle">系统运行概览</p>
    </div>

    <div class="stats-grid">
      <div
        v-for="card in statCards"
        :key="card.key"
        class="stat-card"
        :style="{ '--card-accent': card.color }"
      >
        <div class="card-icon-wrapper">
          <el-icon :size="28"><component :is="card.icon" /></el-icon>
        </div>
        <div class="card-body">
          <div class="card-value" :class="{ 'loading': loading }">
            <template v-if="loading">
              <span class="skeleton">&nbsp;</span>
            </template>
            <template v-else>
              {{ card.value }}<span v-if="card.unit" class="card-unit">{{ card.unit }}</span>
            </template>
          </div>
          <div class="card-label">{{ card.label }}</div>
        </div>
        <div class="card-trend" v-if="!loading && card.trend !== undefined">
          <el-icon :size="14">
            <Top v-if="card.trend > 0" />
            <Bottom v-else-if="card.trend < 0" />
            <Minus v-else />
          </el-icon>
          <span :class="card.trend >= 0 ? 'trend-up' : 'trend-down'">
            {{ Math.abs(card.trend) }}%
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Monitor,
  List,
  WarningFilled,
  User,
  Timer,
  Connection,
  Link,
  Top,
  Bottom,
  Minus,
} from '@element-plus/icons-vue'
import { getDashboardStats } from '@/api/rosApi'
import { useMock, mockSuccess } from '@/api/mock'
import type { DashboardStats, DashboardStatItem } from '@/api/types'

const loading = ref(true)

interface StatCard {
  key: string
  label: string
  value: string | number
  unit?: string
  icon: any
  color: string
  trend?: number
}

const cardMeta: { key: string; icon: any; color: string }[] = [
  { key: 'deviceStatus', icon: Monitor, color: '#409eff' },
  { key: 'taskCount', icon: List, color: '#67c23a' },
  { key: 'faultCount', icon: WarningFilled, color: '#f56c6c' },
  { key: 'onlineUsers', icon: User, color: '#e6a23c' },
  { key: 'responseTime', icon: Timer, color: '#909399' },
  { key: 'concurrency', icon: Connection, color: '#b37feb' },
  { key: 'deviceConnections', icon: Link, color: '#36cfc9' },
]

const statCards = reactive<StatCard[]>(
  cardMeta.map((m) => ({
    key: m.key,
    label: '',
    value: '---',
    unit: '',
    icon: m.icon,
    color: m.color,
    trend: 0,
  }))
)

const mockDashboardStats = (): Promise<{ code: number; message: string; data: DashboardStats }> => {
  return mockSuccess({
    deviceStatus: { label: '设备状态', value: '正常运行', unit: '', trend: 0 },
    taskCount: { label: '任务数', value: 128, unit: '', trend: 12 },
    faultCount: { label: '故障数', value: 3, unit: '', trend: -25 },
    onlineUsers: { label: '在线用户', value: 12, unit: '', trend: 8 },
    responseTime: { label: '响应时间', value: 23, unit: 'ms', trend: -5 },
    concurrency: { label: '并发', value: 156, unit: '', trend: 15 },
    deviceConnections: { label: '设备连接数', value: 45, unit: '', trend: 6 },
  })
}

const fetchDashboardData = async () => {
  loading.value = true

  try {
    let res: any

    if (useMock) {
      res = await mockDashboardStats()
    } else {
      res = await getDashboardStats()
    }

    const data: DashboardStats = res.code === 200 ? res.data : res

    statCards.forEach((card) => {
      const item: DashboardStatItem | undefined = (data as any)[card.key]
      if (item) {
        card.label = item.label
        card.value = item.value
        card.unit = item.unit
        card.trend = item.trend
      }
    })
  } catch (error: any) {
    const errMsg = error?.message || '获取仪表盘数据失败'
    ElMessage.error(errMsg)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchDashboardData()
})
</script>

<style scoped>
.dashboard-container {
  padding: 24px;
}

.page-header {
  margin-bottom: 28px;
}

.page-title {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #303133;
  letter-spacing: 0;
}

.page-subtitle {
  margin: 4px 0 0;
  font-size: 14px;
  color: #909399;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}

.stat-card {
  position: relative;
  display: flex;
  align-items: center;
  gap: 16px;
  background: #fff;
  border-radius: 8px;
  padding: 20px 24px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  border-left: 4px solid var(--card-accent);
  transition: box-shadow 0.25s, transform 0.25s;
  overflow: hidden;
}

.stat-card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.card-icon-wrapper {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 52px;
  height: 52px;
  border-radius: 10px;
  color: var(--card-accent);
  background: color-mix(in srgb, var(--card-accent) 10%, transparent);
}

.card-body {
  flex: 1;
  min-width: 0;
}

.card-value {
  font-size: 26px;
  font-weight: 700;
  color: #303133;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}

.card-unit {
  font-size: 14px;
  font-weight: 400;
  color: #909399;
  margin-left: 2px;
}

.card-label {
  margin-top: 4px;
  font-size: 13px;
  color: #909399;
}

.card-trend {
  position: absolute;
  top: 12px;
  right: 16px;
  display: flex;
  align-items: center;
  gap: 2px;
  font-size: 12px;
  font-weight: 500;
}

.trend-up {
  color: #67c23a;
}

.trend-down {
  color: #f56c6c;
}

.skeleton {
  display: inline-block;
  width: 80px;
  height: 28px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  border-radius: 4px;
  animation: shimmer 1.5s ease-in-out infinite;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 900px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 600px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
