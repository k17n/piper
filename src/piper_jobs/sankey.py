"""Sankey builder: one path per application, adjacent pairs counted into links."""

from __future__ import annotations

from collections import defaultdict

from .filters import AppRow
from .schema import PROGRESS, RANK, Stage

SOURCE_LABELS = {
    "linkedin": "LinkedIn",
    "ats": "Company site / ATS",
    "recruiter": "Recruiter",
    "direct": "Direct",
    "referral": "Referral",
    "other": "Other source",
}


def stage_label(stage: str) -> str:
    return stage.capitalize()


def path_for(row: AppRow) -> list[str]:
    """source → applied → … → final stage. Stages appear in progress order."""
    final = Stage(row.stage)
    steps = [s for s in PROGRESS if s.value in row.reached]
    if Stage.applied not in steps:
        steps.insert(0, Stage.applied)
    if final in RANK:
        steps = [s for s in steps if RANK[s] <= RANK[final]]
        if final not in steps:
            steps.append(final)
    else:
        steps = [s for s in steps if s is not Stage.accepted] + [final]
    source = SOURCE_LABELS.get(row.app.source, SOURCE_LABELS["other"])
    return [source] + [stage_label(s.value) for s in steps]


def build_sankey(rows: list[AppRow]) -> dict:
    link_ids: dict[tuple[str, str], list[int]] = defaultdict(list)
    node_kind: dict[str, str] = {}
    for row in rows:
        path = path_for(row)
        node_kind.setdefault(path[0], "source")
        for name in path[1:]:
            node_kind.setdefault(name, name.lower())
        for a, b in zip(path, path[1:]):
            link_ids[(a, b)].append(row.app.id)

    stage_order = {stage_label(s.value): i for i, s in enumerate(Stage)}
    nodes = sorted(node_kind, key=lambda n: (node_kind[n] != "source", stage_order.get(n, 0), n))
    return {
        "nodes": [{"name": n, "kind": node_kind[n]} for n in nodes],
        "links": [
            {"source": a, "target": b, "value": len(ids), "application_ids": ids}
            for (a, b), ids in link_ids.items()
        ],
    }
