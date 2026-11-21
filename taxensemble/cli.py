import argparse
import json
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory

from .rules import combine
from .report import reports


def invalid_number(token):
    raise ValueError(f"Invalid JSON number: {token}")


def read(path, *, predictions, spellings=None):
    raw = path.read_bytes()
    try:
        data = json.loads(raw.decode("utf-8-sig"), parse_float=Decimal,
                          parse_constant=invalid_number)
    except ValueError as exc:
        raise ValueError(f"{path}: {exc}") from exc
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected an array of objects")
    rows = []
    for index, item in enumerate(data):
        where = f"{path}[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{where}: expected an object")
        for field in ("parent", "child"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ValueError(f"{where}: expected a nonempty string in {field}")
        pair = (item["parent"].strip(), item["child"].strip())
        if not predictions:
            rows.append(pair)
            continue
        score = item.get("score")
        if type(score) not in (int, Decimal):
            raise ValueError(f"{where}: expected a finite JSON number in score")
        for label in pair:
            previous = spellings.setdefault(label.lower(), label)
            if previous != label:
                raise ValueError(f"{where}: inconsistent spelling {label!r} vs {previous!r}")
        rows.append((*pair, Fraction(score)))
    return rows, raw


def write(path, fields, rows):
    keys = fields.split(",")
    objects = [dict(zip(keys, row, strict=True)) for row in rows]
    with path.open("w", encoding="utf-8") as stream:
        json.dump(objects, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description="Combine two scored taxonomy predictions in JSON.")
    for arg in ("a", "b", "out"):
        parser.add_argument("--"+arg, type=Path, required=True)
    parser.add_argument("--gold", type=Path)
    args = parser.parse_args()
    try:
        if args.out.exists():
            raise ValueError(f"Choose a new output directory: {args.out}")
        ids = {}
        rows_a, raw_a = read(args.a, predictions=True, spellings=ids)
        rows_b, raw_b = read(args.b, predictions=True, spellings=ids)
        outputs, audit = combine(rows_a, rows_b)
        tables = {"candidates": ("parent,child,rank_a,rank_b,group,supported_top", audit)}
        if args.gold is not None:
            gold, _ = read(args.gold, predictions=False)
            tables.update(reports(outputs, audit, gold))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=args.out.parent) as tmp:
            root = Path(tmp) / "result"
            predictions = root / "predictions"
            predictions.mkdir(parents=True)
            originals = {"model_a": raw_a, "model_b": raw_b}
            for name, pairs in outputs.items():
                path = predictions / (name + ".json")
                if name in originals:
                    path.write_bytes(originals[name])
                else:
                    write(path, "parent,child", pairs)
            for name, (fields, rows) in tables.items():
                write(root / (name + ".json"), fields, rows)
            root.rename(args.out)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Error: {exc}\n")
