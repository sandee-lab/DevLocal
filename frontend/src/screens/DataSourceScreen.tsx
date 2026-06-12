import { useState, useEffect } from "react";
import { useAppStore } from "../store/useAppStore";
import { useToastStore } from "../store/toastStore";
import { connectSheet, startPipeline, getConfig, saveConfig } from "../api/client";
import { validateSheetUrl, validateRowRange, SHEETS_URL_REGEX } from "../utils/validation";
import Footer from "../components/Footer";

export default function DataSourceScreen() {
  const sheetUrl = useAppStore((s) => s.sheetUrl);
  const setSheetUrl = useAppStore((s) => s.setSheetUrl);
  const sheetNames = useAppStore((s) => s.sheetNames);
  const setSheetNames = useAppStore((s) => s.setSheetNames);
  const setBotEmail = useAppStore((s) => s.setBotEmail);
  const selectedSheet = useAppStore((s) => s.selectedSheet);
  const setSelectedSheet = useAppStore((s) => s.setSelectedSheet);
  const mode = useAppStore((s) => s.mode);
  const setRowLimit = useAppStore((s) => s.setRowLimit);
  const setSessionId = useAppStore((s) => s.setSessionId);
  const setCurrentStep = useAppStore((s) => s.setCurrentStep);
  const projectName = useAppStore((s) => s.projectName);
  const setProjectName = useAppStore((s) => s.setProjectName);
  const allSheetsMode = useAppStore((s) => s.allSheetsMode);
  const setAllSheetsMode = useAppStore((s) => s.setAllSheetsMode);
  const setSheetQueue = useAppStore((s) => s.setSheetQueue);

  const [rowStart, setRowStart] = useState(0);
  const [rowEnd, setRowEnd] = useState(0);
  const [connecting, setConnecting] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [synopsis, setSynopsis] = useState("");
  const [urlError, setUrlError] = useState<string | null>(null);
  const [rowRangeError, setRowRangeError] = useState<string | null>(null);
  const [urlEditing, setUrlEditing] = useState(true);

  // 저장된 URL로 자동 연결하는 헬퍼
  async function autoConnect(url: string) {
    const urlErr = validateSheetUrl(url);
    if (urlErr) return;
    setConnecting(true);
    setError("");
    setUrlError(null);
    try {
      const res = await connectSheet({ sheet_url: url });
      setSheetNames(res.sheet_names);
      setBotEmail(res.bot_email);
      if (res.project_name) setProjectName(res.project_name);
      if (res.sheet_names.length > 0) {
        const savedSheet = useAppStore.getState().selectedSheet;
        if (!savedSheet || !res.sheet_names.includes(savedSheet)) {
          setSelectedSheet(res.sheet_names[0]);
        }
        setUrlEditing(false);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Connection failed";
      setError(msg);
      useToastStore.getState().addToast(msg);
    } finally {
      setConnecting(false);
    }
  }

  // Load saved config on mount — 저장된 URL 있으면 자동 연결
  useEffect(() => {
    getConfig()
      .then((cfg) => {
        if (cfg.saved_url && !sheetUrl) {
          setSheetUrl(cfg.saved_url);
          // 저장된 URL로 즉시 자동 연결
          autoConnect(cfg.saved_url);
        }
        if (cfg.saved_sheet) {
          setSelectedSheet(cfg.saved_sheet);
        }
        if (cfg.bot_email) {
          setBotEmail(cfg.bot_email);
        }
        if (cfg.game_synopsis) {
          setSynopsis(cfg.game_synopsis);
        }
      })
      .catch(() => {});
  }, []);

  async function handleConnect() {
    if (!sheetUrl.trim()) return;
    const urlErr = validateSheetUrl(sheetUrl);
    if (urlErr) {
      setUrlError(urlErr);
      return;
    }
    setConnecting(true);
    setError("");
    setUrlError(null);
    try {
      const res = await connectSheet({ sheet_url: sheetUrl });
      setSheetNames(res.sheet_names);
      setBotEmail(res.bot_email);
      if (res.project_name) setProjectName(res.project_name);
      if (res.sheet_names.length > 0) {
        // 이전 선택 탭이 있고 목록에 포함되면 유지, 아니면 첫 번째 선택
        if (!selectedSheet || !res.sheet_names.includes(selectedSheet)) {
          setSelectedSheet(res.sheet_names[0]);
        }
        setUrlEditing(false);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Connection failed";
      setError(msg);
      useToastStore.getState().addToast(msg);
    } finally {
      setConnecting(false);
    }
  }

  async function handleLoad() {
    // URL 사전 검증
    const urlErr = validateSheetUrl(sheetUrl);
    if (urlErr) {
      setUrlError(urlErr);
      return;
    }
    // Row Range 사전 검증
    const rangeErr = validateRowRange(rowStart, rowEnd);
    if (rangeErr) {
      setRowRangeError(rangeErr);
      return;
    }

    // 즉시 로딩 상태 전환 (2-1, 2-2)
    setLoading(true);
    setError("");
    setCurrentStep("loading");

    if (allSheetsMode) {
      // All Sheets 모드: 시트 큐 세팅 후 첫 시트로 시작
      setSheetQueue([...sheetNames]);
      await startSheet(sheetNames[0]);
      saveConfig({ saved_url: sheetUrl, saved_sheet: "__ALL_SHEETS__" }).catch(() => {});
    } else {
      if (!selectedSheet) {
        setLoading(false);
        setCurrentStep("idle");
        return;
      }
      await startSheet(selectedSheet);
      saveConfig({ saved_url: sheetUrl, saved_sheet: selectedSheet }).catch(() => {});
    }
  }

  async function startSheet(sheetName: string) {
    try {
      const res = await startPipeline({
        sheet_url: sheetUrl,
        sheet_name: sheetName,
        mode,
        target_languages: [], // 빈 배열 = 시트에 컬럼이 존재하는 모든 지원 언어 (백엔드 자동 결정)
        row_start: allSheetsMode ? 0 : rowStart,
        row_end: allSheetsMode ? 0 : rowEnd,
      });
      setSessionId(res.session_id);
    } catch (e) {
      setCurrentStep("idle");
      setError(e instanceof Error ? e.message : "Failed to start");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <main className="flex-1 overflow-y-auto p-4 md:p-8 pb-32 flex flex-col items-center justify-center relative bg-gradient-mesh">
        {/* Decorative background blobs */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none -z-10">
          <div className="absolute top-0 left-1/4 w-[500px] h-[500px] bg-blue-100 rounded-full mix-blend-multiply filter blur-[80px] opacity-70 animate-blob" />
          <div className="absolute top-0 right-1/4 w-[500px] h-[500px] bg-sky-100 rounded-full mix-blend-multiply filter blur-[80px] opacity-70 animate-blob animation-delay-2000" />
        </div>

        <div className="w-full max-w-2xl space-y-8">
          {/* Title section — conditional rendering */}
          <div className="mb-8 flex flex-col items-center justify-center text-center min-h-[8rem]">
            {projectName ? (
              <div className="animate-fade-slide-up">
                <h3 className="text-3xl md:text-4xl font-bold text-text-main tracking-tight">
                  <span className="text-primary">'{projectName}'</span> loaded
                </h3>
                {synopsis && (
                  <p className="text-text-muted text-sm max-w-md mx-auto leading-relaxed mt-2 line-clamp-3">
                    {synopsis}
                  </p>
                )}
              </div>
            ) : (
              <div>
                <h3 className="text-3xl md:text-4xl font-bold text-text-main tracking-tight">
                  Data Source Configuration
                </h3>
                <p className="text-text-muted text-base max-w-lg mx-auto leading-relaxed mt-2">
                  Connect your master Google Sheet to seamlessly sync and
                  automate your localization workflow.
                </p>
              </div>
            )}
          </div>

          {/* Main card — glassmorphism */}
          <form
            onSubmit={(e) => { e.preventDefault(); handleLoad(); }}
            noValidate
            className="rounded-2xl border border-white/50 bg-white/80 backdrop-blur-xl p-8 md:p-10 shadow-soft ring-1 ring-slate-900/5 animate-fade-slide-up"
          >
            <div className="grid grid-cols-1 gap-8">
              {/* Google Sheet URL */}
              <div className="space-y-4">
                <label htmlFor="sheet-url" className="block text-sm font-semibold text-text-main">
                  Google Sheet URL
                </label>

                {/* 표시 모드: 연결 완료 + 편집 아님 */}
                {sheetNames.length > 0 && !urlEditing ? (
                  <div className="group relative flex items-center rounded-xl bg-white ring-1 ring-inset ring-slate-200 shadow-sm transition-all duration-200 hover:ring-slate-300">
                    <div className="flex items-center pl-4 border-r border-slate-100 pr-3 bg-slate-50 rounded-l-xl self-stretch">
                      <img
                        src="https://lh3.googleusercontent.com/aida-public/AB6AXuCUTqR4611swIA4vQeI__WyiAAbdng68ytwlBVg0LUOxyEVpLnOeYFifEtfXArHcrWhXg51tjJLt4F3idymF3-vNCwgv0gu5cR_PdO0VtpNgxwdUTFVSfF_z16U33SHbM1xrP5Wd_RMPShKEUXu9jpybl21XKiHuCYosPvZz5-XnkBankOR0q9OW9UqM3nte6ncfz_LOndztvFBksYyw8jyWPxRdS60e4xi04GtCfu34hkVyKJ-Gsgb6iMmGaxaULvp1AfYnMwGFQ"
                        alt="Sheets"
                        className="h-6 w-6"
                      />
                    </div>
                    <span className="flex-1 py-4 pl-4 pr-2 text-text-main text-sm truncate select-all">
                      {sheetUrl}
                    </span>
                    <div className="flex items-center pr-2">
                      <button
                        type="button"
                        onClick={() => setUrlEditing(true)}
                        aria-label="시트 URL 변경"
                        className="p-2 text-text-muted hover:text-primary rounded-lg hover:bg-primary/5 transition-colors duration-200"
                      >
                        <span className="material-symbols-outlined text-xl" aria-hidden="true">
                          edit
                        </span>
                      </button>
                    </div>
                  </div>
                ) : (
                  /* 편집 모드: 미연결 또는 편집 중 */
                  <div className={`group relative flex items-center rounded-xl bg-white ring-1 ring-inset shadow-sm transition-all duration-200 ${
                    urlError
                      ? "ring-red-400 focus-within:ring-2 focus-within:ring-red-400"
                      : "ring-slate-200 focus-within:ring-2 focus-within:ring-primary focus-within:ring-offset-2 hover:ring-slate-300"
                  }`}>
                    <div className="flex items-center pl-4 border-r border-slate-100 pr-3 bg-slate-50 rounded-l-xl self-stretch">
                      <img
                        src="https://lh3.googleusercontent.com/aida-public/AB6AXuCUTqR4611swIA4vQeI__WyiAAbdng68ytwlBVg0LUOxyEVpLnOeYFifEtfXArHcrWhXg51tjJLt4F3idymF3-vNCwgv0gu5cR_PdO0VtpNgxwdUTFVSfF_z16U33SHbM1xrP5Wd_RMPShKEUXu9jpybl21XKiHuCYosPvZz5-XnkBankOR0q9OW9UqM3nte6ncfz_LOndztvFBksYyw8jyWPxRdS60e4xi04GtCfu34hkVyKJ-Gsgb6iMmGaxaULvp1AfYnMwGFQ"
                        alt="Sheets"
                        className="h-6 w-6"
                      />
                    </div>
                    <input
                      id="sheet-url"
                      type="text"
                      value={sheetUrl}
                      aria-describedby={urlError ? "sheet-url-error" : "sheet-url-hint"}
                      onChange={(e) => {
                        setSheetUrl(e.target.value);
                        if (urlError && SHEETS_URL_REGEX.test(e.target.value)) {
                          setUrlError(null);
                        }
                        // URL 변경 시 기존 연결 데이터 초기화
                        if (sheetNames.length > 0) {
                          setSheetNames([]);
                          setSelectedSheet("");
                          setProjectName("");
                          setBotEmail("");
                          setError("");
                        }
                      }}
                      onBlur={() => {
                        if (!sheetUrl.trim()) return;
                        if (!SHEETS_URL_REGEX.test(sheetUrl)) {
                          setUrlError("올바른 Google Sheets URL을 입력해주세요");
                          return;
                        }
                        setUrlError(null);
                        if (sheetNames.length === 0) handleConnect();
                      }}
                      placeholder="https://docs.google.com/spreadsheets/d/..."
                      className="block w-full border-0 bg-transparent py-4 pl-4 text-text-main placeholder:text-slate-400 focus:ring-0 sm:text-sm sm:leading-6 rounded-r-xl"
                    />
                    <div className="flex items-center pr-2 self-stretch">
                      <button
                        type="button"
                        onClick={handleConnect}
                        disabled={connecting}
                        aria-label="시트 연결"
                        className="p-2 text-text-muted hover:text-primary rounded-lg hover:bg-primary/5 transition-colors duration-200"
                      >
                        <span className="material-symbols-outlined text-xl" aria-hidden="true">
                          {connecting ? "sync" : "content_paste"}
                        </span>
                      </button>
                    </div>
                  </div>
                )}

                {/* Inline URL Error */}
                {urlError && (
                  <div id="sheet-url-error" className="flex items-center gap-1.5 text-xs text-red-600 animate-fade-slide-down">
                    <span className="material-symbols-outlined text-sm" aria-hidden="true">error</span>
                    {urlError}
                  </div>
                )}

                {/* Status / Info */}
                {connecting ? (
                  <div className="flex items-center gap-2 text-xs">
                    <span className="material-symbols-outlined text-sm text-primary animate-spin360">
                      progress_activity
                    </span>
                    <span className="text-primary font-medium">
                      Connecting...
                    </span>
                  </div>
                ) : sheetNames.length > 0 ? (
                  <div className="flex items-center gap-2 text-xs">
                    <span className="material-symbols-outlined text-sm text-emerald-500">
                      check_circle
                    </span>
                    <span className="text-emerald-600 font-medium">
                      Connected — {sheetNames.length} tab
                      {sheetNames.length > 1 ? "s" : ""} found
                    </span>
                  </div>
                ) : !connecting && sheetNames.length === 0 && !sheetUrl.trim() ? (
                  <div id="sheet-url-hint" className="flex items-start gap-2 text-xs text-text-muted bg-blue-50/50 p-2 rounded-lg border border-blue-100/50">
                    <span className="material-symbols-outlined text-sm text-primary mt-0.5" aria-hidden="true">
                      info
                    </span>
                    <span>
                      Ensure the sheet is shared with the service account email
                      before proceeding.
                    </span>
                  </div>
                ) : null}
              </div>

              {/* Sheet Tab + Row Range */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label htmlFor="sheet-tab" className="mb-2 block text-sm font-semibold text-text-main">
                    Sheet Tab Name
                  </label>
                  <div className="relative">
                    <select
                      id="sheet-tab"
                      value={allSheetsMode ? "__ALL_SHEETS__" : selectedSheet}
                      onChange={(e) => {
                        const val = e.target.value;
                        if (val === "__ALL_SHEETS__") {
                          setAllSheetsMode(true);
                          setSelectedSheet(sheetNames[0] || "");
                        } else {
                          setAllSheetsMode(false);
                          setSelectedSheet(val);
                        }
                      }}
                      disabled={sheetNames.length === 0}
                      className="block w-full rounded-xl border-0 bg-white py-3.5 pl-4 pr-10 text-text-main ring-1 ring-inset ring-slate-200 focus:ring-2 focus:ring-primary sm:text-sm sm:leading-6 shadow-sm appearance-none transition-all duration-200 hover:ring-slate-300"
                    >
                      {sheetNames.length === 0 ? (
                        <option value="">Select a tab...</option>
                      ) : (
                        <>
                          <option value="__ALL_SHEETS__">
                            All Sheets ({sheetNames.length} tabs)
                          </option>
                          {sheetNames.map((n) => (
                            <option key={n} value={n}>
                              {n}
                            </option>
                          ))}
                        </>
                      )}
                    </select>
                    <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-4 text-text-muted">
                      <span className="material-symbols-outlined">
                        expand_more
                      </span>
                    </div>
                  </div>
                </div>
                <div className={allSheetsMode ? "opacity-50 pointer-events-none" : ""}>
                  <label htmlFor="row-start" className="mb-2 block text-sm text-text-main">
                    <span className="font-semibold">Row Range</span>{" "}
                    <span className="text-text-muted font-normal">(비워 두면 마지막 행까지 자동 감지)</span>
                  </label>
                  <div className="flex items-center gap-3">
                    <div className="relative w-full">
                      <input
                        id="row-start"
                        type="number"
                        value={rowStart || ""}
                        onChange={(e) => {
                          const v = Number(e.target.value);
                          setRowStart(v);
                          if (rowRangeError) setRowRangeError(null);
                        }}
                        onKeyDown={(e) => {
                          if (e.key === "-" || e.key === "." || e.key === "e") e.preventDefault();
                        }}
                        min={1}
                        step={1}
                        placeholder="1"
                        disabled={allSheetsMode}
                        className="block w-full rounded-xl border-0 bg-white py-3.5 px-3 text-center text-text-main ring-1 ring-inset ring-slate-200 focus:ring-2 focus:ring-primary sm:text-sm sm:leading-6 shadow-sm transition-all hover:ring-slate-300 placeholder:text-slate-400"
                      />
                    </div>
                    <span className="text-slate-300 font-medium text-lg">
                      -
                    </span>
                    <div className="relative w-full">
                      <input
                        id="row-end"
                        type="number"
                        value={rowEnd || ""}
                        onChange={(e) => {
                          const v = Number(e.target.value);
                          setRowEnd(v);
                          setRowLimit(v > 0 ? v - rowStart : 0);
                          if (rowRangeError) setRowRangeError(null);
                        }}
                        onKeyDown={(e) => {
                          if (e.key === "-" || e.key === "." || e.key === "e") e.preventDefault();
                        }}
                        min={1}
                        step={1}
                        placeholder="끝까지"
                        disabled={allSheetsMode}
                        className="block w-full rounded-xl border-0 bg-white py-3.5 px-3 text-center text-text-main ring-1 ring-inset ring-slate-200 focus:ring-2 focus:ring-primary sm:text-sm sm:leading-6 shadow-sm transition-all hover:ring-slate-300 placeholder:text-slate-400"
                      />
                    </div>
                  </div>
                  {rowRangeError && (
                    <p className="text-xs text-red-600 mt-1.5 animate-fade-slide-down">
                      {rowRangeError}
                    </p>
                  )}
                </div>
              </div>
            </div>

            {/* Error message */}
            {error && (
              <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center gap-2 animate-fade-slide-down">
                <span className="material-symbols-outlined text-lg animate-shake">
                  error
                </span>
                {error}
              </div>
            )}
          </form>
        </div>
      </main>

      <Footer
        onAction={handleLoad}
        actionLabel={loading ? "Loading..." : "Load Data"}
        actionIcon={loading ? "progress_activity" : "arrow_forward"}
        actionDisabled={(!selectedSheet && !allSheetsMode) || loading || !!validateSheetUrl(sheetUrl) || !!rowRangeError}
      />
    </>
  );
}
