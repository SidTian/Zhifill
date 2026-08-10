import Link from "next/link";

export default function HomePage() {
  return (
    <div>
      <div className="page-head">
        <div>
          <h1>智填 ZhiFill</h1>
          <p className="lead">
            历史资料 → 知识图谱 → 任务解析 → Agent 填报 → 预览确认 → 回填下载
          </p>
        </div>
      </div>

      <div className="grid-2">
        <section className="card">
          <h2>产品简介</h2>
          <p className="muted" style={{ marginTop: 0 }}>
            用个人历史资料构建知识图谱，自动填写当前任务表格；预览确认后再导出，填写结果默认不回写图谱。
          </p>
          <div className="flow-list">
            <div>
              <span className="tag">资料</span>
              <span>上传简历、证明等历史文件，进入个人知识库</span>
            </div>
            <div>
              <span className="tag">填表</span>
              <span>上传待填 Word / Excel / PDF，生成字段建议值</span>
            </div>
            <div>
              <span className="tag">确认</span>
              <span>预览、改值、确认后下载回填结果</span>
            </div>
          </div>
        </section>

        <section className="card">
          <h2>开始演示</h2>
          <div className="flow-list">
            <div>
              <span className="tag">1</span>
              <span>
                <Link href="/settings">设置</Link> — 配置模型参数
              </span>
            </div>
            <div>
              <span className="tag">2</span>
              <span>
                <Link href="/knowledge">知识库</Link> — 上传资料 / 问答探测
              </span>
            </div>
            <div>
              <span className="tag">3</span>
              <span>
                <Link href="/forms">填表</Link> — 任务列表与上传
              </span>
            </div>
            <div>
              <span className="tag">4</span>
              <span>打开任务 → 改值确认 → 导出下载</span>
            </div>
          </div>
          <div className="row" style={{ marginTop: "1rem" }}>
            <Link className="btn btn-primary" href="/forms/job-demo-001">
              打开示例任务
            </Link>
            <Link className="btn btn-secondary" href="/forms">
              全部任务
            </Link>
            <Link className="btn btn-secondary" href="/knowledge">
              知识库
            </Link>
          </div>
        </section>
      </div>
    </div>
  );
}
