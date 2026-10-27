def plan_extend_entry(
    root: Path,
    entry_id: str,
    extra_changes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entry = load_entry(root, entry_id)
    before = json.loads(json.dumps(entry))
    after = json.loads(json.dumps(entry))
    after["changes"] = list(entry.get("changes") or []) + extra_changes
    return [
        {
            "path": f"undo/entries/{entry_id}.json",
            "before": before,
            "after": after,
        },
        *extra_changes,
    ]
