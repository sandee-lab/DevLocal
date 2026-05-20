import { create } from "zustand";
import type {
  AppStep,
  KoReviewItem,
  ReviewItem,
  FailedRow,
  CostSummary,
  OriginalRow,
  TranslationChunkItem,
  ChunkProgress,
} from "../types";

interface AppState {
  /* ── Connection ── */
  sheetUrl: string;
  sheetNames: string[];
  botEmail: string;
  selectedSheet: string;
  mode: "A" | "B";
  rowLimit: number;

  /* ── Project ── */
  projectName: string;

  /* ── Session ── */
  sessionId: string | null;
  currentStep: AppStep;
  previousStep: AppStep | null;

  /* ── KR Review (HITL 1) ── */
  koReviewResults: KoReviewItem[];
  koDecisions: Record<string, "accepted" | "rejected">;

  /* ── Translation / Review (HITL 2) ── */
  reviewResults: ReviewItem[];
  reviewDecisions: Record<string, "accepted" | "rejected">;
  failedRows: FailedRow[];
  selectedLang: string;
  reviewPage: number;

  /* ── Chunk Streaming (실시간 진행) ── */
  originalRows: OriginalRow[];
  partialKoResults: KoReviewItem[];
  partialTranslations: TranslationChunkItem[];
  partialReviews: ReviewItem[];
  chunkProgress: ChunkProgress | null;

  /* ── Metrics ── */
  costSummary: CostSummary | null;
  totalRows: number;
  cellsUpdated: number;

  /* ── Logs ── */
  logs: string[];
  progressPercent: number;
  progressLabel: string;

  /* ── SSE Connection ── */
  sseStatus: "connected" | "reconnecting" | "disconnected";
  lastHeartbeatAt: number | null;

  /* ── Settings ── */
  settingsOpen: boolean;
  glossary: Record<string, Record<string, string>>;
  customPrompts: Record<string, string>;

  /* ── Help ── */
  helpOpen: boolean;

  /* ── All Sheets Mode ── */
  allSheetsMode: boolean;
  sheetQueue: string[];
  currentSheetIndex: number;
  totalSheetCount: number;

  /* ── Done ── */
  translationsApplied: boolean;
  isWritingToSheet: boolean;

  /* ── Actions ── */
  setSheetUrl: (url: string) => void;
  setSheetNames: (names: string[]) => void;
  setBotEmail: (email: string) => void;
  setSelectedSheet: (name: string) => void;
  setProjectName: (name: string) => void;
  setMode: (mode: "A" | "B") => void;
  setRowLimit: (limit: number) => void;
  setSessionId: (id: string | null) => void;
  setCurrentStep: (step: AppStep) => void;
  setKoReviewResults: (results: KoReviewItem[]) => void;
  setKoDecision: (key: string, decision: "accepted" | "rejected") => void;
  setReviewResults: (results: ReviewItem[]) => void;
  setReviewDecision: (key: string, decision: "accepted" | "rejected") => void;
  setFailedRows: (rows: FailedRow[]) => void;
  setSelectedLang: (lang: string) => void;
  setReviewPage: (page: number) => void;
  setOriginalRows: (rows: OriginalRow[]) => void;
  appendPartialKoResults: (results: KoReviewItem[]) => void;
  appendPartialTranslations: (results: TranslationChunkItem[]) => void;
  appendPartialReviews: (results: ReviewItem[]) => void;
  setChunkProgress: (progress: ChunkProgress | null) => void;
  setCostSummary: (cost: CostSummary | null) => void;
  setTotalRows: (n: number) => void;
  setCellsUpdated: (n: number) => void;
  addLog: (log: string) => void;
  setLogs: (logs: string[]) => void;
  setProgress: (percent: number, label: string) => void;
  setSseStatus: (status: "connected" | "reconnecting" | "disconnected") => void;
  setLastHeartbeatAt: (ts: number | null) => void;
  setTranslationsApplied: (applied: boolean) => void;
  setIsWritingToSheet: (writing: boolean) => void;
  setSettingsOpen: (open: boolean) => void;
  setGlossary: (glossary: Record<string, Record<string, string>>) => void;
  setCustomPrompts: (prompts: Record<string, string>) => void;
  setHelpOpen: (open: boolean) => void;
  setAllSheetsMode: (on: boolean) => void;
  setSheetQueue: (queue: string[]) => void;
  advanceSheetQueue: () => void;
  resetTranslationState: () => void;
  reset: () => void;
}

