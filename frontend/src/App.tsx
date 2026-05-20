import { useEffect, useRef, useState } from "react";
import { useAppStore } from "./store/useAppStore";
import { useSSE } from "./hooks/useSSE";
import { useSheetQueue } from "./hooks/useSheetQueue";
import { useNavigationGuard } from "./hooks/useNavigationGuard";
import { getSessionState } from "./api/client";
import type { AppStep } from "./types";
import Header from "./components/Header";
import SettingsModal from "./components/SettingsModal";
import HelpModal from "./components/HelpModal";
import LogsModal from "./components/LogsModal";
import ToastContainer from "./components/Toast";
import DataSourceScreen from "./screens/DataSourceScreen";
import KoReviewWorkspace from "./screens/KoReviewWorkspace";
import TranslationWorkspace from "./screens/TranslationWorkspace";
import DoneScreen from "./screens/DoneScreen";

function ScreenForStep({ step }: { step: AppStep }) {
  switch (step) {
    case "idle":
      return <DataSourceScreen />;
    case "loading":
    case "ko_review":
      return <KoReviewWorkspace />;
    case "translating":
    case "final_review":
      return <TranslationWorkspace />;
    case "done":
      return <DoneScreen />;
    default:
      return <DataSourceScreen />;
  }
}

// 같은 통합 컴포넌트 내 step 그룹 — 그룹 내 전환은 슬라이드 스킵
const KO_REVIEW_STEPS = new Set<AppStep>(["loading", "ko_review"]);
const TRANSLATION_STEPS = new Set<AppStep>(["translating", "final_review"]);

/**
 * 화면 전환 래퍼 — currentStep 변경 시:
 *  Phase 1 (exit):  현재 화면 fade-slide-left (400ms)
 *  Phase 2 (enter): 새 화면 fade-slide-right (400ms)
 *  단, 같은 그룹(KO_REVIEW_STEPS / TRANSLATION_STEPS) 내 전환은 in-place 처리 (슬라이드 스킵)
 */
function AnimatedScreen() {
  const currentStep = useAppStore((s) => s.currentStep);
  const [displayedStep, setDisplayedStep] = useState(currentStep);
  const [phase, setPhase] = useState<"idle" | "exit" | "enter">("idle");
  const prevStepRef = useRef(currentStep);

  useEffect(() => {
    if (currentStep === prevStepRef.current) return;
    const prev = prevStepRef.current;
    prevStepRef.current = currentStep;

    // 같은 통합 컴포넌트 내 전환 — 슬라이드 스킵
    const sameGroup =
      (KO_REVIEW_STEPS.has(prev) && KO_REVIEW_STEPS.has(currentStep)) ||
      (TRANSLATION_STEPS.has(prev) && TRANSLATION_STEPS.has(currentStep));
    if (sameGroup) {
      setDisplayedStep(currentStep);
      return;
    }

    // Exit phase
    setPhase("exit");

    const exitTimer = setTimeout(() => {
      setDisplayedStep(currentStep);
      setPhase("enter");

      const enterTimer = setTimeout(() => {
        setPhase("idle");
      }, 400);

      return () => clearTimeout(enterTimer);
    }, 400);

    return () => clearTimeout(exitTimer);
  }, [currentStep]);

  const animClass =
    phase === "exit"
      ? "animate-fade-slide-left"
      : phase === "enter"
        ? "animate-fade-slide-right"
        : "";

  return (
    <div
      className={`flex flex-1 flex-col overflow-hidden ${animClass}`}
      style={{ willChange: phase !== "idle" ? "transform, opacity" : "auto" }}
    >
      <ScreenForStep step={displayedStep} />
    </div>
  );
}

export default function App() {
  const currentStep = useAppStore((s) => s.currentStep);
  const [restoring, setRestoring] = useState(false);

  // SSE를 App 레벨에서 유지 — 화면 전환에도 연결 유지
  useSSE();

  // All Sheets 모드: 시트 큐 자동 진행
  useSheetQueue();

  // 작업 중 브라우저 새로고침/탭 닫기 방지
  useNavigationGuard(currentStep !== "idle" && currentStep !== "done");

  // 마운트 시 세션 복원 — localStorage에 저장된 sessionId로 상태 복구
  useEffect(() => {
    const savedId = localStorage.getItem("devlocal_session_id");
    const store = useAppStore.getState();
    if (!savedId || store.sessionId) return;

    setRestoring(true);
    // 5초 타임아웃 — 백엔드 무응답 시 idle로 복귀
    const timeout = setTimeout(() => {
      localStorage.removeItem("devlocal_session_id");
      setRestoring(false);
    }, 5000);

    getSessionState(savedId)
      .then((state) => {
        clearTimeout(timeout);
        const s = useAppStore.getState();
        if (state.current_step === "done" || state.current_step === "idle") {
          localStorage.removeItem("devlocal_session_id");
          return;
        }
        // sessionId 설정 → useSSE의 useEffect 트리거 → SSE 연결
        s.setSessionId(savedId);
        s.setLogs(state.logs);
        s.setTotalRows(state.total_rows ?? 0);
        // 테이블 복원용 original_rows
        if (state.original_rows) {
          s.setOriginalRows(state.original_rows);
        }

        if (state.current_step === "ko_review" && state.ko_review_results) {
          s.setKoReviewResults(state.ko_review_results);
          s.setCurrentStep("ko_review");
        } else if (state.current_step === "final_review" && state.review_results) {
          s.setReviewResults(state.review_results);
          if (state.failed_rows) s.setFailedRows(state.failed_rows);
          if (state.cost_summary) s.setCostSummary(state.cost_summary);
          s.setCurrentStep("final_review");
        } else {
          // loading / translating — SSE가 이어받음
          s.setCurrentStep(state.current_step as AppStep);
        }
      })
      .catch(() => {
        clearTimeout(timeout);
        // 세션 만료 또는 서버 미실행 — 정리 후 idle
        localStorage.removeItem("devlocal_session_id");
      })
      .finally(() => setRestoring(false));

    return () => clearTimeout(timeout);
  }, []);

  if (restoring) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-bg-page font-display">
        <span className="material-symbols-outlined text-3xl text-primary animate-spin360">
          progress_activity
        </span>
      </div>
    );
  }

  return (
    <div className="flex h-screen w-full flex-col overflow-hidden bg-bg-page font-display text-text-main antialiased">
      <Header />
      <AnimatedScreen />
      <SettingsModal />
      <HelpModal />
      <LogsModal />
      <ToastContainer />
    </div>
  );
}
