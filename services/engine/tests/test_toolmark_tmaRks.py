"""Tests for tmaRks TID parsing (no R/network needed)."""

from __future__ import annotations

from verity.examples.toolmark_tmaRks import source_key


def test_source_key_edge_vs_tool():
    tid = "T01SA-F80-01"
    assert source_key(tid, "edge") == "T01SA"  # tool+size+side (the mark generator)
    assert source_key(tid, "tool") == "T01S"  # both faces merged


def test_edge_distinguishes_sides_tool_merges_them():
    a, b = "T07LB-B60-03", "T07LA-B60-03"  # same tool+size, different sides
    assert source_key(a, "edge") != source_key(b, "edge")  # distinct edges
    assert source_key(a, "tool") == source_key(b, "tool") == "T07L"  # same tool
