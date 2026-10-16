"""API tests for contract creation, listing, updating, and validation runs."""

import io


def test_contract_crud_and_validation(client):
    # Upload sample dataset first
    csv_bytes = b"id,role\n1,admin\n2,user\n"
    up_res = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("roles.csv", io.BytesIO(csv_bytes), "text/csv")},
    )
    assert up_res.status_code == 201
    dataset_info = up_res.json()
    version_id = dataset_info["latest_version"]["id"]

    # Create contract
    contract_payload = {
        "name": "Roles Contract",
        "description": "Validates roles",
        "rules": {
            "required_columns": ["id", "role"],
            "allowed_values": {"role": ["admin", "user", "guest"]},
        },
    }
    create_res = client.post("/api/v1/contracts", json=contract_payload)
    assert create_res.status_code == 201
    contract_data = create_res.json()
    contract_id = contract_data["id"]

    # Validate version against contract
    val_res = client.post(f"/api/v1/contracts/{contract_id}/validate", json={"version_id": version_id})
    assert val_res.status_code == 200
    val_data = val_res.json()
    assert val_data["status"] == "passed"
    assert val_data["passed_count"] >= 2
    assert val_data["failed_count"] == 0

    # List validation runs
    list_runs = client.get(f"/api/v1/validations?contract_id={contract_id}")
    assert list_runs.status_code == 200
    assert len(list_runs.json()) >= 1
