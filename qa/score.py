"""Canonical GAIA-style quasi-exact QA scoring used by the parent task line."""

from __future__ import annotations

import re
import string
from typing import Sequence


_FINAL = re.compile(r"FINAL ANSWER:\s*(.+)", re.IGNORECASE)
_THINK_TAG = re.compile(r"</?think\b[^>]*>", re.IGNORECASE)
_PAREN = re.compile(r"^(.*?)[\(（]([^）)]+)[\)）]\s*$")


def extract_final_answer(text: str) -> str:
    if not text:
        return ""
    clean = _THINK_TAG.sub("", str(text))
    matches = _FINAL.findall(clean)
    if matches:
        return matches[-1].strip().splitlines()[0].strip()
    lines = clean.strip().splitlines()
    return lines[-1].strip() if lines else ""


def _normalize_number(value: str) -> str:
    return value.replace("$", "").replace("%", "").replace(",", "").strip()


def _normalize_str(value: str, *, remove_punct: bool = True) -> str:
    value = re.sub(r"\s+", "", value.strip().lower())
    return value.translate(str.maketrans("", "", string.punctuation)) if remove_punct else value


def _is_float(value: str) -> bool:
    try:
        float(_normalize_number(value))
        return True
    except (TypeError, ValueError):
        return False


def _norm_api(value: str) -> str:
    return value.strip().rstrip("()").replace("OSISEngine()", "engine").replace(" ", "")


def api_equivalent(pred: str, gold: str) -> bool:
    pred_api, gold_api = _norm_api(pred), _norm_api(gold)
    if pred_api == gold_api:
        return True
    if pred_api.split(".")[-1] != gold_api.split(".")[-1]:
        return False
    path = [part for part in gold_api.split(".") if part and part != "engine"][:-1]
    lowered = pred_api.lower()
    return bool(path) and all(part.lower() in lowered for part in path)


def _yes_no_aliases(gold: str) -> list[str]:
    value = gold.strip()
    if value in {"是", "yes", "Yes", "true", "True"}:
        return ["是", "yes", "true"]
    if value in {"否", "false", "False"}:
        return ["否", "no", "false", "不存在"]
    return []


def _split_list(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[,;]", value) if part.strip()]


def _paren_variants(value: str) -> list[str]:
    value = (value or "").strip()
    if not value:
        return []
    result = [value]
    matched = _PAREN.fullmatch(value)
    if matched:
        for part in (matched.group(1).strip(), matched.group(2).strip()):
            if part and part not in result:
                result.append(part)
    return result


def _match_atomic_one(pred: str, gold: str) -> bool:
    if _is_float(gold):
        try:
            return float(_normalize_number(pred)) == float(_normalize_number(gold))
        except ValueError:
            return False
    if _normalize_str(pred) == _normalize_str(gold):
        return True
    return "." in gold and api_equivalent(pred, gold)


def _match_atomic(pred: str, gold: str) -> bool:
    return any(_match_atomic_one(variant, gold) for variant in _paren_variants(pred))


def match_answer(pred: str, gold: str, aliases: Sequence[str] | None = None) -> bool:
    if pred is None or gold is None:
        return False
    pred, gold = str(pred).strip(), str(gold).strip()
    candidates = [gold, *(aliases or ()), *_yes_no_aliases(gold)]
    for candidate in candidates:
        candidate = str(candidate).strip()
        if any(separator in candidate for separator in ",;") and not _is_float(candidate):
            expected, actual = _split_list(candidate), _split_list(pred)
            if len(expected) == len(actual) and all(
                _match_atomic(got, want) for got, want in zip(actual, expected)
            ):
                return True
        elif _match_atomic(pred, candidate):
            return True
    return False


def score_answer(text: str, gold: str, aliases: Sequence[str] | None = None) -> dict[str, object]:
    pred = extract_final_answer(text)
    return {"pred": pred, "correct": bool(match_answer(pred, gold, aliases))}
