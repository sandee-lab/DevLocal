import { useEffect, useRef, useState } from "react";
import { useAppStore } from "../store/useAppStore";
import { getLogs } from "../api/client";
import { useFocusTrap } from "../hooks/useFocusTrap";

/**
 * 디버그용 백엔드 로그 뷰어 — 현재 세션의 누적 로그를 표시.
 * - 새로고침 / 전체 복사 / 다운로드 (sessionId가 있을 때).
 * - 자동 새로고침 토글 (3초 폴링).
 */
export default function LogsModal() {
  const open = useAppStore((s) => s.logsOpen);
  const setOpen = useAppStore((s) => s.setLogsOpen);
  const sessionId = useAppStore((s) => s.sessionId);
  const storeLogs = useAppStore((s) => s.logs);

  const [logs, setLogs] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [currentStep, setCurrentStep] = useState<string>("");

  const panelRef = useRef<HTMLDivElement>(null);
  const backdropRef = useRef<HTMLDivElement>(null);
  const preRef = useRef<HTMLPreElement>(null);

  useFocusTrap(panelRef, open);

  async function fetchLogs() {
    setError(null);
    if (!sessionId) {
      // 세션이 없으면 store에 쌓인 SSE 로그를 그대로 표시
      setLogs(storeLogs);
      setCurrentStep("(no session)");
      return;
    }
    try {
      setLoading(true);
      const res = await getLogs(sessionId);
      setLogs(res.logs);
      setCurrentStep(res.current_step);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      // 백엔드 호출 실패 시 store에 쌓인 SSE 로그라도 보여줌
      setLogs(storeLogs);
    } finally {
      setLoading(false);
    }
  }

  // 열릴 때 즉시 1회 로드
  useEffect(() => {
    if (!open) return;
    fetchLogs();

  }, [open, sessionId]);

  // 자동 새로고침 (3초)
  useEffect(() => {
    if (!open || !autoRefresh) return;
    const id = setInterval(fetchLogs, 3000);
    return () => clearInterval(id);

  }, [open, autoRefresh, sessionId]);

  // 새 로그 도착 시 스크롤 하단 유지
  useEffect(() => {
    if (!open) return;
    const el = preRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [logs, open]);

  // ESC 닫기
  useEffect(() => {
    if (!open) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, setOpen]);

  if (!open) return null;

  async function handleCopy() {
    const text = logs.join("\n");
    if (!text) return;
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  function handleDownload() {
    const text = logs.join("\n");
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `backend_logs_${sessionId ?? "session"}_${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div
      ref={backdropRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm animate-fade-in"
      onMouseDown={(e) => {
        if (e.target === backdropRef.current) setOpen(false);
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="logs-modal-title"
        className="w-full max-w-5xl mx-4 bg-white rounded-2xl shadow-2xl border border-slate-200 flex flex-col h-[80vh] animate-fade-slide-up"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-5 pb-3 border-b border-slate-200">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-primary text-2xl" aria-hidden="true">
              terminal
            </span>
            <div>
              <h2 id="logs-modal-title" className="text-lg font-bold text-text-main">
                Backend Logs
              </h2>
              <p className="text-xs text-text-muted">
                session: <span className="font-mono">{sessionId ?? "—"}</span>
                {currentStep && (
                  <span className="ml-2">step: <span className="font-mono">{currentStep}</span></span>
                )}
                <span className="ml-2">lines: {logs.length}</span>
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1.5 text-xs text-text-muted cursor-pointer select-none">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="rounded"
              />
              Auto-refresh (3s)
            </label>
            <button
              type="button"
              onClick={fetchLogs}
              disabled={loading}
              className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium bg-slate-100 hover:bg-slate-200 text-text-main rounded-lg transition-colors disabled:opacity-50"
              title="새로고침"
            >
              <span className={`material-symbols-outlined text-base ${loading ? "animate-spin360" : ""}`}>
                refresh
              </span>
              Refresh
            </button>
            <button
              type="button"
              onClick={handleCopy}
              disabled={logs.length === 0}
              className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium bg-primary text-white hover:bg-primary-dark rounded-lg transition-colors disabled:opacity-50"
              title="전체 로그 복사"
            >
              <span className="material-symbols-outlined text-base">
                {copied ? "check" : "content_copy"}
              </span>
              {copied ? "Copied!" : "Copy All"}
            </button>
            <button
              type="button"
              onClick={handleDownload}
              disabled={logs.length === 0}
              className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium bg-slate-100 hover:bg-slate-200 text-text-main rounded-lg transition-colors disabled:opacity-50"
              title="텍스트 파일로 다운로드"
            >
              <span className="material-symbols-outlined text-base">download</span>
            </button>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="p-2 text-text-muted hover:text-text-main hover:bg-slate-100 rounded-lg transition-colors ml-1"
              aria-label="Close"
            >
              <span className="material-symbols-outlined text-xl">close</span>
            </button>
          </div>
        </div>

        {/* Error banner */}
        {error && (
          <div className="mx-6 mt-3 px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
            ⚠ {error}
          </div>
        )}

        {/* Logs body */}
        <div className="flex-1 overflow-hidden px-6 py-4">
          {logs.length === 0 ? (
            <div className="flex h-full items-center justify-center text-sm text-text-muted">
              {loading ? "Loading logs..." : "No logs yet."}
            </div>
          ) : (
            <pre
              ref={preRef}
              className="h-full overflow-auto font-mono text-[11px] leading-relaxed bg-slate-900 text-slate-100 rounded-lg p-4 custom-scrollbar whitespace-pre-wrap break-words"
            >
              {logs.map((line, i) => (
                <div key={i} className="hover:bg-slate-800/60 px-1">
                  <span className="text-slate-500 select-none mr-3">{String(i + 1).padStart(4, "0")}</span>
                  {line}
                </div>
              ))}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}
