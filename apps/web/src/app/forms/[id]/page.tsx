export default function FormJobPage({
  params,
}: {
  params: { id: string };
}) {
  return (
    <div>
      <h1>任务预览</h1>
      <div className="card">
        <span className="badge warn">占位</span>
        <p>
          Job ID: <code>{params.id}</code>
        </p>
        <p className="muted">
          实现期：字段表 / 多行网格编辑、置信度、来源 snippet、确认后导出。
        </p>
      </div>
    </div>
  );
}
