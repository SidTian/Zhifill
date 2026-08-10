# 智填 ZhiFill · Web

纯前端演示（假数据，**不连后端**）。统筹（SidTian）负责。

## 环境要求

- **Node.js 20.x**（`node -v` 应为 v20）
- npm 10+（随 Node 20 自带）

若版本不对，可用 nvm / fnm 切换到 20。

## 安装与启动

在仓库根目录或本目录执行均可：

```bash
cd apps/web
npm install
npm run dev
```

浏览器打开：**http://127.0.0.1:3000**

停止：终端里 `Ctrl + C`。

### 常用命令

| 命令 | 说明 |
|------|------|
| `npm install` | 安装依赖（首次或 `package.json` 变更后） |
| `npm run dev` | 开发模式，热更新，默认端口 **3000** |
| `npm run build` | 生产构建，检查能否编译通过 |
| `npm run start` | 先 `build` 后，用生产模式启动 |
| `npm run lint` | 代码检查（若已配置） |

生产模式示例：

```bash
cd apps/web
npm run build
npm run start
# 仍访问 http://127.0.0.1:3000
```

### 端口被占用时

```bash
npx next dev -p 3001
```

然后打开 http://127.0.0.1:3001

## 演示怎么点

1. 打开首页 `/` → 点「打开示例任务」或「全部任务」
2. **设置** `/settings`：改模型参数 → 保存；需要时可「重置演示数据」
3. **知识库** `/knowledge`：上传任意文件进列表；输入问题点「查询」
4. **填表** `/forms`：看任务列表，或再上传 Word/Excel/PDF
5. **任务详情** `/forms/job-demo-001`：
   - 编辑字段值
   - 「全部确认」/ 单行「确认」
   - 「保存」
   - 「导出下载」得到 `.filled.txt`
6. 未填写示例：`/forms/job-demo-002` →「生成填写建议」→ 出现建议值后再导出

## 页面一览

| 路径 | 说明 |
|------|------|
| `/` | 首页与入口 |
| `/settings` | 模型设置、重置演示数据 |
| `/knowledge` | 知识库上传 / 列表 / 问答 |
| `/forms` | 填表任务列表与上传 |
| `/forms/[id]` | 字段预览、确认、导出 |

## 数据说明

### 上传落盘（需启动 API）

启动后端后，前端上传会调用真实接口，**原文件不转换**，按原始字节保存：

| 类型 | 接口 | 磁盘路径 |
|------|------|----------|
| 知识库 | `POST /api/knowledge/upload` | `data/knowledge/raw/{id}/{filename}` |
| 填表任务 | `POST /api/forms/upload` | `data/forms/raw/{id}/{filename}` |

元数据索引：`data/knowledge/index.json`、`data/forms/index.json`。  
列表/删除也走 API。API 不可用时前端会回退到 localStorage 演示。

```bash
# 终端 1
cd apps/api && source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# 终端 2
cd apps/web && npm run dev
```

### 其它演示数据

- 填写建议 / 问答等仍用前端假数据：`src/lib/mock-data.ts`
- 字段编辑状态可存 **localStorage**（`zhifill.mock.*`）
- 设置页「重置演示数据」只清浏览器本地缓存，**不会**删服务器 `data/` 文件

## 目录结构（前端相关）

```
apps/web/
  src/app/           # 页面（App Router）
    page.tsx         # 首页
    settings/        # 设置
    knowledge/       # 知识库
    forms/           # 任务列表与详情
  src/components/    # 通用 UI
  src/lib/           # mock 数据与本地 store
  package.json
```

## 常见问题

| 现象 | 处理 |
|------|------|
| `next: command not found` | 先在本目录执行 `npm install` |
| 依赖安装很慢/失败 | `npm install --registry=https://registry.npmjs.org/` |
| 页面空白或报错 | 看终端 `npm run dev` 日志；或 `npm run build` 查编译错误 |
| 示例任务不见了 | 设置页点「重置演示数据」 |
| 想清干净 | 浏览器 DevTools → Application → Local Storage → 删 `zhifill.mock.*` |
