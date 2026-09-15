"""NetworkX compliance graph built from SQLite trade facts."""

from __future__ import annotations

from typing import Any

import networkx as nx
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.data.models import (
    AgreementEligibility,
    DocumentRequirement,
    HsCode,
    SourceDocument,
    TariffRate,
    TradeAgreement,
)


def build_trade_graph(session: Session) -> nx.DiGraph:
    graph = nx.DiGraph()

    for hs in session.scalars(select(HsCode)).all():
        graph.add_node(f"hs:{hs.code}", kind="hs_code", code=hs.code, label=hs.description)

    for agr in session.scalars(select(TradeAgreement)).all():
        graph.add_node(f"agreement:{agr.id}", kind="agreement", id=agr.id, label=agr.name)

    for doc in session.scalars(select(SourceDocument)).all():
        graph.add_node(f"source:{doc.id}", kind="source", id=doc.id, label=doc.title)

    for rate in session.scalars(select(TariffRate)).all():
        corridor = f"corridor:{rate.origin}->{rate.destination}"
        if corridor not in graph:
            graph.add_node(
                corridor,
                kind="corridor",
                origin=rate.origin,
                destination=rate.destination,
                label=f"{rate.origin}→{rate.destination}",
            )
        rate_node = f"tariff:{rate.id}"
        graph.add_node(
            rate_node,
            kind="tariff",
            id=rate.id,
            rate=float(rate.rate),
            status=rate.status,
            label=f"{rate.hs_code} {rate.rate}%",
        )
        graph.add_edge(f"hs:{rate.hs_code}", rate_node, rel="has_tariff_rule")
        graph.add_edge(rate_node, corridor, rel="applies_to")
        graph.add_edge(rate_node, f"source:{rate.source_document_id}", rel="supported_by_source")

    for rule in session.scalars(select(AgreementEligibility)).all():
        rule_node = f"eligibility:{rule.id}"
        graph.add_node(
            rule_node,
            kind="eligibility",
            id=rule.id,
            preferential_rate=float(rule.preferential_rate_pct),
            status=rule.status,
            label=f"{rule.hs_code} pref {rule.preferential_rate_pct}%",
        )
        graph.add_edge(f"hs:{rule.hs_code}", rule_node, rel="eligible_under_candidate")
        graph.add_edge(rule_node, f"agreement:{rule.agreement_id}", rel="eligible_under")
        graph.add_edge(rule_node, f"source:{rule.source_document_id}", rel="supported_by_source")
        if rule.certificate_doc_code:
            cert = f"certificate:{rule.certificate_doc_code}"
            if cert not in graph:
                graph.add_node(
                    cert,
                    kind="certificate",
                    code=rule.certificate_doc_code,
                    label=rule.certificate_doc_code,
                )
            graph.add_edge(rule_node, cert, rel="requires_certificate")

    for req in session.scalars(select(DocumentRequirement)).all():
        doc_node = f"docreq:{req.doc_code}:{req.origin}:{req.destination}:{req.hs_code or '*'}"
        graph.add_node(
            doc_node,
            kind="document_requirement",
            code=req.doc_code,
            label=req.doc_label,
        )
        corridor = f"corridor:{req.origin}->{req.destination}"
        if corridor not in graph:
            graph.add_node(
                corridor,
                kind="corridor",
                origin=req.origin,
                destination=req.destination,
                label=f"{req.origin}→{req.destination}",
            )
        graph.add_edge(corridor, doc_node, rel="requires")
        if req.hs_code:
            graph.add_edge(f"hs:{req.hs_code}", doc_node, rel="requires")

    return graph


def fta_path_for_hs(
    graph: nx.DiGraph,
    *,
    hs_code: str,
    agreement_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return a simple evidence path HS → eligibility → agreement → source/cert."""
    hs_node = f"hs:{hs_code}"
    if hs_node not in graph:
        return []

    paths: list[dict[str, Any]] = []
    for _, eligibility, edge_data in graph.out_edges(hs_node, data=True):
        if edge_data.get("rel") != "eligible_under_candidate":
            continue
        elig = graph.nodes[eligibility]
        if agreement_id and not any(
            tgt == f"agreement:{agreement_id}"
            for _, tgt, ed in graph.out_edges(eligibility, data=True)
            if ed.get("rel") == "eligible_under"
        ):
            continue
        step = {
            "nodes": [
                {"id": hs_node, **graph.nodes[hs_node]},
                {"id": eligibility, **elig},
            ],
            "edges": [{"from": hs_node, "to": eligibility, "rel": "eligible_under_candidate"}],
        }
        for _, tgt, ed in graph.out_edges(eligibility, data=True):
            step["nodes"].append({"id": tgt, **graph.nodes[tgt]})
            step["edges"].append({"from": eligibility, "to": tgt, "rel": ed.get("rel")})
        paths.append(step)
    return paths


def graph_summary(graph: nx.DiGraph) -> dict[str, Any]:
    kinds: dict[str, int] = {}
    for _, data in graph.nodes(data=True):
        kind = str(data.get("kind", "unknown"))
        kinds[kind] = kinds.get(kind, 0) + 1
    return {"nodes": graph.number_of_nodes(), "edges": graph.number_of_edges(), "by_kind": kinds}