const initialState = {
  sheetUrl: "",
  sheetNames: [] as string[],
  botEmail: "",
  selectedSheet: "",
  projectName: "",
  mode: "A" as const,
  rowLimit: 0,
  sessionId: null as string | null,
  currentStep: "idle" as AppStep,
  previousStep: null as AppStep | null,
  koReviewResults: [] as KoReviewItem[],
  koDecisions: {} as Record<string, "accepted" | "rejected">,
  reviewResults: [] as ReviewItem[],
  reviewDecisions: {} as Record<string, "accepted" | "rejected">,
  failedRows: [] as FailedRow[],
  selectedLang: "en",
  reviewPage: 1,
  originalRows: [] as OriginalRow[],
  partialKoResults: [] as KoReviewItem[],
  partialTranslations: [] as TranslationChunkItem[],
  partialReviews: [] as ReviewItem[],
  chunkProgress: null as ChunkProgress | null,
  costSummary: null as CostSummary | null,
  totalRows: 0,
  cellsUpdated: 0,
  logs: [] as string[],
  progressPercent: 0,
  progressLabel: "",
  sseStatus: "disconnected" as const,
  lastHeartbeatAt: null as number | null,
  settingsOpen: false,
  helpOpen: false,
  glossary: {} as Record<string, Record<string, string>>,
  customPrompts: {} as Record<string, string>,
  allSheetsMode: false,
  sheetQueue: [] as string[],
  currentSheetIndex: 0,
  totalSheetCount: 0,
  translationsApplied: false,
  isWritingToSheet: false,
};

export const useAppStore = create<AppState>((set) => ({
  ...initialState,

  setSheetUrl: (url) => set({ sheetUrl: url }),
  setSheetNames: (names) => set({ sheetNames: names }),
  setBotEmail: (email) => set({ botEmail: email }),
  setSelectedSheet: (name) => set({ selectedSheet: name }),
  setProjectName: (name) => set({ projectName: name }),
  setMode: (mode) => set({ mode }),
  setRowLimit: (limit) => set({ rowLimit: limit }),
  setSessionId: (id) => {
    set({ sessionId: id });
    if (id) localStorage.setItem("devlocal_session_id", id);
    else localStorage.removeItem("devlocal_session_id");
  },
  setCurrentStep: (step) =>
    set((s) => ({
      currentStep: step,
      previousStep: s.currentStep,
      // translating 진입 시 progress 리셋 + 스트리밍 데이터 초기화
      ...(step === "translating"
        ? {
            progressPercent: 0,
            progressLabel: "Starting translation...",
            partialTranslations: [],
            partialReviews: [],
          }
        : {}),
    })),
  setKoReviewResults: (results) => set({ koReviewResults: results }),
  setKoDecision: (key, decision) =>
    set((s) => ({ koDecisions: { ...s.koDecisions, [key]: decision } })),
  setReviewResults: (results) => set({ reviewResults: results }),
  setReviewDecision: (key, decision) =>
    set((s) => ({
      reviewDecisions: { ...s.reviewDecisions, [key]: decision },
    })),
  setFailedRows: (rows) => set({ failedRows: rows }),
  setSelectedLang: (lang) => set({ selectedLang: lang }),
  setReviewPage: (page) => set({ reviewPage: page }),
  setOriginalRows: (rows) => set({ originalRows: rows }),
  appendPartialKoResults: (results) =>
    set((s) => ({ partialKoResults: [...s.partialKoResults, ...results] })),
  appendPartialTranslations: (results) =>
    set((s) => ({ partialTranslations: [...s.partialTranslations, ...results] })),
  appendPartialReviews: (results) =>
    set((s) => ({ partialReviews: [...s.partialReviews, ...results] })),
  setChunkProgress: (progress) => set({ chunkProgress: progress }),
  setCostSummary: (cost) => set({ costSummary: cost }),
  setTotalRows: (n) => set({ totalRows: n }),
  setCellsUpdated: (n) => set({ cellsUpdated: n }),
  addLog: (log) => set((s) => ({ logs: [...s.logs, log] })),
  setLogs: (logs) => set({ logs }),
  setProgress: (percent, label) =>
    set({ progressPercent: percent, progressLabel: label }),
  setSseStatus: (status) => set({ sseStatus: status }),
  setLastHeartbeatAt: (ts) => set({ lastHeartbeatAt: ts }),
  setTranslationsApplied: (applied) => set({ translationsApplied: applied }),
  setIsWritingToSheet: (writing) => set({ isWritingToSheet: writing }),
  setSettingsOpen: (open) => set({ settingsOpen: open }),
  setHelpOpen: (open) => set({ helpOpen: open }),
  setGlossary: (glossary) => set({ glossary }),
  setCustomPrompts: (prompts) => set({ customPrompts: prompts }),
  setAllSheetsMode: (on) => set({ allSheetsMode: on }),
  setSheetQueue: (queue) => set({ sheetQueue: queue, currentSheetIndex: 0, totalSheetCount: queue.length }),
  advanceSheetQueue: () =>
    set((s) => ({ currentSheetIndex: s.currentSheetIndex + 1 })),
  resetTranslationState: () =>
    set({
      // KR Review (HITL 1)
      koReviewResults: [],
      koDecisions: {},
      partialKoResults: [],
      // Translation / Review (HITL 2)
      reviewResults: [],
      reviewDecisions: {},
      failedRows: [],
      partialTranslations: [],
      partialReviews: [],
      // Streaming & Metrics
      originalRows: [],
      chunkProgress: null,
      costSummary: null,
      cellsUpdated: 0,
      progressPercent: 0,
      progressLabel: "",
      translationsApplied: false,
      selectedLang: "en",
      reviewPage: 1,
    }),
  reset: () => {
    localStorage.removeItem("devlocal_session_id");
    set(initialState);
  },
}));
