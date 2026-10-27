"use client";

import {
  deleteFormJobRemote,
  downloadFilledForm,
  fillFormFieldRemote,
  patchFormFieldsRemote,
  deleteKnowledgeRemote,
  getSettingsRemote,
  listFormJobsRemote,
  queryKnowledgeRemote,
  listKnowledgeRemote,
  putSettingsRemote,
  uploadForm as apiUploadForm,
  uploadKnowledge as apiUploadKnowledge,
  type ApiSettings,
} from "./api";
import {
  DEFAULT_SETTINGS,
  MOCK_FIELDS_FILLED,
  MOCK_JOBS,
  MOCK_KNOWLEDGE,
  delay,
} from "./mock-data";
import type {
  AppSettings,
  FormField,
  FormJob,
  KnowledgeDoc,
  QueryHit,
} from "./types";

const KEYS = {
  settings: "zhifill.mock.settings",
  knowledge: "zhifill.mock.knowledge",
  jobs: "zhifill.mock.jobs",
} as const;

const DRAFT_KEY = "zhifill.draft.job";

function read<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function write<T>(key: string, value: T): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(key, JSON.stringify(value));
}

function readDraft(): FormJob | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(DRAFT_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as FormJob;
  } catch {
    return null;
  }
}

function writeDraft(job: FormJob | null): void {
  if (typeof window === "undefined") return;
  if (!job) sessionStorage.removeItem(DRAFT_KEY);
  else sessionStorage.setItem(DRAFT_KEY, JSON.stringify(job));
}

function uid(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
}

function emptyFieldsFromTemplate(): FormField[] {
  return structuredClone(MOCK_FIELDS_FILLED).map((f) => ({
    ...f,
    value: null,
    confidence: null,
    status: "empty" as const,
    sources: [],
  }));
}

function mapFormat(fmt: string | undefined, filename: string): FormJob["format"] {
  const f = (fmt || filename.split(".").pop() || "docx").toLowerCase();
  if (f === "xlsx" || f === "xls") return "xlsx";
  if (f === "pdf") return "pdf";
  return "docx";
}

function toApiSettings(s: AppSettings): ApiSettings {
  return {
    llm_provider: s.llm_provider,
    llm_api_base: s.llm_api_base,
    llm_api_key: s.llm_api_key?.trim() ? s.llm_api_key : null,
    llm_model: s.llm_model,
    embedding_model: s.embedding_model,
    max_table_rows: s.max_table_rows,
    summary_language: "Chinese",
  };
}

function fromApiSettings(s: ApiSettings, mockMode = false): AppSettings {
  return {
    llm_provider: s.llm_provider,
    llm_api_base: s.llm_api_base,
    llm_api_key: s.llm_api_key ?? "",
    llm_model: s.llm_model,
    embedding_model: s.embedding_model,
    max_table_rows: s.max_table_rows ?? 50,
    mock_mode: mockMode,
  };
}

