"""하위 호환용 진입점.

vault 도구는 이제 ``server.create_app``에서 기본 등록된다. 예전 설정
(``python -m psim_mcp.server_vault``)으로 실행해도 동일한 서버가 뜨도록 남겨 둔다.
새 설정에서는 ``psim-mcp`` 콘솔 스크립트를 그대로 쓰면 된다.
"""

from __future__ import annotations

from psim_mcp.server import create_app as create_vault_app
from psim_mcp.server import main

__all__ = ["create_vault_app", "main"]

if __name__ == "__main__":
    main()
