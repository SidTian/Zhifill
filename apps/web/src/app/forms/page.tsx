"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { API_BASE } from "@/lib/api";
import { Badge, Button, Empty, Spinner, StatusDot } from "@/components/ui";
import { formatTime } from "@/lib/mock-data";
import { mockApi } from "@/lib/mock-store";
import type { FormJob } from "@/lib/types";

const STEP_LABEL: Record<FormJob["step"], string> = {
  uploaded: "已上传落盘",
  parsed: "已解析结构",
  filled: "已生成填写",
  exported: "已导出",
};

export default function FormsPage() {
  const router = useRouter();
  const [jobs, setJobs] = useState<FormJob[]>([]);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const reload = useCallback(async () => {
    setJobs(await mockApi.listJobs());
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 2800);
    return () => clearTimeout(t);
  }, [toast]);

  async function onDelete(id: string, source: "server" | "local" | undefined) {
    setBusy(true);
    try {
      await mockApi.deleteJob(id, source);
      await reload();
      setToast("已删除");
    } catch (e) {
      setToast(e instanceof Error ? e.message : "删除失败");
    } finally {
      setBusy(false);
    }
  }

  async function onUpload(file: File | null) {
    if (!file) return;
    setBusy(true);
    try {
      const job = await mockApi.uploadForm(file);
      await reload();
      if (job.source === "server") {
        setToast("已解析。编辑字段和值后，点保存才会写入本地");
      } else {
        setToast("API 不可用。这是临时页面，点保存才会写入本地");
      }
      router.push(`/forms/${job.id}`);
    } catch (e) {
      setToast(e instanceof Error ? e.message : "上传失败");
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>填表任务</h1>
          <p className="lead">
            上传待填文件；原文件保存到{" "}
            <code>data/forms/raw/&#123;id&#125;/</code>
          </p>
        </div>
        <Badge tone="info">API {API_BASE}</Badge>
      </div>

      <section className="card">
        <h2>新建任务</h2>
        <label className="dropzone">
          <input
            ref={inputRef}
            type="file"
            accept=".docx,.doc,.xlsx,.xls,.pdf"
            disabled={busy}
            onChange={(e) => void onUpload(e.target.files?.[0] ?? null)}
          />
          {busy ? (
            <Spinner label="上传并解析…" />
          ) : (
            <>
              上传 Word / Excel / PDF
              <div className="list-meta" style={{ marginTop: "0.35rem" }}>
                .docx / .xlsx 会识别空格和填空栏；PDF 与旧版 .doc / .xls 只保存
              </div>
            </>
          )}
        </label>
      </section>

      <section className="card">
        <h2>任务列表（{jobs.length}）</h2>
        {jobs.length === 0 ? (
          <Empty>暂无任务</Empty>
        ) : (
          <div>
            {jobs.map((j) => (
              <div className="list-item" key={j.id}>
                <div>
                  <div>
                    <StatusDot
                      status={j.status === "stored" ? "succeeded" : j.status}
                    />
                    <strong>{j.title}</strong>{" "}
                    <Badge tone="muted">{j.format}</Badge>{" "}
                    <Badge tone="info">{STEP_LABEL[j.step]}</Badge>{" "}
                    {j.source === "server" ? (
                      <Badge tone="ok">已落盘</Badge>
                    ) : (
                      <Badge tone="warn">本地</Badge>
                    )}
                  </div>
                  <div className="list-meta">
                    {j.filename} · {formatTime(j.created_at)} · {j.fields.length}{" "}
                    字段
                  </div>
                  {j.path ? (
                    <div className="list-meta">
                      path: <code>{j.path}</code>
                    </div>
                  ) : null}
                  <div className="list-meta">
                    id: <code>{j.id}</code>
                  </div>
                </div>
                <div style={{ display: "flex", gap: "0.4rem" }}>
                  <Link className="btn btn-secondary btn-sm" href={`/forms/${j.id}`}>
                    打开
                  </Link>
                  <Button
                    variant="danger"
                    className="btn-sm"
                    disabled={busy}
                    onClick={() => void onDelete(j.id, j.source)}
                  >
                    删除
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {toast ? <div className="toast">{toast}</div> : null}
    </div>
  );
}
