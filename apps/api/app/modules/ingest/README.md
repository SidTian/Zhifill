# P1 — Ingest

## I/O

- **In**: `IngestRequest` (`doc_id`, `FileRef`, options)
- **Out**: `DocumentBundle` (non-empty `text`)

## Must

- Support knowledge types: pdf, docx, md, txt, xlsx
- Produce clean text (+ optional tables/chunks_hint)
- Never call LightRAG / LLM

## Implement

Edit `service.py` only. Keep `port.py` stable.
