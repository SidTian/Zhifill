export default function KnowledgePage() {
  return (
    <div>
      <h1>知识库</h1>
      <div className="card">
        <span className="badge warn">占位 · P1 解析 + P2 图谱</span>
        <p className="muted">
          上传 pdf/docx/md/txt/xlsx → Ingest → LightRAG 增量更新图谱节点。
          支持列表、删除、简单问答探测。
        </p>
        <p>
          API: <code>POST /api/knowledge/upload</code> ·{" "}
          <code>POST /api/knowledge/query</code>（当前 501）
        </p>
      </div>
    </div>
  );
}
