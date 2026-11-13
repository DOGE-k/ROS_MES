import { defineStore } from 'pinia';
import { computed, ref } from 'vue';

// 会话保持是前端偏好：不写入后端连接配置，避免开关一开就把现有会话作废。
export const SESSION_TTL_OPTIONS = [
  { minutes: 15, label: '15 分钟' },
  { minutes: 30, label: '30 分钟' },
  { minutes: 60, label: '60 分钟' },
  { minutes: 0, label: '不限时' },
] as const;

const SETTINGS_KEY = 'mes.finetuning.session.settings';
const SNAPSHOT_PREFIX = 'mes.finetuning.session.snapshot.';
const DEFAULT_TTL_MINUTES = 30;

interface StoredSettings {
  enabled: boolean;
  ttlMinutes: number;
}

const readSettings = (): StoredSettings => {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (!raw) return { enabled: false, ttlMinutes: DEFAULT_TTL_MINUTES };
    const parsed = JSON.parse(raw) as Partial<StoredSettings>;
    const minutes = Number(parsed?.ttlMinutes);
    return {
      enabled: Boolean(parsed?.enabled),
      ttlMinutes: SESSION_TTL_OPTIONS.some((item) => item.minutes === minutes)
        ? minutes
        : DEFAULT_TTL_MINUTES,
    };
  } catch {
    return { enabled: false, ttlMinutes: DEFAULT_TTL_MINUTES };
  }
};

export const useFineTuningSessionStore = defineStore('fineTuningSession', () => {
  const initial = readSettings();
  const enabled = ref(initial.enabled);
  const ttlMinutes = ref(initial.ttlMinutes);
  // null 表示不限时；后端按本次请求传入的秒数判定有效期。
  const ttlSeconds = computed<number | null>(() =>
    ttlMinutes.value > 0 ? ttlMinutes.value * 60 : null,
  );

  const persist = () => {
    try {
      localStorage.setItem(
        SETTINGS_KEY,
        JSON.stringify({ enabled: enabled.value, ttlMinutes: ttlMinutes.value }),
      );
    } catch {
      /* 隐私模式下写入失败只影响下次默认值，不阻断页面 */
    }
  };

  const setEnabled = (value: boolean) => {
    enabled.value = Boolean(value);
    persist();
  };

  const setTtlMinutes = (value: number) => {
    const minutes = Number(value);
    if (!SESSION_TTL_OPTIONS.some((item) => item.minutes === minutes)) return;
    ttlMinutes.value = minutes;
    persist();
  };

  // 各臂的输入值、点云与回执记录只在本机缓存；跨端只恢复模块与工程臂绑定。
  const saveSnapshot = (sessionId: string, data: unknown) => {
    if (!sessionId) return;
    try {
      sessionStorage.setItem(`${SNAPSHOT_PREFIX}${sessionId}`, JSON.stringify(data));
    } catch {
      /* 快照超限或隐私模式：续接时退回最小恢复，不影响会话有效性 */
    }
  };

  const loadSnapshot = <T>(sessionId: string): T | null => {
    if (!sessionId) return null;
    try {
      const raw = sessionStorage.getItem(`${SNAPSHOT_PREFIX}${sessionId}`);
      return raw ? (JSON.parse(raw) as T) : null;
    } catch {
      return null;
    }
  };

  const clearSnapshot = (sessionId?: string) => {
    try {
      if (sessionId) {
        sessionStorage.removeItem(`${SNAPSHOT_PREFIX}${sessionId}`);
        return;
      }
      const keys: string[] = [];
      for (let index = 0; index < sessionStorage.length; index += 1) {
        const key = sessionStorage.key(index);
        if (key && key.startsWith(SNAPSHOT_PREFIX)) keys.push(key);
      }
      keys.forEach((key) => sessionStorage.removeItem(key));
    } catch {
      /* 清理失败不阻断流程 */
    }
  };

  return {
    enabled,
    ttlMinutes,
    ttlSeconds,
    setEnabled,
    setTtlMinutes,
    saveSnapshot,
    loadSnapshot,
    clearSnapshot,
  };
});
