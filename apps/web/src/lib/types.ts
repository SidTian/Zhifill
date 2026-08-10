export type JobStatus = "pending" | "running" | "succeeded" | "failed";

export type FieldStatus =
  | "empty"
  | "suggested"
  | "confirmed"
  | "rejected"
  | "manual";

export type Locator =
  | { kind: "excel_cell"; sheet: string; row: number; col: number; merged_range?: string | null }
  | { kind: "word_cell"; table_index: number; row: number; col: number }
  | { kind: "word_bookmark"; name: string }
  | { kind: "pdf_acroform"; field_name: string }
  | { kind: "pdf_bbox"; page: number; x0: number; y0: number; x1: number; y1: number };

export type SourceRef = {
  doc_id: string | null;
  snippet: string;
  score: number | null;
};

export type FormField = {
  id: string;
  name: string;
  field_type: "text" | "date" | "number" | "single_choice" | "multi" | "other";
  value: string | null;
  original_value: string | null;
  required: boolean;
  confidence: number | null;
  sources: SourceRef[];
  status: FieldStatus;
  layout: "label_value" | "header_row_table";
  row_group_id: string | null;
  row_index: number | null;
  column_key: string | null;
  locator: Locator;
  notes: string | null;
};

export type KnowledgeDoc = {
  id: string;
  title: string;
  filename: string;
  media_type: string;
  status: JobStatus;
  updated_at: string;
  size: number;
};

export type FormJob = {
  id: string;
  title: string;
  filename: string;
  format: "docx" | "xlsx" | "pdf";
  status: JobStatus;
  created_at: string;
  step: "uploaded" | "parsed" | "filled" | "exported";
  fields: FormField[];
};

export type AppSettings = {
  llm_provider: "openai_compatible" | "ollama";
  llm_api_base: string;
  llm_api_key: string;
  llm_model: string;
  embedding_model: string;
  max_table_rows: number;
  mock_mode: boolean;
};

export type QueryHit = {
  snippet: string;
  doc_id: string;
  score: number;
};
