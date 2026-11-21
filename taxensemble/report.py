"""Record-based metrics and diagnostics over unique lowercased pairs."""
from collections import Counter, defaultdict


def normalize(pair):
    return tuple(label.lower() for label in pair)


def group_pairs(pairs, column):
    groups = defaultdict(set)
    for pair in pairs:
        groups[pair[column]].add(pair[1-column])
    return groups


def reports(outputs, audit, gold):
    ref = set(map(normalize, gold))
    parents = group_pairs(ref, 1)
    children = group_pairs(ref, 0)
    multi = {h for h, ps in parents.items() if len(ps) > 1}
    records = len(gold)
    systems = {k: set(map(normalize, v)) for k, v in outputs.items()}
    metrics, structure, by_parent, multiplicity = [], [], [], []
    for name, predicted in systems.items():
        n = len(outputs[name])
        hits = predicted & ref
        tp = len(hits)
        fp = predicted - ref
        metrics.append((name, n, records, len(ref), tp, len(fp), len(ref-hits),
                        tp/n if n else 0, tp/records if records else 0,
                        2*tp/(n+records) if n+records else 0))
        reversed_edges = sum((h, p) in ref for p, h in fp)
        siblings = sum(bool(parents.get(p, set()) & parents.get(h, set())) for p, h in fp)
        structure.append((name, reversed_edges, siblings, sum(h in multi for p, h in hits)))
        predicted_children = group_pairs(predicted, 0)
        for p in sorted(children.keys() | predicted_children.keys()):
            predicted_h, ref_h = predicted_children[p], children.get(p, set())
            by_parent.append((name, p, len(ref_h), len(predicted_h & ref_h),
                              len(predicted_h-ref_h), len(ref_h-predicted_h)))
        by_child = group_pairs(predicted, 1)
        for basis, groups in (("gold", parents), ("prediction", by_child)):
            buckets = defaultdict(lambda: [0, 0, 0, 0])
            for h in parents.keys() | by_child.keys():
                g, s = parents.get(h, set()), by_child.get(h, set())
                row = buckets[len(groups.get(h, set()))]
                for i, value in enumerate((1, len(g), len(s), len(s & g))):
                    row[i] += value
            multiplicity.extend((name, basis, k, *vals) for k, vals in sorted(buckets.items()))
    decisions = Counter()
    for p, h, _, _, group, _ in audit:
        decisions[group, normalize((p,h)) in ref] += 1
    groups = ("only_a","only_b","first_both","first_a","first_b","first_neither")
    supported = systems["supported_top"]
    changes = []
    for name, baseline in systems.items():
        for change, diff in (("removed", baseline-supported), ("added", supported-baseline)):
            changes.extend((name, change, p, h, int((p,h) in ref), int(h in multi))
                           for p, h in sorted(diff))
    return {
        "metrics": ("method,predicted_records,gold_records,gold_unique,tp,fp,fn,precision,recall,f1", metrics),
        "decisions": ("group,kept,pairs,tp,fp", [
            (g, int(g in groups[2:5]), decisions[g,True]+decisions[g,False],
             decisions[g,True], decisions[g,False]) for g in groups]),
        "by_parent": ("method,parent,gold_children,tp,fp,fn", by_parent),
        "structure": ("method,reversed_fp,sibling_fp,tp_on_gold_multiparent_children", structure),
        "multiplicity": ("method,group_by,parent_count,children,gold_pairs,predicted_pairs,tp", multiplicity),
        "changes": ("baseline,change_to_supported_top,parent,child,in_gold,gold_multiparent_child", changes),
        "missing_supported": ("parent,child,in_union", [
            (p,h,int((p,h) in systems["union"])) for p,h in sorted(ref-supported)]),
    }
