"""Combine two sequences of (parent, child, score). No gold data used."""
from collections import defaultdict
from fractions import Fraction

STRATEGIES = (
    "model_a", "model_b", "union", "intersection", "top_a", "top_b",
    "top_intersection", "top_agreement", "supported_top", "rescue",
    "pareto", "reciprocal_rank", "transitive",
)


def reachable(graph, start):
    seen = {start}
    pending = [start]
    while pending:
        for node in graph[pending.pop()]:
            if node not in seen:
                seen.add(node)
                pending.append(node)
    return seen


def transitive_filter(pairs):
    original = defaultdict(set)
    for parent, child in pairs:
        original[child].add(parent)
        original.setdefault(parent, set())
    graph = {node: parents.copy() for node, parents in original.items()}
    for child in sorted(graph):
        for parent in sorted(original[child]):
            # Given child -> parent, a return path means SCC-internal.
            if child in reachable(original, parent):
                continue
            graph[child].remove(parent)
            if parent not in reachable(graph, child):
                graph[child].add(parent)
    for node in original:
        if reachable(original, node) != reachable(graph, node):
            raise RuntimeError(f"Reachability changed for {node!r}")
    return {(p, h) for h, parents in graph.items() for p in parents}


def index(rows):
    scores = defaultdict(dict)
    for p, h, score in rows:
        scores[h][p] = max(score, scores[h].get(p, score))
    return scores


def ranks(scores):
    order = sorted(scores, key=lambda p: (-scores[p], p))
    return {p: i for i, p in enumerate(order, 1)}


def combine(rows_a, rows_b):
    a, b = index(rows_a), index(rows_b)
    outputs = {name: [] for name in STRATEGIES}
    audit = []
    for name, rows in (("model_a", rows_a), ("model_b", rows_b)):
        outputs[name] = [(p, h) for p, h, _ in rows]
    for h in sorted(a.keys() | b.keys()):
        ra, rb = ranks(a[h]), ranks(b[h])
        union, shared = ra.keys() | rb.keys(), ra.keys() & rb.keys()
        ta, tb = set(list(ra)[:1]), set(list(rb)[:1])
        supported = (ta | tb) & shared
        # Scan in A order. A new minimum rank in B is non-dominated.
        frontier = set()
        best = len(rb) + 1
        for p in ra:
            if p in shared and rb[p] < best:
                frontier.add(p)
                best = rb[p]
        def reciprocal(p):
            return sum(Fraction(1, r[p]) for r in (ra, rb) if p in r)
        selected = {
            "union": union, "intersection": shared, "top_a": ta, "top_b": tb,
            "top_intersection": {min(shared, key=lambda p: (-(a[h][p]+b[h][p]), p))} if shared else set(),
            "top_agreement": ta & tb, "supported_top": supported,
            "rescue": supported if ra and rb else ta | tb, "pareto": frontier,
            "reciprocal_rank": {min(union, key=lambda p: (-reciprocal(p), p))},
        }
        for method, parents in selected.items():
            outputs[method].extend((p, h) for p in parents)
        for p in sorted(union):
            if p not in shared:
                group = "only_a" if p in ra else "only_b"
            else:
                group = {(True, True): "first_both", (True, False): "first_a",
                         (False, True): "first_b", (False, False): "first_neither"}[p in ta, p in tb]
            audit.append((p, h, ra.get(p), rb.get(p), group, int(p in supported)))
    outputs["transitive"] = transitive_filter(outputs["supported_top"])
    return {k: sorted(v, key=lambda pair: pair[::-1]) for k, v in outputs.items()}, audit
