/**
 * Glossary 공용 타입 + 경량 헬퍼 (xlsx 의존 없음 — 렌더 경로에서 동기 사용).
 * 무거운 파일 입출력(xlsx)은 ./glossaryFile.ts 에서 동적 import.
 */

/** 번역 대상 언어 — 언어 추가/제거 시 이 목록이 단일 출처 (UI·파서가 함께 따라온다) */
export const TARGET_LANGS = ["en", "ja", "zh-CN", "zh-TW"] as const;
export type TargetLang = (typeof TARGET_LANGS)[number];

/** UI 표시용 짧은 라벨 (단어집 파일 헤더 표기와 일치) */
export const TARGET_LANG_LABELS: Record<TargetLang, string> = {
  en: "EN",
  ja: "JA",
  "zh-CN": "CN",
  "zh-TW": "TW",
};

export type Glossary = Record<string, Record<string, string>>;

export interface ImportStats {
  counts: Record<TargetLang, number>; // 언어별 등록 항목 수
  skippedRows: number; // KO가 비어 건너뛴 데이터 행 수
}

export interface ImportResult {
  glossary: Glossary; // TARGET_LANGS 키 모두 존재 (전체 교체용)
  stats: ImportStats;
}

/** KO 합집합 키 목록 (TARGET_LANGS 순서대로 처음 등장한 순) */
export function unifiedKeys(glossary: Glossary): string[] {
  return [
    ...new Set(TARGET_LANGS.flatMap((lang) => Object.keys(glossary[lang] ?? {}))),
  ];
}
