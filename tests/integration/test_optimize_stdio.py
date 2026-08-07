from __future__ import annotations

import json
import os
import sys
from datetime import timedelta

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.integration
async def test_optimize_validation_response_survives_stdio_startup(tmp_path) -> None:
    # Given
    env = {
        **os.environ,
        "PSIM_MODE": "mock",
        "PSIM_OUTPUT_DIR": str(tmp_path / "output"),
        "ALLOWED_PROJECT_DIRS": json.dumps([str(tmp_path)]),
        "LOG_DIR": str(tmp_path / "logs"),
    }
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "psim_mcp.server"],
        env=env,
        cwd=os.getcwd(),
    )

    # When
    async with stdio_client(server) as streams:
        async with ClientSession(
            *streams,
            read_timeout_seconds=timedelta(seconds=3),
        ) as session:
            await session.initialize()
            response = await session.call_tool("optimize_circuit", {"request": {}})

    # Then
    payload = json.loads(response.content[0].text)
    assert payload["success"] is False
    assert payload["error"]["code"] == "VALIDATION_ERROR"
