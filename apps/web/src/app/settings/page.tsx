"use client";

import { useEffect, useState } from "react";
import { Badge, Button, Field, Spinner } from "@/components/ui";
import { DEFAULT_SETTINGS } from "@/lib/mock-data";
import { mockApi } from "@/lib/mock-store";
import type { AppSettings } from "@/lib/types";

export default function SettingsPage() {
  const [form, setForm] = useState<AppSettings>(DEFAULT_SETTINGS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    setForm(mockApi.getSettings());
    setLoading(false);
  }, []);

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setMsg(null);
    try {
      await mockApi.saveSettings(form);
      setMsg("设置已保存");
    } finally {
      setSaving(false);
    }
  }

  function onReset() {
    mockApi.resetAll();
    setForm(DEFAULT_SETTINGS);
    setMsg("已重置演示数据（设置 / 知识库 / 任务）");
  }

  if (loading) {
    return (
      <div className="card">
        <Spinner />
      </div>
    );
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>设置</h1>
          <p className="lead">LLM / Embedding 与演示数据</p>
        </div>
        <Badge tone="info">本地演示</Badge>
      </div>

      <form className="card" onSubmit={onSave}>
        <Field label="LLM Provider">
          <select
            value={form.llm_provider}
            onChange={(e) =>
              setForm({
                ...form,
                llm_provider: e.target.value as AppSettings["llm_provider"],
              })
            }
          >
            <option value="ollama">Ollama</option>
            <option value="openai_compatible">OpenAI 兼容</option>
          </select>
        </Field>

        <Field label="API Base" hint="例如 http://127.0.0.1:11434/v1">
          <input
            type="text"
            value={form.llm_api_base}
            onChange={(e) => setForm({ ...form, llm_api_base: e.target.value })}
          />
        </Field>

        <Field label="API Key" hint="Ollama 可留空">
          <input
            type="password"
            value={form.llm_api_key}
            onChange={(e) => setForm({ ...form, llm_api_key: e.target.value })}
            autoComplete="off"
          />
        </Field>

        <div className="grid-2">
          <Field label="对话模型">
            <input
              type="text"
              value={form.llm_model}
              onChange={(e) => setForm({ ...form, llm_model: e.target.value })}
            />
          </Field>
          <Field label="Embedding 模型">
            <input
              type="text"
              value={form.embedding_model}
              onChange={(e) =>
                setForm({ ...form, embedding_model: e.target.value })
              }
            />
          </Field>
        </div>

        <Field label="多行表最大行数">
          <input
            type="number"
            min={1}
            max={500}
            value={form.max_table_rows}
            onChange={(e) =>
              setForm({
                ...form,
                max_table_rows: Number(e.target.value) || 50,
              })
            }
          />
        </Field>

        <div className="row">
          <Button type="submit" disabled={saving}>
            {saving ? "保存中…" : "保存设置"}
          </Button>
          <Button type="button" variant="secondary" onClick={onReset}>
            重置演示数据
          </Button>
        </div>

        {msg ? <div className="alert alert-info">{msg}</div> : null}
      </form>
    </div>
  );
}
