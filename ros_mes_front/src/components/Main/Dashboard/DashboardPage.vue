<template>
  <div class="dashboard-container mes-page">
    <!-- 欢迎横幅 -->
    <div class="welcome-banner">
      <div class="welcome-left">
        <h1 class="welcome-title">
          {{ greeting }}，{{ userStore.nickname || userStore.account || '操作员' }}
        </h1>
        <p class="welcome-sub">{{ todayText }} · 系统运行概览</p>
      </div>
      <div class="welcome-deco">
        <svg viewBox="0 0 24 24" width="72" height="72" fill="none" stroke="rgba(255,255,255,0.9)" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="4" y="9" width="16" height="11" rx="2"/>
          <circle cx="9" cy="14.5" r="1.4" fill="rgba(255,255,255,0.9)" stroke="none"/>
          <circle cx="15" cy="14.5" r="1.4" fill="rgba(255,255,255,0.9)" stroke="none"/>
          <path d="M12 9V5"/>
          <circle cx="12" cy="3.6" r="1.4"/>
        </svg>
      </div>
    </div>

    <div class="stats-grid">
      <div
        v-for="card in statCards"
        :key="card.key"
        class="stat-card"
        :style="{ '--card-accent': card.color }"
      >
        <div class="card-icon-wrapper">
          <el-icon :size="24"><component :is="card.icon" /></el-icon>
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
          <span class="trend-chip" :class="card.trend >= 0 ? 'trend-up' : 'trend-down'">
            <el-icon :size="12">
              <Top v-if="card.trend > 0" />
              <Bottom v-else-if="card.trend < 0" />
              <Minus v-else />
            </el-icon>
            {{ Math.abs(card.trend) }}%
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
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
import { useUserStore } from '@/stores/user'
import type { DashboardStats, DashboardStatItem } from '@/api/types'

const loading = ref(true)
const userStore = useUserStore()

const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return '夜深了'
  if (hour < 12) return '早上好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
})

const todayText = computed(() => {
  const now = new Date()
  const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  return `${now.getFullYear()} 年 ${now.getMonth() + 1} 月 ${now.getDate()} 日 ${weekdays[now.getDay()]}`
})

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
  { key: 'deviceStatus', icon: Monitor, color: '#2563eb' },
  { key: 'taskCount', icon: List, color: '#16a34a' },
  { key: 'faultCount', icon: WarningFilled, color: '#dc2626' },
  { key: 'onlineUsers', icon: User, color: '#d97706' },
  { key: 'responseTime', icon: Timer, color: '#7c3aed' },
  { key: 'concurrency', icon: Connection, color: '#0891b2' },
  { key: 'deviceConnections', icon: Link, color: '#0d9488' },
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
/* ===== 欢迎横幅 ===== */
.welcome-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-radius: var(--mes-radius-lg);
  padding: 26px 32px;
  margin-bottom: 20px;
  color: #fff;
  background:
    radial-gradient(ellipse 70% 120% at 85% 20%, rgba(96, 165, 250, 0.35), transparent),
    linear-gradient(120deg, #1e3a8a 0%, #1d4ed8 55%, #2563eb 100%);
  box-shadow: 0 8px 24px rgba(29, 78, 216, 0.25);
  overflow: hidden;
}

.welcome-title {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.welcome-sub {
  margin: 8px 0 0;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.75);
  letter-spacing: 0.5px;
}

.welcome-deco {
  opacity: 0.9;
  flex-shrink: 0;
}

/* ===== 统计卡片 ===== */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.stat-card {
  position: relative;
  display: flex;
  align-items: center;
  gap: 16px;
  background: #fff;
  border-radius: var(--mes-radius-lg);
  border: 1px solid var(--mes-border-light);
  padding: 20px 22px;
  box-shadow: var(--mes-shadow-card);
  transition: box-shadow 0.25s, transform 0.25s;
  overflow: hidden;
}

/* 顶部彩色光条 */
.stat-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--card-accent), transparent 70%);
  opacity: 0.9;
}

.stat-card:hover {
  box-shadow: var(--mes-shadow-hover);
  transform: translateY(-3px);
}

.card-icon-wrapper {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 12px;
  color: var(--card-accent);
  background: color-mix(in srgb, var(--card-accent) 10%, transparent);
}

.card-body {
  flex: 1;
  min-width: 0;
}

.card-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--mes-text-title);
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-unit {
  font-size: 13px;
  font-weight: 400;
  color: var(--mes-text-faint);
  margin-left: 2px;
}

.card-label {
  margin-top: 4px;
  font-size: 13px;
  color: var(--mes-text-sub);
}

.card-trend {
  position: absolute;
  top: 14px;
  right: 14px;
}

.trend-chip {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 12px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
}

.trend-up {
  color: #16a34a;
  background: rgba(22, 163, 74, 0.1);
}

.trend-down {
  color: #dc2626;
  background: rgba(220, 38, 38, 0.1);
}

.skeleton {
  display: inline-block;
  width: 80px;
  height: 26px;
  background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%);
  background-size: 200% 100%;
  border-radius: 6px;
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
