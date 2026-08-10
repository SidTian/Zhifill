export default function SettingsPage() {
  return (
    <div>
      <h1>设置</h1>
      <div className="card">
        <span className="badge warn">占位 · P4 + Maintainer</span>
        <p className="muted">
          将配置 LLM Provider（OpenAI 兼容 / Ollama）、API Base、Key、Embedding
          模型。对应 <code>PUT /api/settings</code>（当前 501）。
        </p>
        <ul className="clean">
          <li>llm_provider</li>
          <li>llm_api_base / llm_api_key</li>
          <li>llm_model / embedding_model</li>
          <li>max_table_rows</li>
        </ul>
      </div>
    </div>
  );
}
