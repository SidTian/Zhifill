"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Badge, Button, Empty, Spinner, StatusDot } from "@/components/ui";
import { formatBytes, formatTime } from "@/lib/mock-data";
import { mockApi } from "@/lib/mock-store";
import type { KnowledgeDoc, QueryHit } from "@/lib/types";

export default function KnowledgePage() {
  const [docs, setDocs] = useState<KnowledgeDoc[]>([]);
  const [busy, setBusy] = useState(false);
  const [q, setQ] = useState("我的手机号和工作单位是什么？");
  const [answer, setAnswer] = useState<string | null>(null);
  const [hits, setHits] = useState<QueryHit[]>([]);
  const [toast, setToast] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const reload = useCallback(() => {
    setDocs(mockApi.listKnowledge());
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 2400);
    return () => clearTimeout(t);
  }, [toast]);

  async function onUpload(file: File | null) {
    if (!file) return;
    setBusy(true);
    try {
      await mockApi.uploadKnowledge(file);
      reload();
      setToast(`已入库：${file.name}`);
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function onDelete(id: string) {
    setBusy(true);
    try {
      await mockApi.deleteKnowledge(id);
      reload();
      setToast("已删除");
    } finally {
      setBusy(false);
    }
  }

  async function onQuery() {
    setBusy(true);
    try {
      const res = await mockApi.queryKnowledge(q);
      setAnswer(res.answer);
      setHits(res.hits);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>知识库</h1>
          <p className="lead">上传历史资料，探测个人知识问答</p>
        </div>
        <Badge tone="info">本地演示</Badge>
      </div>

      <section className="card">
        <h2>上传历史资料</h2>
        <label className={`dropzone ${busy ? "drag" : ""}`}>
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.docx,.doc,.md,.txt,.xlsx,.xls,.png,.jpg"
            disabled={busy}
            onChange={(e) => onUpload(e.target.files?.[0] ?? null)}
          />
          {busy ? (
            <Spinner label="解析并写入知识库…" />
          ) : (
            <>
              点击选择文件，或拖拽到此处
              <div className="list-meta" style={{ marginTop: "0.35rem" }}>
                支持 pdf / docx / md / txt / xlsx
              </div>
            </>
          )}
        </label>
      </section>

      <section className="card">
        <h2>已入库文档（{docs.length}）</h2>
        {docs.length === 0 ? (
          <Empty>暂无文档，先上传一个试试</Empty>
        ) : (
          <div>
            {docs.map((d) => (
              <div className="list-item" key={d.id}>
                <div>
                  <div>
                    <StatusDot status={d.status} />
                    <strong>{d.title}</strong>
                  </div>
                  <div className="list-meta">
                    {d.filename} · {formatBytes(d.size)} ·{" "}
                    {formatTime(d.updated_at)}
                  </div>
                  <div className="list-meta">
                    id: <code>{d.id}</code>
                  </div>
                </div>
                <Button
                  variant="danger"
                  className="btn-sm"
                  disabled={busy}
                  onClick={() => onDelete(d.id)}
                >
                  删除
                </Button>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="card">
        <h2>知识问答</h2>
        <div className="row" style={{ alignItems: "stretch" }}>
          <input
            style={{ flex: 1, minWidth: 200 }}
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="输入问题…"
            onKeyDown={(e) => {
              if (e.key === "Enter") void onQuery();
            }}
          />
          <Button onClick={() => void onQuery()} disabled={busy}>
            {busy ? "查询中…" : "查询"}
          </Button>
        </div>
        {answer ? (
          <div style={{ marginTop: "0.9rem" }}>
            <pre
              style={{
                whiteSpace: "pre-wrap",
                margin: 0,
                fontFamily: "inherit",
                background: "#f8fafc",
                padding: "0.75rem",
                borderRadius: 10,
                border: "1px solid var(--border)",
              }}
            >
              {answer}
            </pre>
            {hits.map((h, i) => (
              <div className="source" key={i}>
                <code>{h.doc_id}</code> · score {h.score.toFixed(2)}
                <div>{h.snippet}</div>
              </div>
            ))}
          </div>
        ) : null}
      </section>

      {toast ? <div className="toast">{toast}</div> : null}
    </div>
  );
}
