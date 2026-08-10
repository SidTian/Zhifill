"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Badge, Button, Empty, Spinner } from "@/components/ui";
import { confidenceLabel, formatTime } from "@/lib/mock-data";
import { mockApi } from "@/lib/mock-store";
import type { FieldStatus, FormField, FormJob } from "@/lib/types";

function confClass(c: number | null): string {
  if (c == null || c <= 0) return "conf";
  if (c >= 0.85) return "conf conf-high";
  if (c >= 0.6) return "conf conf-mid";
  return "conf conf-low";
}

function stepClass(current: FormJob["step"], name: FormJob["step"]): string {
  const order: FormJob["step"][] = ["uploaded", "parsed", "filled", "exported"];
  const ci = order.indexOf(current);
  const ni = order.indexOf(name);
  if (ni < ci) return "step done";
  if (ni === ci) return "step on";
  return "step";
}

export default function FormJobPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [job, setJob] = useState<FormJob | null>(null);
  const [fields, setFields] = useState<FormField[]>([]);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [missing, setMissing] = useState(false);

  const reload = useCallback(() => {
    const j = mockApi.getJob(id);
    if (!j) {
      setMissing(true);
      setJob(null);
      setFields([]);
      return;
    }
    setMissing(false);
    setJob(j);
    setFields(structuredClone(j.fields));
  }, [id]);

  useEffect(() => {
    reload();
  }, [reload]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 2600);
    return () => clearTimeout(t);
  }, [toast]);

  const singles = useMemo(
    () => fields.filter((f) => f.layout === "label_value"),
    [fields],
  );

  const tableGroups = useMemo(() => {
    const map = new Map<string, FormField[]>();
    for (const f of fields) {
      if (f.layout !== "header_row_table" || !f.row_group_id) continue;
      const arr = map.get(f.row_group_id) ?? [];
      arr.push(f);
      map.set(f.row_group_id, arr);
    }
    return [...map.entries()];
  }, [fields]);

  function updateField(fid: string, patch: Partial<FormField>) {
    setFields((prev) =>
      prev.map((f) => (f.id === fid ? { ...f, ...patch } : f)),
    );
  }

  function setValue(fid: string, value: string) {
    updateField(fid, {
      value: value === "" ? null : value,
      status: value === "" ? "empty" : "manual",
    });
  }

  function setStatus(fid: string, status: FieldStatus) {
    updateField(fid, { status });
  }

  async function onFill() {
    setBusy(true);
    try {
      const j = await mockApi.runFill(id);
      setJob(j);
      setFields(structuredClone(j.fields));
      setToast("已生成填写建议");
    } catch (e) {
      setToast(e instanceof Error ? e.message : "填写失败");
    } finally {
      setBusy(false);
    }
  }

  async function onSave() {
    setBusy(true);
    try {
      const j = await mockApi.saveFields(id, fields);
      setJob(j);
      setToast("修改已保存");
    } finally {
      setBusy(false);
    }
  }

  function confirmAllSuggested() {
    setFields((prev) =>
      prev.map((f) =>
        f.status === "suggested" ? { ...f, status: "confirmed" } : f,
      ),
    );
  }

  async function onExport() {
    setBusy(true);
    try {
      await mockApi.saveFields(id, fields);
      const { filename, blob } = await mockApi.exportJob(id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      reload();
      setToast(`已下载：${filename}`);
    } catch (e) {
      setToast(e instanceof Error ? e.message : "导出失败");
    } finally {
      setBusy(false);
    }
  }

  if (missing) {
    return (
      <div className="card">
        <Empty>
          找不到任务 <code>{id}</code>
          <div style={{ marginTop: "0.75rem" }}>
            <Link href="/forms">返回任务列表</Link>
          </div>
        </Empty>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="card">
        <Spinner />
      </div>
    );
  }

  const needFill =
    job.step === "parsed" || fields.every((f) => f.status === "empty");

  return (
    <div>
      <div className="page-head">
        <div>
          <p className="muted" style={{ margin: "0 0 0.25rem" }}>
            <Link href="/forms">← 填表任务</Link>
          </p>
          <h1>{job.title}</h1>
          <p className="lead">
            {job.filename} · {formatTime(job.created_at)}
          </p>
          <div className="steps">
            <span className={stepClass(job.step, "uploaded")}>上传</span>
            <span className={stepClass(job.step, "parsed")}>结构解析</span>
            <span className={stepClass(job.step, "filled")}>智能填写</span>
            <span className={stepClass(job.step, "exported")}>导出</span>
          </div>
        </div>
        <div className="actions">
          {needFill ? (
            <Button onClick={() => void onFill()} disabled={busy}>
              {busy ? "填写中…" : "生成填写建议"}
            </Button>
          ) : null}
          <Button
            variant="secondary"
            onClick={confirmAllSuggested}
            disabled={busy}
          >
            全部确认
          </Button>
          <Button variant="secondary" onClick={() => void onSave()} disabled={busy}>
            保存
          </Button>
          <Button onClick={() => void onExport()} disabled={busy}>
            导出下载
          </Button>
        </div>
      </div>

      <section className="card">
        <h2>字段预览</h2>
        {singles.length === 0 ? (
          <Empty>无字段</Empty>
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th style={{ width: "16%" }}>字段</th>
                  <th style={{ width: "26%" }}>值</th>
                  <th>置信度</th>
                  <th>状态</th>
                  <th>来源</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {singles.map((f) => (
                  <tr key={f.id}>
                    <td>
                      <strong>{f.name}</strong>
                      {f.required ? <span className="muted"> *</span> : null}
                    </td>
                    <td>
                      <input
                        type="text"
                        value={f.value ?? ""}
                        placeholder="(空)"
                        onChange={(e) => setValue(f.id, e.target.value)}
                      />
                    </td>
                    <td>
                      <span className={confClass(f.confidence)}>
                        {confidenceLabel(f.confidence)}
                        {f.confidence != null && f.confidence > 0
                          ? ` ${(f.confidence * 100).toFixed(0)}%`
                          : ""}
                      </span>
                    </td>
                    <td>
                      <Badge
                        tone={
                          f.status === "confirmed"
                            ? "ok"
                            : f.status === "suggested"
                              ? "info"
                              : f.status === "empty"
                                ? "muted"
                                : "warn"
                        }
                      >
                        {f.status}
                      </Badge>
                    </td>
                    <td>
                      {f.sources.map((s, i) => (
                        <div className="source" key={i}>
                          {s.doc_id ? <code>{s.doc_id}</code> : null} {s.snippet}
                        </div>
                      ))}
                      {f.notes ? <div className="source">{f.notes}</div> : null}
                      {!f.sources.length && !f.notes ? (
                        <span className="muted">—</span>
                      ) : null}
                    </td>
                    <td>
                      <div className="stack">
                        <Button
                          className="btn-sm"
                          variant="secondary"
                          onClick={() => setStatus(f.id, "confirmed")}
                        >
                          确认
                        </Button>
                        <Button
                          className="btn-sm"
                          variant="ghost"
                          onClick={() => {
                            setValue(f.id, "");
                            setStatus(f.id, "rejected");
                          }}
                        >
                          清空
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {tableGroups.map(([gid, groupFields]) => {
        const rows = new Map<number, FormField[]>();
        const cols = new Set<string>();
        for (const f of groupFields) {
          const r = f.row_index ?? 0;
          const arr = rows.get(r) ?? [];
          arr.push(f);
          rows.set(r, arr);
          if (f.column_key) cols.add(f.column_key);
        }
        const colKeys = [...cols];
        const colLabel: Record<string, string> = {
          org: "单位",
          role: "职位",
          period: "起止时间",
        };
        return (
          <section className="card" key={gid}>
            <h2>工作经历</h2>
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>#</th>
                    {colKeys.map((c) => (
                      <th key={c}>{colLabel[c] ?? c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[...rows.entries()]
                    .sort((a, b) => a[0] - b[0])
                    .map(([ri, cells]) => (
                      <tr key={ri}>
                        <td>{ri + 1}</td>
                        {colKeys.map((ck) => {
                          const cell = cells.find((c) => c.column_key === ck);
                          if (!cell) return <td key={ck} />;
                          return (
                            <td key={ck}>
                              <input
                                type="text"
                                value={cell.value ?? ""}
                                onChange={(e) =>
                                  setValue(cell.id, e.target.value)
                                }
                              />
                              <div style={{ marginTop: 4 }}>
                                <span className={confClass(cell.confidence)}>
                                  {confidenceLabel(cell.confidence)}
                                </span>
                              </div>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </section>
        );
      })}

      {busy ? (
        <div className="card tight">
          <Spinner label="处理中…" />
        </div>
      ) : null}

      {toast ? <div className="toast">{toast}</div> : null}
    </div>
  );
}
