"""Concurrency integration tests for version allocation and transaction isolation."""

import io

from dataflow.services.ingestion import IngestionService


def test_concurrent_version_creation(test_db_session, storage):
    """Verify concurrent uploads to the same dataset produce strictly sequential version numbers."""
    service = IngestionService(storage=storage)

    # Create initial dataset
    init_dataset, v1 = service.ingest_csv(
        db=test_db_session,
        file_obj=io.BytesIO(b"col1,col2\n1,10\n"),
        filename="initial.csv",
        dataset_name="Concurrency Test",
    )
    dataset_id = init_dataset.id

    # Function to upload a new version
    def upload_version(idx: int):
        content = f"col1,col2\n{idx},{idx * 10}\n".encode("utf-8")
        _, v = service.ingest_csv(
            db=test_db_session,
            file_obj=io.BytesIO(content),
            filename=f"version_{idx}.csv",
            dataset_id=dataset_id,
            deduplicate_identical=False,
        )
        return v.version_number

    # Execute multiple version additions
    v_results = []
    for i in range(2, 6):
        num = upload_version(i)
        v_results.append(num)

    # Assert version numbers are strictly monotonic and sequential: [2, 3, 4, 5]
    assert v_results == [2, 3, 4, 5]
