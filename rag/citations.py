"""Output gate for citations (spec §7.5, D9).

Every ``[n]`` in an answer must point at a passage that was actually retrieved
for it. Markers may be single (``[2]``), grouped (``[1, 3]``) or chained
(``[1][3]``). Invalid numbers are removed; a group keeps its valid numbers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .segments import map_prose

#: ``[1]``, ``[1, 2]``, ``[1,2;3]`` — numbers separated by comma/semicolon.
MARKER = re.compile(r'\[(\s*\d{1,3}(?:\s*[,;]\s*\d{1,3})*\s*)\]')
_MARKER_WITH_SPACE = re.compile(r'([ \t]*)' + MARKER.pattern)


@dataclass(frozen=True)
class GateResult:
    text: str
    cited: frozenset[int]  # valid numbers that remain in the text
    removed: frozenset[int]  # numbers that were stripped


def validate(text: str, allowed: set[int]) -> GateResult:
    """Keep only citations to retrieved passages. Code and math are never touched.

    ``dp[3]`` inside a code block or ``a_{[1]}`` inside a formula is not a
    citation (see :mod:`rag.segments`).
    """
    cited: set[int] = set()
    removed: set[int] = set()

    def replace(match: re.Match) -> str:
        leading, inner = match.group(1), match.group(2)
        numbers = [int(n) for n in re.split(r'\s*[,;]\s*', inner.strip())]
        keep = []
        for n in numbers:
            if n in allowed:
                if n not in keep:
                    keep.append(n)
            else:
                removed.add(n)
        cited.update(keep)
        if not keep:
            return ''  # a removed marker takes the space before it ("word [9]." -> "word.")
        return leading + ''.join(f'[{n}]' for n in keep)

    def gate_prose(prose: str) -> str:
        # No other whitespace tidying: list indentation, line breaks and Markdown hard
        # breaks (two trailing spaces) are left exactly as written.
        return _MARKER_WITH_SPACE.sub(replace, prose)

    cleaned = map_prose(text, gate_prose).strip()
    return GateResult(text=cleaned, cited=frozenset(cited), removed=frozenset(removed))
