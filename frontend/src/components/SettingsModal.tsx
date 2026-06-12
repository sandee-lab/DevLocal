import { useState, useEffect, useMemo, useRef } from "react";
import { useAppStore } from "../store/useAppStore";
import { getConfig, saveConfig } from "../api/client";
import { useFocusTrap } from "../hooks/useFocusTrap";
import { TARGET_LANGS, TARGET_LANG_LABELS, unifiedKeys } from "../utils/glossary";
import type { Glossary, TargetLang } from "../utils/glossary";

type Tab = "prompting" | "glossary";

type EntryDraft = Record<"ko" | TargetLang, string>;
const EMPTY_ENTRY: EntryDraft = { ko: "", en: "", ja: "", "zh-CN": "", "zh-TW": "" };
const ADD_FIELDS: { key: keyof EntryDraft; label: string; placeholder: string }[] = [
  { key: "ko", label: "Source (KO)", placeholder: "e.g., 전설" },
  { key: "en", label: "EN", placeholder: "e.g., Legend" },
  { key: "ja", label: "JA", placeholder: "e.g., 伝説" },
  { key: "zh-CN", label: "CN (간체)", placeholder: "e.g., 传说" },
  { key: "zh-TW", label: "TW (번체)", placeholder: "e.g., 傳說" },
];

