"use client";

import {
  DEFAULT_SETTINGS,
  MOCK_FIELDS_FILLED,
  MOCK_JOBS,
  MOCK_KNOWLEDGE,
  MOCK_QUERY_ANSWERS,
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

function uid(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
}

export const mockApi = {
  getSettings(): AppSettings {
    return { ...DEFAULT_SETTINGS, ...read(KEYS.settings, {}) };
  },

  async saveSettings(next: AppSettings): Promise<AppSettings> {
    await delay(400);
    write(KEYS.settings, next);
    return next;
  },

  listKnowledge(): KnowledgeDoc[] {
    return read(KEYS.knowledge, structuredClone(MOCK_KNOWLEDGE));
  },

  async uploadKnowledge(file: File): Promise<KnowledgeDoc> {
    await delay(900);
    const docs = this.listKnowledge();
    const doc: KnowledgeDoc = {
      id: uid("doc"),
      title: file.name.replace(/\.[^.]+$/, ""),
      filename: file.name,
      media_type: file.type || "application/octet-stream",
      status: "succeeded",
      updated_at: new Date().toISOString(),
      size: file.size,
    };
    write(KEYS.knowledge, [doc, ...docs]);
    return doc;
  },

  async deleteKnowledge(id: string): Promise<void> {
    await delay(300);
    write(
      KEYS.knowledge,
      this.listKnowledge().filter((d) => d.id !== id),
    );
  },

  async queryKnowledge(q: string): Promise<{ answer: string; hits: QueryHit[] }> {
    await delay(700);
    const base = MOCK_QUERY_ANSWERS.default;
    if (!q.trim()) {
      return { answer: "请输入问题。", hits: [] };
    }
    return {
      answer: `问题：「${q.trim()}」\n${base.answer}`,
      hits: base.hits,
    };
  },

  listJobs(): FormJob[] {
    return read(KEYS.jobs, structuredClone(MOCK_JOBS));
  },

  getJob(id: string): FormJob | null {
    return this.listJobs().find((j) => j.id === id) ?? null;
  },

  async uploadForm(file: File): Promise<FormJob> {
    await delay(1000);
    const jobs = this.listJobs();
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
      fields: structuredClone(MOCK_FIELDS_FILLED).map((f) => ({
        ...f,
        value: null,
        confidence: null,
        status: "empty" as const,
        sources: [],
      })),
    };
    write(KEYS.jobs, [job, ...jobs]);
    return job;
  },

  async runFill(jobId: string): Promise<FormJob> {
    await delay(1200);
    const jobs = this.listJobs();
    const idx = jobs.findIndex((j) => j.id === jobId);
    if (idx < 0) throw new Error("任务不存在");
    const filled: FormJob = {
      ...jobs[idx],
      status: "succeeded",
      step: "filled",
      fields: structuredClone(MOCK_FIELDS_FILLED),
    };
    jobs[idx] = filled;
    write(KEYS.jobs, jobs);
    return filled;
  },

  async saveFields(jobId: string, fields: FormField[]): Promise<FormJob> {
    await delay(350);
    const jobs = this.listJobs();
    const idx = jobs.findIndex((j) => j.id === jobId);
    if (idx < 0) throw new Error("任务不存在");
    jobs[idx] = { ...jobs[idx], fields };
    write(KEYS.jobs, jobs);
    return jobs[idx];
  },

  async exportJob(jobId: string): Promise<{ filename: string; blob: Blob }> {
    await delay(800);
    const job = this.getJob(jobId);
    if (!job) throw new Error("任务不存在");

    const jobs = this.listJobs();
    const idx = jobs.findIndex((j) => j.id === jobId);
    if (idx >= 0) {
      jobs[idx] = { ...jobs[idx], step: "exported" };
      write(KEYS.jobs, jobs);
    }

    const lines = [
      `# 智填 ZhiFill 导出`,
      `任务: ${job.title}`,
      `文件: ${job.filename}`,
      `时间: ${new Date().toISOString()}`,
      ``,
      `## 字段`,
      ...job.fields.map(
        (f) =>
          `- [${f.status}] ${f.name} = ${f.value ?? "(空)"}  confidence=${f.confidence ?? "n/a"}`,
      ),
    ];
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
