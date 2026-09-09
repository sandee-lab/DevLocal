// DOM·외부 서버 없이 SSE 연결 수명과 시트 큐의 경합을 검증한다.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import ts from "typescript";

function harness(hookName, overrides = {}) {
  const timers = new Map();
  const connections = [];
  const cleanups = [];
  let timerId = 0;
  let stateResponse = Promise.resolve({ current_step: "translating" });
  const state = {
    sessionId: "session-1", currentStep: "loading", originalRows: [],
    koReviewResults: [], reviewResults: [], logs: [], allSheetsMode: false,
    sheetQueue: ["first", "second"], currentSheetIndex: 0, isWritingToSheet: false,
    ...overrides,
  };
  for (const field of ["SessionId", "CurrentStep", "SseStatus", "OriginalRows", "KoReviewResults", "TotalRows",
    "ReviewResults", "FailedRows", "CostSummary", "TranslationsApplied", "CellsUpdated", "Logs", "SelectedSheet"] ) {
    state[`set${field}`] = (value) => { state[field[0].toLowerCase() + field.slice(1)] = value; };
  }
  state.setProgress = (percent, label) => { state.progressPercent = percent; state.progressLabel = label; };
  state.addLog = (line) => state.logs.push(line);
  state.advanceSheetQueue = () => state.currentSheetIndex++;
  state.resetTranslationState = () => {};
  const store = (select) => select(state);
  store.getState = () => state;

  class FakeEventSource extends EventTarget {
    static CLOSED = 2;
    static CONNECTING = 0;
    readyState = 0;
    constructor() { super(); connections.push(this); }
    close() { this.readyState = 2; }
    emit(type, data) { this.dispatchEvent(new MessageEvent(type, { data: JSON.stringify(data) })); }
  }

  const exports = {};
  const source = readFileSync(new URL(`../src/hooks/${hookName}.ts`, import.meta.url), "utf8");
  const compiled = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
  } }).outputText;
  vm.runInNewContext(compiled, {
    exports, EventSource: FakeEventSource, MessageEvent, Date,
    setTimeout(callback, delay) { const id = ++timerId; timers.set(id, { callback, delay }); return id; },
    clearTimeout(id) { timers.delete(id); },
    require(name) {
      if (name === "react") return {
        useRef: (current) => ({ current }),
        useEffect: (effect) => { const cleanup = effect(); if (cleanup) cleanups.push(cleanup); },
      };
      if (name.includes("useAppStore")) return { useAppStore: store };
      if (name.includes("client")) return {
        getSessionState: () => stateResponse,
        startPipeline: async () => ({ session_id: "session-2" }),
      };
      throw new Error(`예상하지 못한 import: ${name}`);
    },
  });
  exports[hookName]();
  return {
    state, connections, timers,
    setStateResponse: (response) => { stateResponse = response; },
    cleanup: () => cleanups.forEach((cleanup) => cleanup()),
    async tick() {
      const scheduled = [...timers.entries()];
      timers.clear();
      for (const [, timer] of scheduled) await timer.callback();
      await Promise.resolve();
    },
  };
}

const tests = [
  ["SSE 연결 전 번역이 끝나도 검수 화면으로 전환", async () => {
    const h = harness("useSSE");
    h.connections[0].emit("node_update", { node: "reviewer", step: "translating", logs: [] });
    h.connections[0].emit("final_review_ready", { review_results: [], failed_rows: [] });
    await h.tick();
    assert.equal(h.state.currentStep, "final_review");
    h.cleanup();
  }],
  ["다른 연결에서 취소하면 한국어 승인 화면으로 동기화", async () => {
    const h = harness("useSSE", { currentStep: "translating" });
    h.connections[0].emit("final_review_ready", { review_results: [], failed_rows: [] });
    h.connections[0].emit("ko_review_ready", { results: [{ key: "restored" }], count: 1 });
    await h.tick();
    assert.equal(h.state.currentStep, "ko_review");
    assert.equal(h.state.koReviewResults[0].key, "restored");
    h.cleanup();
  }],
  ["CONNECTING 상태의 네트워크 오류도 재연결하고 서버 상태를 복원", async () => {
    const h = harness("useSSE");
    h.connections[0].onerror(new Event("error"));
    assert.equal(h.connections[0].readyState, 2);
    assert.equal(h.state.sseStatus, "reconnecting");
    assert.equal([...h.timers.values()][0].delay, 1000);
    h.setStateResponse(Promise.resolve({ current_step: "final_review", review_results: [], failed_rows: [] }));
    await h.tick();
    h.connections[1].onopen();
    await Promise.resolve();
    assert.equal(h.state.currentStep, "final_review");
    h.cleanup();
  }],
  ["세션 종료 후 지연된 화면 전환을 취소", async () => {
    const h = harness("useSSE");
    h.connections[0].emit("ko_review_ready", { results: [], count: 0 });
    h.cleanup();
    await h.tick();
    assert.equal(h.state.currentStep, "loading");
    assert.equal(h.timers.size, 0);
  }],
  ["번역 취소 뒤 이전 완료 타이머가 검수 화면을 덮어쓰지 않음", async () => {
    const h = harness("useSSE", { currentStep: "translating" });
    h.connections[0].emit("final_review_ready", { review_results: [], failed_rows: [] });
    h.state.currentStep = "ko_review";
    await h.tick();
    assert.equal(h.state.currentStep, "ko_review");
    h.cleanup();
  }],
  ["서버 작업 오류 시 idle로 복구하고 세션 연결 해제", () => {
    const h = harness("useSSE", { currentStep: "translating" });
    h.connections[0].emit("error", { message: "모의 실패" });
    assert.equal(h.state.currentStep, "idle");
    assert.equal(h.state.sessionId, null);
    assert.equal(h.connections[0].readyState, 2);
    h.cleanup();
  }],
  ["완료 이벤트에서 실제 저장 결과를 반영", () => {
    const h = harness("useSSE", { currentStep: "final_review" });
    h.connections[0].emit("done", { translations_applied: true, updates_count: 3 });
    assert.equal(h.state.currentStep, "done");
    assert.equal(h.state.translationsApplied, true);
    assert.equal(h.state.cellsUpdated, 3);
    h.cleanup();
  }],
  ["시트 저장 중에는 다음 시트를 시작하지 않음", async () => {
    const h = harness("useSheetQueue", { currentStep: "done", allSheetsMode: true, isWritingToSheet: true });
    assert.equal(h.timers.size, 0);
    await h.tick();
    assert.equal(h.state.currentSheetIndex, 0);
  }],
  ["다음 시트 시작 시 선택된 시트 이름도 동기화", async () => {
    const h = harness("useSheetQueue", { currentStep: "done", allSheetsMode: true });
    await h.tick();
    assert.equal(h.state.selectedSheet, "second");
    assert.equal(h.state.sessionId, "session-2");
    assert.equal(h.state.currentStep, "loading");
    h.cleanup();
  }],
];

for (const [name, test] of tests) {
  await test();
  console.log(`통과: ${name}`);
}
console.log(`프론트엔드 회귀 검증 ${tests.length}건 통과`);
