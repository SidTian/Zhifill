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

## Implement

`service.py` with LightRAG; keep `port.py` stable for P3 mocks.
