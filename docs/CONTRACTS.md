# 接口契约

跨模块的 **输入/输出是唯一真相**。实现必须符合契约；未先改契约，禁止在业务代码里另起一套类型。

人员编号以 **[DIVISION.md](./DIVISION.md)** 的 **1.1 / 1.2 / 1.3 / 2.1 / 2.2 / 统筹** 为准。

## 版本规则

- 包版本：`packages/contracts/VERSION`（semver）
- **破坏性变更**：升高 MAJOR，PR 说明，更新 fixtures
- **仅新增字段**：升高 MINOR
- **仅文档/样例**：升高 PATCH

## 目录结构

```
packages/contracts/
  VERSION
  openapi/openapi.yaml
  jsonschema/          # 规范校验
  fixtures/            # 成功/失败样例
  python/aff_contracts/  # Pydantic 镜像
```

## 模块端口与交接

| 方向 | Port（实现期） | 关键产出 |
|------|----------------|----------|
| 1.1 | `IngestPort` | `DocumentBundle`（text 非空） |
| 1.2 | `FormStructurePort` | 文档结构 + 位置/locator 基础 |
| 1.3 | `TaskSemanticsPort` | 字段语义 + **TaskSpec**（任务需求） |
| 2.1 | `RagPort` + **Schema 文档** | 图谱增删查；Schema 为全组标准 |
| 2.2 | `FillPort` / Agent | `FillResult` |
| 统筹 | `ExportPort` + HTTP | 导出文件；前端消费 OpenAPI |

> `TaskSpec`、结构树等若尚无 schema 文件，由 **1.3 / 1.2** 起草 PR，统筹 + 2.1/2.2 会签后合入。

## 协作者规则

1. 只依赖契约包 + 其他模块的 `port.py`
2. 不改字段含义，除非同时 bump 版本
3. **1.2 → 统筹回填**：可写回位置必须能落到稳定 `locator`
4. **1.1 → 2.1**：`DocumentBundle.text` 必须非空
5. **1.3 → 2.2**：TaskSpec 须能表达「查哪些实体/属性」
6. **2.2 → 统筹**：FillResult 供预览；**禁止**默认把确认值 upsert 回图谱
7. **Schema** 变更由 **2.1** 发起

## HTTP 一览

见 `packages/contracts/openapi/openapi.yaml`。健康检查 `GET /api/health` 须 200；业务接口随实现从 501 变为可用。