export const mockApi = {
  async getSettings(): Promise<AppSettings> {
    const localMock = read(KEYS.settings, {} as Partial<AppSettings>).mock_mode;
    try {
      const remote = await getSettingsRemote();
      return fromApiSettings(remote, Boolean(localMock));
    } catch {
      return { ...DEFAULT_SETTINGS, ...read(KEYS.settings, {}) };
    }
  },

  async saveSettings(next: AppSettings): Promise<AppSettings> {
    write(KEYS.settings, { mock_mode: next.mock_mode });
    try {
      const saved = await putSettingsRemote(toApiSettings(next));
      return fromApiSettings(saved, next.mock_mode);
    } catch (e) {
      write(KEYS.settings, next);
      throw e;
    }
  },

  listKnowledgeLocal(): KnowledgeDoc[] {
    return read(KEYS.knowledge, structuredClone(MOCK_KNOWLEDGE));
  },

  async listKnowledge(): Promise<KnowledgeDoc[]> {
    try {
      const remote = await listKnowledgeRemote();
      return remote.map((d) => ({
        id: d.id,
        title: d.title,
        filename: d.filename,
        media_type: d.media_type,
        status: d.status,
        updated_at: d.updated_at || d.created_at || new Date().toISOString(),
        size: d.size,
        path: d.path,
        sha256: d.sha256,
        note: d.note,
        ingest_status: d.ingest_status,
        graph_status: d.graph_status,
        source: "server" as const,
      }));
    } catch {
      return this.listKnowledgeLocal().map((d) => ({ ...d, source: "local" as const }));
    }
  },

  async uploadKnowledge(file: File): Promise<KnowledgeDoc> {
    try {
      const d = await apiUploadKnowledge(file);
      return {
        id: d.id,
        title: d.title,
        filename: d.filename,
        media_type: d.media_type,
        status: d.status,
        updated_at: d.updated_at || d.created_at || new Date().toISOString(),
        size: d.size,
        path: d.path,
        sha256: d.sha256,
        note: d.note,
        ingest_status: d.ingest_status,
        graph_status: d.graph_status,
        source: "server",
      };
    } catch (e) {
      // API 不可用时回退本地演示
      await delay(400);
      const docs = this.listKnowledgeLocal();
      const doc: KnowledgeDoc = {
        id: uid("doc"),
        title: file.name.replace(/\.[^.]+$/, ""),
        filename: file.name,
        media_type: file.type || "application/octet-stream",
        status: "succeeded",
        updated_at: new Date().toISOString(),
        size: file.size,
        source: "local",
        note: e instanceof Error ? `本地回退: ${e.message}` : "本地回退",
      };
      write(KEYS.knowledge, [doc, ...docs]);
      return doc;
    }
  },

  async deleteJob(id: string, source?: "server" | "local"): Promise<void> {
    if (source !== "local") {
      await deleteFormJobRemote(id);
    }
    write(
      KEYS.jobs,
      this.listJobsLocal().filter((j) => j.id !== id),
    );
  },

  async deleteKnowledge(id: string): Promise<void> {
    try {
      await deleteKnowledgeRemote(id);
      return;
    } catch {
      await delay(200);
      write(
        KEYS.knowledge,
        this.listKnowledgeLocal().filter((d) => d.id !== id),
      );
    }
  },

  async queryKnowledge(q: string): Promise<{ answer: string; hits: QueryHit[] }> {
    if (!q.trim()) {
      return { answer: "请输入问题。", hits: [] };
    }
    const res = await queryKnowledgeRemote(q.trim());
    return {
      answer: res.answer,
      hits: (res.contexts ?? []).map((item) => ({
        snippet: item.content,
        doc_id: item.doc_id ?? "",
        score: item.score ?? 0,
      })),
    };
  },

  listJobsLocal(): FormJob[] {
    return read(KEYS.jobs, structuredClone(MOCK_JOBS));
  },

  async listJobs(): Promise<FormJob[]> {
    const local = this.listJobsLocal();
    const localById = new Map(local.map((j) => [j.id, j]));
    try {
      const remote = await listFormJobsRemote();
      const fromServer: FormJob[] = remote.map((j) => {
        const prev = localById.get(j.id);
        return {
          id: j.id,
          title: j.title,
          filename: j.filename,
          format: mapFormat(j.format, j.filename),
          status: j.status,
          created_at: j.created_at || new Date().toISOString(),
          step: prev?.step || (j.step as FormJob["step"]) || "uploaded",
          fields: prev?.fields ?? (Array.isArray(j.fields) ? (j.fields as FormJob["fields"]) : []),
          path: j.path,
          sha256: j.sha256,
          size: j.size,
          note: j.note,
          structure_notes: j.structure_notes ?? prev?.structure_notes,
          task_spec: j.task_spec ?? prev?.task_spec,
          source: "server",
        };
      });
      // keep pure-local demo jobs not on server
      const serverIds = new Set(fromServer.map((j) => j.id));
      const localsOnly = local
        .filter((j) => !serverIds.has(j.id))
        .map((j) => ({ ...j, source: "local" as const }));
      return [...fromServer, ...localsOnly];
    } catch {
      return local.map((j) => ({ ...j, source: "local" as const }));
    }
  },

  getJob(id: string): FormJob | null {
    return this.listJobsLocal().find((j) => j.id === id) ?? null;
  },

  async getJobAsync(id: string): Promise<FormJob | null> {
    const jobs = await this.listJobs();
    const found = jobs.find((j) => j.id === id);
    if (found) return found;
    const draft = readDraft();
    return draft?.id === id ? draft : null;
  },

  async uploadForm(file: File): Promise<FormJob> {
    try {
      const j = await apiUploadForm(file);
      const job: FormJob = {
        id: j.id,
        title: j.title,
        filename: j.filename,
        format: mapFormat(j.format, j.filename),
        status: j.status,
        created_at: j.created_at || new Date().toISOString(),
        step: (j.step as FormJob["step"]) || "uploaded",
        fields: Array.isArray(j.fields) ? (j.fields as FormJob["fields"]) : [],
        path: j.path,
        sha256: j.sha256,
        size: j.size,
        note: j.note,
        structure_notes: j.structure_notes,
        task_spec: j.task_spec,
        source: "server",
      };
      writeDraft(null);
      return job;
    } catch (e) {
      await delay(400);
      const ext = file.name.split(".").pop()?.toLowerCase();
      const format = ext === "xlsx" || ext === "xls" ? "xlsx" : ext === "pdf" ? "pdf" : "docx";
      const job: FormJob = {
        id: uid("job"),
        title: file.name.replace(/\.[^.]+$/, ""),
        filename: file.name,
        format,
        status: "succeeded",
        created_at: new Date().toISOString(),
        step: "parsed",
        fields: emptyFieldsFromTemplate(),
        source: "local",
        note: e instanceof Error ? `本地回退: ${e.message}` : "本地回退",
      };
      writeDraft(job);
      return job;
    }
  },

  async fillField(jobId: string, fieldId: string): Promise<FormField> {
    return fillFormFieldRemote(jobId, fieldId);
  },

  async saveFields(jobId: string, fields: FormField[]): Promise<FormJob> {
    try {
      const saved = await patchFormFieldsRemote(jobId, fields);
      const job: FormJob = {
        id: saved.id,
        title: saved.title,
        filename: saved.filename,
        format: mapFormat(saved.format, saved.filename),
        status: saved.status,
        created_at: saved.created_at || new Date().toISOString(),
        step: (saved.step as FormJob["step"]) || "parsed",
        fields: Array.isArray(saved.fields) ? (saved.fields as FormField[]) : fields,
        path: saved.path,
        sha256: saved.sha256,
        size: saved.size,
        note: saved.note,
        structure_notes: saved.structure_notes,
        task_spec: saved.task_spec,
        source: "server",
      };
      const stored = this.listJobsLocal().filter((item) => item.id !== job.id);
      write(KEYS.jobs, [job, ...stored]);
      if (readDraft()?.id === jobId) writeDraft(null);
      return job;
    } catch {
      // 后端不可用时仍保留本地修改
    }
    const jobs = this.listJobsLocal();
    const idx = jobs.findIndex((j) => j.id === jobId);
    if (idx < 0) {
      const remote = await this.getJobAsync(jobId);
      if (!remote) throw new Error("任务不存在");
      const next = { ...remote, fields };
      const stored = read(KEYS.jobs, [] as FormJob[]);
      write(KEYS.jobs, [next, ...stored.filter((j) => j.id !== jobId)]);
      if (readDraft()?.id === jobId) writeDraft(null);
      return next;
    }
    jobs[idx] = { ...jobs[idx], fields };
    write(KEYS.jobs, jobs);
    if (readDraft()?.id === jobId) writeDraft(null);
    return jobs[idx];
  },

  async exportJob(jobId: string): Promise<{ filename: string; blob: Blob }> {
    try {
      return await downloadFilledForm(jobId);
    } catch (e) {
      if (e instanceof Error && !e.message.includes("Failed to fetch")) throw e;
    }
    let job = this.getJob(jobId);
    if (!job) {
      job = await this.getJobAsync(jobId);
    }
    if (!job) throw new Error("任务不存在");

    const jobs = this.listJobsLocal();
    const idx = jobs.findIndex((j) => j.id === jobId);
    if (idx >= 0) {
      jobs[idx] = { ...jobs[idx], step: "exported" };
      write(KEYS.jobs, jobs);
    } else {
      write(KEYS.jobs, [{ ...job, step: "exported" }, ...jobs]);
    }

    const lines = [
      `# 智填 ZhiFill 导出`,
      `任务: ${job.title}`,
      `文件: ${job.filename}`,
      job.path ? `存储路径: ${job.path}` : "",
      `时间: ${new Date().toISOString()}`,
      ``,
      `## 字段`,
      ...job.fields.map(
        (f) =>
          `- [${f.status}] ${f.name} = ${f.value ?? "(空)"}  confidence=${f.confidence ?? "n/a"}`,
      ),
    ].filter(Boolean);
    const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
    const base = job.filename.replace(/\.[^.]+$/, "");
    return { filename: `${base}.filled.txt`, blob };
  },

  resetAll(): void {
    localStorage.removeItem(KEYS.settings);
    localStorage.removeItem(KEYS.knowledge);
    localStorage.removeItem(KEYS.jobs);
  },
};
