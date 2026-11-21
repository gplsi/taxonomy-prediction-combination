# Combining Predictions from Two Models for Taxonomy Discovery

**One command runs every strategy.** Provide two JSON files with scored parent–child predictions. The program writes 13 JSON files to `<out>/predictions/`: two copies of the original model outputs and one file for each of the 11 derived strategies. To use a particular strategy, take its file from that directory. For example, the supported top candidate rule writes `<out>/predictions/supported\_top.json`.

## Quick start

From the repository root, run the bundled example with Python 3.10 or later. The program uses the Python standard library.

```bash
python -m taxensemble --a examples/a.json --b examples/b.json --out results
```

This creates `results/predictions/` and `results/candidates.json`. Open [the strategy table](#strategies) to find the filename you need. Replace the two example paths with your own prediction files to run the same strategies on your data.

To compare precision, recall, and F1 across strategies, pass a gold reference and read `metrics.json` in the output directory.

```bash
python -m taxensemble --a examples/a.json --b examples/b.json --gold examples/gold.json --out results-evaluated
```

Use a new output directory for each run. The gold reference is used only for evaluation. You can also install the package with `python -m pip install .` and run `taxonomy-ensemble` with the same arguments.

## Input format

Each file is a UTF-8 JSON array of objects. Use `\[]` to represent an empty list of relations.

**Model predictions** (`--a` and `--b`). Supply one object per candidate relation, with a finite numeric `score`. Higher scores indicate more preferred parents for the same child. Apply any model-specific candidate selection before exporting the file. If a model gives distances, negate them so that smaller distances rank higher.

```json
\[
  {"parent": "instrument", "child": "violin", "score": 0.9},
  {"parent": "strings", "child": "violin", "score": 0.8}
]
```

Use the same labels or stable identifiers in both model files. The program trims surrounding whitespace and rejects prediction identifiers that differ only in case. Use distinct identifiers for concepts with the same label. If a model proposes no parent for a child, omit that child from its predictions. When a model repeats a pair, its original output retains every record and the derived strategies use the highest score for that pair.

**Gold reference** (`--gold`, optional). Each object represents an annotated direct relation. The optional `ID` identifies the source record. Evaluation uses the `parent` and `child` fields.

```json
\[
  {"ID": "TR\_00000001", "parent": "Strings", "child": "violin"},
  {"ID": "TR\_00000002", "parent": "instrument", "child": "strings"}
]
```

## Strategies

For each child, a model's candidates are ranked by descending score. The highest-scoring candidate has rank 1. Ties are broken by ascending Unicode lexicographic order of the parent identifier.

|File in `<out>/predictions/`|What it contains|
|-|-|
|`model\_a.json`, `model\_b.json`|The original model predictions, including scores. Use them as baselines when evaluating the derived strategies.|
|`union.json`|Every pair proposed by either model.|
|`intersection.json`|Every pair proposed by both models. A child can keep multiple parents.|
|`top\_a.json`, `top\_b.json`|The highest-ranked parent for each child in the corresponding model's list.|
|`top\_intersection.json`|One shared parent per child, chosen by the highest mean score. A sole shared candidate is always kept. Use comparable score scales across models for this strategy.|
|`top\_agreement.json`|A parent only when both models rank it first for that child.|
|`supported\_top.json`|A shared parent that at least one model ranks first. A child can keep two parents when the models rank different shared candidates first.|
|`rescue.json`|Applies the supported top candidate rule and keeps the first candidate for children covered by only one model. If both models have candidates and their lists are disjoint, the child receives no parent.|
|`pareto.json`|Shared parents for which no other shared parent ranks strictly higher in both original lists.|
|`reciprocal\_rank.json`|One parent per child from the union, chosen by the highest sum of reciprocal ranks with zero offset. A missing candidate contributes zero in that model's list.|
|`transitive.json`|The supported top pairs after removing direct relations for which an alternative child-to-parent path remains.|

The mean-score and reciprocal-rank rules break ties by ascending parent identifier. Each derived strategy writes an array of objects with `parent` and `child`. The transitive filter examines edges in lexicographic order by child and then parent. It keeps edges within strongly connected components and preserves self-loops. After filtering, it verifies that every node reaches the same set of nodes as before. This check can be costly on dense graphs.

### Worked example

In the bundled example, model A ranks `instrument` first for `violin`, while model B ranks `strings` first. Both models propose both parents.

|Strategy|Parents returned for `violin`|
|-|-|
|Intersection|`instrument`, `strings`|
|Top agreement|None, because the models rank different parents first|
|Supported top candidate|`instrument`, `strings`|
|Top of the intersection by mean score|`strings`, with a mean of 0.875 versus 0.83 for `instrument`|
|Transitive filter|`strings`, because `instrument` remains reachable through `violin → strings → instrument`|

For `oboe`, both models rank `woodwind` second behind different candidates that are exclusive to each model. The Pareto rule keeps `woodwind` because no shared parent outranks it in both models. The supported top candidate rule assigns no parent to `oboe`.

## Reports and metrics

`candidates.json` is always generated. All other reports below require `--gold`.

|File in `<out>/`|Contents|
|-|-|
|`candidates.json`|Each pair in the union, its rank in each model (`null` if absent), its agreement group, and whether `supported\_top` keeps it (`1` or `0`).|
|`metrics.json`|Predicted and gold record counts, distinct gold pairs, true positives (TP), false positives (FP), false negatives (FN), precision, recall, and F1 for each strategy.|
|`decisions.json`|Pair, TP, and FP counts for each of the six mutually exclusive groups defined by candidate presence and rank.|
|`by\_parent.json`|Distinct gold children, TP, FP, and FN for each parent appearing in a strategy's predictions or in the gold reference.|
|`changes.json`|Pairs added or removed when moving from each strategy to `supported\_top`. Includes whether each pair is in the gold reference and whether its child has multiple gold parents.|
|`missing\_supported.json`|False negatives for `supported\_top` and whether each pair appears in the union.|
|`structure.json`|False positives that reverse a gold relation, false positives linking concepts with a shared gold parent, and true positives for children with multiple gold parents. The two FP counts can overlap.|
|`multiplicity.json`|Results grouped by the number of gold parents or predicted parents per child. Each group counts children, gold pairs, predicted pairs, and true positives. A group can include children with zero parents on the corresponding side.|

Evaluation lowercases parent and child labels with `str.lower()`. TP, FP, and FN count distinct pairs. With `A` distinct matching pairs, `n` prediction records, and `N` gold records, precision is `A/n`, recall is `A/N`, and F1 is `2A/(n+N)`. The program returns zero for a metric with a zero denominator. Duplicate records count toward their respective denominators. For example, one correct prediction matching two identical gold records yields recall of 0.5 and zero false negatives.

## Tests

```bash
python -m unittest discover -s tests -v
```

The strategy and transitive filter implementations are in `taxensemble/rules.py`. Evaluation lives in `taxensemble/report.py`, and the command-line interface and JSON I/O are in `taxensemble/cli.py`.

