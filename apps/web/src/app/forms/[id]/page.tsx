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
  const [progress, setProgress] = useState<string | null>(null);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [toast, setToast] = useState<string | null>(null);
  const [missing, setMissing] = useState(false);

  const reload = useCallback(async () => {
    const j = await mockApi.getJobAsync(id);
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
    void reload();
  }, [reload]);

  useEffect(() => {
    setSelected((prev) => {
      const ids = new Set(fields.map((item) => item.id));
      const next = { ...prev };
      let changed = false;
      for (const item of fields) {
        if (!(item.id in next)) {
          next[item.id] = true;
          changed = true;
        }
      }
      for (const key of Object.keys(next)) {
        if (!ids.has(key)) {
          delete next[key];
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, [fields]);

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
    const targets = fields.filter(
      (item) => item.layout === "label_value" && item.name.trim() && selected[item.id] !== false,
    );
    if (!targets.length) {
      setToast("请先勾选要填写的字段");
      return;
    }
    setBusy(true);
    let filled = 0;
    let failed = 0;
    try {
      for (let i = 0; i < targets.length; i++) {
        const current = targets[i];
        setProgress(`正在填写 ${i + 1}/${targets.length}：${current.name}`);
        try {
          const field = await mockApi.fillField(id, current.id);
          setFields((prev) => prev.map((item) => (item.id === field.id ? { ...item, ...field } : item)));
          if (field.value) filled += 1;
        } catch {
          failed += 1;
        }
      }
      setJob((prev) => (prev ? { ...prev, step: "filled" } : prev));
      setToast(failed ? `已填写 ${filled} 个，失败 ${failed} 个` : `已填写 ${filled} 个字段`);
    } finally {
      setBusy(false);
      setProgress(null);
    }
  }

  function blankField(): FormField {
    return {
      id: `manual_${crypto.randomUUID()}`,
      name: "新字段",
      field_type: "text",
      value: null,
      original_value: null,
      required: false,
      confidence: null,
      sources: [],
      status: "empty",
      layout: "label_value",
      row_group_id: null,
      row_index: null,
      column_key: null,
      locator: { kind: "word_bookmark", name: "manual" },
      notes: "未对齐",
    };
  }

  async function persistFields(next: FormField[]) {
    setBusy(true);
    try {
      const j = await mockApi.saveFields(id, next);
      setJob(j);
      setFields(structuredClone(j.fields));
    } catch (e) {
      setToast(e instanceof Error ? e.message : "保存字段失败");
    } finally {
      setBusy(false);
    }
  }

  async function addField() {
    await persistFields([...fields, blankField()]);
  }

  async function removeField(fieldId: string) {
    await persistFields(fields.filter((item) => item.id !== fieldId));
  }

  async function onSave() {
    setBusy(true);
    try {
      const j = await mockApi.saveFields(id, fields);
      setJob(j);
      setFields(structuredClone(j.fields));
      setToast("已保存");
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
      await reload();
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

  const visible = fields.filter((item) => item.layout === "label_value");
  const allChecked = visible.length > 0 && visible.every((item) => selected[item.id] !== false);

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
            {job.path ? (
              <>
                <br />
                存储: <code>{job.path}</code>
              </>
            ) : null}
          </p>
          <div className="steps">
            <span className={stepClass(job.step, "uploaded")}>上传</span>
            <span className={stepClass(job.step, "parsed")}>结构解析</span>
            <span className={stepClass(job.step, "filled")}>智能填写</span>
            <span className={stepClass(job.step, "exported")}>导出</span>
          </div>
        </div>
        <div className="actions">
          <Button onClick={() => void onFill()} disabled={busy}>
            {busy ? progress ?? "填写中…" : "生成填写建议"}
          </Button>
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
        <h2>字段与值</h2>
        <p className="list-meta">
          可添加、删除字段，也可直接改字段名和值。添加和删除会立即保存。
        </p>
        <div className="actions" style={{ marginBottom: "0.75rem" }}>
          <Button variant="secondary" disabled={busy} onClick={() => void addField()}>
            添加字段
          </Button>
        </div>
        {job.structure_notes?.length ? (
          <ul className="list-meta">
            {job.structure_notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        ) : job.note ? (
          <p className="list-meta">{job.note}</p>
        ) : null}
        {singles.length === 0 ? (
          <Empty>还没有字段，可以添加</Empty>
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th className="pick-cell" title="全选或取消。只有勾选的字段会生成填写建议">
                    <label className="pick">
                      <input
                        type="checkbox"
                        checked={allChecked}
                        aria-label="全选字段"
                        onChange={(e) => {
                          const on = e.target.checked;
                          setSelected((prev) => {
                            const next = { ...prev };
                            for (const item of visible) next[item.id] = on;
                            return next;
                          });
                        }}
                      />
                      <span />
                    </label>
                  </th>
                  <th style={{ width: "16%" }}>字段</th>
                  <th style={{ width: "26%" }}>值</th>
                  <th>置信度</th>
                  <th>状态</th>
                  <th>来源</th>
                  <th className="ops-cell">操作</th>
                </tr>
              </thead>
              <tbody>
                {singles.map((f) => (
                  <tr key={f.id}>
                    <td className="pick-cell">
                      <label className="pick" title="勾选后，点「生成填写建议」才会填写这一行">
                        <input
                          type="checkbox"
                          checked={selected[f.id] !== false}
                          aria-label={`选择 ${f.name || "字段"}`}
                          onChange={(e) =>
                            setSelected((prev) => ({ ...prev, [f.id]: e.target.checked }))
                          }
                        />
                        <span />
                      </label>
                    </td>
                    <td>
                      <input
                        type="text"
                        value={f.name}
                        onChange={(e) => updateField(f.id, { name: e.target.value })}
                      />
                      {f.notes ? (
                        <div className="list-meta">{f.notes}</div>
                      ) : null}
                    </td>
                    <td>
                      <textarea
                        className="value-box"
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
                      {f.sources.length || f.notes ? (
                        <div className="source-box">
                          {f.sources.map((s, i) => (
                            <div className="source" key={i}>
                              {s.doc_id ? <code>{s.doc_id}</code> : null} {s.snippet}
                            </div>
                          ))}
                          {f.notes ? <div className="source">{f.notes}</div> : null}
                        </div>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td className="ops-cell">
                      <div className="row-actions">
                        <Button
                          className="btn-sm"
                          variant="secondary"
                          title="确认这个建议值"
                          onClick={() => setStatus(f.id, "confirmed")}
                        >
                          确认
                        </Button>
                        <Button
                          className="btn-sm"
                          variant="ghost"
                          title="清空这一格的值"
                          onClick={() => {
                            setValue(f.id, "");
                            setStatus(f.id, "rejected");
                          }}
                        >
                          清空
                        </Button>
                        <Button
                          className="btn-sm"
                          variant="danger"
                          title="从表格中删除这个字段"
                          disabled={busy}
                          onClick={() => void removeField(f.id)}
                        >
                          删除
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
