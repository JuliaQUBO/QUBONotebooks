# Notebook data

This directory contains small, committed inputs that let the teaching notebooks
run and be checked without network access. Data-refresh commands are explicit
maintenance operations; normal notebook execution and CI do not contact the
source services.

## TCGA AML cancer-genomics aggregate

The `9-CancerGenomics_*` files are a reproducibility fixture for the planned
cancer-genomics lesson:

- `9-CancerGenomics_genes.csv` records the selected gene order, raw mutation-
  record count, and patient coverage;
- `9-CancerGenomics_coverage.csv` is the coverage vector `D`, labeled by gene;
- `9-CancerGenomics_comutation.csv` is the labeled co-mutation matrix `A`; and
- `9-CancerGenomics_provenance.json` records the source metadata, query,
  retrieval time, aggregation rules, row counts, license, and SHA-256 checksums.

The source query uses the public cBioPortal REST API with study `laml_tcga`,
molecular profile `laml_tcga_mutations`, sample list `laml_tcga_all`, and the
detailed mutation projection. Genes are ranked by descending mutation-record
count, with ascending gene symbol as the tie-break, and the first 33 are kept.
The coverage value for a selected gene is the number of unique patients with at
least one mutation record for that gene. Each off-diagonal `A[i,j]` is the
number of unique patients observed with both selected genes; repeated variants
and multiple samples for the same patient-gene pair therefore contribute once.
The diagonal is zero, and every pair `i < j` is populated symmetrically.

Only these gene-level aggregates are committed. Raw API responses and
patient/sample identifiers are neither written by the refresh script nor stored
in the repository. The source-record digest in the provenance file is computed
in memory over a canonical representation so a refresh can be audited without
redistributing that representation.

### Refreshing the fixture

From the repository root, run the opt-in network command:

```sh
make refresh-tcga-aml
```

This overwrites the four `9-CancerGenomics_*` files after validating the public
study, mutation profile, sample list, response fields, and aggregate invariants.
The default endpoint is `https://www.cbioportal.org/api`; the exact request and
retrieval time are captured in the provenance file. A refresh can legitimately
change when cBioPortal republishes the study. Given the same API response and
the same `--retrieved-at` value, `scripts/fetch_tcga_aml.py` writes byte-identical
files. Review all data and provenance diffs before committing a refresh, then
run:

```sh
make test-python
```

The refresh is intentionally excluded from `make test`, ordinary notebook
execution, and CI. It fails closed if the public-data metadata or required
response schema no longer matches the documented contract.

### Terms, attribution, and intended use

cBioPortal describes its generally available datasets as licensed under the
[Open Data Commons Open Database License 1.0][odbl], subject to any terms stated
for an individual study; see the [cBioPortal data-access FAQ][cbioportal-faq].
The queried study is marked public by the API. This derived fixture retains
cBioPortal and original-study attribution in its provenance. TCGA data users
should also review the [NCI genomic data policies][nci-policies] before
refreshing or redistributing data.

This fixture supports an educational optimization workflow. It is not a current
clinical dataset, is not suitable for patient-level analysis, and must not be
used as a basis for medical conclusions.

References:

- [cBioPortal for Cancer Genomics][cbioportal], including the API-hosted TCGA
  AML study;
- Ley et al., [*Genomic and epigenomic landscapes of adult de novo acute
  myeloid leukemia*][tcga-aml], *New England Journal of Medicine* (2013);
- Mazumder and Tayur, [published optimization tutorial][tutorial]; and
- the tutorial's [companion example repository][companion], cited for context
  only and not copied as implementation source.

[cbioportal]: https://www.cbioportal.org/
[cbioportal-faq]: https://docs.cbioportal.org/user-guide/faq/
[companion]: https://github.com/arulrhikm/Solving-QUBOs-on-Quantum-Computers
[nci-policies]: https://www.cancer.gov/ccg/research/genome-sequencing/tcga/history/policies
[odbl]: https://opendatacommons.org/licenses/odbl/1-0/
[tcga-aml]: https://pubmed.ncbi.nlm.nih.gov/23634996/
[tutorial]: https://doi.org/10.1287/educ.2025.0288
