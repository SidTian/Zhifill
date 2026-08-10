"""Contract mirrors — keep in sync with packages/contracts/jsonschema."""

from aff_contracts.common import ErrorBody, FileRef, JobStatus, SourceRef
from aff_contracts.export import ExportRequest, ExportResult
from aff_contracts.fill import (
    FillFormRequest,
    FillResult,
    FormField,
    FormJob,
    ParseFormRequest,
    ParseFormResult,
)
from aff_contracts.ingest import DocumentBundle, IngestRequest
from aff_contracts.rag import (
    DeleteDocumentRequest,
    RagQueryRequest,
    RagQueryResult,
    UpsertDocumentRequest,
    UpsertDocumentResult,
)
from aff_contracts.settings import Settings

__all__ = [
    "DeleteDocumentRequest",
    "DocumentBundle",
    "ErrorBody",
    "ExportRequest",
    "ExportResult",
    "FileRef",
    "FillFormRequest",
    "FillResult",
    "FormField",
    "FormJob",
    "IngestRequest",
    "JobStatus",
    "ParseFormRequest",
    "ParseFormResult",
    "RagQueryRequest",
    "RagQueryResult",
    "Settings",
    "SourceRef",
    "UpsertDocumentRequest",
    "UpsertDocumentResult",
]

__version__ = "0.1.0"
