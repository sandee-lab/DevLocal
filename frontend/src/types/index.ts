/* ── App Step (워크플로우 단계) ── */
export type AppStep =
  | "idle"
  | "loading"
  | "ko_review"
  | "translating"
  | "final_review"
  | "done";

/* ── API Request/Response ── */
export interface ConnectRequest {
  sheet_url: string;
}

export interface ConnectResponse {
  sheet_names: string[];
  bot_email: string;
  project_name?: string;
}

export interface StartRequest {
  sheet_url: string;
  sheet_name: string;
  mode: string;
  target_languages: string[];
  row_start: number;
  row_end: number;
}

export interface StartResponse {
  session_id: string;
}

export interface ApprovalRequest {
  decision: "approved" | "rejected";
}

export interface SessionStateResponse {
  session_id: string;
  current_step: string;
  ko_review_count: number;
  review_count: number;
  fail_count: number;
  cost_summary: CostSummary | null;
  logs: string[];
  // 세션 복원용
  ko_review_results?: KoReviewItem[] | null;
  review_results?: ReviewItem[] | null;
  failed_rows?: FailedRow[] | null;
  original_rows?: OriginalRow[] | null;
  total_rows?: number;
}

/* ── Domain Types ── */
export interface CostSummary {
  input_tokens: number;
  output_tokens: number;
  reasoning_tokens: number;
  cached_tokens: number;
  estimated_cost_usd: number;
}

export interface KoReviewItem {
  key: string;
  original: string;
  revised: string;
  comment: string;
  has_issue: boolean;
  row_index?: number;
}

export interface ReviewItem {
  key: string;
  lang: string;
  original_ko: string;
  old_translation: string;
  translated: string;
  reason: string;
  row_index?: number;
}

export interface FailedRow {
  key: string;
  lang: string;
  reason: string;
  row_index?: number;
}

/* ── SSE Event Types ── */
export type SSEEventType =
  | "node_update"
  | "ko_review_ready"
  | "final_review_ready"
  | "done"
  | "error"
  | "ping";

export interface NodeUpdateData {
  node: string;
  step: string;
  logs: string[];
}

export interface KoReviewReadyData {
  results: KoReviewItem[];
  count: number;
  report: Record<string, unknown>[] | null;
}

export interface FinalReviewReadyData {
  review_results: ReviewItem[];
  failed_rows: FailedRow[];
  report: Record<string, unknown>[] | null;
  cost: {
    input_tokens: number;
    output_tokens: number;
    reasoning_tokens?: number;
    cached_tokens?: number;
    estimated_cost_usd?: number;
  };
}

/* ── Chunk Streaming Types ── */
export interface OriginalRow {
  key: string;
  korean: string;
  row_index?: number;
}

export interface ChunkProgress {
  done: number;
  total: number;
  lang?: string;
}

export interface TranslationChunkItem {
  key: string;
  lang: string;
  translated: string;
  row_index?: number;
}

export interface KoReviewChunkData {
  chunk_results: KoReviewItem[];
  progress: ChunkProgress;
}

export interface TranslationChunkData {
  chunk_results: TranslationChunkItem[];
  progress: ChunkProgress;
}

export interface ReviewChunkData {
  chunk_results: ReviewItem[];
  progress: ChunkProgress;
}

/* ── Config ── */
export interface AppConfig {
  saved_url?: string;
  saved_sheet?: string;
  backup_folder?: string;
  bot_email?: string;
  glossary?: Record<string, Record<string, string>>;
  custom_prompts?: Record<string, string>;
  game_synopsis?: string;
  tone_and_manner?: string;
}
