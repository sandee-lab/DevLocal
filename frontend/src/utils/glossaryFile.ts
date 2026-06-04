/**
 * Glossary 파일 입출력 — .xlsx / .csv 파싱 + .xlsx 내보내기.
 *
 * xlsx(SheetJS)를 정적 import 하므로 이 모듈은 SettingsModal 에서
 * **동적 import** 로만 불러온다 (업로드/내보내기 시점에만 로드 → 초기 번들 경량화).
 *
 * 파일 양식: ko / en / jp 3열 (헤더 별칭·순서 자유, 대소문자·공백 무시).
 * 내부 저장 구조 { ja: {ko→ja}, en: {ko→en} } 로 변환한다.
 * 빈 칸은 해당 언어만 건너뛰고, KO가 빈 행은 통째로 건너뛴다.
 */
import * as XLSX from "xlsx";
import type { Glossary, ImportResult } from "./glossary";
import { unifiedKeys } from "./glossary";

// 헤더 별칭 (norm() 으로 정규화 후 비교)
const KO_ALIASES = ["ko", "kor", "korean", "kr", "한국어", "원문", "source", "src"];
const EN_ALIASES = ["en", "eng", "english", "영어", "영문"];
const JA_ALIASES = ["ja", "jp", "jpn", "jap", "japanese", "일본어", "일어"];

function norm(v: unknown): string {
  return String(v ?? "").trim().toLowerCase();
}

function findCol(headerRow: unknown[], aliases: string[]): number {
  return headerRow.findIndex((cell) => aliases.includes(norm(cell)));
}

/** 파일을 읽어 { ja, en } glossary 와 통계를 반환. 양식 오류 시 throw. */
export async function parseGlossaryFile(file: File): Promise<ImportResult> {
  // CSV는 텍스트로 읽어 UTF-8 디코딩 (array 로 읽으면 SheetJS가 Latin1 로 오인 → 한글 깨짐).
  // xlsx/xls 는 바이너리(zip) 이므로 arrayBuffer 로 읽는다.
  const isCsv =
    file.name.toLowerCase().endsWith(".csv") || file.type === "text/csv";
  const wb = isCsv
    ? XLSX.read(await file.text(), { type: "string" })
    : XLSX.read(await file.arrayBuffer(), { type: "array" });
  const sheetName = wb.SheetNames[0];
  if (!sheetName) {
    throw new Error("파일에 시트가 없습니다.");
  }
  const sheet = wb.Sheets[sheetName];
  const rows = XLSX.utils.sheet_to_json<unknown[]>(sheet, {
    header: 1,
    defval: "",
    blankrows: false,
    raw: false,
  });

  // 헤더 행 탐색 — 앞쪽 10행 내에서 ko 열을 가진 첫 행을 헤더로 사용
  let headerIdx = -1;
  let koIdx = -1;
  let enIdx = -1;
  let jaIdx = -1;
  const scanLimit = Math.min(rows.length, 10);
  for (let i = 0; i < scanLimit; i++) {
    const k = findCol(rows[i], KO_ALIASES);
    if (k >= 0) {
      headerIdx = i;
      koIdx = k;
      enIdx = findCol(rows[i], EN_ALIASES);
      jaIdx = findCol(rows[i], JA_ALIASES);
      break;
    }
  }

  if (koIdx < 0) {
    throw new Error(
      "ko 헤더 열을 찾을 수 없습니다. 첫 행에 ko / en / jp 헤더가 있는지 확인하세요.",
    );
  }
  if (enIdx < 0 && jaIdx < 0) {
    throw new Error(
      "en 또는 jp 헤더 열을 찾을 수 없습니다. 최소 한 개의 대상 언어 열이 필요합니다.",
    );
  }

  const ja: Record<string, string> = {};
  const en: Record<string, string> = {};
  let skippedRows = 0;

  for (let i = headerIdx + 1; i < rows.length; i++) {
    const row = rows[i];
    const ko = String(row[koIdx] ?? "").trim();
    if (!ko) {
      skippedRows++;
      continue;
    }
    if (enIdx >= 0) {
      const v = String(row[enIdx] ?? "").trim();
      if (v) en[ko] = v;
    }
    if (jaIdx >= 0) {
      const v = String(row[jaIdx] ?? "").trim();
      if (v) ja[ko] = v;
    }
  }

  return {
    glossary: { ja, en },
    stats: {
      jaCount: Object.keys(ja).length,
      enCount: Object.keys(en).length,
      skippedRows,
    },
  };
}

/** 현재 glossary 를 ko/en/jp 3열 .xlsx 로 내보내기 (비어 있으면 헤더만 = 템플릿). */
export function exportGlossaryFile(glossary: Glossary): void {
  const ja = glossary.ja ?? {};
  const en = glossary.en ?? {};
  const aoa: string[][] = [["ko", "en", "jp"]];
  for (const ko of unifiedKeys(glossary)) {
    aoa.push([ko, en[ko] ?? "", ja[ko] ?? ""]);
  }
  const ws = XLSX.utils.aoa_to_sheet(aoa);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Glossary");
  XLSX.writeFile(wb, "glossary.xlsx");
}
