"""API tests for transformation preview, apply, and version comparison."""

import io


def test_transformations_and_comparison_api(client):
    csv_bytes = b"id,city,temp\n1,Seattle,55\n2,Boston,65\n"
    up_res = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("weather.csv", io.BytesIO(csv_bytes), "text/csv")},
    )
    assert up_res.status_code == 201
    dataset_info = up_res.json()
    dataset_id = dataset_info["id"]
    v1_id = dataset_info["latest_version"]["id"]

    ops = [
        {"op": "rename_columns", "mapping": {"temp": "temperature_f"}},
        {"op": "trim_strings", "columns": ["city"], "uppercase": True},
    ]

    # Preview
    preview_res = client.post(
        "/api/v1/transformations/preview",
        json={"dataset_id": dataset_id, "version_id": v1_id, "operations": ops},
    )
    assert preview_res.status_code == 200
    pdata = preview_res.json()
    assert "temperature_f" in pdata["columns"]
    assert pdata["preview_rows"][0]["city"] == "SEATTLE"

    # Apply
    apply_res = client.post(
        "/api/v1/transformations/apply",
        json={"dataset_id": dataset_id, "version_id": v1_id, "operations": ops, "reason": "Rename and uppercase"},
    )
    assert apply_res.status_code == 201
    adata = apply_res.json()
    v2_id = adata["new_version_id"]
    assert adata["version_number"] == 2

    # Compare v1 and v2
    comp_res = client.post(
        "/api/v1/versions/compare",
        json={"version_a_id": v1_id, "version_b_id": v2_id},
    )
    assert comp_res.status_code == 200
    comp_data = comp_res.json()
    assert "temperature_f" in comp_data["columns_added"]
    assert "temp" in comp_data["columns_removed"]

    # Verify lineage endpoint
    lineage_res = client.get(f"/api/v1/versions/{v2_id}/lineage")
    assert lineage_res.status_code == 200
    lineage_data = lineage_res.json()
    assert len(lineage_data["nodes"]) == 2
    assert len(lineage_data["edges"]) == 1
    assert lineage_data["edges"][0]["source"] == v1_id
    assert lineage_data["edges"][0]["target"] == v2_id
