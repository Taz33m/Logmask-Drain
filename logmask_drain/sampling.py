"""Sampling strategies for offline mask synthesis."""

from __future__ import annotations

import math
import random
from collections import Counter

import regex


HEX_TOKEN = regex.compile(r"^(?:0x)?[0-9a-fA-F]{8,}$")
DIGITS = regex.compile(r"\d+")


def normalize_for_sampling(line: str, mode: str = "digits_hex") -> str:
    if mode == "none":
        return line
    tokens: list[str] = []
    for token in line.split():
        if mode == "digits_hex" and HEX_TOKEN.match(token):
            tokens.append("<HEX>")
        elif mode in {"digits", "digits_hex"}:
            tokens.append(DIGITS.sub("<NUM>", token))
        else:
            tokens.append(token)
    return " ".join(tokens)


def token_entropy(line: str) -> float:
    tokens = line.split()
    if not tokens:
        return 0.0
    counts = Counter(tokens)
    total = len(tokens)
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def jaccard_tokens(left: str, right: str) -> float:
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens and not right_tokens:
        return 1.0
    union = left_tokens | right_tokens
    return len(left_tokens & right_tokens) / len(union)


def sample_lines(
    lines: list[str],
    *,
    k: int = 50,
    mode: str = "entropy_greedy",
    jaccard_threshold: float = 0.8,
    normalize_mode: str = "digits_hex",
    seed: int = 0,
) -> list[str]:
    if k <= 0:
        return []
    if len(lines) <= k:
        return list(lines)

    indexed = list(enumerate(lines))
    if mode == "random":
        rng = random.Random(seed)
        chosen = indexed[:]
        rng.shuffle(chosen)
        return [line for _, line in chosen[:k]]
    if mode == "longest":
        chosen = sorted(indexed, key=lambda item: (-len(item[1].split()), -len(item[1]), item[0]))
        return [line for _, line in chosen[:k]]

    scored = [
        (index, line, normalize_for_sampling(line, normalize_mode), token_entropy(normalize_for_sampling(line, normalize_mode)))
        for index, line in indexed
    ]
    scored.sort(key=lambda item: (-item[3], item[0]))

    if mode == "entropy_only":
        return [line for _, line, _, _ in scored[:k]]
    if mode != "entropy_greedy":
        raise ValueError("mode must be random, longest, entropy_only, or entropy_greedy")

    selected: list[tuple[int, str, str, float]] = []
    for candidate in scored:
        normalized = candidate[2]
        if all(jaccard_tokens(normalized, item[2]) < jaccard_threshold for item in selected):
            selected.append(candidate)
            if len(selected) == k:
                break

    if len(selected) < k:
        selected_indices = {item[0] for item in selected}
        for candidate in scored:
            if candidate[0] not in selected_indices:
                selected.append(candidate)
                selected_indices.add(candidate[0])
                if len(selected) == k:
                    break

    selected.sort(key=lambda item: item[0])
    return [line for _, line, _, _ in selected]

