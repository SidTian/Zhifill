import { API_BASE, getHealth } from "@/lib/api";

export default async function HomePage() {
  let health: { status: string; phase?: string } | null = null;
  let error: string | null = null;
  try {
    health = await getHealth();
  } catch (e) {
    error = e instanceof Error ? e.message : "API unreachable";
  }

  return (
    <div>
      <h1>智填 ZhiFill</h1>
      <p className="muted">
        知识文件 → LightRAG 图谱 → 表格填写 → 预览确认 → 下载
      </p>
      <div className="card">
        <span className="badge warn">Phase 0 · 契约骨架</span>
        <p style={{ marginTop: "0.75rem" }}>
          业务模块尚未实现。请阅读仓库 <code>docs/</code> 与{" "}
          <code>packages/contracts</code>，按 OWNERS 分工实现。
        </p>
        <ul className="clean">
          <li>
            API Base: <code>{API_BASE}</code>
          </li>
          <li>
            Health:{" "}
            {health ? (
              <strong>
                {health.status}
                {health.phase ? ` (${health.phase})` : ""}
              </strong>
            ) : (
              <span className="muted">{error}</span>
            )}
          </li>
        </ul>
      </div>
    </div>
  );
}
