/**
 * Glossary 공용 타입 + 경량 헬퍼 (xlsx 의존 없음 — 렌더 경로에서 동기 사용).
 * 무거운 파일 입출력(xlsx)은 ./glossaryFile.ts 에서 동적 import.
 */
export type Glossary = Record<string, Record<string, string>>;

export interface ImportStats {
  jaCount: number;
  enCount: number;
  skippedRows: number; // KO가 비어 건너뛴 데이터 행 수
}

export interface ImportResult {
  glossary: Glossary; // { ja, en } — 항상 두 키 모두 존재 (전체 교체용)
  stats: ImportStats;
}

/** KO 합집합 순서 (ja 먼저, 그다음 en 전용 키) 로 정렬된 키 목록 반환 */
export function unifiedKeys(glossary: Glossary): string[] {
  const ja = glossary.ja ?? {};
  const en = glossary.en ?? {};
  const keys: string[] = [];
  const seen = new Set<string>();
  for (const k of [...Object.keys(ja), ...Object.keys(en)]) {
    if (!seen.has(k)) {
      seen.add(k);
      keys.push(k);
    }
  }
  return keys;
}