export default function SettingsModal() {
  const open = useAppStore((s) => s.settingsOpen);
  const setOpen = useAppStore((s) => s.setSettingsOpen);
  const selectedSheet = useAppStore((s) => s.selectedSheet);
  const customPrompts = useAppStore((s) => s.customPrompts);
  const setGlossary = useAppStore((s) => s.setGlossary);
  const setCustomPrompts = useAppStore((s) => s.setCustomPrompts);

  const [tab, setTab] = useState<Tab>("prompting");
  const [synopsisText, setSynopsisText] = useState("");
  const [toneText, setToneText] = useState("");
  const [promptText, setPromptText] = useState("");
  const [localGlossary, setLocalGlossary] = useState<Glossary>({});
  const [newEntry, setNewEntry] = useState<EntryDraft>(EMPTY_ENTRY);
  const [importError, setImportError] = useState("");
  const [importNotice, setImportNotice] = useState("");
  const [saving, setSaving] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const backdropRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useFocusTrap(panelRef, open);

  // Load config when modal opens
  useEffect(() => {
    if (!open) {
      setLoaded(false);
      return;
    }
    getConfig()
      .then((cfg) => {
        const g = cfg.glossary ?? {};
        const p = cfg.custom_prompts ?? {};
        setLocalGlossary(g);
        setGlossary(g);
        setCustomPrompts(p);
        setSynopsisText(cfg.game_synopsis ?? "");
        setToneText(cfg.tone_and_manner ?? "");
        setPromptText(selectedSheet ? p[selectedSheet] ?? "" : "");
        setLoaded(true);
      })
      .catch(() => setLoaded(true));
  }, [open]);

  // Update prompt text when sheet changes while modal is open
  useEffect(() => {
    if (open && loaded) {
      setPromptText(selectedSheet ? customPrompts[selectedSheet] ?? "" : "");
    }
  }, [selectedSheet, open, loaded]);

  // KO 합집합 기준 통합 행 — 인라인 편집 키 입력마다 재계산하지 않도록 memo
  const rows = useMemo(
    () =>
      unifiedKeys(localGlossary).map((ko) => {
        const row = { ko } as { ko: string } & Record<TargetLang, string>;
        for (const lang of TARGET_LANGS) row[lang] = localGlossary[lang]?.[ko] ?? "";
        return row;
      }),
    [localGlossary],
  );

  if (!open) return null;

  function handleAddEntry() {
    const ko = newEntry.ko.trim();
    if (!ko || TARGET_LANGS.every((lang) => !newEntry[lang].trim())) return; // KO 필수 + 최소 한 개 대상언어
    setLocalGlossary((prev) => {
      const next = { ...prev };
      for (const lang of TARGET_LANGS) {
        next[lang] = { ...prev[lang] };
        const v = newEntry[lang].trim();
        if (v) next[lang][ko] = v;
        else delete next[lang][ko];
      }
      return next;
    });
    setNewEntry(EMPTY_ENTRY);
  }

  function handleDeleteEntry(ko: string) {
    setLocalGlossary((prev) => {
      const next = { ...prev };
      for (const lang of TARGET_LANGS) {
        next[lang] = { ...prev[lang] };
        delete next[lang][ko];
      }
      return next;
    });
  }

  // 인라인 편집 — 대상언어 셀 값 변경. 빈 값이면 해당 언어 키 제거.
  function handleEditTarget(ko: string, lang: TargetLang, value: string) {
    setLocalGlossary((prev) => {
      const langMap = { ...(prev[lang] ?? {}) };
      if (value.trim()) langMap[ko] = value;
      else delete langMap[ko];
      return { ...prev, [lang]: langMap };
    });
  }

  async function handleExport() {
    const { exportGlossaryFile } = await import("../utils/glossaryFile");
    exportGlossaryFile(localGlossary);
  }

  async function handleFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (e.target) e.target.value = ""; // 같은 파일 재선택 허용
    if (!file) return;
    setImportError("");
    setImportNotice("");
    try {
      const { parseGlossaryFile } = await import("../utils/glossaryFile");
      const { glossary, stats } = await parseGlossaryFile(file);
      const warnings = TARGET_LANGS.filter((lang) => stats.counts[lang] === 0).map(
        (lang) =>
          `⚠ ${TARGET_LANG_LABELS[lang]} 0개 — 기존 ${TARGET_LANG_LABELS[lang]} 단어집이 모두 사라집니다.`,
      );
      const summary =
        "불러오기: " +
        TARGET_LANGS.map((lang) => `${TARGET_LANG_LABELS[lang]} ${stats.counts[lang]}개`).join(" · ") +
        (stats.skippedRows ? ` · 한국어 빈 행 ${stats.skippedRows}개 건너뜀` : "");
      const ok = window.confirm(
        `${summary}\n\n현재 단어집을 이 내용으로 전체 교체합니다. 계속할까요?` +
          (warnings.length ? `\n\n${warnings.join("\n")}` : ""),
      );
      if (!ok) return;
      setLocalGlossary(glossary);
      setImportNotice(`${summary} — 저장하려면 [Save Settings]를 누르세요.`);
    } catch (err) {
      setImportError(
        err instanceof Error ? err.message : "파일을 읽을 수 없습니다.",
      );
    }
  }

  async function handleSave() {
    setSaving(true);
    const updatedPrompts = { ...customPrompts };
    if (selectedSheet) {
      if (promptText.trim()) {
        updatedPrompts[selectedSheet] = promptText.trim();
      } else {
        delete updatedPrompts[selectedSheet];
      }
    }
    try {
      await saveConfig({
        glossary: localGlossary,
        custom_prompts: updatedPrompts,
        game_synopsis: synopsisText.trim() || undefined,
        tone_and_manner: toneText.trim() || undefined,
      });
      setGlossary(localGlossary);
      setCustomPrompts(updatedPrompts);
      setOpen(false);
    } catch {
      // silent — config save is non-critical
    } finally {
      setSaving(false);
    }
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
        aria-labelledby="settings-modal-title"
        className="w-full max-w-4xl mx-4 bg-white rounded-2xl shadow-2xl border border-slate-200 flex flex-col max-h-[85vh] animate-fade-slide-up"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-8 pt-7 pb-2">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-primary text-2xl" aria-hidden="true">
              tune
            </span>
            <h2 id="settings-modal-title" className="text-xl font-bold text-text-main">
              Custom Instructions & Glossary
            </h2>
          </div>
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="p-2 text-text-muted hover:text-text-main hover:bg-slate-100 rounded-lg transition-colors"
          >
            <span className="material-symbols-outlined text-xl" aria-hidden="true">close</span>
          </button>
        </div>

        {/* No sheet selected — gate */}
        {!selectedSheet ? (
          <div className="flex-1 flex flex-col items-center justify-center px-8 py-16 text-center">
            <span className="material-symbols-outlined text-5xl text-slate-300 mb-4" aria-hidden="true">
              table_chart
            </span>
            <p className="text-base font-semibold text-text-main mb-1">
              No sheet selected
            </p>
            <p className="text-sm text-text-muted max-w-xs">
              Connect to a Google Sheet and select a tab first, then come back
              to configure prompts and glossary.
            </p>
          </div>
        ) : (
        <>
        {/* Tabs */}
        <div className="px-8 pt-4 pb-2">
          <div className="flex bg-slate-100/80 rounded-xl p-1.5 border border-slate-200" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={tab === "prompting"}
              onClick={() => setTab("prompting")}
              className={`flex-1 py-2.5 text-sm font-semibold rounded-lg transition-all duration-200 ${
                tab === "prompting"
                  ? "bg-white text-primary shadow-sm"
                  : "text-slate-500 hover:text-text-main"
              }`}
            >
              AI Prompting
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === "glossary"}
              onClick={() => setTab("glossary")}
              className={`flex-1 py-2.5 text-sm font-semibold rounded-lg transition-all duration-200 ${
                tab === "glossary"
                  ? "bg-white text-primary shadow-sm"
                  : "text-slate-500 hover:text-text-main"
              }`}
            >
              Glossary
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-8 py-5" role="tabpanel">
          {tab === "prompting" && (
            <div className="space-y-5">
              {/* Game Synopsis */}
              <div>
                <h3 className="text-base font-semibold text-text-main">
                  Game Synopsis
                </h3>
                <p className="text-sm text-text-muted mt-1">
                  Describe the game world, story, and key characters. This
                  context helps the AI understand the game and translate
                  accordingly.
                </p>
              </div>
              <textarea
                value={synopsisText}
                onChange={(e) => setSynopsisText(e.target.value)}
                placeholder="E.g., A space adventure game where Robot 404 delivers packages across the galaxy..."
                className="w-full h-28 rounded-xl border border-slate-200 bg-white p-4 text-sm text-text-main placeholder:text-slate-400 focus:ring-2 focus:ring-primary focus:border-transparent resize-none transition-all"
              />

              {/* Tone & Manner */}
              <div>
                <h3 className="text-base font-semibold text-text-main">
                  Tone & Manner
                </h3>
                <p className="text-sm text-text-muted mt-1">
                  Define the overall translation style and voice.
                </p>
              </div>
              <textarea
                value={toneText}
                onChange={(e) => setToneText(e.target.value)}
                placeholder="E.g., Humorous and casual tone. Avoid overly formal language..."
                className="w-full h-16 rounded-xl border border-slate-200 bg-white p-4 text-sm text-text-main placeholder:text-slate-400 focus:ring-2 focus:ring-primary focus:border-transparent resize-none transition-all"
              />

              {/* Custom Instructions (per sheet) */}
              <div>
                <h3 className="text-base font-semibold text-text-main">
                  Custom AI Instructions
                </h3>
                <p className="text-sm text-text-muted mt-1">
                  Additional rules for the AI translator, specific to this
                  sheet.
                  {selectedSheet && (
                    <span className="ml-1 text-primary font-medium">
                      ({selectedSheet})
                    </span>
                  )}
                </p>
              </div>
              <textarea
                value={promptText}
                onChange={(e) => setPromptText(e.target.value)}
                placeholder="E.g., Translate with a medieval fantasy tone. Use formal pronouns for characters. Avoid modern slang..."
                className="w-full h-28 rounded-xl border border-slate-200 bg-white p-4 text-sm text-text-main placeholder:text-slate-400 focus:ring-2 focus:ring-primary focus:border-transparent resize-none transition-all"
              />
              <div className="flex items-start gap-2 text-xs text-text-muted bg-blue-50/50 p-3 rounded-lg border border-blue-100/50">
                <span className="material-symbols-outlined text-sm text-primary mt-0.5" aria-hidden="true">
                  info
                </span>
                <span>
                  Synopsis and Tone are global settings shared across all
                  sheets. Custom Instructions are saved per sheet tab.
                </span>
              </div>
            </div>
          )}

          {tab === "glossary" && (
            <div className="space-y-5">
              <div>
                <h3 className="text-base font-semibold text-text-main">
                  Translation Glossary
                </h3>
                <p className="text-sm text-text-muted mt-1">
                  Define fixed translations for specific terms. These are
                  enforced during translation and post-processing.
                </p>
              </div>

              {/* Bulk import / export toolbar */}
              <div className="flex flex-wrap items-center gap-2 bg-slate-50 border border-slate-200 rounded-xl p-3">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".xlsx,.xls,.csv"
                  onChange={handleFileSelected}
                  className="hidden"
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="inline-flex items-center gap-1.5 px-3.5 py-2 text-sm font-semibold rounded-lg bg-primary text-white hover:bg-primary-dark transition-colors shadow-sm"
                >
                  <span className="material-symbols-outlined text-base" aria-hidden="true">
                    upload_file
                  </span>
                  {"\uD30C\uC77C \uC5C5\uB85C\uB4DC (.xlsx/.csv)"}
                </button>
                <button
                  type="button"
                  onClick={handleExport}
                  className="inline-flex items-center gap-1.5 px-3.5 py-2 text-sm font-medium rounded-lg bg-white border border-slate-200 text-text-muted hover:text-text-main hover:border-slate-300 transition-colors"
                >
                  <span className="material-symbols-outlined text-base" aria-hidden="true">
                    download
                  </span>
                  {"\uB0B4\uBCF4\uB0B4\uAE30 / \uD15C\uD50C\uB9BF"}
                </button>
                <span className="text-xs text-text-muted ml-auto">
                  {"ko / en / jp / cn / tw 5\uC5F4 \u00B7 \uBE48 \uCE78\uC740 \uBB34\uC2DC \u00B7 \uC5C5\uB85C\uB4DC \uC2DC \uC804\uCCB4 \uAD50\uCCB4"}
                </span>
              </div>

              {importError && (
                <div className="flex items-start gap-2 text-xs text-red-600 bg-red-50 p-3 rounded-lg border border-red-100">
                  <span className="material-symbols-outlined text-sm mt-0.5" aria-hidden="true">
                    error
                  </span>
                  <span>{importError}</span>
                </div>
              )}
              {importNotice && (
                <div className="flex items-start gap-2 text-xs text-emerald-700 bg-emerald-50 p-3 rounded-lg border border-emerald-100">
                  <span className="material-symbols-outlined text-sm mt-0.5" aria-hidden="true">
                    check_circle
                  </span>
                  <span>{importNotice}</span>
                </div>
              )}

              {/* Add new entry \u2014 KO / EN / JA */}
              <div className="flex gap-2 items-end">
                {ADD_FIELDS.map((f) => (
                  <div key={f.key} className="flex-1">
                    <label className="block text-xs font-medium text-text-muted mb-1.5">
                      {f.label}
                    </label>
                    <input
                      type="text"
                      value={newEntry[f.key]}
                      onChange={(e) =>
                        setNewEntry((prev) => ({ ...prev, [f.key]: e.target.value }))
                      }
                      onKeyDown={(e) => e.key === "Enter" && handleAddEntry()}
                      placeholder={f.placeholder}
                      className="w-full rounded-lg border border-slate-200 bg-white py-2.5 px-3 text-sm text-text-main placeholder:text-slate-400 focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                    />
                  </div>
                ))}
                <button
                  type="button"
                  onClick={handleAddEntry}
                  disabled={
                    !newEntry.ko.trim() ||
                    TARGET_LANGS.every((lang) => !newEntry[lang].trim())
                  }
                  className="shrink-0 p-2.5 rounded-lg bg-primary text-white hover:bg-primary-dark disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  <span className="material-symbols-outlined text-lg" aria-hidden="true">add</span>
                </button>
              </div>

              {/* Glossary table \u2014 unified KO / EN / JA */}
              {rows.length > 0 ? (
                <div className="border border-slate-200 rounded-xl overflow-hidden">
                  <table className="w-full text-sm table-fixed">
                    <thead>
                      <tr className="bg-slate-50 border-b border-slate-200">
                        <th scope="col" className="text-left py-2.5 px-4 font-semibold text-text-muted text-xs uppercase tracking-wider w-1/4">
                          Source (KO)
                        </th>
                        {TARGET_LANGS.map((lang) => (
                          <th key={lang} scope="col" className="text-left py-2.5 px-4 font-semibold text-text-muted text-xs uppercase tracking-wider">
                            {TARGET_LANG_LABELS[lang]}
                          </th>
                        ))}
                        <th scope="col" className="w-12" />
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row) => (
                        <tr
                          key={row.ko}
                          className="border-b border-slate-100 last:border-0 hover:bg-slate-50/50 transition-colors"
                        >
                          <td className="py-1.5 px-4 text-text-main font-medium break-words">
                            {row.ko}
                          </td>
                          {TARGET_LANGS.map((lang) => (
                            <td key={lang} className="py-1.5 px-2">
                              <input
                                type="text"
                                value={row[lang]}
                                onChange={(e) =>
                                  handleEditTarget(row.ko, lang, e.target.value)
                                }
                                placeholder={"\u2014"}
                                className="w-full rounded-md border border-transparent bg-transparent py-1.5 px-2 text-sm text-text-main hover:border-slate-200 focus:bg-white focus:border-primary focus:ring-1 focus:ring-primary transition-all"
                              />
                            </td>
                          ))}
                          <td className="py-1.5 px-2 text-center">
                            <button
                              type="button"
                              onClick={() => handleDeleteEntry(row.ko)}
                              className="p-1 text-slate-400 hover:text-red-500 rounded transition-colors"
                            >
                              <span className="material-symbols-outlined text-base" aria-hidden="true">
                                delete
                              </span>
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-center py-10 text-text-muted text-sm border border-dashed border-slate-200 rounded-xl">
                  <span className="material-symbols-outlined text-3xl text-slate-300 mb-2 block" aria-hidden="true">
                    book_2
                  </span>
                  {"\uB2E8\uC5B4\uC9D1\uC774 \uBE44\uC5B4 \uC788\uC2B5\uB2C8\uB2E4."}
                  <br />
                  {"\uD30C\uC77C\uC744 \uC5C5\uB85C\uB4DC\uD558\uAC70\uB098 \uC704\uC5D0\uC11C \uC9C1\uC811 \uCD94\uAC00\uD558\uC138\uC694."}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-8 py-5 border-t border-slate-100">
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="px-6 py-2.5 text-sm font-medium text-text-muted hover:text-text-main transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="px-6 py-2.5 text-sm font-bold text-white bg-primary hover:bg-primary-dark rounded-xl transition-colors disabled:opacity-50 shadow-sm"
          >
            {saving ? "Saving..." : "Save Settings"}
          </button>
        </div>
        </>
        )}
      </div>
    </div>
  );
}
