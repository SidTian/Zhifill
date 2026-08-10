/** 后端 API 客户端（上传落盘等） */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

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
