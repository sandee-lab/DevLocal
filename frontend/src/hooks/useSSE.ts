import { useEffect, useRef } from "react";
import { useAppStore } from "../store/useAppStore";
import { getSessionState } from "../api/client";
import type {
  AppStep,
  NodeUpdateData,
  KoReviewReadyData,
  FinalReviewReadyData,
  KoReviewChunkData,
  TranslationChunkData,
  ReviewChunkData,
} from "../types";

// 재연결 설정
const MAX_RECONNECT = 5;
const BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 16000;

/**
 * SSE 스트림 훅 — sessionId가 설정되면 연결, 전체 파이프라인 동안 유지
 * App.tsx 레벨에서 호출하여 화면 전환에도 연결이 유지되도록 함
 *
 * 재연결: 네트워크 끊김 시 exponential backoff로 최대 5회 재시도
 * 앱 에러: 서버가 보낸 error 이벤트는 재연결하지 않음
 */
export function useSSE() {
  const sessionId = useAppStore((s) => s.sessionId);
  const esRef = useRef<EventSource | null>(null);
  const reconnectCountRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const closedIntentionallyRef = useRef(false);

  useEffect(() => {
    if (!sessionId) return;

    closedIntentionallyRef.current = false;
    reconnectCountRef.current = 0;

    function connect() {
      const es = new EventSource(`/api/stream/${sessionId}`);
      esRef.current = es;
      const store = useAppStore.getState;

      es.onopen = () => {
        const wasReconnect = reconnectCountRef.current > 0;
        reconnectCountRef.current = 0;
        store().setSseStatus("connected");

        // 재연결 시 끊김 동안 놓친 상태 전환 동기화
        if (wasReconnect && sessionId) {
          getSessionState(sessionId)
            .then((state) => {
              const s = store();
              const cur = s.currentStep;
              // 테이블 복원용 original_rows
              if (state.original_rows && s.originalRows.length === 0) {
                s.setOriginalRows(state.original_rows);
              }
              // 백엔드가 이미 다음 단계로 진행했으면 프론트도 전환
              if (state.current_step === "ko_review" && cur !== "ko_review" && state.ko_review_results) {
                s.setKoReviewResults(state.ko_review_results);
                s.setTotalRows(state.total_rows ?? 0);
                s.setCurrentStep("ko_review");
              } else if (state.current_step === "final_review" && cur !== "final_review" && state.review_results) {
                s.setReviewResults(state.review_results);
                if (state.failed_rows) s.setFailedRows(state.failed_rows);
                if (state.cost_summary) s.setCostSummary(state.cost_summary);
                s.setCurrentStep("final_review");
              } else if (state.current_step === "done" && cur !== "done") {
                s.setCurrentStep("done");
              } else if (state.current_step !== cur) {
                s.setCurrentStep(state.current_step as AppStep);
              }
            })
            .catch(() => {
              // 동기화 실패 — SSE 이벤트로 자연스럽게 보완
            });
        }
      };

      /* ── 노드 수준 업데이트 ── */
      es.addEventListener("node_update", (e) => {
        const data: NodeUpdateData = JSON.parse(e.data);
        const s = store();
        s.setLogs(data.logs);

        if (data.step === "loading") {
          // Loading phase — 고정 진행률
          const loadingMap: Record<string, [number, string]> = {
            data_backup: [10, "Backing up data..."],
            context_glossary: [25, "Preparing glossary & context..."],
            ko_review: [50, "Reviewing Korean text..."],
          };
          const p = loadingMap[data.node];
          if (p) s.setProgress(p[0], p[1]);
        } else if (data.step === "translating") {
          // Translating phase — 라벨만 업데이트 (진행률은 chunk 이벤트가 담당)
          const labelMap: Record<string, string> = {
            translator: "Translator Agent working...",
            reviewer: "Reviewer Agent checking quality...",
            should_retry: "Retrying failed translations...",
          };
          const label = labelMap[data.node];
          if (label) {
            // reviewer 시작 시 최소 60% 보장 (translator 완료 의미)
            if (data.node === "reviewer") {
              s.setProgress(Math.max(s.progressPercent, 60), label);
            } else if (data.node === "should_retry") {
              s.setProgress(Math.max(s.progressPercent, 85), label);
            } else {
              s.setProgress(s.progressPercent, label);
            }
          }
        }
      });

      /* ── 원본 데이터 수신 (Loading 화면 테이블용) ── */
      es.addEventListener("original_data", (e) => {
        const data = JSON.parse(e.data);
        store().setOriginalRows(data.rows);
      });

      /* ── 노드 하트비트 (stall 감지) ── */
      es.addEventListener("heartbeat", () => {
        store().setLastHeartbeatAt(Date.now());
      });

      /* ── 라이브 로그 라인 (LogsModal 실시간 갱신용) ── */
      es.addEventListener("log_line", (e) => {
        try {
          const data = JSON.parse(e.data);
          if (typeof data.text === "string" && data.text) {
            store().addLog(data.text);
          }
        } catch {
          /* malformed event — ignore */
        }
      });

      /* ── 한국어 검수 — 청크별 부분 결과 ── */
      es.addEventListener("ko_review_chunk", (e) => {
        const data: KoReviewChunkData = JSON.parse(e.data);
        const s = store();
        s.appendPartialKoResults(data.chunk_results);
        s.setChunkProgress(data.progress);
        const pct = Math.round(
          (data.progress.done / data.progress.total) * 100,
        );
        s.setProgress(
          pct,
          `Reviewing Korean... (${data.progress.done}/${data.progress.total})`,
        );
      });

      /* ── 번역 — 청크별 부분 결과 (전체의 0% → 60%) ── */
      es.addEventListener("translation_chunk", (e) => {
        const data: TranslationChunkData = JSON.parse(e.data);
        const s = store();
        s.appendPartialTranslations(data.chunk_results);
        s.setChunkProgress(data.progress);
        const rawPct = data.progress.done / data.progress.total;
        const scaledPct = Math.round(rawPct * 60); // 0-60% 범위
        const lang = data.progress.lang?.toUpperCase() ?? "";
        s.setProgress(
          scaledPct,
          `Translator Agent — ${lang} (${data.progress.done}/${data.progress.total})`,
        );
      });

      /* ── 검수 — 청크별 부분 결과 (전체의 60% → 95%) ── */
      es.addEventListener("review_chunk", (e) => {
        const data: ReviewChunkData = JSON.parse(e.data);
        const s = store();
        s.appendPartialReviews(data.chunk_results);
        s.setChunkProgress(data.progress);
        const rawPct = data.progress.total > 0
          ? data.progress.done / data.progress.total
          : 0;
        const scaledPct = 60 + Math.round(rawPct * 35); // 60-95% 범위
        s.setProgress(
          scaledPct,
          `Reviewer Agent — checking (${data.progress.done}/${data.progress.total})`,
        );
      });

      /* ── 한국어 검수 완료 → 항상 리뷰 화면 표시 (0건이어도 컨펌 필요) ── */
      es.addEventListener("ko_review_ready", (e) => {
        const data: KoReviewReadyData = JSON.parse(e.data);
        const s = store();
        s.setKoReviewResults(data.results);
        s.setTotalRows(data.count);
        s.setProgress(100, "Korean review complete");
        setTimeout(() => s.setCurrentStep("ko_review"), 1500);
      });

      /* ── 번역 검수 완료 → 600ms dwell 후 화면 전환 ── */
      es.addEventListener("final_review_ready", (e) => {
        const data: FinalReviewReadyData = JSON.parse(e.data);
        const s = store();
        s.setReviewResults(data.review_results);
        s.setFailedRows(data.failed_rows);
        if (data.cost) {
          // backend가 정확한 단가로 estimated_cost_usd까지 계산해서 전달 → 그대로 사용
          s.setCostSummary({
            input_tokens: data.cost.input_tokens,
            output_tokens: data.cost.output_tokens,
            reasoning_tokens: data.cost.reasoning_tokens ?? 0,
            cached_tokens: data.cost.cached_tokens ?? 0,
            estimated_cost_usd: data.cost.estimated_cost_usd ?? 0,
          });
        }
        s.setProgress(100, "Translation complete");
        setTimeout(() => s.setCurrentStep("final_review"), 600);
      });

      /* ── 완료 — 의도적 종료 ── */
      es.addEventListener("done", () => {
        // Stale "done" 이벤트 무시 (구 세션에서 늦게 도착한 경우)
        if (useAppStore.getState().sessionId !== sessionId) return;
        closedIntentionallyRef.current = true;
        store().setCurrentStep("done");
        store().setSseStatus("disconnected");
        es.close();
      });

      /* ── 앱 레벨 에러 (서버가 보낸 error 이벤트 — MessageEvent) ── */
      es.addEventListener("error", (e) => {
        if (e instanceof MessageEvent) {
          try {
            const data = JSON.parse(e.data);
            store().addLog(`[ERROR] ${data.message}`);
          } catch {
            // non-JSON error event
          }
          closedIntentionallyRef.current = true;
          store().setSseStatus("disconnected");
          es.close();
          // All Sheets 모드: 에러 발생해도 큐 진행 (다음 시트로 이동)
          if (useAppStore.getState().allSheetsMode) {
            store().setCurrentStep("done");
          }
        }
      });

      /* ── 연결 끊김 (네트워크 에러) → 재연결 시도 ── */
      es.onerror = () => {
        if (closedIntentionallyRef.current) return;
        if (es.readyState === EventSource.CLOSED) {
          es.close();
          esRef.current = null;
          attemptReconnect();
        }
      };
    }

    function attemptReconnect() {
      if (reconnectCountRef.current >= MAX_RECONNECT) {
        useAppStore.getState().setSseStatus("disconnected");
        return;
      }
      useAppStore.getState().setSseStatus("reconnecting");
      const delay = Math.min(
        BASE_DELAY_MS * 2 ** reconnectCountRef.current,
        MAX_DELAY_MS,
      );
      reconnectCountRef.current++;
      reconnectTimerRef.current = setTimeout(() => connect(), delay);
    }

    connect();

    return () => {
      closedIntentionallyRef.current = true;
      clearTimeout(reconnectTimerRef.current);
      esRef.current?.close();
      esRef.current = null;
    };
  }, [sessionId]);

  return esRef;
}
