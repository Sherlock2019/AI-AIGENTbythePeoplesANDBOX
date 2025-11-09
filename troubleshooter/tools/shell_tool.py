from __future__ import annotations

import shlex
import subprocess

SAFE_WHITELIST = {"id", "whoami", "uname", "ls", "pwd", "echo"}


class ShellTool:
    def run(self, cmd: str) -> str:
        head = shlex.split(cmd or "echo")[0]
        if head not in SAFE_WHITELIST:
            return f"[blocked] '{head}' not allowed"
        try:
            output = subprocess.check_output(
                cmd, shell=True, stderr=subprocess.STDOUT, timeout=8
            )
            return output.decode("utf-8", errors="ignore")
        except Exception as exc:
            return f"[error] {exc}"
