"""API integration tests for Dataset upload, listing, preview, and download."""

import io


def test_upload_and_get_dataset(client):
    csv_bytes = b"col_a,col_b\nval1,10\nval2,20\n"
    response = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("test.csv", io.BytesIO(csv_bytes), "text/csv")},
        data={"name": "API Test Dataset", "description": "Testing through API"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "API Test Dataset"
    assert data["version_count"] == 1
    dataset_id = data["id"]
    assert data["latest_version"]["id"] is not None

    # List datasets
    list_res = client.get("/api/v1/datasets")
    assert list_res.status_code == 200
    assert list_res.json()["total"] >= 1

    # Preview rows
    preview_res = client.get(f"/api/v1/datasets/{dataset_id}/preview")
    assert preview_res.status_code == 200
    preview_data = preview_res.json()
    assert preview_data["total_rows"] == 2
    assert len(preview_data["rows"]) == 2

    # Download
    dl_res = client.get(f"/api/v1/datasets/{dataset_id}/download")
    assert dl_res.status_code == 200
    assert b"col_a,col_b" in dl_res.content

    # Delete (soft archive)
    del_res = client.delete(f"/api/v1/datasets/{dataset_id}")
    assert del_res.status_code == 200


def test_health_endpoints(client):
    res_live = client.get("/api/v1/health/live")
    assert res_live.status_code == 200
    assert res_live.json()["status"] == "alive"

    res_ready = client.get("/api/v1/health/ready")
    assert res_ready.status_code == 200
    assert res_ready.json()["status"] == "ready"
