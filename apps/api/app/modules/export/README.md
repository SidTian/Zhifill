# P4 — Export

## I/O

- **In**: `ExportRequest` (source file + confirmed `FormField[]` with locators)
- **Out**: `ExportResult` (output FileRef + optional side_files)

## Writers

`writers/excel.py`, `word.py`, `pdf.py` — preserve layout; locator-based only.
