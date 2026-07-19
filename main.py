"""Port and Web Gating Changes:
- Made web adapter mandatory: the `WEB_ENABLED` toggle is removed; the FastAPI web panel starts unconditionally.
- Backend port fallback: resolves `BACKEND_PORT`, then `WEB_PORT`, defaulting to `8000`.
- Rationale: simplify deployments by making the central web panel a core, mandatory system.
- How to revert: restore the WEB_ENABLED env checks and reset the port variables.

Nebula — top-level launcher.

This is the ONE file you run: `python main.py`.

All three platform adapters (Discord, Telegram, Web) share a single set
of core.database/auth/memory/coins instances and a single
ai.handler.AIHandler, all constructed exactly once here. That sharing is
what makes identity, memory, and coin balance genuinely cross-platform:
a message sent via Telegram and a message sent via Discord (or the web
panel) for the SAME Nebula account read and write through the exact
same objects, not siloed copies of the same sqlite file.

Each adapter is independently optional: whichever of DISCORD_TOKEN /
TELEGRAM_BOT_TOKEN / WEB_ENABLED is set in .env determines which
adapter(s) actually start. All three, some, or (if none are set)
none — with an explicit error in that last case rather than silently
doing nothing, matching this project's "explicit failure over silent
fallback" principle everywhere else (see core/auth.py, core/memory.py,
tools/search.py).

--- Web adapter addition ---

Confirmed with Sina: the web adapter (FastAPI + uvicorn, serving
web_backend/app.py's app) gets its own entry in this same asyncio.gather()
alongside Discord/Telegram, run as an in-process ASGI server via
uvicorn.Server rather than a separate `uvicorn web_backend.app:app`
process/command. This keeps the "one file you run: python main.py"
promise intact for the backend -- the ONLY separate process a person
running Nebula needs to think about is the Next.js frontend itself
(a genuinely different runtime, Node.js vs Python, which can't share
this event loop regardless), not the API server.

Gating: WEB_ENABLED=true (plus JWT_SECRET and OAUTH_TOKEN_ENCRYPTION_KEY,
both required for web_backend/app.py's create_app() to succeed) turns
the web adapter on, mirroring how DISCORD_TOKEN / TELEGRAM_BOT_TOKEN
already gate their adapters. WEB_PORT (default 8000) picks the port.
"""
import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from core.database import DatabaseManager
from core.auth import AuthManager
from core.memory import MemoryManager
from core.coins import CoinManager
from tools.search import SearchTool
from ai.handler import AIHandler

import discord_bot.client as discord_client
import telegram_bot.client as telegram_client


def _should_install_deps(frontend_dir: str) -> bool:
    """
    Returns True if packages need to be installed.
    Checks if node_modules is missing or if package.json has been modified since the last installation.
    """
    node_modules_path = os.path.join(frontend_dir, "node_modules")
    if not os.path.isdir(node_modules_path):
        return True

    package_json_path = os.path.join(frontend_dir, "package.json")
    state_file_path = os.path.join(frontend_dir, ".package_json_last_installed")

    if not os.path.exists(package_json_path):
        return False

    if not os.path.exists(state_file_path):
        return True

    return os.path.getmtime(package_json_path) > os.path.getmtime(state_file_path)


def _update_last_installed_state(frontend_dir: str):
    """
    Writes a dummy state file to mark the last successful package installation time.
    """
    state_file_path = os.path.join(frontend_dir, ".package_json_last_installed")
    try:
        with open(state_file_path, "w") as f:
            f.write("installed")
    except Exception as e:
        print(f"Warning: could not write installation state file: {e}")


async def _run_subprocess_with_logging(cmd: list, cwd: str, prefix: str) -> int:
    """
    Executes a command asynchronously, streaming and forwarding stdout/stderr to the console with a prefix.
    Supports clean termination and process group isolation to prevent zombie processes on PaaS/Railway.
    """
    import subprocess
    import signal

    preexec = None
    creationflags = 0
    if sys.platform != "win32":
        preexec = os.setsid
    else:
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            preexec_fn=preexec,
            creationflags=creationflags
        )

        assert process.stdout is not None
        async for raw_line in process.stdout:
            line = raw_line.decode(errors="replace").rstrip()
            print(f"{prefix} {line}")

        returncode = await process.wait()
        return returncode
    except asyncio.CancelledError:
        if process and process.returncode is None:
            print(f"{prefix} Terminating subprocess (PID {process.pid})...")
            try:
                if sys.platform != "win32":
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    for _ in range(30):
                        if process.returncode is not None:
                            break
                        await asyncio.sleep(0.1)
                    if process.returncode is None:
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                else:
                    process.terminate()
                    await process.wait()
            except Exception as e:
                print(f"{prefix} Error cleaning up subprocess: {e}")
        raise
    except Exception as e:
        print(f"{prefix} Subprocess execution error: {e}")
        if process and process.returncode is None:
            try:
                process.terminate()
                await process.wait()
            except Exception:
                pass
        return -1


