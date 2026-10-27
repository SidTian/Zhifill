/** 后端 API 客户端（上传落盘等） */

import type { FormField, FormJob } from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

/** 与 packages/contracts Settings 对齐 */
export type ApiSettings = {
  llm_provider: "openai_compatible" | "ollama";
  llm_api_base: string;
  llm_api_key: string | null;
  llm_model: string;
  embedding_model: string;
  extract_model?: string | null;
  query_model?: string | null;
  max_table_rows: number;
  summary_language?: string;
};

export type KnowledgeUploadResult = {
  id: string;
  title: string;
  filename: string;
  media_type: string;
  format?: string;
  status: string;
  size: number;
  sha256?: string;
  path?: string;
  created_at?: string;
  updated_at?: string;
  note?: string;
  ingest_status?: string;
  graph_status?: string;
};

export type FormUploadResult = {
  id: string;
  title: string;
  filename: string;
  media_type: string;
  format: "docx" | "xlsx" | "pdf" | string;
  status: string;
  step: string;
  size: number;
  sha256?: string;
  path?: string;
  created_at?: string;
  updated_at?: string;
  fields?: unknown[];
  structure_notes?: string[];
  task_spec?: FormJob["task_spec"];
  note?: string;
};

async function parseError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") return data.detail;
    if (data?.detail?.message) return data.detail.message;
    if (data?.message) return data.message;
    return JSON.stringify(data);
  } catch {
    return res.statusText || `HTTP ${res.status}`;
  }
}

export async function getHealth(): Promise<{
  status: string;
  phase?: string;
  version?: string;
}> {
  const res = await fetch(`${API_BASE}/api/health`, { cache: "no-store" });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function uploadKnowledge(
  file: File,
  docId?: string,
): Promise<KnowledgeUploadResult> {
  const fd = new FormData();
  fd.append("file", file);
  if (docId) fd.append("doc_id", docId);
  const res = await fetch(`${API_BASE}/api/knowledge/upload`, {
    method: "POST",
    body: fd,
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function queryKnowledgeRemote(query: string): Promise<{
  answer: string;
  contexts: {
    content: string;
    doc_id: string | null;
    score: number | null;
  }[];
}> {
  const res = await fetch(`${API_BASE}/api/knowledge/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function listKnowledgeRemote(): Promise<KnowledgeUploadResult[]> {
  const res = await fetch(`${API_BASE}/api/knowledge`, { cache: "no-store" });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function deleteKnowledgeRemote(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/knowledge/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(await parseError(res));
}

export async function fillFormFieldRemote(
  id: string,
  fieldId: string,
): Promise<FormField> {
  const res = await fetch(
    `${API_BASE}/api/forms/jobs/${encodeURIComponent(id)}/fill?field_id=${encodeURIComponent(fieldId)}`,
    { method: "POST" },
  );
  if (!res.ok) throw new Error(await parseError(res));
  const body = await res.json();
  return (body.field ?? body) as FormField;
}

export async function patchFormFieldsRemote(
  id: string,
  fields: FormField[],
): Promise<FormUploadResult> {
  const res = await fetch(`${API_BASE}/api/forms/jobs/${encodeURIComponent(id)}/fields`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fields }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function downloadFilledForm(id: string): Promise<{ filename: string; blob: Blob }> {
  const exported = await fetch(`${API_BASE}/api/forms/jobs/${encodeURIComponent(id)}/export`, {
    method: "POST",
  });
  if (!exported.ok) throw new Error(await parseError(exported));
  const meta = await exported.json();
  const res = await fetch(`${API_BASE}/api/forms/jobs/${encodeURIComponent(id)}/download`);
  if (!res.ok) throw new Error(await parseError(res));
  const blob = await res.blob();
  return { filename: String(meta.download_name || "form.filled"), blob };
}

export async function uploadForm(file: File): Promise<FormUploadResult> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${API_BASE}/api/forms/upload`, {
    method: "POST",
    body: fd,
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function listFormJobsRemote(): Promise<FormUploadResult[]> {
  const res = await fetch(`${API_BASE}/api/forms/jobs`, { cache: "no-store" });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function deleteFormJobRemote(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/forms/jobs/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
  if (res.status === 404) return;
  if (!res.ok) throw new Error(await parseError(res));
}

export async function getSettingsRemote(): Promise<ApiSettings> {
  const res = await fetch(`${API_BASE}/api/settings`, { cache: "no-store" });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function putSettingsRemote(
  body: ApiSettings,
): Promise<ApiSettings> {
  const res = await fetch(`${API_BASE}/api/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}
