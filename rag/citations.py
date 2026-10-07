"""Output gate for citations (spec §7.5, D9).

Every ``[n]`` in an answer must point at a passage that was actually retrieved
for it. Markers may be single (``[2]``), grouped (``[1, 3]``) or chained
(``[1][3]``). Invalid numbers are removed; a group keeps its valid numbers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

#: ``[1]``, ``[1, 2]``, ``[1,2;3]`` — numbers separated by comma/semicolon.
MARKER = re.compile(r'\[(\s*\d{1,3}(?:\s*[,;]\s*\d{1,3})*\s*)\]')


@dataclass(frozen=True)
class GateResult:
    text: str
    cited: frozenset[int]  # valid numbers that remain in the text
    removed: frozenset[int]  # numbers that were stripped


def validate(text: str, allowed: set[int]) -> GateResult:
    cited: set[int] = set()
    removed: set[int] = set()

    def replace(match: re.Match) -> str:
        numbers = [int(n) for n in re.split(r'\s*[,;]\s*', match.group(1).strip())]
        keep = []
        for n in numbers:
            if n in allowed:
                if n not in keep:
                    keep.append(n)
            else:
                removed.add(n)
        cited.update(keep)
        return ''.join(f'[{n}]' for n in keep)

    cleaned = MARKER.sub(replace, text)
    # Tidy spaces left where a whole marker was removed ("word [9]." -> "word.").
    cleaned = re.sub(r'[ \t]+([.,;:!?])', r'\1', cleaned)
    cleaned = re.sub(r'[ \t]{2,}', ' ', cleaned).strip()
    return GateResult(text=cleaned, cited=frozenset(cited), removed=frozenset(removed))
