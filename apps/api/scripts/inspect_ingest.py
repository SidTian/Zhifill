from __future__ import annotations

import argparse
import hashlib
import mimetypes
import sys
from pathlib import Path


# 确保可以从 apps/api/scripts 运行
API_ROOT = Path(__file__).resolve().parents[1]

if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))


from aff_contracts import FileRef, IngestRequest
from app.modules.ingest.service import IngestService


MIME_BY_SUFFIX = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".pdf": "application/pdf",
    ".docx": (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document"
    ),
    ".xlsx": (
        "application/vnd.openxmlformats-officedocument."
        "spreadsheetml.sheet"
    ),
}


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)

    return digest.hexdigest()


def detect_mime(path: Path) -> str:
    suffix = path.suffix.lower()

    if suffix in MIME_BY_SUFFIX:
        return MIME_BY_SUFFIX[suffix]

    guessed_mime, _ = mimetypes.guess_type(path.name)

    return guessed_mime or "application/octet-stream"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect a real file using the Zhifill "
            "ingest service."
        )
    )

    parser.add_argument(
        "file",
        help="Path to the file to ingest.",
    )

    parser.add_argument(
        "-o",
        "--output",
        help=(
            "Optional path for saving the "
            "DocumentBundle JSON."
        ),
    )

    args = parser.parse_args()

    path = Path(args.file).expanduser().resolve()

    if not path.exists():
        raise SystemExit(
            f"File does not exist: {path}"
        )

    if not path.is_file():
        raise SystemExit(
            f"Not a file: {path}"
        )

    mime = detect_mime(path)

    request = IngestRequest(
        doc_id="doc_local_inspect",
        file=FileRef(
            path=str(path),
            filename=path.name,
            mime=mime,
            sha256=calculate_sha256(path),
            size=path.stat().st_size,
        ),
    )

    bundle = IngestService().ingest(request)

    json_text = bundle.model_dump_json(
        indent=2,
    )

    print(json_text)

    if args.output:
        output_path = Path(
            args.output
        ).expanduser().resolve()

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_path.write_text(
            json_text,
            encoding="utf-8",
        )

        print()
        print(
            f"Saved JSON to: {output_path}"
        )


if __name__ == "__main__":
    main()
