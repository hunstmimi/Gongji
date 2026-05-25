from __future__ import annotations

import uvicorn

from agent_app.config import resolve_host, resolve_port


if __name__ == "__main__":
    uvicorn.run("app:app", host=resolve_host(), port=resolve_port(), reload=False)

