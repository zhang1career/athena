"""
Invoke cursor-cli (cursor-agent / agent) for "执行改进" flow.
Uses CURSOR_API_KEY from environment; binary resolution follows mimi-bro.
"""
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

CURSOR_CLI_TIMEOUT_DEFAULT = 600  # 10 min


def _resolve_cursor_bin() -> tuple[Optional[Path], bool]:
    """
    Resolve headless cursor-cli. Prefer cursor-agent/agent (headless);
    cursor from PATH is often the editor CLI.
    Returns (resolved_path, use_run_subcommand). use_run is False for cursor-agent/agent.
    """
    env_path = os.getenv("CURSOR_CLI_PATH")
    if env_path:
        p = Path(env_path).expanduser().resolve()
        if p.exists():
            use_run = p.name.lower() not in ("cursor-agent", "agent")
            return p, use_run

    for name in ("cursor-agent", "agent"):
        path_bin = shutil.which(name)
        if path_bin:
            return Path(path_bin), False
    cursor_agent_local = Path(os.path.expanduser("~/.local/bin/cursor-agent"))
    if cursor_agent_local.exists():
        return cursor_agent_local, False

    path_cursor = shutil.which("cursor")
    if path_cursor:
        return Path(path_cursor), True
    return None, True


def run_cursor_cli(
    workspace_path: Path,
    prompt: str,
    log_path: Optional[Path] = None,
    timeout: int = CURSOR_CLI_TIMEOUT_DEFAULT,
    api_key: Optional[str] = None,
) -> dict:
    """
    Run cursor-cli with the given prompt in the given workspace.
    api_key: defaults to CURSOR_API_KEY from env.
    Returns dict with: exit_code, log_path (str or None), output_preview (last 500 chars), error (str or None).
    """
    workspace_path = workspace_path.resolve()
    api_key = api_key or os.environ.get("CURSOR_API_KEY", "").strip()
    resolved, use_run = _resolve_cursor_bin()
    if not resolved:
        return {
            "exit_code": -1,
            "log_path": None,
            "output_preview": None,
            "error": "cursor-cli 未找到（请安装 cursor agent 或设置 CURSOR_CLI_PATH）",
        }

    cmd = [str(resolved)]
    if use_run:
        cmd.append("run")
    if api_key:
        cmd.extend(["--api-key", api_key])
    cmd.extend([
        "-p",
        "-f",
        "--output-format", "text",
        "--mode", "plan",
        "--workspace", str(workspace_path),
        prompt,
    ])

    if log_path is None:
        log_path = workspace_path / "cursor_cli_run.log"
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with log_path.open("w", encoding="utf-8") as lf:
            proc = subprocess.Popen(
                cmd,
                cwd=str(workspace_path),
                stdout=lf,
                stderr=subprocess.STDOUT,
                text=True,
                env={**os.environ},
            )
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                lf.write("\n[cursor_cli] timeout\n")
                return {
                    "exit_code": 124,
                    "log_path": str(log_path),
                    "output_preview": "(执行超时)",
                    "error": "cursor-cli 执行超时",
                }
        code = proc.returncode
        content = log_path.read_text(encoding="utf-8", errors="replace")
        preview = content[-500:] if len(content) > 500 else content
        return {
            "exit_code": code,
            "log_path": str(log_path),
            "output_preview": preview.strip() or None,
            "error": None if code == 0 else f"cursor-cli 退出码 {code}",
        }
    except Exception as e:
        return {
            "exit_code": -1,
            "log_path": str(log_path) if log_path else None,
            "output_preview": None,
            "error": str(e),
        }
