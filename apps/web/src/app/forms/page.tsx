"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Badge, Empty, Spinner, StatusDot } from "@/components/ui";
import { formatTime } from "@/lib/mock-data";
import { mockApi } from "@/lib/mock-store";
import type { FormJob } from "@/lib/types";

const STEP_LABEL: Record<FormJob["step"], string> = {
  uploaded: "已上传",
  parsed: "已解析结构",
  filled: "已生成填写",
  exported: "已导出",
};

export default function FormsPage() {
  const router = useRouter();
  const [jobs, setJobs] = useState<FormJob[]>([]);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const reload = useCallback(() => {
    setJobs(mockApi.listJobs());
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  async function onUpload(file: File | null) {
    if (!file) return;
    setBusy(true);
    try {
      const job = await mockApi.uploadForm(file);
      reload();
      router.push(`/forms/${job.id}`);
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
          <p className="lead">上传待填文件，自动生成建议值，预览后导出</p>
        </div>
        <Badge tone="info">本地演示</Badge>
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
            <Spinner label="解析文档结构…" />
          ) : (
            <>
              上传 Word / Excel / PDF
              <div className="list-meta" style={{ marginTop: "0.35rem" }}>
                上传后进入任务详情，可一键生成填写建议
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
                    <StatusDot status={j.status} />
                    <strong>{j.title}</strong>{" "}
                    <Badge tone="muted">{j.format}</Badge>{" "}
                    <Badge tone="info">{STEP_LABEL[j.step]}</Badge>
                  </div>
                  <div className="list-meta">
                    {j.filename} · {formatTime(j.created_at)} ·{" "}
                    {j.fields.length} 字段
                  </div>
                  <div className="list-meta">
                    id: <code>{j.id}</code>
                  </div>
                </div>
                <Link className="btn btn-secondary btn-sm" href={`/forms/${j.id}`}>
                  打开
                </Link>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
