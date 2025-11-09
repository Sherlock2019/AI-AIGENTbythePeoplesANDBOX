from __future__ import annotations

import builtins

SAFE_BUILTINS = {name: getattr(builtins, name) for name in ["len", "range", "min", "max", "sum", "print"]}


class PythonTool:
    def run(self, code: str) -> str:
        local_env: dict = {}
        try:
            exec(
                compile(code, "<snippet>", "exec"),
                {"__builtins__": SAFE_BUILTINS},
                local_env,
            )
            return str(local_env.get("result", "ok"))
        except Exception as exc:
            return f"[py-error] {exc}"
