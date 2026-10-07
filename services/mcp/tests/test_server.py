"""The stdio tool inventory exposes client-visible titles and safety hints."""

import asyncio

from verity_mcp.server import mcp


def test_tools_list_publishes_titles_and_safety_annotations():
    tools = asyncio.run(mcp.list_tools())
    assert {tool.name for tool in tools} == {
        "service_health",
        "detect_mark_type",
        "compare_marks",
        "calibrate_score",
        "list_references",
        "scorer_config",
    }
    for tool in tools:
        assert tool.title and tool.title.strip()
        assert tool.title != tool.name
        assert tool.annotations is not None
        assert tool.annotations.model_dump(exclude_none=True) == {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        }