async def _start_web_ui():
    """
    Automates installation, building, and running of the Next.js frontend (web_frontend).
    Concurrently handles npm install (if package.json changed or node_modules missing)
    and executes npm run dev or npm run start based on NODE_ENV.
    Stdout/stderr logs from Next.js are neatly piped and forwarded to Python console logs.
    """
    frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web_frontend")

    if not os.path.isdir(frontend_dir):
        print(f"ERROR: Web UI directory not found at {frontend_dir}. Skipping Next.js startup.")
        return

    npm_executable = "npm.cmd" if sys.platform == "win32" else "npm"

    # 1. Dependency installation check
    if _should_install_deps(frontend_dir):
        print("[web_frontend] Missing or outdated dependencies. Running 'npm install'...")
        code = await _run_subprocess_with_logging([npm_executable, "install"], cwd=frontend_dir, prefix="[web_frontend:install]")
        if code != 0:
            print(f"ERROR: 'npm install' failed with exit code {code}. Cannot start Web UI.")
            return
        _update_last_installed_state(frontend_dir)
        print("[web_frontend] 'npm install' completed successfully.")

    # 2. Production build check (if not in development mode)
    node_env = os.getenv("NODE_ENV", "production").strip().lower()
    is_dev = node_env == "development"

    if not is_dev:
        next_dir = os.path.join(frontend_dir, ".next")
        if not os.path.isdir(next_dir):
            print("[web_frontend] No production build found (.next/ missing). Running 'npm run build'...")
            code = await _run_subprocess_with_logging([npm_executable, "run", "build"], cwd=frontend_dir, prefix="[web_frontend:build]")
            if code != 0:
                print(f"ERROR: 'npm run build' failed with exit code {code}. Cannot start Web UI.")
                return
            print("[web_frontend] 'npm run build' completed successfully.")

    # 3. Execution
    run_cmd = "dev" if is_dev else "start"
    print(f"Web UI configured — starting Next.js frontend via 'npm run {run_cmd}' on port 8080.")
    await _run_subprocess_with_logging([npm_executable, "run", run_cmd], cwd=frontend_dir, prefix="[web_frontend]")


async def _start_web_adapter(db, auth, memory, coins, ai_handler):
    """Constructs web_backend's FastAPI app and serves it in-process via
    uvicorn.Server.serve() -- an awaitable coroutine, same shape as
    discord_client.start() and telegram_client.start(), so it slots
    into the same asyncio.gather() call below without needing its own
    event loop (uvicorn.run() would try to own the loop itself, which
    is exactly what discord_bot/client.py's start() docstring already
    explains must be avoided when multiple adapters share one loop)."""
    import uvicorn
    from web_backend.app import create_app

    app = create_app(db, auth, memory, coins, ai_handler)
    port = int(os.getenv('BACKEND_PORT', os.getenv('WEB_PORT', '8000')))
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    print(f"Web adapter configured — starting on port {port}.")
    await server.serve()


async def main():
    # DB_PATH lets the Docker image point nebula.db at a mounted volume
    # (see docker-compose.yml's DB_PATH=/app/data/nebula.db) instead of
    # the container's ephemeral filesystem. Defaults to "nebula.db"
    # (relative to CWD), unchanged from before, for anyone running
    # main.py directly outside Docker.
    db = DatabaseManager(db_path=os.getenv('DB_PATH', 'nebula.db'))
    auth = AuthManager(db)
    memory = MemoryManager(db)
    coins = CoinManager(db)
    search_tool = SearchTool()
    ai_handler = AIHandler(db, auth, memory, coins, search_tool)

    tasks = []

    discord_token = os.getenv('DISCORD_TOKEN')
    if discord_token:
        bot = discord_client.build_bot(db, auth, memory, coins, search_tool, ai_handler)
        tasks.append(discord_client.start(bot, discord_token))
        print("Discord adapter configured — starting.")
    else:
        print("DISCORD_TOKEN not set — Discord adapter disabled.")

    telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if telegram_token:
        application = telegram_client.build_application(
            db, auth, memory, coins, search_tool, ai_handler, telegram_token
        )
        tasks.append(telegram_client.start(application))
        print("Telegram adapter configured — starting.")
    else:
        print("TELEGRAM_BOT_TOKEN not set — Telegram adapter disabled.")

    # Web adapter is mandatory. Always initialize web features unconditionally.
    missing = [v for v in ('JWT_SECRET', 'OAUTH_TOKEN_ENCRYPTION_KEY') if not os.getenv(v)]
    if missing:
        print(
            f"ERROR: Web adapter is mandatory but {', '.join(missing)} "
            f"{'is' if len(missing) == 1 else 'are'} not set — web adapter cannot start. "
            "See .env.sample for how to generate these."
        )
    else:
        tasks.append(_start_web_adapter(db, auth, memory, coins, ai_handler))

    # Next.js web frontend adapter is started unconditionally
    tasks.append(_start_web_ui())

    if not tasks:
        print(
            "ERROR: No platform adapters are running. Ensure that "
            "JWT_SECRET and OAUTH_TOKEN_ENCRYPTION_KEY are configured in your .env file "
            "so the mandatory web adapter can start."
        )
        return

    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    def handle_signal():
        print("Received termination signal. Triggering graceful shutdown...")
        shutdown_event.set()

    if sys.platform != "win32":
        import signal
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, handle_signal)
            except Exception as e:
                print(f"Warning: could not register signal handler for {sig}: {e}")

    gather_task = asyncio.create_task(asyncio.gather(*tasks))

    try:
        if sys.platform != "win32":
            await asyncio.wait(
                [gather_task, shutdown_event.wait()],
                return_when=asyncio.FIRST_COMPLETED
            )
            if shutdown_event.is_set():
                print("Graceful shutdown initiated. Cancelling active tasks...")
                gather_task.cancel()
                try:
                    await gather_task
                except asyncio.CancelledError:
                    pass
        else:
            await gather_task
    except asyncio.CancelledError:
        gather_task.cancel()
        try:
            await gather_task
        except asyncio.CancelledError:
            pass
        raise
    finally:
        if not gather_task.done():
            gather_task.cancel()
            try:
                await gather_task
            except Exception:
                pass
        print("All processes cleaned up. Exiting main.")


if __name__ == "__main__":
    asyncio.run(main())
