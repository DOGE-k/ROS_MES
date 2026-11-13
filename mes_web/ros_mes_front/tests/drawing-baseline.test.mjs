import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import test from 'node:test';
import ts from 'typescript';

const source = fs.readFileSync(new URL('../src/api/drawingBaseline.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const module = { exports: {} };
vm.runInNewContext(compiled, { module, exports: module.exports });
const {
  createDrawingBaseline, observeDrawingPosition, observeDrawingRunning,
  confirmDrawingBaseline, tickDrawingBaseline, interruptDrawingBaseline, restoreDrawingBaseline,
} = module.exports;

const metadata = () => ({
  generation: 'drawing-1', unitId: 32, seg: 0, connectionRevision: 2,
  drawingId: 7, drawingSource: 'database',
});
const sampleAll = (state, positions, now) => positions.forEach((value, index) => observeDrawingPosition(state, index, value, now));
const sampleUntil = (state, positions, from, until) => {
  for (let now = from; now <= until; now += 1000) sampleAll(state, positions, now);
};
const movingState = () => {
  const state = createDrawingBaseline(metadata(), [0, 0, 0]);
  confirmDrawingBaseline(state, 0);
  sampleAll(state, [1, 2, 3], 0);
  return state;
};

test('a drawing baseline requires movement and ten seconds of fresh stable samples', () => {
  const state = movingState();
  assert.equal(state.motionObserved, true);
  assert.equal(state.status, 'settling');
  assert.equal(state.stableSince, 0);
  sampleUntil(state, [1, 2, 3], 1000, 9000);
  tickDrawingBaseline(state, 9999);
  assert.equal(state.values, null);
  sampleAll(state, [1, 2, 3], 10000);
  assert.equal(state.status, 'locked');
  assert.deepEqual(Array.from(state.values), [1, 2, 3]);
});

test('seeds detect movement while all three post-dispatch samples are still required', () => {
  const state = createDrawingBaseline(metadata(), [10, 20, 30]);
  confirmDrawingBaseline(state, 0);
  assert.deepEqual(Array.from(state.samples), [null, null, null]);
  observeDrawingPosition(state, 0, 10.02, 0);
  assert.equal(state.motionObserved, true);
  assert.equal(state.stableSince, null);
  sampleUntil(state, [10.02, 20, 30], 1000, 10000);
  assert.equal(state.values, null);
  sampleAll(state, [10.02, 20, 30], 11000);
  assert.equal(state.status, 'locked');
});

test('unchanged positions and movements within resolution keep waiting for movement', () => {
  const state = createDrawingBaseline(metadata(), [0, 0, 0]);
  confirmDrawingBaseline(state, 0);
  sampleUntil(state, [0, 0, 0], 0, 12000);
  sampleAll(state, [0.005, 0, 0], 13000);
  sampleAll(state, [0.01000000000001, 0, 0], 14000);
  assert.equal(state.status, 'waiting_motion');
  assert.equal(state.motionObserved, false);
  assert.equal(state.values, null);
  sampleAll(state, [0.0101, 0, 0], 15000);
  assert.equal(state.motionObserved, true);
  assert.equal(state.stableSince, 15000);
});

test('a running event establishes movement and repeated running restarts the stable window', () => {
  const state = createDrawingBaseline(metadata());
  confirmDrawingBaseline(state, 0);
  sampleAll(state, [5, 6, 7], 0);
  observeDrawingRunning(state, 0);
  sampleUntil(state, [5, 6, 7], 1000, 2000);
  observeDrawingRunning(state, 2000);
  sampleUntil(state, [5, 6, 7], 3000, 11000);
  assert.equal(state.status, 'settling');
  sampleAll(state, [5, 6, 7], 12000);
  assert.equal(state.status, 'locked');
});

test('jitter within a whole-window range of 0.01 permits locking', () => {
  const state = createDrawingBaseline(metadata(), [0, 0, 0]);
  confirmDrawingBaseline(state, 0);
  for (let now = 0; now <= 10000; now += 1000) {
    sampleAll(state, [now % 2000 === 0 ? 0.02 : 0.03, 1, 2], now);
  }
  assert.equal(state.status, 'locked');
});

test('small per-frame drift beyond the whole-window range restarts observation', () => {
  const state = createDrawingBaseline(metadata(), [0, 0, 0]);
  confirmDrawingBaseline(state, 0);
  for (let now = 0; now <= 20000; now += 1000) sampleAll(state, [1 + now / 1000 * 0.009, 2, 3], now);
  assert.equal(state.status, 'settling');
  assert.equal(state.values, null);
  assert.equal(state.stableSince, 20000);
  sampleUntil(state, [1.18, 2, 3], 21000, 30000);
  assert.equal(state.status, 'locked');
});

test('movement of any axis resets the common ten-second window', () => {
  const state = movingState();
  sampleUntil(state, [1, 2, 3], 1000, 9000);
  sampleAll(state, [1, 2, 3.02], 10000);
  assert.equal(state.stableSince, 10000);
  sampleUntil(state, [1, 2, 3.02], 11000, 19000);
  assert.equal(state.values, null);
  sampleAll(state, [1, 2, 3.02], 20000);
  assert.equal(state.status, 'locked');
});

test('a timer without continuing telemetry cannot freeze the previous samples', () => {
  const state = movingState();
  tickDrawingBaseline(state, 10000);
  assert.equal(state.status, 'settling');
  assert.equal(state.stableSince, null);
  assert.equal(state.values, null);
});

test('all three axes must supply a sample covering the end of the ten-second window', () => {
  const state = movingState();
  sampleUntil(state, [1, 2, 3], 1000, 9000);
  tickDrawingBaseline(state, 10000);
  observeDrawingPosition(state, 0, 1, 10000);
  observeDrawingPosition(state, 1, 2, 10000);
  assert.equal(state.values, null);
  observeDrawingPosition(state, 2, 3, 10000);
  assert.equal(state.status, 'locked');
});

test('a gap over three seconds requires a new full stable window', () => {
  const state = movingState();
  sampleUntil(state, [1, 2, 3], 1000, 4000);
  sampleAll(state, [1, 2, 3], 7501);
  assert.equal(state.stableSince, 7501);
  sampleUntil(state, [1, 2, 3], 8501, 16501);
  sampleAll(state, [1, 2, 3], 17500);
  assert.equal(state.values, null);
  sampleAll(state, [1, 2, 3], 17501);
  assert.equal(state.status, 'locked');
});

test('one missing axis interrupts the common window despite other axes continuing', () => {
  const state = movingState();
  for (let now = 1000; now <= 12000; now += 1000) {
    observeDrawingPosition(state, 0, 1, now);
    observeDrawingPosition(state, 1, 2, now);
    tickDrawingBaseline(state, now);
  }
  assert.equal(state.stableSince, null);
  assert.equal(state.values, null);
});

test('invalid samples interrupt collection and never become fabricated zero positions', () => {
  for (const invalid of [null, undefined, NaN, Infinity, -Infinity, '', '3', false]) {
    const state = movingState();
    sampleUntil(state, [1, 2, 3], 1000, 9000);
    observeDrawingPosition(state, 2, invalid, 9500);
    assert.equal(state.samples[2], null);
    assert.equal(state.stableSince, null);
    tickDrawingBaseline(state, 10000);
    assert.equal(state.values, null);
    sampleUntil(state, [1, 2, 3], 10000, 19000);
    assert.equal(state.values, null);
    sampleAll(state, [1, 2, 3], 20000);
    assert.equal(state.status, 'locked');
  }
});

test('a disconnect keeps observed movement but discards the incomplete window', () => {
  const state = movingState();
  sampleUntil(state, [1, 2, 3], 1000, 9000);
  interruptDrawingBaseline(state);
  assert.equal(state.motionObserved, true);
  assert.deepEqual(Array.from(state.samples), [null, null, null]);
  tickDrawingBaseline(state, 20000);
  assert.equal(state.values, null);
  sampleUntil(state, [1, 2, 3], 20000, 30000);
  assert.equal(state.status, 'locked');
});

test('samples and stability collected during HTTP sending are kept until confirmation', () => {
  const state = createDrawingBaseline(metadata(), [0, 0, 0]);
  sampleUntil(state, [1, 2, 3], 0, 12000);
  assert.equal(state.confirmed, false);
  assert.equal(state.status, 'settling');
  assert.equal(state.values, null);
  assert.equal(state.stableSince, 0);
  confirmDrawingBaseline(state, 12000);
  assert.equal(state.status, 'locked');
  assert.deepEqual(Array.from(state.values), [1, 2, 3]);
});

test('post-dispatch failure prevents later samples or confirmation from locking', () => {
  const state = movingState();
  state.status = 'failed';
  state.values = null;
  sampleUntil(state, [1, 2, 3], 1000, 15000);
  confirmDrawingBaseline(state, 15000);
  assert.equal(state.status, 'failed');
  assert.equal(state.values, null);
});

test('a fixed baseline survives subsequent fine-tuning while new raw samples remain available', () => {
  const state = movingState();
  sampleUntil(state, [1, 2, 3], 1000, 10000);
  const fixed = state.values;
  sampleAll(state, [11, -2, 4.5], 12000);
  observeDrawingRunning(state, 12000);
  tickDrawingBaseline(state, 20000);
  assert.equal(state.status, 'locked');
  assert.equal(state.values, fixed);
  assert.deepEqual(Array.from(state.values), [1, 2, 3]);
  assert.deepEqual(Array.from(state.samples, sample => sample.position), [11, -2, 4.5]);
  observeDrawingPosition(state, 1, null, 21000);
  interruptDrawingBaseline(state);
  assert.equal(state.status, 'locked');
  assert.equal(state.values, fixed);
});

test('restoring fixed values discards old browser timestamps and retains metadata', () => {
  const state = movingState();
  sampleUntil(state, [1, 2, 3], 1000, 10000);
  const restored = restoreDrawingBaseline(JSON.parse(JSON.stringify(state)));
  assert.equal(restored.status, 'locked');
  assert.deepEqual(Array.from(restored.values), [1, 2, 3]);
  assert.deepEqual(Array.from(restored.samples), [null, null, null]);
  assert.equal(restored.stableSince, null);
  assert.equal(restored.generation, 'drawing-1');
  assert.equal(restored.connectionRevision, 2);
});

test('restoring an unfinished window retains movement and restarts ten seconds on new samples', () => {
  const state = movingState();
  sampleUntil(state, [1, 2, 3], 1000, 9000);
  const restored = restoreDrawingBaseline(JSON.parse(JSON.stringify(state)));
  assert.equal(restored.motionObserved, true);
  assert.equal(restored.confirmed, true);
  assert.equal(restored.status, 'settling');
  assert.equal(restored.stableSince, null);
  assert.deepEqual(Array.from(restored.samples), [null, null, null]);
  tickDrawingBaseline(restored, 50000);
  assert.equal(restored.values, null);
  sampleUntil(restored, [1, 2, 3], 0, 9000);
  assert.equal(restored.values, null);
  sampleAll(restored, [1, 2, 3], 10000);
  assert.equal(restored.status, 'locked');
});

test('restoring before movement retains valid origins without reusing old samples', () => {
  const state = createDrawingBaseline(metadata(), [10, 20, 30]);
  confirmDrawingBaseline(state, 9000);
  const restored = restoreDrawingBaseline(JSON.parse(JSON.stringify(state)));
  assert.equal(restored.motionObserved, false);
  assert.deepEqual(Array.from(restored.samples), [null, null, null]);
  sampleAll(restored, [11, 20, 30], 0);
  assert.equal(restored.motionObserved, true);
  sampleUntil(restored, [11, 20, 30], 1000, 10000);
  assert.equal(restored.status, 'locked');
});

test('invalid legacy metadata is refused and invalid fixed values return to observation', () => {
  for (const invalid of [null, {}, { ...metadata(), seg: 15 }, { ...metadata(), unitId: -1 }]) {
    assert.equal(restoreDrawingBaseline(invalid), null);
  }
  const restored = restoreDrawingBaseline({
    ...metadata(), status: 'locked', motionObserved: true, confirmed: true, values: [1, null, 3],
  });
  assert.equal(restored.status, 'settling');
  assert.equal(restored.values, null);
});
