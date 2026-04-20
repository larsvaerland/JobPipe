from jobpipe.core import job_catalog as compat_catalog
from jobpipe.runtime import catalog as runtime_catalog


def test_core_job_catalog_reexports_runtime_catalog_symbols() -> None:
    assert compat_catalog.ingest_catalog_job is runtime_catalog.ingest_catalog_job
    assert compat_catalog.canonical_job_row is runtime_catalog.canonical_job_row
    assert compat_catalog.load_source_record_index is runtime_catalog.load_source_record_index
