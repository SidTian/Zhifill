import type { AppSettings, FormField, FormJob, KnowledgeDoc } from "./types";

export const DEFAULT_SETTINGS: AppSettings = {
  llm_provider: "ollama",
  llm_api_base: "http://127.0.0.1:11434/v1",
  llm_api_key: "",
  llm_model: "qwen2.5:7b",
  embedding_model: "nomic-embed-text",
  max_table_rows: 50,
  mock_mode: true,
};

export const MOCK_KNOWLEDGE: KnowledgeDoc[] = [
  {
    id: "doc-resume-2024",
    title: "个人简历（2024）",
    filename: "resume_2024.pdf",
    media_type: "application/pdf",
    status: "succeeded",
    updated_at: "2026-08-08T10:20:00+08:00",
    size: 248320,
  },
  {
    id: "doc-id-scan",
    title: "身份证信息摘录",
    filename: "id_notes.md",
    media_type: "text/markdown",
    status: "succeeded",
    updated_at: "2026-08-07T16:05:00+08:00",
    size: 2048,
  },
  {
    id: "doc-work-cert",
    title: "在职证明",
    filename: "employment.docx",
    media_type:
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    status: "succeeded",
    updated_at: "2026-08-06T09:40:00+08:00",
    size: 51200,
  },
];

function field(
  partial: Omit<FormField, "sources" | "notes" | "original_value"> & {
    sources?: FormField["sources"];
    notes?: string | null;
    original_value?: string | null;
  },
): FormField {
  return {
    original_value: partial.original_value ?? null,
    sources: partial.sources ?? [],
    notes: partial.notes ?? null,
    ...partial,
  };
}

export const MOCK_FIELDS_FILLED: FormField[] = [
  field({
    id: "f-name",
    name: "姓名",
    field_type: "text",
    value: "田思德",
    required: true,
    confidence: 0.96,
    status: "suggested",
    layout: "label_value",
    row_group_id: null,
    row_index: null,
    column_key: null,
    locator: { kind: "word_cell", table_index: 0, row: 1, col: 1 },
    sources: [
      {
        doc_id: "doc-resume-2024",
        snippet: "姓名：田思德；性别：男；手机：138****6600",
        score: 0.91,
      },
    ],
  }),
  field({
    id: "f-id",
    name: "身份证号",
    field_type: "text",
    value: "110101199001011234",
    required: true,
    confidence: 0.88,
    status: "suggested",
    layout: "label_value",
    row_group_id: null,
    row_index: null,
    column_key: null,
    locator: { kind: "word_cell", table_index: 0, row: 1, col: 3 },
    sources: [
      {
        doc_id: "doc-id-scan",
        snippet: "公民身份号码 110101199001011234",
        score: 0.84,
      },
    ],
  }),
  field({
    id: "f-phone",
    name: "手机号",
    field_type: "text",
    value: "13800136600",
    required: true,
    confidence: 0.82,
    status: "suggested",
    layout: "label_value",
    row_group_id: null,
    row_index: null,
    column_key: null,
    locator: { kind: "word_cell", table_index: 0, row: 2, col: 1 },
    sources: [
      {
        doc_id: "doc-resume-2024",
        snippet: "联系电话：13800136600",
        score: 0.79,
      },
    ],
  }),
  field({
    id: "f-company",
    name: "工作单位",
    field_type: "text",
    value: "智填科技有限公司",
    required: false,
    confidence: 0.77,
    status: "suggested",
    layout: "label_value",
    row_group_id: null,
    row_index: null,
    column_key: null,
    locator: { kind: "word_cell", table_index: 0, row: 3, col: 1 },
    sources: [
      {
        doc_id: "doc-work-cert",
        snippet: "兹证明田思德同志现任职于智填科技有限公司",
        score: 0.8,
      },
    ],
  }),
  field({
    id: "f-title",
    name: "职务",
    field_type: "text",
    value: "软件工程师",
    required: false,
    confidence: 0.74,
    status: "suggested",
    layout: "label_value",
    row_group_id: null,
    row_index: null,
    column_key: null,
    locator: { kind: "word_cell", table_index: 0, row: 3, col: 3 },
    sources: [
      {
        doc_id: "doc-resume-2024",
        snippet: "职位：软件工程师",
        score: 0.72,
      },
    ],
  }),
  field({
    id: "f-edu-school",
    name: "毕业院校",
    field_type: "text",
    value: null,
    required: false,
    confidence: 0,
    status: "empty",
    layout: "label_value",
    row_group_id: null,
    row_index: null,
    column_key: null,
    locator: { kind: "word_cell", table_index: 1, row: 1, col: 1 },
    notes: "图谱无充分证据，保持空值",
  }),
  // multi-row table sample
  field({
    id: "f-exp-0-org",
    name: "经历-单位",
    field_type: "text",
    value: "智填科技有限公司",
    required: false,
    confidence: 0.8,
    status: "suggested",
    layout: "header_row_table",
    row_group_id: "exp",
    row_index: 0,
    column_key: "org",
    locator: { kind: "word_cell", table_index: 2, row: 1, col: 0 },
    sources: [
      {
        doc_id: "doc-work-cert",
        snippet: "任职于智填科技有限公司",
        score: 0.78,
      },
    ],
  }),
  field({
    id: "f-exp-0-role",
    name: "经历-职位",
    field_type: "text",
    value: "软件工程师",
    required: false,
    confidence: 0.79,
    status: "suggested",
    layout: "header_row_table",
    row_group_id: "exp",
    row_index: 0,
    column_key: "role",
    locator: { kind: "word_cell", table_index: 2, row: 1, col: 1 },
  }),
  field({
    id: "f-exp-0-period",
    name: "经历-起止",
    field_type: "text",
    value: "2022-07 至今",
    required: false,
    confidence: 0.7,
    status: "suggested",
    layout: "header_row_table",
    row_group_id: "exp",
    row_index: 0,
    column_key: "period",
    locator: { kind: "word_cell", table_index: 2, row: 1, col: 2 },
  }),
  field({
    id: "f-exp-1-org",
    name: "经历-单位",
    field_type: "text",
    value: "某互联网公司",
    required: false,
    confidence: 0.65,
    status: "suggested",
    layout: "header_row_table",
    row_group_id: "exp",
    row_index: 1,
    column_key: "org",
    locator: { kind: "word_cell", table_index: 2, row: 2, col: 0 },
  }),
  field({
    id: "f-exp-1-role",
    name: "经历-职位",
    field_type: "text",
    value: "实习开发",
    required: false,
    confidence: 0.62,
    status: "suggested",
    layout: "header_row_table",
    row_group_id: "exp",
    row_index: 1,
    column_key: "role",
    locator: { kind: "word_cell", table_index: 2, row: 2, col: 1 },
  }),
  field({
    id: "f-exp-1-period",
    name: "经历-起止",
    field_type: "text",
    value: "2021-06 ~ 2021-09",
    required: false,
    confidence: 0.6,
    status: "suggested",
    layout: "header_row_table",
    row_group_id: "exp",
    row_index: 1,
    column_key: "period",
    locator: { kind: "word_cell", table_index: 2, row: 2, col: 2 },
  }),
];

