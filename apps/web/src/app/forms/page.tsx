export default function FormsPage() {
  return (
    <div>
      <h1>填表任务</h1>
      <div className="card">
        <span className="badge warn">占位 · P3 解析填写 + P4 导出</span>
        <p className="muted">
          上传 xlsx/docx/pdf → 解析字段 → 问图谱填值 → 预览编辑（含多行网格）→
          下载。填写结果不回写知识库。
        </p>
        <p>
          API: <code>POST /api/forms/upload</code> ·{" "}
          <code>POST /api/forms/jobs/&#123;id&#125;/fill</code> ·{" "}
          <code>POST .../export</code>（当前 501）
        </p>
      </div>
    </div>
  );
}
