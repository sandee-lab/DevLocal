import { useEffect, useRef } from "react";
import { useAppStore } from "../store/useAppStore";
import { startPipeline } from "../api/client";

/**
 * All Sheets 모드 시 시트 큐를 관리하는 훅.
 * 한 시트의 번역이 "done"에 도달하면 2초 후 다음 시트를 자동 시작.
 * App.tsx 레벨에서 호출.
 */
export function useSheetQueue() {
  const currentStep = useAppStore((s) => s.currentStep);
  const allSheetsMode = useAppStore((s) => s.allSheetsMode);
  const sheetQueue = useAppStore((s) => s.sheetQueue);
  const currentSheetIndex = useAppStore((s) => s.currentSheetIndex);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    if (currentStep !== "done" || !allSheetsMode) return;
    if (currentSheetIndex + 1 >= sheetQueue.length) return;

    timerRef.current = setTimeout(async () => {
      const s = useAppStore.getState();
      const nextSheet = sheetQueue[currentSheetIndex + 1];
      s.advanceSheetQueue();
      s.resetTranslationState();
      s.setSessionId(null);         // 구 SSE 즉시 종료 — late "done" 이벤트 수신 방지
      s.setCurrentStep("loading");

      try {
        const res = await startPipeline({
          sheet_url: s.sheetUrl,
          sheet_name: nextSheet,
          mode: s.mode,
          target_languages: [], // 빈 배열 = 시트에 컬럼이 존재하는 모든 지원 언어 (백엔드 자동 결정)
          row_start: 0,
          row_end: 0,
        });
        s.setSessionId(res.session_id);
      } catch (err) {
        s.addLog(
          `[ERROR] Sheet "${nextSheet}" failed: ${err instanceof Error ? err.message : String(err)}`,
        );
        s.setCurrentStep("done"); // 다음 시트로 자동 진행
      }
    }, 2000);

    return () => clearTimeout(timerRef.current);
  }, [currentStep, allSheetsMode, currentSheetIndex, sheetQueue]);
}
