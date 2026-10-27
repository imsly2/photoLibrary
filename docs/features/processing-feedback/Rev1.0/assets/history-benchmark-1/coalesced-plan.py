def plan_extend_entry(
    root: Path,
    entry_id: str,
    extra_changes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entry = load_entry(root, entry_id)
    before = json.loads(json.dumps(entry))
    after = json.loads(json.dumps(entry))
    # An extended scan updates its source record for every file. Retaining each
    # growing intermediate snapshot makes the history quadratic in file count.
    # Undo already uses the first before per path, and redo the last after; store
    # exactly those endpoints, retaining path order and this operation's identity.
    by_path: dict[str, dict[str, Any]] = {}
    for change in [*(entry.get("changes") or []), *extra_changes]:
        path = change["path"]
        if path not in by_path:
            by_path[path] = dict(change)
        else:
            by_path[path]["after"] = change["after"]
    after["changes"] = list(by_path.values())
    return [
        {
            "path": f"undo/entries/{entry_id}.json",
            "before": before,
            "after": after,
        },
        *extra_changes,
    ]
