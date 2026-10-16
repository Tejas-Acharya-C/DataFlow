"""Dataset version comparison and lineage analysis."""

from typing import Any, Dict

from dataflow.models.dataset import DatasetVersion


def compare_versions(version_a: DatasetVersion, version_b: DatasetVersion) -> Dict[str, Any]:
    """Compare two versions of a dataset and compute deltas."""
    cols_a = {item["name"]: item.get("type", "unknown") for item in version_a.schema_json}
    cols_b = {item["name"]: item.get("type", "unknown") for item in version_b.schema_json}

    names_a = set(cols_a.keys())
    names_b = set(cols_b.keys())

    added = sorted(list(names_b - names_a))
    removed = sorted(list(names_a - names_b))
    retained = sorted(list(names_a & names_b))

    schema_changes = []
    for col in retained:
        type_a = cols_a[col]
        type_b = cols_b[col]
        if type_a != type_b:
            schema_changes.append({
                "column": col,
                "change": "type_changed",
                "old_type": type_a,
                "new_type": type_b,
            })

    for col in added:
        schema_changes.append({
            "column": col,
            "change": "column_added",
            "type": cols_b[col],
        })

    for col in removed:
        schema_changes.append({
            "column": col,
            "change": "column_removed",
            "type": cols_a[col],
        })

    return {
        "version_a_number": version_a.version_number,
        "version_b_number": version_b.version_number,
        "row_count_delta": version_b.row_count - version_a.row_count,
        "column_count_delta": version_b.column_count - version_a.column_count,
        "columns_added": added,
        "columns_removed": removed,
        "columns_retained": retained,
        "schema_changes": schema_changes,
    }
