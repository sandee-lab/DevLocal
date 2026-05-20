import { useAppStore } from "../store/useAppStore";
import StepIndicator from "./StepIndicator";

export default function Header() {
  const currentStep = useAppStore((s) => s.currentStep);
  const sseStatus = useAppStore((s) => s.sseStatus);
  const allSheetsMode = useAppStore((s) => s.allSheetsMode);
  const sheetQueue = useAppStore((s) => s.sheetQueue);
  const currentSheetIndex = useAppStore((s) => s.currentSheetIndex);
  const totalSheetCount = useAppStore((s) => s.totalSheetCount);
  const setLogsOpen = useAppStore((s) => s.setLogsOpen);

  const statusConfig = {
    connected: { dot: "bg-emerald-500 animate-dot-pulse", label: "Connected" },
    reconnecting: { dot: "bg-amber-400 animate-breathe", label: "Reconnecting..." },
    disconnected: { dot: "bg-slate-300", label: "Disconnected" },
  };
  const status = statusConfig[sseStatus];

  return (
    <header className="flex h-20 items-center justify-between border-b border-border-subtle/60 bg-white/80 backdrop-blur-md px-8 shadow-sm shrink-0 z-30">
      {/* Logo */}
      <div className="flex items-center gap-3 min-w-[240px]">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-primary-dark text-white shadow-md">
          <span className="material-symbols-outlined text-2xl">translate</span>
        </div>
        <div>
          <h2 className="text-lg font-bold text-text-main tracking-tight leading-none">
            Rabbit Loc
          </h2>
          <span className="text-[10px] uppercase tracking-wider font-semibold text-text-muted">
            Localization Tool
          </span>
        </div>
      </div>

      {/* Step indicator */}
      <div className="flex flex-col items-center gap-1">
        <StepIndicator currentStep={currentStep} />
        {allSheetsMode && totalSheetCount > 1 && currentStep !== "idle" && (
          <span className="text-[10px] font-semibold text-primary bg-primary/10 px-2 py-0.5 rounded-full">
            Sheet {currentSheetIndex + 1}/{totalSheetCount}: {sheetQueue[currentSheetIndex] || ""}
          </span>
        )}
      </div>

      {/* Right side: logs + connection status */}
      <div className="min-w-[240px] flex justify-end items-center gap-2">
        <button
          type="button"
          onClick={() => setLogsOpen(true)}
          className="flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-50 hover:bg-slate-100 rounded-lg border border-border-subtle text-text-muted hover:text-text-main transition-colors"
          title="백엔드 로그 보기"
          aria-label="View backend logs"
        >
          <span className="material-symbols-outlined text-base" aria-hidden="true">
            terminal
          </span>
          <span className="text-xs font-medium">Logs</span>
        </button>
        {currentStep !== "idle" && (
          currentStep === "done" ? (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-50 rounded-lg border border-emerald-200">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              <span className="text-xs font-medium text-emerald-600">
                Completed
              </span>
            </div>
          ) : (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-50 rounded-lg border border-border-subtle">
              <span className={`w-2 h-2 rounded-full ${status.dot}`} />
              <span className="text-xs font-medium text-text-muted">
                {status.label}
              </span>
            </div>
          )
        )}
      </div>
    </header>
  );
}