export const MOCK_JOBS: FormJob[] = [
  {
    id: "job-demo-001",
    title: "入职信息登记表",
    filename: "onboarding_form.docx",
    format: "docx",
    status: "succeeded",
    created_at: "2026-08-10T09:30:00+08:00",
    step: "filled",
    fields: structuredClone(MOCK_FIELDS_FILLED),
  },
  {
    id: "job-demo-002",
    title: "项目申报表（未填写）",
    filename: "project_apply.xlsx",
    format: "xlsx",
    status: "succeeded",
    created_at: "2026-08-09T15:10:00+08:00",
    step: "parsed",
    fields: [
      field({
        id: "p-title",
        name: "项目名称",
        field_type: "text",
        value: null,
        required: true,
        confidence: null,
        status: "empty",
        layout: "label_value",
        row_group_id: null,
        row_index: null,
        column_key: null,
        locator: { kind: "excel_cell", sheet: "Sheet1", row: 2, col: 2 },
      }),
      field({
        id: "p-owner",
        name: "负责人",
        field_type: "text",
        value: null,
        required: true,
        confidence: null,
        status: "empty",
        layout: "label_value",
        row_group_id: null,
        row_index: null,
        column_key: null,
        locator: { kind: "excel_cell", sheet: "Sheet1", row: 3, col: 2 },
      }),
    ],
  },
];

export const MOCK_QUERY_ANSWERS: Record<string, { answer: string; hits: { snippet: string; doc_id: string; score: number }[] }> = {
  default: {
    answer:
      "根据知识库：姓名田思德，手机 13800136600，现任职智填科技有限公司软件工程师。",
    hits: [
      {
        doc_id: "doc-resume-2024",
        snippet: "姓名：田思德……职位：软件工程师……电话：13800136600",
        score: 0.89,
      },
      {
        doc_id: "doc-work-cert",
        snippet: "现任职于智填科技有限公司",
        score: 0.81,
      },
    ],
  },
};

export function delay(ms = 600): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString("zh-CN");
  } catch {
    return iso;
  }
}

export function confidenceLabel(c: number | null): string {
  if (c == null) return "—";
  if (c >= 0.85) return "高";
  if (c >= 0.6) return "中";
  if (c > 0) return "低";
  return "无";
}
