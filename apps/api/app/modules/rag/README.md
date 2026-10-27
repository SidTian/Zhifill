# P2 — RAG / LightRAG

## I/O

- **Upsert**: `UpsertDocumentRequest` → `UpsertDocumentResult`
- **Delete**: `DeleteDocumentRequest` → None
- **Query**: `RagQueryRequest` → `RagQueryResult`

## Graph update rules

| Event | Action |
|-------|--------|
| New doc_id | insert → merge nodes/edges |
| Same doc_id update | delete old + insert (`reindex`) |
| Delete | remove doc contribution |

- working_dir: `data/lightrag`
- Consume `DocumentBundle` only (no raw file parsing)
- New uploads **must** update graph node content via LightRAG

## Schema

个人知识库封闭名单：[`SCHEMA.md`](./SCHEMA.md)，机器可读副本 [`personal_kb.schema.json`](./personal_kb.schema.json)。版本 0.1.0。1.3 / 2.2 只对齐其中的属性名。

## Implement

`service.py` with LightRAG; keep `port.py` stable for P3 mocks.
