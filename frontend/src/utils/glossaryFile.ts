/**
 * Glossary 파일 입출력 — .xlsx / .csv 파싱 + .xlsx 내보내기.
 *
 * xlsx(SheetJS)를 정적 import 하므로 이 모듈은 SettingsModal 에서
 * **동적 import** 로만 불러온다 (업로드/내보내기 시점에만 로드 → 초기 번들 경량화).
 *
 * 파일 양식: ko + 대상언어 열 (헤더 별칭·순서 자유, 대소문자·공백 무시).
 * 내부 저장 구조 { en: {ko→en}, ja: {ko→ja} } 로 변환한다.
 * 빈 칸은 해당 언어만 건너뛰고, KO가 빈 행은 통째로 건너뛴다.
 */
import * as XLSX from "xlsx";
import type { Glossary, ImportResult, TargetLang } from "./glossary";
import { TARGET_LANGS, unifiedKeys } from "./glossary";

// 헤더 별칭 (norm() 으로 정규화 후 비교) + 내보내기 시 헤더명
const KO_ALIASES = ["ko", "kor", "korean", "kr", "한국어", "원문", "source", "src"];
const TARGET_HEADERS: Record<TargetLang, { aliases: string[]; exportAs: string }> = {
  en: { aliases: ["en", "eng", "english", "영어", "영문"], exportAs: "en" },
  ja: { aliases: ["ja", "jp", "jpn", "jap", "japanese", "일본어", "일어"], exportAs: "jp" },
  "zh-CN": {
    aliases: ["cn", "zh-cn", "zhcn", "zh-hans", "schinese", "chinese_cn", "간체", "중국어간체", "简体", "简体中文"],
    exportAs: "cn",
  },
  "zh-TW": {
    aliases: ["tw", "zh-tw", "zhtw", "zh-hant", "tchinese", "chinese_tw", "번체", "중국어번체", "繁體", "繁体", "繁體中文"],
    exportAs: "tw",
  },
};

// 에러 문구용 대상언어 헤더 나열 (e.g. "en / jp / cn / tw")
const TARGET_HEADER_NAMES = TARGET_LANGS.map(
  (lang) => TARGET_HEADERS[lang].exportAs,
).join(" / ");

function norm(v: unknown): string {
  return String(v ?? "").trim().toLowerCase();
}

function findCol(headerRow: unknown[], aliases: string[]): number {
  return headerRow.findIndex((cell) => aliases.includes(norm(cell)));
}

function cellText(row: unknown[], idx: number): string {
  return String(row[idx] ?? "").trim();
}

/** 파일을 읽어 glossary 와 통계를 반환. 양식 오류 시 throw. */
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
  const targetIdx = {} as Record<TargetLang, number>;
  const scanLimit = Math.min(rows.length, 10);
  for (let i = 0; i < scanLimit; i++) {
    const k = findCol(rows[i], KO_ALIASES);
    if (k >= 0) {
      headerIdx = i;
      koIdx = k;
      for (const lang of TARGET_LANGS) {
        targetIdx[lang] = findCol(rows[i], TARGET_HEADERS[lang].aliases);
      }
      break;
    }
  }

  if (koIdx < 0) {
    throw new Error(
      `ko 헤더 열을 찾을 수 없습니다. 첫 행에 ko / ${TARGET_HEADER_NAMES} 헤더가 있는지 확인하세요.`,
    );
  }
  if (TARGET_LANGS.every((lang) => targetIdx[lang] < 0)) {
    throw new Error(
      `대상 언어 헤더 열(${TARGET_HEADER_NAMES})을 찾을 수 없습니다. 최소 한 개의 대상 언어 열이 필요합니다.`,
    );
  }

  const glossary: Glossary = {};
  for (const lang of TARGET_LANGS) glossary[lang] = {};
  let skippedRows = 0;

  for (let i = headerIdx + 1; i < rows.length; i++) {
    const ko = cellText(rows[i], koIdx);
    if (!ko) {
      skippedRows++;
      continue;
    }
    for (const lang of TARGET_LANGS) {
      if (targetIdx[lang] < 0) continue;
      const v = cellText(rows[i], targetIdx[lang]);
      if (v) glossary[lang][ko] = v;
    }
  }

  const counts = {} as Record<TargetLang, number>;
  for (const lang of TARGET_LANGS) {
    counts[lang] = Object.keys(glossary[lang]).length;
  }
  return { glossary, stats: { counts, skippedRows } };
}

/** 현재 glossary 를 ko + 대상언어 열 .xlsx 로 내보내기 (비어 있으면 헤더만 = 템플릿). */
export function exportGlossaryFile(glossary: Glossary): void {
  const aoa: string[][] = [
    ["ko", ...TARGET_LANGS.map((lang) => TARGET_HEADERS[lang].exportAs)],
  ];
  for (const ko of unifiedKeys(glossary)) {
    aoa.push([ko, ...TARGET_LANGS.map((lang) => glossary[lang]?.[ko] ?? "")]);
  }
  const ws = XLSX.utils.aoa_to_sheet(aoa);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Glossary");
  XLSX.writeFile(wb, "glossary.xlsx");
}
