#!/usr/bin/env python3
"""Refresh the aggregate TCGA AML inputs used by the cancer-genomics notebook.

The public cBioPortal response is reduced to gene-level counts and a co-mutation
matrix. Raw mutation records and patient/sample identifiers are never written.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import NamedTuple, Sequence


API_BASE = "https://www.cbioportal.org/api"
STUDY_ID = "laml_tcga"
MOLECULAR_PROFILE_ID = "laml_tcga_mutations"
SAMPLE_LIST_ID = "laml_tcga_all"
TOP_N = 33
PAGE_SIZE = 1_000
SCRIPT_VERSION = 1
USER_AGENT = "JuliaQUBO-QUBONotebooks-TCGA-refresh/1.0"

GENES_FILENAME = "9-CancerGenomics_genes.csv"
COVERAGE_FILENAME = "9-CancerGenomics_coverage.csv"
COMUTATION_FILENAME = "9-CancerGenomics_comutation.csv"
PROVENANCE_FILENAME = "9-CancerGenomics_provenance.json"
OUTPUT_FILENAMES = (
    GENES_FILENAME,
    COVERAGE_FILENAME,
    COMUTATION_FILENAME,
)

DATABASE_LICENSE_URL = "https://opendatacommons.org/licenses/odbl/1-0/"
CBIOPORTAL_DATA_TERMS_URL = "https://docs.cbioportal.org/user-guide/faq/"
TCGA_AML_STUDY_URL = "https://pubmed.ncbi.nlm.nih.gov/23634996/"


class DataValidationError(ValueError):
    """Raised when source data do not satisfy the expected public schema."""


class Aggregate(NamedTuple):
    """Patient-level aggregate for the selected genes."""

    genes: tuple[str, ...]
    mutation_record_counts: tuple[int, ...]
    patient_coverage: tuple[int, ...]
    comutation: tuple[tuple[int, ...], ...]
    raw_record_count: int
    unique_patient_gene_count: int
    patient_count: int


class SourceMetadata(NamedTuple):
    """Public cBioPortal metadata associated with a mutation response."""

    study: dict
    molecular_profile: dict
    sample_list: dict


class FetchResult(NamedTuple):
    """Mutation records and the public metadata used to obtain them."""

    records: list[dict]
    source: SourceMetadata


def _required_mapping(value: object, field: str, record_index: int) -> dict:
    if not isinstance(value, dict):
        raise DataValidationError(
            f"mutation record {record_index} field {field!r} must be an object"
        )
    return value


def _required_string(mapping: dict, field: str, context: str) -> str:
    value = mapping.get(field)
    if not isinstance(value, str) or not value.strip():
        raise DataValidationError(f"{context} requires a non-empty {field!r}")
    return value.strip()


def _required_integer(mapping: dict, field: str, context: str) -> int:
    value = mapping.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise DataValidationError(f"{context} requires an integer {field!r}")
    return value


def _normalized_record(record: object, index: int) -> tuple[str, str, str, int]:
    mapping = _required_mapping(record, "record", index)
    context = f"mutation record {index}"
    patient_id = _required_string(mapping, "patientId", context)
    sample_id = _required_string(mapping, "sampleId", context)
    entrez_gene_id = _required_integer(mapping, "entrezGeneId", context)
    gene = _required_mapping(mapping.get("gene"), "gene", index)
    symbol = _required_string(gene, "hugoGeneSymbol", f"{context} gene")
    nested_entrez = _required_integer(gene, "entrezGeneId", f"{context} gene")
    if nested_entrez != entrez_gene_id:
        raise DataValidationError(
            f"{context} has inconsistent top-level and gene entrezGeneId values"
        )
    return patient_id, sample_id, symbol, entrez_gene_id


def build_aggregate(records: Sequence[object], *, top_n: int = TOP_N) -> Aggregate:
    """Rank genes by mutation records and aggregate unique patient-gene pairs."""

    if top_n <= 0:
        raise DataValidationError("top_n must be a positive integer")
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        raise DataValidationError("mutation response must be a sequence")

    record_counts: Counter[str] = Counter()
    patient_genes: dict[str, set[str]] = defaultdict(set)
    for index, record in enumerate(records):
        patient_id, _sample_id, symbol, _entrez_gene_id = _normalized_record(
            record, index
        )
        record_counts[symbol] += 1
        patient_genes[patient_id].add(symbol)

    ranked_genes = sorted(record_counts, key=lambda gene: (-record_counts[gene], gene))
    if len(ranked_genes) < top_n:
        raise DataValidationError(
            f"requested {top_n} genes, but the response contains only "
            f"{len(ranked_genes)} unique genes"
        )
    genes = tuple(ranked_genes[:top_n])
    gene_index = {gene: index for index, gene in enumerate(genes)}

    patient_coverage = [0] * top_n
    comutation = [[0] * top_n for _ in range(top_n)]
    for observed_genes in patient_genes.values():
        selected_indices = sorted(
            gene_index[gene] for gene in observed_genes if gene in gene_index
        )
        for index in selected_indices:
            patient_coverage[index] += 1
        for left, right in combinations(selected_indices, 2):
            comutation[left][right] += 1
            comutation[right][left] += 1

    aggregate = Aggregate(
        genes=genes,
        mutation_record_counts=tuple(record_counts[gene] for gene in genes),
        patient_coverage=tuple(patient_coverage),
        comutation=tuple(tuple(row) for row in comutation),
        raw_record_count=len(records),
        unique_patient_gene_count=sum(len(genes) for genes in patient_genes.values()),
        patient_count=len(patient_genes),
    )
    validate_aggregate(aggregate)
    return aggregate


def validate_aggregate(aggregate: Aggregate) -> None:
    """Validate dimensions and count invariants for a generated aggregate."""

    size = len(aggregate.genes)
    if size == 0 or len(set(aggregate.genes)) != size:
        raise DataValidationError("aggregate genes must be non-empty and unique")
    if len(aggregate.mutation_record_counts) != size:
        raise DataValidationError("mutation record counts do not match gene count")
    if len(aggregate.patient_coverage) != size:
        raise DataValidationError("patient coverage does not match gene count")
    if len(aggregate.comutation) != size or any(
        len(row) != size for row in aggregate.comutation
    ):
        raise DataValidationError("co-mutation matrix must be square")

    for index, (record_count, coverage) in enumerate(
        zip(aggregate.mutation_record_counts, aggregate.patient_coverage)
    ):
        if record_count < 0 or coverage < 0:
            raise DataValidationError("aggregate counts must be nonnegative")
        if coverage > record_count:
            raise DataValidationError(
                f"coverage for {aggregate.genes[index]} exceeds mutation records"
            )
        if aggregate.comutation[index][index] != 0:
            raise DataValidationError("co-mutation matrix diagonal must be zero")
        for other in range(size):
            count = aggregate.comutation[index][other]
            if count < 0:
                raise DataValidationError("co-mutation counts must be nonnegative")
            if count != aggregate.comutation[other][index]:
                raise DataValidationError("co-mutation matrix must be symmetric")
            if count > min(coverage, aggregate.patient_coverage[other]):
                raise DataValidationError(
                    "co-mutation count cannot exceed either gene's coverage"
                )


def canonical_record_digest(records: Sequence[object]) -> str:
    """Hash a canonical minimal representation without retaining it on disk."""

    normalized = []
    for index, record in enumerate(records):
        patient_id, sample_id, symbol, entrez_gene_id = _normalized_record(
            record, index
        )
        normalized.append(
            {
                "entrezGeneId": entrez_gene_id,
                "gene": symbol,
                "patientId": patient_id,
                "sampleId": sample_id,
            }
        )
    normalized.sort(
        key=lambda row: (
            row["patientId"],
            row["sampleId"],
            row["gene"],
            row["entrezGeneId"],
        )
    )
    payload = json.dumps(
        normalized,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _request_json(
    url: str,
    *,
    method: str = "GET",
    body: dict | None = None,
    timeout: float = 60.0,
) -> object:
    encoded_body = None
    if body is not None:
        encoded_body = json.dumps(body, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=encoded_body,
        method=method,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                raise RuntimeError(
                    f"cBioPortal returned unexpected HTTP status {status}"
                )
            payload = response.read()
    except urllib.error.HTTPError as error:
        details = error.read(500).decode("utf-8", errors="replace")
        raise RuntimeError(
            f"cBioPortal request failed with HTTP {error.code}: {details}"
        ) from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"cBioPortal request failed: {error.reason}") from error

    try:
        return json.loads(payload)
    except json.JSONDecodeError as error:
        raise RuntimeError("cBioPortal returned invalid JSON") from error


def validate_source_metadata(source: SourceMetadata) -> None:
    """Require the exact public study/profile/sample-list contract."""

    study_id = _required_string(source.study, "studyId", "study metadata")
    if study_id != STUDY_ID:
        raise DataValidationError(f"unexpected studyId {study_id!r}")
    if source.study.get("publicStudy") is not True:
        raise DataValidationError(f"study {STUDY_ID!r} is not public")
    groups = source.study.get("groups", "")
    if not isinstance(groups, str) or "PUBLIC" not in groups.split(","):
        raise DataValidationError(f"study {STUDY_ID!r} is not in the PUBLIC group")

    profile_id = _required_string(
        source.molecular_profile,
        "molecularProfileId",
        "molecular profile metadata",
    )
    if profile_id != MOLECULAR_PROFILE_ID:
        raise DataValidationError(f"unexpected molecularProfileId {profile_id!r}")
    if source.molecular_profile.get("studyId") != STUDY_ID:
        raise DataValidationError("molecular profile belongs to a different study")
    if source.molecular_profile.get("molecularAlterationType") != "MUTATION_EXTENDED":
        raise DataValidationError("molecular profile is not mutation data")
    if source.molecular_profile.get("datatype") != "MAF":
        raise DataValidationError("molecular profile does not use MAF data")

    sample_list_id = _required_string(
        source.sample_list,
        "sampleListId",
        "sample list metadata",
    )
    if sample_list_id != SAMPLE_LIST_ID:
        raise DataValidationError(f"unexpected sampleListId {sample_list_id!r}")
    if source.sample_list.get("studyId") != STUDY_ID:
        raise DataValidationError("sample list belongs to a different study")
    sample_count = _required_integer(
        source.sample_list,
        "sampleCount",
        "sample list metadata",
    )
    if sample_count <= 0:
        raise DataValidationError("sample list must contain at least one sample")


def fetch_source(
    *,
    api_base: str = API_BASE,
    page_size: int = PAGE_SIZE,
    timeout: float = 60.0,
) -> FetchResult:
    """Fetch and validate the current public AML mutation cohort."""

    if page_size <= 0 or page_size > 10_000_000:
        raise ValueError("page_size must be between 1 and 10,000,000")
    api_base = api_base.rstrip("/")
    study = _request_json(f"{api_base}/studies/{STUDY_ID}", timeout=timeout)
    profile = _request_json(
        f"{api_base}/molecular-profiles/{MOLECULAR_PROFILE_ID}",
        timeout=timeout,
    )
    sample_list = _request_json(
        f"{api_base}/sample-lists/{SAMPLE_LIST_ID}",
        timeout=timeout,
    )
    source = SourceMetadata(
        study=_required_mapping(study, "study", 0),
        molecular_profile=_required_mapping(profile, "molecular_profile", 0),
        sample_list=_required_mapping(sample_list, "sample_list", 0),
    )
    validate_source_metadata(source)

    records: list[dict] = []
    page_number = 0
    while True:
        query = urllib.parse.urlencode(
            {
                "projection": "DETAILED",
                "pageSize": page_size,
                "pageNumber": page_number,
            }
        )
        page = _request_json(
            f"{api_base}/molecular-profiles/{MOLECULAR_PROFILE_ID}/"
            f"mutations/fetch?{query}",
            method="POST",
            body={"sampleListId": SAMPLE_LIST_ID},
            timeout=timeout,
        )
        if not isinstance(page, list):
            raise DataValidationError("mutation endpoint response must be a list")
        if not all(isinstance(record, dict) for record in page):
            raise DataValidationError("mutation endpoint returned a non-object record")
        records.extend(page)
        if len(page) < page_size:
            break
        page_number += 1

    if not records:
        raise DataValidationError("mutation endpoint returned no records")
    return FetchResult(records=records, source=source)


def _write_csv(path: Path, rows: Sequence[Sequence[object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerows(rows)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _public_source_summary(source: SourceMetadata) -> dict:
    study_fields = (
        "studyId",
        "name",
        "description",
        "publicStudy",
        "groups",
        "importDate",
        "referenceGenome",
        "allSampleCount",
        "sequencedSampleCount",
    )
    profile_fields = (
        "molecularProfileId",
        "studyId",
        "name",
        "description",
        "molecularAlterationType",
        "datatype",
    )
    sample_list_fields = (
        "sampleListId",
        "studyId",
        "name",
        "description",
        "sampleCount",
    )
    return {
        "study": {
            key: source.study[key] for key in study_fields if key in source.study
        },
        "molecular_profile": {
            key: source.molecular_profile[key]
            for key in profile_fields
            if key in source.molecular_profile
        },
        "sample_list": {
            key: source.sample_list[key]
            for key in sample_list_fields
            if key in source.sample_list
        },
    }


def write_artifacts(
    output_dir: Path,
    aggregate: Aggregate,
    source: SourceMetadata,
    *,
    retrieved_at: str,
    mutation_records_sha256: str,
    api_base: str = API_BASE,
    page_size: int = PAGE_SIZE,
) -> tuple[Path, ...]:
    """Write deterministic aggregate CSV files and their provenance manifest."""

    validate_aggregate(aggregate)
    validate_source_metadata(source)
    try:
        parsed_retrieved_at = datetime.fromisoformat(
            retrieved_at.removesuffix("Z") + "+00:00"
        )
    except ValueError as error:
        raise ValueError("retrieved_at must be a valid RFC 3339 UTC timestamp") from error
    if (
        not retrieved_at.endswith("Z")
        or parsed_retrieved_at.utcoffset() != timezone.utc.utcoffset(None)
    ):
        raise ValueError("retrieved_at must be an RFC 3339 UTC timestamp ending in Z")
    if len(mutation_records_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in mutation_records_sha256
    ):
        raise ValueError("mutation_records_sha256 must be a lowercase SHA-256 digest")
    if page_size <= 0 or page_size > 10_000_000:
        raise ValueError("page_size must be between 1 and 10,000,000")
    api_base = api_base.rstrip("/")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".tcga-aml-", dir=output_dir) as tmp:
        temporary = Path(tmp)
        genes_path = temporary / GENES_FILENAME
        coverage_path = temporary / COVERAGE_FILENAME
        comutation_path = temporary / COMUTATION_FILENAME

        _write_csv(
            genes_path,
            [
                ("rank", "gene", "mutation_record_count", "patient_coverage"),
                *(
                    (rank, gene, records, coverage)
                    for rank, (gene, records, coverage) in enumerate(
                        zip(
                            aggregate.genes,
                            aggregate.mutation_record_counts,
                            aggregate.patient_coverage,
                        ),
                        start=1,
                    )
                ),
            ],
        )
        _write_csv(
            coverage_path,
            [
                ("gene", "patient_count"),
                *zip(aggregate.genes, aggregate.patient_coverage),
            ],
        )
        _write_csv(
            comutation_path,
            [
                ("gene", *aggregate.genes),
                *(
                    (gene, *row)
                    for gene, row in zip(aggregate.genes, aggregate.comutation)
                ),
            ],
        )

        output_sha256 = {
            path.name: _file_sha256(path)
            for path in (genes_path, coverage_path, comutation_path)
        }
        provenance = {
            "aggregate": {
                "aggregation_unit": "unique patientId-gene pairs",
                "co_mutation_definition": (
                    "number of unique patients containing both selected genes"
                ),
                "patient_count": aggregate.patient_count,
                "raw_mutation_record_count": aggregate.raw_record_count,
                "selected_gene_count": len(aggregate.genes),
                "selection_rule": (
                    "descending mutation-record count, then ascending gene symbol"
                ),
                "unique_patient_gene_count": aggregate.unique_patient_gene_count,
            },
            "generated_by": "scripts/fetch_tcga_aml.py",
            "script_version": SCRIPT_VERSION,
            "license": {
                "id": "ODC-ODbL-1.0",
                "name": "Open Data Commons Open Database License 1.0",
                "terms_url": CBIOPORTAL_DATA_TERMS_URL,
                "url": DATABASE_LICENSE_URL,
                "attribution": (
                    "cBioPortal and the original TCGA AML study must be cited"
                ),
            },
            "mutation_records_sha256": mutation_records_sha256,
            "output_row_counts": {
                COMUTATION_FILENAME: len(aggregate.genes),
                COVERAGE_FILENAME: len(aggregate.genes),
                GENES_FILENAME: len(aggregate.genes),
            },
            "output_sha256": output_sha256,
            "query": {
                "body": {"sampleListId": SAMPLE_LIST_ID},
                "endpoint": (
                    f"{api_base}/molecular-profiles/{MOLECULAR_PROFILE_ID}/"
                    "mutations/fetch"
                ),
                "method": "POST",
                "pagination": {
                    "pageNumber": "starts at 0 and increments until a short page",
                    "pageSize": page_size,
                },
                "projection": "DETAILED",
            },
            "references": {
                "cbioportal": "https://www.cbioportal.org/",
                "tcga_aml_study": TCGA_AML_STUDY_URL,
            },
            "retrieved_at": retrieved_at,
            "schema_version": 1,
            "source": _public_source_summary(source),
        }
        provenance_path = temporary / PROVENANCE_FILENAME
        provenance_path.write_text(
            json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        written_paths = []
        for name in (*OUTPUT_FILENAMES, PROVENANCE_FILENAME):
            destination = output_dir / name
            os.replace(temporary / name, destination)
            written_paths.append(destination)
    return tuple(written_paths)


def _utc_timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch public TCGA AML mutations from cBioPortal and write only "
            "deterministic gene-level aggregate files."
        )
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "notebooks_data",
        help="Directory for aggregate CSV and provenance files.",
    )
    parser.add_argument(
        "--api-base",
        default=API_BASE,
        help="cBioPortal API base URL (primarily for controlled testing).",
    )
    parser.add_argument("--top-n", type=int, default=TOP_N)
    parser.add_argument("--page-size", type=int, default=PAGE_SIZE)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument(
        "--retrieved-at",
        help="Override the RFC 3339 UTC retrieval timestamp for reproducibility tests.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fetched = fetch_source(
        api_base=args.api_base,
        page_size=args.page_size,
        timeout=args.timeout,
    )
    aggregate = build_aggregate(fetched.records, top_n=args.top_n)
    written = write_artifacts(
        args.output_dir,
        aggregate,
        fetched.source,
        retrieved_at=args.retrieved_at or _utc_timestamp(),
        mutation_records_sha256=canonical_record_digest(fetched.records),
        api_base=args.api_base,
        page_size=args.page_size,
    )
    print(
        f"Wrote {len(written)} aggregate files for {len(aggregate.genes)} genes "
        f"from {aggregate.raw_record_count} mutation records."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
