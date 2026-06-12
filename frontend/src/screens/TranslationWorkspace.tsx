import { useEffect, useMemo, useRef, useState } from "react";
import { useAppStore } from "../store/useAppStore";
import {
  cancelTranslation,
  approveFinal,
  getDownloadUrl,
} from "../api/client";
import { useCountUp } from "../hooks/useCountUp";
import { highlightDiff } from "../utils/diffHighlight";
import { TARGET_LANG_LABELS } from "../utils/glossary";
import type { TargetLang } from "../utils/glossary";
import Footer from "../components/Footer";
import ConfirmModal from "../components/ConfirmModal";

const PAGE_SIZE = 10;

/**
 * 통합 번역 화면 — TranslatingScreen + FinalReviewScreen 합본.
 * currentStep 기반으로 mode를 결정하고, translating → review 전환 시
 * 페이지 이동 없이 in-place 트랜지션으로 처리.
 */
export default function TranslationWorkspace() {
  /* ── Store ── */
  const currentStep = useAppStore((s) => s.currentStep);
  const sessionId = useAppStore((s) => s.sessionId);
  const setCurrentStep = useAppStore((s) => s.setCurrentStep);
  const progressPercent = useAppStore((s) => s.progressPercent);
  const progressLabel = useAppStore((s) => s.progressLabel);
  const originalRows = useAppStore((s) => s.originalRows);
  const partialTranslations = useAppStore((s) => s.partialTranslations);
  const partialReviews = useAppStore((s) => s.partialReviews);
  const reviewResults = useAppStore((s) => s.reviewResults);
  const failedRows = useAppStore((s) => s.failedRows);
  const reviewDecisions = useAppStore((s) => s.reviewDecisions);
  const setReviewDecision = useAppStore((s) => s.setReviewDecision);
  const selectedLang = useAppStore((s) => s.selectedLang);
  const setSelectedLang = useAppStore((s) => s.setSelectedLang);
  const costSummary = useAppStore((s) => s.costSummary);
  const setTranslationsApplied = useAppStore((s) => s.setTranslationsApplied);
  const setCellsUpdated = useAppStore((s) => s.setCellsUpdated);
  const setIsWritingToSheet = useAppStore((s) => s.setIsWritingToSheet);
  const resetTranslationState = useAppStore((s) => s.resetTranslationState);
  const reset = useAppStore((s) => s.reset);

  /* ── Local State ── */
  const [page, setPage] = useState(1);
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [expandedNote, setExpandedNote] = useState<string | null>(null);
  const [showBackModal, setShowBackModal] = useState(false);
  const [showUnconfirmedModal, setShowUnconfirmedModal] = useState(false);
  const [showDiscardModal, setShowDiscardModal] = useState(false);

  /* ── Mode ── */
  const mode = currentStep === "final_review" ? "review" : "translating";
  const prevModeRef = useRef(mode);

  useEffect(() => {
    if (prevModeRef.current === "translating" && mode === "review") {
      setPage(1);
      setExpandedNote(null);
    }
    prevModeRef.current = mode;
  }, [mode]);

  /* ── Row drip-feed animation ── */
  const doneIndicesRef = useRef(new Set<string>());

  /* ── Derived ── */
  const isComplete = progressPercent >= 100;

  /* ── Progress card values (translating → review 전환) ── */
  const cardPercent = mode === "review" ? 100 : progressPercent;
  const animPct = useCountUp(cardPercent, 500);
  const cardLabel = mode === "review"
    ? "Translation & Review complete"
    : (progressLabel || "Initializing...");
  const cardComplete = mode === "review" || isComplete;

  const agentPhase: "init" | "translator" | "reviewer" | "complete" =
    isComplete
      ? "complete"
      : progressLabel.includes("Translator") ||
          progressLabel.includes("Retrying")
        ? "translator"
        : progressLabel.includes("Reviewer")
          ? "reviewer"
          : "init";

  const availableLangs = useMemo(() => {
    if (mode === "review") {
      const langs = new Set(reviewResults.map((r) => r.lang));
      for (const f of failedRows) langs.add(f.lang);
      return Array.from(langs);
    }
    const s = new Set<string>();
    for (const t of partialTranslations) s.add(t.lang);
    return Array.from(s).sort();
  }, [mode, reviewResults, failedRows, partialTranslations]);

  const activeLang = availableLangs.includes(selectedLang)
    ? selectedLang
    : (availableLangs[0] ?? "en");

  useEffect(() => {
    if (activeLang !== selectedLang) setSelectedLang(activeLang);
  }, [activeLang, selectedLang, setSelectedLang]);

  const translationMap = useMemo(() => {
    const m = new Map<string, string>();
    for (const t of partialTranslations) {
      if (t.lang === activeLang) {
        const mk = t.row_index != null ? `ri_${t.row_index}` : t.key;
        m.set(mk, t.translated);
      }
    }
    return m;
  }, [partialTranslations, activeLang]);

  const reviewMap = useMemo(() => {
    const m = new Map<string, { reason: string; old_translation: string }>();
    for (const r of partialReviews) {
      if (r.lang === activeLang) {
        const mk = r.row_index != null ? `ri_${r.row_index}` : r.key;
        m.set(mk, { reason: r.reason, old_translation: r.old_translation });
      }
    }
    return m;
  }, [partialReviews, activeLang]);

  /* ── Unified Rows ── */
  type RowStatus = "pending" | "translating" | "translated" | "reviewing" | "reviewed" | "failed";

  const unifiedRows = useMemo(() => {
    if (mode === "review") {
      const reviewed = reviewResults
        .filter((r) => r.lang === activeLang)
        .map((r) => ({
          rowKey: r.row_index != null ? `${r.row_index}_${r.lang}` : `${r.key}_${r.lang}`,
          key: r.key,
          lang: r.lang,
          original_ko: r.original_ko,
          old_translation: r.old_translation,
          translated: r.translated,
          reason: r.reason,
          isDone: true,
          hasChange: r.old_translation !== r.translated,
          rowStatus: "reviewed" as RowStatus,
        }));
      const failed = failedRows
        .filter((f) => f.lang === activeLang)
        .map((f) => ({
          rowKey: f.row_index != null ? `${f.row_index}_${f.lang}_fail` : `${f.key}_${f.lang}_fail`,
          key: f.key,
          lang: f.lang,
          original_ko: "",
          old_translation: "",
          translated: "",
          reason: f.reason,
          isDone: true,
          hasChange: false,
          rowStatus: "failed" as RowStatus,
        }));
      return [...reviewed, ...failed];
    }
    return originalRows.map((row) => {
      const mk = row.row_index != null ? `ri_${row.row_index}` : row.key;
      const translated = translationMap.get(mk);
      const review = reviewMap.get(mk);
      const isDone = translated !== undefined;
      const hasReview = review !== undefined;
      const hasChange =
        isDone && review ? review.old_translation !== translated : false;

      let rowStatus: RowStatus;
      if (!isDone) {
        if (agentPhase === "init") {
          rowStatus = "pending";
        } else if (agentPhase === "reviewer" || agentPhase === "complete") {
          rowStatus = "translated";
        } else {
          rowStatus = "translating";
        }
      } else if (hasReview || agentPhase === "complete") {
        rowStatus = "reviewed";
      } else if (agentPhase === "reviewer") {
        rowStatus = "reviewing";
      } else {
        rowStatus = "translated";
      }

      return {
        rowKey: row.row_index != null ? `${row.row_index}_${activeLang}` : `${row.key}_${activeLang}`,
        key: row.key,
        lang: activeLang,
        original_ko: row.korean,
        old_translation: review?.old_translation ?? "",
        translated: translated ?? "",
        reason: review?.reason ?? "",
        isDone,
        hasChange,
        rowStatus,
      };
    });
  }, [mode, reviewResults, failedRows, originalRows, translationMap, reviewMap, activeLang, agentPhase]);

  const totalPages = Math.max(1, Math.ceil(unifiedRows.length / PAGE_SIZE));
  const pageRows = unifiedRows.slice(
    (page - 1) * PAGE_SIZE,
    page * PAGE_SIZE,
  );

  const changedCount = useMemo(
    () =>
      reviewResults.filter((r) => r.old_translation !== r.translated).length,
    [reviewResults],
  );
  const unchangedCount = reviewResults.length - changedCount;

  const barColor = cardComplete ? "bg-emerald-500" : "bg-primary";
  const barShadow = cardComplete
    ? "shadow-[0_0_12px_rgba(16,185,129,0.4)]"
    : "shadow-[0_0_12px_rgba(14,165,233,0.3)]";
  const pctColor = cardComplete ? "text-emerald-500" : "text-primary";

  /* ── Handlers ── */
  async function handleCancel() {
    if (!sessionId || cancelling) return;
    setCancelling(true);
    setCancelError(null);
    try {
      await cancelTranslation(sessionId);
      resetTranslationState();
      setCurrentStep("ko_review");
    } catch (e) {
      setCancelError(
        `Cancel failed: ${e instanceof Error ? e.message : "Unknown error"}`,
      );
    } finally {
      setCancelling(false);
    }
  }

  async function handleFinalApproval(decision: "approved" | "rejected") {
    if (!sessionId) return;
    setSubmitError(null);

    if (decision === "approved") {
      // Optimistic UI: 즉시 DoneScreen으로 전환, 시트 쓰기는 백그라운드
      setIsWritingToSheet(true);
      setCurrentStep("done");
      approveFinal(sessionId, { decision })
        .then((res) => {
          setTranslationsApplied(res.translations_applied ?? false);
          setCellsUpdated(res.updates_count ?? 0);
        })
        .catch(() => {
          // DoneScreen에서 에러 상태 표시 (isWritingToSheet 유지하지 않음)
          setTranslationsApplied(false);
        })
        .finally(() => setIsWritingToSheet(false));
    } else {
      // Rejected — 시트 쓰기 없으므로 빠름, 동기 처리
      setSubmitting(true);
      try {
        await approveFinal(sessionId, { decision });
        setCurrentStep("done");
      } catch (e) {
        setSubmitError(
          `Final approval failed: ${e instanceof Error ? e.message : "Unknown error"}`,
        );
      } finally {
        setSubmitting(false);
      }
    }
  }

  function handleApproveAllPage() {
    for (const row of pageRows) {
      const dk = row.rowKey ?? `${row.key}_${row.lang}`;
      if (!reviewDecisions[dk]) setReviewDecision(dk, "accepted");
    }
  }

  /* ── Undecided count (변경된 항목만 대상) ── */
  const undecidedCount = useMemo(() => {
    return reviewResults.filter((r) => {
      const dk = r.row_index != null ? `${r.row_index}_${r.lang}` : `${r.key}_${r.lang}`;
      const hasChange = r.old_translation !== r.translated;
      return hasChange && !reviewDecisions[dk];
    }).length;
  }, [reviewResults, reviewDecisions]);

  function handleBack() {
    setShowBackModal(true);
  }

  function handleConfirmClick() {
    if (undecidedCount > 0) {
      setShowUnconfirmedModal(true);
    } else {
      handleFinalApproval("approved");
    }
  }

  function doApproveWithAutoAccept() {
    // 미확인 항목을 모두 accepted로 설정
    for (const r of reviewResults) {
      const dk = `${r.key}_${r.lang}`;
      if (!reviewDecisions[dk]) setReviewDecision(dk, "accepted");
    }
    handleFinalApproval("approved");
  }

  function handleDiscard() {
    setShowDiscardModal(true);
  }

  const error = cancelError || submitError;

  /* ── Render ── */
  return (
    <>
      <main className="flex-1 overflow-y-auto p-4 md:p-8 pb-32">
        <div
          className={`mx-auto space-y-6 transition-[max-width] duration-500 ${
            mode === "review" ? "max-w-[1400px]" : "max-w-5xl"
          }`}
        >
          {/* ═══ Title Area — cross-fade (no height collapse) ═══ */}
          <div className="relative min-h-[72px]">
            {/* Translating Title */}
            <div
              className={`transition-opacity duration-400 ease-out ${
                mode === "translating"
                  ? "opacity-100"
                  : "opacity-0 pointer-events-none absolute inset-0"
              }`}
            >
              <div className="text-center">
                <h1 className="text-2xl font-bold text-text-main">
                  Translating...
                </h1>
                <p className="mt-2 text-sm text-text-muted">
                  AI is translating your content. This may take a few minutes.
                </p>
              </div>
            </div>

            {/* Review Title */}
            <div
              className={`transition-opacity duration-400 ease-out ${
                mode === "review"
                  ? "opacity-100"
                  : "opacity-0 pointer-events-none absolute inset-0"
              }`}
            >
              <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
                <div className="space-y-2">
                  <div className="flex items-center gap-3">
                    <h1 className="text-3xl font-bold text-text-main tracking-tight">
                      Translation Review
                    </h1>
                    <span className="px-3 py-1 rounded-full bg-primary-light text-primary-dark text-xs font-bold border border-primary/20">
                      Step 4 of 5
                    </span>
                  </div>
                  <p className="text-text-muted text-base max-w-2xl">
                    Review AI-generated translations against the source
                    (Korean). Confirm changes before exporting to game engine
                    format.
                  </p>
                </div>
                {sessionId && (
                  <a
                    href={getDownloadUrl(sessionId, "translation_report")}
                    className="hidden md:flex items-center gap-2 px-4 py-2.5 rounded-lg border border-border-subtle bg-white hover:bg-surface-pale text-text-muted hover:text-primary transition-colors duration-200 font-semibold text-sm shadow-sm h-10"
                  >
                    <span className="material-symbols-outlined text-xl" aria-hidden="true">
                      download
                    </span>
                    Download CSV Backup
                  </a>
                )}
              </div>
            </div>
          </div>

          {/* ═══ Progress Card (ALWAYS visible — never fades out) ═══ */}
          <section className="rounded-xl border border-border-subtle bg-bg-surface p-6 shadow-soft animate-fade-slide-up">
            <div className="flex items-center justify-between mb-3">
              <span className={`text-sm font-medium text-text-muted ${!cardComplete ? "animate-breathe" : ""}`} aria-live="polite">
                {cardLabel}
              </span>
              <span
                className={`text-2xl font-bold tabular-nums ${pctColor}`}
              >
                {animPct}%
              </span>
            </div>
            <div className="relative w-full overflow-hidden rounded-full bg-slate-100 h-3.5" role="progressbar" aria-valuenow={cardPercent} aria-valuemin={0} aria-valuemax={100} aria-label="번역 진행률">
              <div
                className={`absolute top-0 left-0 h-full rounded-full transition-all duration-700 ease-out ${barColor} ${barShadow}`}
                style={{ width: `${cardPercent}%` }}
              />
              {cardPercent > 0 && cardPercent < 100 && (
                <div
                  className="absolute inset-0 animate-shimmer"
                  style={{
                    background:
                      "linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.35) 50%, transparent 100%)",
                    width: `${cardPercent}%`,
                  }}
                />
              )}
              {cardComplete && (
                <div
                  className="absolute inset-0 animate-shimmer-once"
                  style={{
                    background:
                      "linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.5) 50%, transparent 100%)",
                  }}
                />
              )}
            </div>

            {/* ETA hint (translating mode only) */}
            {mode === "translating" && !cardComplete && (
              <p className="mt-2 text-xs text-text-muted text-center">
                {(() => {
                  const rows = originalRows.length || 1;
                  const langs = availableLangs.length || 1;
                  const translateMin = Math.ceil((rows * langs) / 25) * 0.5;
                  const reviewMin = Math.ceil((rows * langs) / 25) * 0.5;
                  const totalMin = Math.ceil(translateMin + reviewMin);
                  return totalMin <= 1
                    ? "약 1분 이내 소요 예상"
                    : `약 ${totalMin}분 소요 예상`;
                })()}
              </p>
            )}

            {/* Grid-collapse: summary stats (review mode only) */}
            <div
              className="grid transition-[grid-template-rows] duration-500 ease-out"
              style={{ gridTemplateRows: mode === "review" ? "1fr" : "0fr" }}
            >
              <div className="overflow-hidden">
                {mode === "review" && (
                  <div className="mt-4 pt-3 border-t border-border-subtle grid grid-cols-2 md:grid-cols-4 gap-4">
                    {[
                      { icon: "translate", iconColor: "text-primary", label: "Total Strings", value: String(reviewResults.length), valueColor: "text-text-main" },
                      { icon: "swap_horiz", iconColor: "text-emerald-500", label: "Changed", value: String(changedCount), valueColor: "text-emerald-600" },
                      { icon: "horizontal_rule", iconColor: "text-slate-400", label: "Unchanged", value: String(unchangedCount), valueColor: "text-slate-400" },
                      { icon: "paid", iconColor: "text-amber-500", label: "Est. Cost", value: `$${costSummary?.estimated_cost_usd?.toFixed(4) ?? "\u2014"}`, valueColor: "text-text-main" },
                    ].map((stat) => (
                      <div
                        key={stat.label}
                        className="rounded-xl border border-border-subtle bg-bg-surface p-4 shadow-soft"
                      >
                        <div className="flex items-center gap-2 mb-2">
                          <span className={`material-symbols-outlined text-lg ${stat.iconColor}`} aria-hidden="true">
                            {stat.icon}
                          </span>
                          <span className="text-xs font-medium text-text-muted">
                            {stat.label}
                          </span>
                        </div>
                        <span className={`text-2xl font-bold tabular-nums ${stat.valueColor}`}>
                          {stat.value}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Agent pipeline — instant render (no slide animation) */}
            {mode === "translating" && agentPhase !== "init" && (
              <div className="mt-4 pt-3 border-t border-border-subtle flex items-center justify-center gap-3">
                {/* Translator */}
                <div
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg border transition-all duration-500 ${
                    agentPhase === "translator"
                      ? "border-primary bg-primary-light/60 shadow-sm"
                      : agentPhase === "reviewer" ||
                          agentPhase === "complete"
                        ? "border-emerald-200 bg-emerald-50/60"
                        : "border-border-subtle bg-slate-50"
                  }`}
                >
                  <span
                    className={`material-symbols-outlined text-lg ${
                      agentPhase === "translator"
                        ? "text-primary animate-spin360"
                        : agentPhase === "reviewer" ||
                            agentPhase === "complete"
                          ? "text-emerald-500"
                          : "text-text-muted"
                    }`}
                    aria-hidden="true"
                  >
                    {agentPhase === "translator"
                      ? "progress_activity"
                      : agentPhase === "reviewer" ||
                          agentPhase === "complete"
                        ? "check_circle"
                        : "circle"}
                  </span>
                  <span
                    className={`text-xs font-semibold ${
                      agentPhase === "translator"
                        ? "text-primary-dark"
                        : agentPhase === "reviewer" ||
                            agentPhase === "complete"
                          ? "text-emerald-600"
                          : "text-text-muted"
                    }`}
                  >
                    Translator
                  </span>
                </div>

                <span
                  className={`material-symbols-outlined text-lg transition-colors duration-500 ${
                    agentPhase === "reviewer" || agentPhase === "complete"
                      ? "text-emerald-400"
                      : "text-slate-300"
                  }`}
                  aria-hidden="true"
                >
                  arrow_forward
                </span>

                {/* Reviewer */}
                <div
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg border transition-all duration-500 ${
                    agentPhase === "reviewer"
                      ? "border-primary bg-primary-light/60 shadow-sm"
                      : agentPhase === "complete"
                        ? "border-emerald-200 bg-emerald-50/60"
                        : "border-border-subtle bg-slate-50"
                  }`}
                >
                  <span
                    className={`material-symbols-outlined text-lg ${
                      agentPhase === "reviewer"
                        ? "text-primary animate-spin360"
                        : agentPhase === "complete"
                          ? "text-emerald-500"
                          : "text-text-muted"
                    }`}
                    aria-hidden="true"
                  >
                    {agentPhase === "reviewer"
                      ? "progress_activity"
                      : agentPhase === "complete"
                        ? "check_circle"
                        : "circle"}
                  </span>
                  <span
                    className={`text-xs font-semibold ${
                      agentPhase === "reviewer"
                        ? "text-primary-dark"
                        : agentPhase === "complete"
                          ? "text-emerald-600"
                          : "text-text-muted"
                    }`}
                  >
                    Reviewer
                  </span>
                </div>

                <span
                  className={`material-symbols-outlined text-lg transition-colors duration-500 ${
                    agentPhase === "complete"
                      ? "text-emerald-400"
                      : "text-slate-300"
                  }`}
                  aria-hidden="true"
                >
                  arrow_forward
                </span>

                {/* Complete */}
                <div
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg border transition-all duration-500 ${
                    agentPhase === "complete"
                      ? "border-emerald-200 bg-emerald-50/60 shadow-sm"
                      : "border-border-subtle bg-slate-50"
                  }`}
                >
                  <span
                    className={`material-symbols-outlined text-lg ${
                      agentPhase === "complete"
                        ? "text-emerald-500"
                        : "text-text-muted"
                    }`}
                    aria-hidden="true"
                  >
                    {agentPhase === "complete" ? "check_circle" : "circle"}
                  </span>
                  <span
                    className={`text-xs font-semibold ${
                      agentPhase === "complete"
                        ? "text-emerald-600"
                        : "text-text-muted"
                    }`}
                  >
                    Complete
                  </span>
                </div>
              </div>
            )}
          </section>

          {/* ═══ Error Banner ═══ */}
          {error && (
            <div className="flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 animate-fade-slide-down">
              <span className="material-symbols-outlined text-lg animate-shake" aria-hidden="true">
                error
              </span>
              {error}
              <button
                type="button"
                onClick={() => {
                  setCancelError(null);
                  setSubmitError(null);
                }}
                className="ml-auto text-red-400 hover:text-red-600"
                aria-label="오류 닫기"
              >
                <span className="material-symbols-outlined text-lg" aria-hidden="true">
                  close
                </span>
              </button>
            </div>
          )}

          {/* ═══ Data Table ═══ */}
          {mode === "translating" && originalRows.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 gap-4">
              <span className="material-symbols-outlined text-5xl text-primary animate-spin360" aria-hidden="true">
                progress_activity
              </span>
              <p className="text-sm text-text-muted animate-breathe">
                Preparing translation...
              </p>
            </div>
          ) : (
            <div className="flex flex-col min-h-[500px] animate-fade-slide-up">
              <div className="w-full bg-white border border-border-subtle rounded-xl overflow-hidden flex flex-col shadow-md h-full">
                {/* Toolbar */}
                <div className="p-4 border-b border-border-subtle bg-surface-pale/50 flex flex-wrap justify-between items-center gap-4">
                  <div className="flex items-center gap-4">
                    {/* Language tabs */}
                    {availableLangs.length > 0 && (
                      <div className="flex items-center gap-1" role="tablist" aria-label="언어 선택">
                        <span className="text-xs font-medium text-text-muted mr-2">
                          Language:
                        </span>
                        {availableLangs.map((lang) => (
                          <button
                            type="button"
                            role="tab"
                            aria-selected={lang === activeLang}
                            key={lang}
                            onClick={() => {
                              setSelectedLang(lang);
                              setPage(1);
                            }}
                            className={`px-3 py-1 rounded-full text-xs font-semibold transition-all duration-200 ${
                              lang === activeLang
                                ? "bg-primary text-white shadow-sm"
                                : "text-text-muted hover:bg-slate-100"
                            }`}
                          >
                            {TARGET_LANG_LABELS[lang as TargetLang] ?? lang.toUpperCase()}
                          </button>
                        ))}
                      </div>
                    )}

                    <div className="h-6 w-[1px] bg-border-subtle" />

                    {mode === "review" ? (
                      <>
                        <h3 className="text-text-main font-bold text-lg hidden sm:block">
                          Review Drafts
                        </h3>
                        <span className="bg-white px-2 py-0.5 rounded text-xs text-text-muted border border-border-subtle font-medium shadow-sm">
                          {unifiedRows.length} Strings
                        </span>
                      </>
                    ) : (
                      <span className="text-xs text-text-muted tabular-nums">
                        {translationMap.size}/{originalRows.length} translated
                      </span>
                    )}
                  </div>

                  <div className="flex gap-3 items-center">
                    {/* Pagination */}
                    <div className="flex items-center bg-white rounded-lg border border-border-subtle p-0.5 shadow-sm">
                      <button
                        type="button"
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                        disabled={page <= 1}
                        className="w-8 h-8 flex items-center justify-center rounded text-text-muted hover:text-primary hover:bg-surface-pale transition-colors duration-200 active:scale-[0.95] disabled:opacity-30"
                        aria-label="이전 페이지"
                      >
                        <span className="material-symbols-outlined text-xl" aria-hidden="true">
                          chevron_left
                        </span>
                      </button>
                      <span className="text-sm text-text-main font-bold px-3 min-w-[80px] text-center">
                        {page} / {totalPages}
                      </span>
                      <button
                        type="button"
                        onClick={() =>
                          setPage((p) => Math.min(totalPages, p + 1))
                        }
                        disabled={page >= totalPages}
                        className="w-8 h-8 flex items-center justify-center rounded text-text-muted hover:text-primary hover:bg-surface-pale transition-colors duration-200 active:scale-[0.95] disabled:opacity-30"
                        aria-label="다음 페이지"
                      >
                        <span className="material-symbols-outlined text-xl" aria-hidden="true">
                          chevron_right
                        </span>
                      </button>
                    </div>

                    {/* Approve All (review mode) */}
                    {mode === "review" && (
                      <button
                        type="button"
                        onClick={handleApproveAllPage}
                        className="flex items-center gap-2 px-3 py-2 rounded-lg bg-primary-light/50 border border-primary/20 text-primary-dark text-xs font-bold hover:bg-primary-light transition-colors duration-200 shadow-sm uppercase tracking-wide"
                      >
                        <span className="material-symbols-outlined text-base" aria-hidden="true">
                          done_all
                        </span>
                        Approve Page
                      </button>
                    )}
                  </div>
                </div>

                {/* Completion banner (translating, 100%) — grid-collapse for smooth height */}
                <div
                  className="grid transition-[grid-template-rows] duration-300 ease-out"
                  style={{ gridTemplateRows: mode === "translating" && isComplete ? "1fr" : "0fr" }}
                >
                  <div className="overflow-hidden">
                    <div className="flex items-center gap-3 px-5 py-3 bg-emerald-50 border-b border-emerald-200 animate-fade-slide-down">
                      <span className="material-symbols-outlined text-emerald-600 animate-bounce-in" aria-hidden="true">
                        check_circle
                      </span>
                      <span className="text-sm font-semibold text-emerald-700">
                        Translation complete — moving to review
                      </span>
                    </div>
                  </div>
                </div>

                {/* Grid header */}
                <div className={`grid gap-4 px-6 py-3 bg-surface-pale border-b border-border-subtle text-xs font-bold text-text-muted uppercase tracking-wider sticky top-0 z-10 ${
                  mode === "review" ? "grid-cols-12" : "grid-cols-12"
                }`}>
                  <div className="col-span-1">AI Note</div>
                  <div className={mode === "review" ? "col-span-3" : "col-span-3"}>Source (KR)</div>
                  {mode === "review" && (
                    <div className="col-span-3">Previous Translation</div>
                  )}
                  <div className={mode === "review" ? "col-span-3" : "col-span-6"}>
                    {mode === "review" ? "New Translation" : "Translation"}
                  </div>
                  <div className="col-span-2 text-center">
                    {mode === "review" ? "Action" : "Status"}
                  </div>
                </div>

                {/* Rows */}
                <div className="overflow-y-auto custom-scrollbar flex-1 bg-white min-h-[400px]">
                  {pageRows.map((row) => {
                    const rowKey = row.rowKey ?? `${row.key}_${row.lang}`;
                    const isFailed = row.rowStatus === "failed";
                    const isUnchanged = mode === "review" && row.isDone && !row.hasChange && !isFailed;

                    // Drip-feed row animation (translating mode only)
                    let showRowAnim = false;
                    if (mode === "translating" && row.isDone) {
                      if (!doneIndicesRef.current.has(rowKey)) {
                        doneIndicesRef.current.add(rowKey);
                        showRowAnim = true;
                      }
                    }

                    return (
                      <div
                        key={rowKey}
                        className={`grid grid-cols-12 gap-4 px-6 py-5 border-b border-surface-pale items-center hover:bg-surface-pale/30 transition-all duration-200 group ${
                          isFailed ? "bg-red-50/60" : isUnchanged ? "opacity-45 hover:opacity-100" : ""
                        } ${showRowAnim ? "animate-row-fade-in" : ""}`}
                      >
                        {/* AI Note */}
                        <div className="col-span-1 relative">
                          {row.reason ? (
                            <>
                              <button
                                type="button"
                                onClick={() =>
                                  setExpandedNote(
                                    expandedNote === rowKey ? null : rowKey,
                                  )
                                }
                                className={`flex items-center gap-1.5 px-2 py-1.5 rounded-md text-xs font-semibold transition-all duration-200 w-fit ${
                                  row.hasChange
                                    ? "text-primary-dark bg-primary-light/50 border border-primary/10 hover:bg-primary-light"
                                    : "text-text-muted hover:text-primary hover:bg-primary-light/50"
                                }`}
                              >
                                <span className="material-symbols-outlined text-lg" aria-hidden="true">
                                  sticky_note_2
                                </span>
                                {mode === "review" && (
                                  <span className="hidden xl:inline">Note</span>
                                )}
                              </button>
                              {expandedNote === rowKey && (
                                <div className="absolute left-0 top-full mt-1 z-20 w-80 p-3 rounded-lg bg-white border border-border-subtle shadow-lg text-xs text-text-main leading-relaxed animate-popover-in">
                                  {row.reason}
                                </div>
                              )}
                            </>
                          ) : row.isDone ? (
                            <span className="text-gray-300 text-xs">
                              &mdash;
                            </span>
                          ) : null}
                        </div>

                        {/* Source KR */}
                        <div className={`${mode === "review" ? "col-span-3" : "col-span-3"} text-text-main text-sm font-medium leading-relaxed`}>
                          <span className="line-clamp-2">
                            {row.original_ko}
                          </span>
                        </div>

                        {/* Previous Translation (review mode only) */}
                        {mode === "review" && (
                          <div className="col-span-3">
                            {row.old_translation ? (
                              isUnchanged ? (
                                <span className="text-text-muted text-sm leading-relaxed line-clamp-2">
                                  {row.old_translation}
                                </span>
                              ) : (
                                <span className="text-diff-removed-text bg-diff-removed-bg/40 px-1.5 py-0.5 rounded text-sm leading-relaxed line-through decoration-diff-removed-text/40 line-clamp-2">
                                  {row.old_translation}
                                </span>
                              )
                            ) : row.isDone ? (
                              <span className="text-text-muted text-sm italic opacity-60">
                                No previous translation
                              </span>
                            ) : (
                              <span className="text-gray-300">&mdash;</span>
                            )}
                          </div>
                        )}

                        {/* Translation / New Translation */}
                        <div className={`${mode === "review" ? "col-span-3" : "col-span-6"} text-sm leading-relaxed`}>
                          {row.isDone ? (
                            mode === "review" && row.hasChange && row.old_translation ? (
                              <span className="text-text-main line-clamp-2">
                                {highlightDiff(
                                  row.old_translation,
                                  row.translated,
                                )}
                              </span>
                            ) : (
                              <span
                                className={
                                  row.hasChange
                                    ? "text-text-main"
                                    : mode === "review" ? "text-text-muted" : "text-text-main"
                                }
                              >
                                <span className={mode === "review" ? "line-clamp-2" : "line-clamp-3"}>
                                  {row.translated}
                                </span>
                              </span>
                            )
                          ) : (
                            <span className="text-gray-300">&mdash;</span>
                          )}
                        </div>

                        {/* Action / Status */}
                        <div className="col-span-2 flex justify-center">
                          {mode === "review" ? (
                            row.rowStatus === "failed" ? (
                              <span className="inline-flex items-center gap-1 rounded-full border border-red-400 bg-red-50 px-2.5 py-0.5 text-xs font-medium text-red-600">
                                <span className="material-symbols-outlined text-sm" aria-hidden="true">
                                  error
                                </span>
                                검수실패
                              </span>
                            ) : row.hasChange ? (
                              <div className="flex gap-2 opacity-40 group-hover:opacity-100 transition-opacity">
                                <button
                                  type="button"
                                  onClick={() =>
                                    setReviewDecision(rowKey, "accepted")
                                  }
                                  className={`w-9 h-9 flex items-center justify-center rounded-full transition-colors duration-200 ${
                                    reviewDecisions[rowKey] === "accepted"
                                      ? "bg-primary text-white"
                                      : "bg-surface-pale text-text-muted hover:text-white hover:bg-primary"
                                  }`}
                                  aria-label="번역 수락"
                                >
                                  <span className="material-symbols-outlined text-xl" aria-hidden="true">
                                    check
                                  </span>
                                </button>
                                <button
                                  type="button"
                                  onClick={() =>
                                    setReviewDecision(rowKey, "rejected")
                                  }
                                  className={`w-9 h-9 flex items-center justify-center rounded-full transition-colors duration-200 ${
                                    reviewDecisions[rowKey] === "rejected"
                                      ? "bg-red-500 text-white"
                                      : "bg-surface-pale text-text-muted hover:text-white hover:bg-red-500"
                                  }`}
                                  aria-label="번역 거부"
                                >
                                  <span className="material-symbols-outlined text-xl" aria-hidden="true">
                                    close
                                  </span>
                                </button>
                              </div>
                            ) : (
                              <span className="inline-flex items-center gap-1 rounded-full border border-emerald-400 bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-600">
                                <span className="material-symbols-outlined text-sm" aria-hidden="true">
                                  check
                                </span>
                                OK
                              </span>
                            )
                          ) : row.rowStatus === "pending" ? (
                            <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-xs font-medium text-slate-400 animate-breathe">
                              <span className="material-symbols-outlined text-sm" aria-hidden="true">
                                hourglass_empty
                              </span>
                              Pending
                            </span>
                          ) : row.rowStatus === "translating" ? (
                            <span className="inline-flex items-center gap-1 rounded-full border border-primary/20 bg-primary-light/50 px-2.5 py-0.5 text-xs font-medium text-primary animate-breathe">
                              <span className="material-symbols-outlined text-sm animate-spin360" aria-hidden="true">
                                progress_activity
                              </span>
                              Translating
                            </span>
                          ) : row.rowStatus === "translated" ? (
                            <span className="inline-flex items-center gap-1 rounded-full border border-primary/20 bg-primary-light px-2.5 py-0.5 text-xs font-medium text-primary-dark animate-badge-enter">
                              <span className="material-symbols-outlined text-sm" aria-hidden="true">
                                check
                              </span>
                              Translated
                            </span>
                          ) : row.rowStatus === "reviewing" ? (
                            <span className="inline-flex items-center gap-1 rounded-full border border-amber-400 bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-600 animate-breathe">
                              <span className="material-symbols-outlined text-sm animate-spin360" aria-hidden="true">
                                progress_activity
                              </span>
                              Reviewing
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 rounded-full border border-emerald-400 bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-600 animate-badge-enter">
                              <span className="material-symbols-outlined text-sm" aria-hidden="true">
                                check
                              </span>
                              Reviewed
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Table footer */}
                <div className="p-3 bg-surface-pale/50 border-t border-border-subtle text-center text-xs text-text-muted font-medium">
                  Showing{" "}
                  {Math.min((page - 1) * PAGE_SIZE + 1, unifiedRows.length)}-
                  {Math.min(page * PAGE_SIZE, unifiedRows.length)} of{" "}
                  {unifiedRows.length} entries
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* ═══ Footer ═══ */}
      {mode === "translating" ? (
        <Footer
          showCancel
          onCancel={cancelling ? undefined : handleCancel}
          actionLabel={cancelling ? "Cancelling..." : "Translating..."}
          actionDisabled
        />
      ) : (
        <Footer
          onBack={handleBack}
          onAction={handleConfirmClick}
          actionLabel={submitting ? "Processing..." : "Confirm & Push to Sheet"}
          actionIcon="cloud_upload"
          actionDisabled={submitting}
          showDiscard
          onDiscard={handleDiscard}
        />
      )}

      {/* ═══ Modals ═══ */}
      <ConfirmModal
        open={showBackModal}
        onClose={() => setShowBackModal(false)}
        onConfirm={() => { setShowBackModal(false); reset(); }}
        title="작업을 중단하시겠습니까?"
        description="진행 중인 모든 내용이 초기화됩니다. 계속하시겠습니까?"
        confirmLabel="확인"
        cancelLabel="취소"
        variant="warning"
      />
      <ConfirmModal
        open={showUnconfirmedModal}
        onClose={() => setShowUnconfirmedModal(false)}
        onConfirm={() => { setShowUnconfirmedModal(false); doApproveWithAutoAccept(); }}
        title="Unconfirmed Items Detected"
        description={
          <>
            미확인 항목이 <strong>{undecidedCount}건</strong> 있습니다.
            진행하면 미확인 항목은 자동으로 <strong>'수락'</strong>됩니다.
          </>
        }
        confirmLabel="Confirm & Proceed"
        cancelLabel="Cancel"
        variant="warning"
      />
      <ConfirmModal
        open={showDiscardModal}
        onClose={() => setShowDiscardModal(false)}
        onConfirm={() => { setShowDiscardModal(false); reset(); }}
        title="변경사항을 폐기하시겠습니까?"
        description="모든 번역 결과가 삭제되고 시트에는 아무 변경도 적용되지 않습니다."
        confirmLabel="폐기하기"
        cancelLabel="취소"
        variant="danger"
      />
    </>
  );
}
