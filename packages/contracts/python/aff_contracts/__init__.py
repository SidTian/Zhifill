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
from aff_contracts.form_structure import FormStructureResult
from aff_contracts.ingest import DocumentBundle, IngestRequest
from aff_contracts.rag import (
    DeleteDocumentRequest,
    RagContext,
    RagQueryRequest,
    RagQueryResult,
    UpsertDocumentRequest,
    UpsertDocumentResult,
)
from aff_contracts.settings import Settings
from aff_contracts.task_spec import TaskField, TaskSpec

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
    "FormStructureResult",
    "IngestRequest",
    "JobStatus",
    "ParseFormRequest",
    "ParseFormResult",
    "RagContext",
    "RagQueryRequest",
    "RagQueryResult",
    "Settings",
    "SourceRef",
    "TaskField",
    "TaskSpec",
    "UpsertDocumentRequest",
    "UpsertDocumentResult",
]

__version__ = "0.3.0"
