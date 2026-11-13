export const DRAWING_BASELINE_STABLE_MS = 10000;
export const DRAWING_BASELINE_MAX_SAMPLE_GAP_MS = 3000;
export const DRAWING_BASELINE_TOLERANCE = 0.01;
const FLOAT_EPSILON = 1e-9;

export interface DrawingBaselineMetadata {
  generation: string;
  unitId: number;
  seg: number;
  connectionRevision: number | null;
  drawingId: number | null;
  drawingSource: string;
}

export interface DrawingPositionSample {
  position: number;
  receivedAt: number;
}

export interface DrawingBaselineState extends DrawingBaselineMetadata {
  status: 'waiting_motion' | 'settling' | 'locked' | 'failed';
  confirmed: boolean;
  motionObserved: boolean;
  samples: Array<DrawingPositionSample | null>;
  values: number[] | null;
  stableSince: number | null;
  origins: Array<number | null>;
  windowMin: number[] | null;
  windowMax: number[] | null;
}

const finiteNumber = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const validTime = (now: number) => finiteNumber(now) && now >= 0;

export function createDrawingBaseline(
  metadata: DrawingBaselineMetadata,
  seedPositions: ReadonlyArray<number | null> = [],
): DrawingBaselineState {
  return {
    ...metadata,
    status: 'waiting_motion',
    confirmed: false,
    motionObserved: false,
    samples: [null, null, null],
    values: null,
    stableSince: null,
    origins: [0, 1, 2].map(index => finiteNumber(seedPositions[index]) ? seedPositions[index]! : null),
    windowMin: null,
    windowMax: null,
  };
}

function resetWindow(state: DrawingBaselineState) {
  state.stableSince = null;
  state.windowMin = null;
  state.windowMax = null;
  state.status = state.motionObserved ? 'settling' : 'waiting_motion';
}

function freshSamples(state: DrawingBaselineState, now: number) {
  return state.samples.every(sample => sample !== null &&
    now >= sample.receivedAt && now - sample.receivedAt <= DRAWING_BASELINE_MAX_SAMPLE_GAP_MS);
}

function startWindow(state: DrawingBaselineState, positions: number[], now: number) {
  state.status = 'settling';
  state.stableSince = now;
  state.windowMin = [...positions];
  state.windowMax = [...positions];
}

export function tickDrawingBaseline(state: DrawingBaselineState, now: number): void {
  if (state.status === 'locked' || state.status === 'failed') return;
  if (!validTime(now) || !state.motionObserved || !freshSamples(state, now)) {
    resetWindow(state);
    return;
  }
  const positions = state.samples.map(sample => sample!.position);
  if (state.stableSince === null || state.windowMin === null || state.windowMax === null) {
    startWindow(state, positions, now);
  } else {
    for (let index = 0; index < 3; index++) {
      state.windowMin[index] = Math.min(state.windowMin[index]!, positions[index]!);
      state.windowMax[index] = Math.max(state.windowMax[index]!, positions[index]!);
    }
    const moved = positions.some((_, index) =>
      state.windowMax![index]! - state.windowMin![index]! > DRAWING_BASELINE_TOLERANCE + FLOAT_EPSILON);
    if (moved) startWindow(state, positions, now);
  }
  const windowEnd = state.stableSince! + DRAWING_BASELINE_STABLE_MS;
  const completeWindow = state.samples.every(sample => sample!.receivedAt >= windowEnd);
  if (state.confirmed && now >= windowEnd && completeWindow) {
    state.values = [...positions];
    state.status = 'locked';
  }
}

export function observeDrawingPosition(
  state: DrawingBaselineState,
  index: number,
  value: unknown,
  now: number,
): void {
  if (!Number.isInteger(index) || index < 0 || index > 2 || !validTime(now)) {
    interruptDrawingBaseline(state);
    return;
  }
  if (!finiteNumber(value)) {
    state.samples[index] = null;
    if (state.status !== 'locked' && state.status !== 'failed') resetWindow(state);
    return;
  }
  if (state.status !== 'locked' && state.status !== 'failed' && !freshSamples(state, now)) resetWindow(state);
  state.samples[index] = { position: value, receivedAt: now };
  if (state.status === 'locked' || state.status === 'failed') return;
  const origin = state.origins[index];
  if (origin === null) state.origins[index] = value;
  else if (Math.abs(value - origin!) > DRAWING_BASELINE_TOLERANCE + FLOAT_EPSILON) state.motionObserved = true;
  tickDrawingBaseline(state, now);
}

export function observeDrawingRunning(state: DrawingBaselineState, now: number): void {
  if (state.status === 'locked' || state.status === 'failed') return;
  if (!validTime(now)) {
    interruptDrawingBaseline(state);
    return;
  }
  state.motionObserved = true;
  resetWindow(state);
  tickDrawingBaseline(state, now);
}

export function confirmDrawingBaseline(state: DrawingBaselineState, now: number): void {
  if (state.status === 'failed') return;
  state.confirmed = true;
  tickDrawingBaseline(state, now);
}

export function interruptDrawingBaseline(state: DrawingBaselineState): void {
  state.samples = [null, null, null];
  if (state.status !== 'locked' && state.status !== 'failed') resetWindow(state);
}

export function restoreDrawingBaseline(raw: unknown): DrawingBaselineState | null {
  if (!raw || typeof raw !== 'object') return null;
  const value = raw as Record<string, unknown>;
  if (typeof value.generation !== 'string' || !value.generation ||
    !Number.isInteger(value.unitId) || Number(value.unitId) <= 0 ||
    !Number.isInteger(value.seg) || Number(value.seg) < 0 || Number(value.seg) > 14 ||
    (value.connectionRevision !== null && (!Number.isInteger(value.connectionRevision) || Number(value.connectionRevision) < 0)) ||
    (value.drawingId !== null && (!Number.isInteger(value.drawingId) || Number(value.drawingId) <= 0)) ||
    typeof value.drawingSource !== 'string' || !value.drawingSource) return null;
  const origins = Array.isArray(value.origins)
    ? value.origins.map(position => finiteNumber(position) ? position : null) : [];
  const state = createDrawingBaseline({
    generation: value.generation,
    unitId: Number(value.unitId),
    seg: Number(value.seg),
    connectionRevision: value.connectionRevision as number | null,
    drawingId: value.drawingId as number | null,
    drawingSource: value.drawingSource,
  }, origins);
  state.confirmed = value.confirmed === true;
  state.motionObserved = value.motionObserved === true;
  if (value.status === 'locked' && Array.isArray(value.values) && value.values.length === 3 && value.values.every(finiteNumber)) {
    state.status = 'locked';
    state.values = [...value.values];
    state.confirmed = true;
    state.motionObserved = true;
  } else if (value.status === 'failed') state.status = 'failed';
  else resetWindow(state);
  return state;
}
