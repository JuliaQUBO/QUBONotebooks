from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "fetch_tcga_aml.py"
DATA_DIR = REPO_ROOT / "notebooks_data"
GENES_PATH = DATA_DIR / "9-CancerGenomics_genes.csv"
COVERAGE_PATH = DATA_DIR / "9-CancerGenomics_coverage.csv"
COMUTATION_PATH = DATA_DIR / "9-CancerGenomics_comutation.csv"
PROVENANCE_PATH = DATA_DIR / "9-CancerGenomics_provenance.json"

SPEC = importlib.util.spec_from_file_location("fetch_tcga_aml", SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
fetch_tcga_aml = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch_tcga_aml)


def mutation(patient: str, sample: str, gene: str, entrez: int) -> dict:
    return {
        "patientId": patient,
        "sampleId": sample,
        "entrezGeneId": entrez,
        "gene": {
            "entrezGeneId": entrez,
            "hugoGeneSymbol": gene,
        },
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


class AggregateConstructionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.records = [
            mutation("p1", "s1", "A", 1),
            # A second sample for the same patient-gene pair still counts once.
            mutation("p1", "s1-repeat", "A", 1),
            mutation("p1", "s1", "B", 2),
            mutation("p2", "s2", "A", 1),
            mutation("p2", "s2", "C", 3),
            mutation("p3", "s3", "B", 2),
            mutation("p3", "s3", "C", 3),
            mutation("p4", "s4", "D", 4),
        ]

    def test_ranks_records_then_deduplicates_patient_gene_coverage(self) -> None:
        aggregate = fetch_tcga_aml.build_aggregate(self.records, top_n=3)

        self.assertEqual(("A", "B", "C"), aggregate.genes)
        self.assertEqual((3, 2, 2), aggregate.mutation_record_counts)
        self.assertEqual((2, 2, 2), aggregate.patient_coverage)
        self.assertEqual(7, aggregate.unique_patient_gene_count)
        self.assertEqual(4, aggregate.patient_count)

    def test_constructs_every_symmetric_pair_with_zero_diagonal(self) -> None:
        aggregate = fetch_tcga_aml.build_aggregate(self.records, top_n=3)

        self.assertEqual(
            (
                (0, 1, 1),
                (1, 0, 1),
                (1, 1, 0),
            ),
            aggregate.comutation,
        )

    def test_ties_are_broken_by_gene_symbol(self) -> None:
        aggregate = fetch_tcga_aml.build_aggregate(
            [
                mutation("p1", "s1", "ZETA", 1),
                mutation("p2", "s2", "ALPHA", 2),
            ],
            top_n=2,
        )

        self.assertEqual(("ALPHA", "ZETA"), aggregate.genes)

    def test_missing_required_fields_fail_closed(self) -> None:
        incomplete = [
            {
                "patientId": "p1",
                "sampleId": "s1",
                "entrezGeneId": 1,
                "gene": {"entrezGeneId": 1},
            }
        ]

        with self.assertRaisesRegex(
            fetch_tcga_aml.DataValidationError,
            "hugoGeneSymbol",
        ):
            fetch_tcga_aml.build_aggregate(incomplete, top_n=1)

    def test_refuses_more_genes_than_the_response_contains(self) -> None:
        with self.assertRaisesRegex(
            fetch_tcga_aml.DataValidationError,
            "requested 5 genes",
        ):
            fetch_tcga_aml.build_aggregate(self.records, top_n=5)


class SourceFetchingTests(unittest.TestCase):
    def test_fetches_the_current_post_endpoint_and_paginates(self) -> None:
        first_page = [
            mutation("p1", "s1", "A", 1),
            mutation("p2", "s2", "B", 2),
        ]
        second_page = [mutation("p3", "s3", "C", 3)]
        calls = []

        def request(url, *, method="GET", body=None, timeout=60.0):
            calls.append((url, method, body, timeout))
            if url.endswith("/studies/laml_tcga"):
                return {
                    "studyId": "laml_tcga",
                    "publicStudy": True,
                    "groups": "PUBLIC",
                }
            if url.endswith("/molecular-profiles/laml_tcga_mutations"):
                return {
                    "molecularProfileId": "laml_tcga_mutations",
                    "studyId": "laml_tcga",
                    "molecularAlterationType": "MUTATION_EXTENDED",
                    "datatype": "MAF",
                }
            if url.endswith("/sample-lists/laml_tcga_all"):
                return {
                    "sampleListId": "laml_tcga_all",
                    "studyId": "laml_tcga",
                    "sampleCount": 3,
                }
            if "pageNumber=0" in url:
                return first_page
            if "pageNumber=1" in url:
                return second_page
            raise AssertionError(f"unexpected request: {url}")

        with mock.patch.object(fetch_tcga_aml, "_request_json", side_effect=request):
            fetched = fetch_tcga_aml.fetch_source(
                api_base="https://example.test/api/",
                page_size=2,
                timeout=12.0,
            )

        self.assertEqual(first_page + second_page, fetched.records)
        mutation_calls = [call for call in calls if "mutations/fetch" in call[0]]
        self.assertEqual(2, len(mutation_calls))
        self.assertEqual(["POST", "POST"], [call[1] for call in mutation_calls])
        self.assertEqual(
            [{"sampleListId": "laml_tcga_all"}] * 2,
            [call[2] for call in mutation_calls],
        )
        self.assertTrue(
            all("projection=DETAILED" in call[0] for call in mutation_calls)
        )
        self.assertTrue(all("pageSize=2" in call[0] for call in mutation_calls))


class ArtifactWritingTests(unittest.TestCase):
    def test_outputs_are_deterministic_and_contain_no_patient_identifiers(self) -> None:
        records = [
            mutation("TCGA-PRIVATE-1", "TCGA-PRIVATE-1-01", "A", 1),
            mutation("TCGA-PRIVATE-2", "TCGA-PRIVATE-2-01", "B", 2),
            mutation("TCGA-PRIVATE-2", "TCGA-PRIVATE-2-01", "A", 1),
        ]
        aggregate = fetch_tcga_aml.build_aggregate(records, top_n=2)
        source = fetch_tcga_aml.SourceMetadata(
            study={
                "studyId": "laml_tcga",
                "name": "AML fixture",
                "publicStudy": True,
                "groups": "PUBLIC",
                "importDate": "2026-01-07 14:58:26",
                "referenceGenome": "hg19",
            },
            molecular_profile={
                "molecularProfileId": "laml_tcga_mutations",
                "studyId": "laml_tcga",
                "molecularAlterationType": "MUTATION_EXTENDED",
                "datatype": "MAF",
            },
            sample_list={
                "sampleListId": "laml_tcga_all",
                "studyId": "laml_tcga",
                "sampleCount": 2,
            },
        )
        record_digest = fetch_tcga_aml.canonical_record_digest(records)

        with (
            tempfile.TemporaryDirectory() as first_tmp,
            tempfile.TemporaryDirectory() as second_tmp,
        ):
            first = Path(first_tmp)
            second = Path(second_tmp)
            for output in (first, second):
                fetch_tcga_aml.write_artifacts(
                    output,
                    aggregate,
                    source,
                    retrieved_at="2026-07-20T00:00:00Z",
                    mutation_records_sha256=record_digest,
                )

            for name in (
                *fetch_tcga_aml.OUTPUT_FILENAMES,
                fetch_tcga_aml.PROVENANCE_FILENAME,
            ):
                self.assertEqual(
                    (first / name).read_bytes(),
                    (second / name).read_bytes(),
                )
                self.assertNotIn(b"TCGA-PRIVATE", (first / name).read_bytes())

            provenance = json.loads(
                (first / fetch_tcga_aml.PROVENANCE_FILENAME).read_text()
            )
            for name, expected_digest in provenance["output_sha256"].items():
                self.assertEqual(expected_digest, sha256(first / name))

    def test_rejects_non_public_source_metadata(self) -> None:
        source = fetch_tcga_aml.SourceMetadata(
            study={"studyId": "laml_tcga", "publicStudy": False},
            molecular_profile={
                "molecularProfileId": "laml_tcga_mutations",
                "studyId": "laml_tcga",
                "molecularAlterationType": "MUTATION_EXTENDED",
                "datatype": "MAF",
            },
            sample_list={
                "sampleListId": "laml_tcga_all",
                "studyId": "laml_tcga",
                "sampleCount": 1,
            },
        )

        with self.assertRaisesRegex(
            fetch_tcga_aml.DataValidationError,
            "not public",
        ):
            fetch_tcga_aml.validate_source_metadata(source)


class CommittedArtifactTests(unittest.TestCase):
    def test_committed_aggregate_is_complete_symmetric_and_provenanced(self) -> None:
        with GENES_PATH.open(newline="") as handle:
            gene_rows = list(csv.DictReader(handle))
        with COVERAGE_PATH.open(newline="") as handle:
            coverage_rows = list(csv.DictReader(handle))
        with COMUTATION_PATH.open(newline="") as handle:
            matrix_rows = list(csv.reader(handle))
        provenance = json.loads(PROVENANCE_PATH.read_text())

        genes = [row["gene"] for row in gene_rows]
        mutation_counts = [int(row["mutation_record_count"]) for row in gene_rows]
        coverage = [int(row["patient_count"]) for row in coverage_rows]

        self.assertEqual(33, len(genes))
        self.assertEqual(33, len(set(genes)))
        self.assertEqual(list(range(1, 34)), [int(row["rank"]) for row in gene_rows])
        self.assertEqual(genes, [row["gene"] for row in coverage_rows])
        self.assertEqual(
            coverage,
            [int(row["patient_coverage"]) for row in gene_rows],
        )
        self.assertTrue(all(value >= 0 for value in mutation_counts + coverage))
        self.assertTrue(
            all(
                patient_count <= mutation_count
                for patient_count, mutation_count in zip(coverage, mutation_counts)
            )
        )
        self.assertTrue(
            all(
                left > right or (left == right and genes[index] < genes[index + 1])
                for index, (left, right) in enumerate(
                    zip(mutation_counts, mutation_counts[1:])
                )
            )
        )

        self.assertEqual(["gene", *genes], matrix_rows[0])
        self.assertEqual(33, len(matrix_rows[1:]))
        matrix = []
        for index, row in enumerate(matrix_rows[1:]):
            self.assertEqual(genes[index], row[0])
            self.assertEqual(33, len(row[1:]))
            matrix.append([int(value) for value in row[1:]])

        for i in range(33):
            self.assertEqual(0, matrix[i][i])
            for j in range(33):
                self.assertEqual(matrix[i][j], matrix[j][i])
                self.assertGreaterEqual(matrix[i][j], 0)
                self.assertLessEqual(matrix[i][j], coverage[i])
                self.assertLessEqual(matrix[i][j], coverage[j])

        self.assertEqual("ODC-ODbL-1.0", provenance["license"]["id"])
        self.assertEqual("POST", provenance["query"]["method"])
        self.assertEqual(
            {"sampleListId": "laml_tcga_all"},
            provenance["query"]["body"],
        )
        self.assertTrue(provenance["source"]["study"]["publicStudy"])
        self.assertEqual(33, provenance["aggregate"]["selected_gene_count"])
        self.assertEqual(1, provenance["script_version"])
        self.assertEqual(
            {
                "9-CancerGenomics_comutation.csv": 33,
                "9-CancerGenomics_coverage.csv": 33,
                "9-CancerGenomics_genes.csv": 33,
            },
            provenance["output_row_counts"],
        )

        self.assertEqual(
            {
                "9-CancerGenomics_comutation.csv",
                "9-CancerGenomics_coverage.csv",
                "9-CancerGenomics_genes.csv",
            },
            set(provenance["output_sha256"]),
        )
        for name, expected_digest in provenance["output_sha256"].items():
            self.assertEqual(expected_digest, sha256(DATA_DIR / name))

        committed_text = "\n".join(
            path.read_text() for path in (GENES_PATH, COVERAGE_PATH, COMUTATION_PATH)
        )
        self.assertNotIn("TCGA-AB-", committed_text)
        self.assertNotIn("patientId", committed_text)
        self.assertNotIn("sampleId", committed_text)


if __name__ == "__main__":
    unittest.main()
