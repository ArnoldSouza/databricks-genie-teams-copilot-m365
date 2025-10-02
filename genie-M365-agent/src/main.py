"""
Microsoft Agents (`microsoft_agents`) application for use with M365 (Teams / Playground / Copilot Studio).

Module: main.py
Purpose: Web application host for a Microsoft Agents-based bot (Databricks Genie – M365 Agents).
"""

# ─────────────────────────────────────────────────────────────────────────────
# Project: Databricks Genie – M365 Agents
# File: databricks-genie-M365_agents/src/main.py
# Version: 0.1.0 (documentation pass, 2025-10-01)
# Author: Arnold Souza (arnoldporto@gmail.com | https://www.linkedin.com/in/arnoldsouza/)
# License: MIT
# Derived from: Luiz Carrossoni and Ryan Bates — see: https://github.com/carrossoni/DatabricksGenieBOT/tree/main
# Description: AioHTTP host for a Microsoft Agents application, exposing health,
#              readiness, static files, and the /api/messages endpoint for Teams/
#              Playground/Copilot Studio integration.
# ─────────────────────────────────────────────────────────────────────────────

import logging
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Awaitable, Optional, Dict, Any, List
from os import environ

from aiohttp import web
from aiohttp.web import Request, Response, Application
from aiohttp.web_middlewares import normalize_path_middleware

from microsoft_agents.hosting.core import AgentApplication
from microsoft_agents.hosting.aiohttp import (
    start_agent_process,
    jwt_authorization_middleware,
    CloudAdapter,
)

# Agent artifacts (import from local package)
from .agent import AGENT_APP, CONNECTION_MANAGER, VERSION as AGENT_VERSION

# ------------------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------------------
ms_agents_logger = logging.getLogger("microsoft_agents")
ms_agents_logger.addHandler(logging.StreamHandler())
ms_agents_logger.setLevel(logging.INFO)

logger = logging.getLogger("app")
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(handler)
logger.setLevel(logging.INFO)


# ------------------------------------------------------------------------------
# Environment helpers
# ------------------------------------------------------------------------------
def _env_bool(name: str, default: bool = False) -> bool:
    """
    Parse a boolean configuration value from an environment variable.

    Truthy values (case-insensitive): {"1", "true", "yes", "on", "y"}

    Args:
        name: Environment variable name.
        default: Value to return if the variable is unset or empty.

    Returns:
        The parsed boolean value or the provided default.
    """
    val = environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on", "y"}


def _env_int(name: str, default: int) -> int:
    """
    Parse an integer configuration value from an environment variable.

    Args:
        name: Environment variable name.
        default: Fallback value if parsing fails or variable is unset.

    Returns:
        Parsed integer value or the provided default.
    """
    try:
        return int(environ.get(name, str(default)))
    except Exception:
        return default


def _env_csv(name: str, default: str = "") -> List[str]:
    """
    Parse a comma-separated list from an environment variable.

    Args:
        name: Environment variable name.
        default: Default string used if the variable is not set.

    Returns:
        A list of trimmed, non-empty string tokens.
    """
    raw = environ.get(name, default)
    return [x.strip() for x in raw.split(",") if x.strip()]


# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------
@dataclass
class AppConfig:
    """
    Application configuration loaded from environment variables.

    Environment variables and defaults:
        HOST: Host interface to bind to (default "0.0.0.0").
        PORT: Primary HTTP port (default 8000).
        BASE_API: Base path to mount the API sub-app (default "/api").
        MESSAGES_PATH: Relative path under BASE_API for bot messages (default "/messages").
        PUBLIC_MOUNT: URL path prefix for static files (default "/public").
        PUBLIC_DIR: Filesystem directory serving static assets (default "./public").

        CLIENT_MAX_SIZE_MB: Max request size in megabytes for the root app (default 10).
        ENABLE_CORS: Enable CORS responses (default False).
        ALLOWED_ORIGINS: CSV list of allowed origins for CORS (default empty).
        STATIC_CACHE_SECONDS: Cache duration for static assets (default 3600).
        ENABLE_METRICS: Toggle metrics (placeholder; not used in this module).
        LOG_LEVEL: Application log level (default "INFO").
        DEBUG: Enable debug responses in error payloads (default False).

        COMPAT_LISTEN_3978: Also listen on port 3978 (Bot Framework default) with a
                            lightweight companion app for local Teams/Playground (default True).
    """

    host: str = environ.get("HOST", "0.0.0.0")
    port: int = _env_int("PORT", 8000)
    base_api: str = environ.get("BASE_API", "/api")
    messages_path: str = environ.get("MESSAGES_PATH", "/messages")
    public_mount: str = environ.get("PUBLIC_MOUNT", "/public")
    public_dir: str = environ.get("PUBLIC_DIR", "./public")

    client_max_size_mb: int = _env_int("CLIENT_MAX_SIZE_MB", 10)
    enable_cors: bool = _env_bool("ENABLE_CORS", False)
    allowed_origins: List[str] = field(default_factory=lambda: _env_csv("ALLOWED_ORIGINS", ""))
    static_cache_seconds: int = _env_int("STATIC_CACHE_SECONDS", 3600)
    enable_metrics: bool = _env_bool("ENABLE_METRICS", False)
    log_level: str = environ.get("LOG_LEVEL", "INFO").upper()
    debug: bool = _env_bool("DEBUG", False)

    # Compatibility: also listen on port 3978 for local Playground/Teams testing
    compat_listen_3978: bool = _env_bool("COMPAT_LISTEN_3978", True)

    def client_max_size_bytes(self) -> int:
        """
        Convert the client_max_size_mb setting to bytes.

        Returns:
            The request size limit in bytes (minimum 1 MB).
        """
        return max(1, self.client_max_size_mb) * 1024 * 1024


# ------------------------------------------------------------------------------
# Middlewares
# ------------------------------------------------------------------------------
@web.middleware
async def error_middleware(
    request: Request, handler: Callable[[Request], Awaitable[Response]]
) -> Response:
    """
    Global error translator.

    - Converts uncaught web.HTTPException into JSON with {error, status, detail?}.
    - Converts any other Exception into 500 JSON payload.
    - Includes 'detail' only when DEBUG is enabled.

    Args:
        request: Incoming HTTP request.
        handler: Next handler in the chain.

    Returns:
        Response: JSON response on error or the downstream handler's response.
    """
    try:
        return await handler(request)
    except web.HTTPException as http_err:
        payload = {"error": http_err.reason or "HTTP error", "status": http_err.status}
        if request.app["config"].debug:
            payload["detail"] = http_err.text or ""
        return web.json_response(payload, status=http_err.status)
    except Exception as e:
        req_id = request.get("request_id", "")
        logger.error(
            json.dumps(
                {
                    "event": "unhandled_exception",
                    "request_id": req_id,
                    "path": request.path if hasattr(request, "path") else "<no-path>",
                    "error": type(e).__name__,
                }
            )
        )
        payload = {"error": "Internal server error", "status": 500}
        if isinstance(request, Request) and request.app.get("config", None) and request.app["config"].debug:
            payload["detail"] = str(e)
        return web.json_response(payload, status=500)


@web.middleware
async def request_logger_middleware(
    request: Request, handler: Callable[[Request], Awaitable[Response]]
) -> Response:
    """
    Access logger and request ID injector.

    - Assigns/propagates an X-Request-ID for correlation.
    - Logs JSON line with method, path, status, duration, remote, user agent.
    - Adds 'X-Request-ID' header to the outgoing response.
    """
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request["request_id"] = req_id

    start = time.time()
    try:
        resp = await handler(request)
        return resp
    finally:
        duration_ms = int((time.time() - start) * 1000)
        status_code = getattr(getattr(request, "response", None), "status", 0)
        if "resp" in locals():
            status_code = getattr(resp, "status", status_code)

        logger.info(
            json.dumps(
                {
                    "event": "access",
                    "request_id": req_id,
                    "method": getattr(request, "method", "<no-method>"),
                    "path": getattr(request, "path", "<no-path>"),
                    "status": status_code,
                    "duration_ms": duration_ms,
                    "remote": request.remote,
                    "user_agent": request.headers.get("User-Agent", ""),
                }
            )
        )

        # Best-effort header injection
        try:
            if "resp" in locals():
                resp.headers["X-Request-ID"] = req_id
        except Exception:
            pass


@web.middleware
async def security_headers_middleware(
    request: Request, handler: Callable[[Request], Awaitable[Response]]
) -> Response:
    """
    Apply a minimal set of security-related response headers.

    Sets:
        X-Content-Type-Options=nosniff
        X-Frame-Options=DENY
        Referrer-Policy=no-referrer
        X-XSS-Protection=0 (legacy/no-op)
        Removes 'Server' header if present.
    """
    resp = await handler(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    resp.headers.setdefault("X-XSS-Protection", "0")
    resp.headers.pop("Server", None)
    return resp


def cors_middleware_factory(config: AppConfig):
    """
    Build a CORS middleware driven by AppConfig.

    Behavior:
        - If ENABLE_CORS is false, simply delegates to next handler.
        - For preflight (OPTIONS) requests, returns 204.
        - For allowed origins, sets standard CORS headers.

    Args:
        config: The application configuration.

    Returns:
        An aiohttp-compatible middleware callable.
    """

    @web.middleware
    async def cors_middleware(
        request: Request, handler: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not config.enable_cors:
            return await handler(request)

        origin = request.headers.get("Origin")
        allowed = origin in config.allowed_origins if origin else False

        if request.method == "OPTIONS":
            resp = web.Response(status=204)
        else:
            resp = await handler(request)

        if allowed and origin:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Vary"] = "Origin"
            resp.headers["Access-Control-Allow-Credentials"] = "true"
            resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
            resp.headers["Access-Control-Allow-Headers"] = "Authorization,Content-Type,X-Request-ID"
            resp.headers["Access-Control-Max-Age"] = "600"
        return resp

    return cors_middleware


# ------------------------------------------------------------------------------
# Request handlers
# ------------------------------------------------------------------------------
async def handle_root(request: Request) -> Response:
    """
    Simple landing page with pointers to health endpoints and API path.

    Args:
        request: Incoming HTTP request.

    Returns:
        HTML response with basic service info.
    """
    html = (
        "<!doctype html><html><head><meta charset='utf-8'><title>Genie Bot</title></head>"
        "<body style='font-family:system-ui,Segoe UI,Roboto,Arial,sans-serif;padding:24px;'>"
        "<h1>Genie Bot is running</h1>"
        "<p>Send messages to <code>POST "
        f"{request.app['config'].base_api}{request.app['config'].messages_path}"
        "</code>.</p>"
        "<ul>"
        "<li><a href='/healthz'>/healthz</a></li>"
        "<li><a href='/readyz'>/readyz</a></li>"
        "<li><a href='/livez'>/livez</a></li>"
        "</ul>"
        "</body></html>"
    )
    return web.Response(text=html, content_type="text/html")


async def healthz(_req: Request) -> Response:
    """
    Liveness-style health endpoint.

    Returns:
        JSON {'status': 'ok'}
    """
    return web.json_response({"status": "ok"})


async def livez(_req: Request) -> Response:
    """
    Process heartbeat endpoint (alias of health in this app).

    Returns:
        JSON {'status': 'alive'}
    """
    return web.json_response({"status": "alive"})


async def readiness_check(app: Application) -> Dict[str, Any]:
    """
    Internal readiness probe, verifying required objects are mounted.

    Checks:
        - 'agent_app' (AgentApplication)
        - 'adapter' (CloudAdapter)
        - 'api_app' (API sub-application presence)

    Args:
        app: The root aiohttp application.

    Returns:
        Dict with readiness fields:
            ready (bool), reasons (list[str]), version (str)
    """
    ready = True
    reasons: List[str] = []
    if app.get("agent_app") is None:
        ready = False
        reasons.append("agent_app is missing")
    if app.get("adapter") is None:
        ready = False
        reasons.append("adapter is missing")
    if "api_app" not in app:
        ready = False
        reasons.append("api subapp missing")
    return {"ready": ready, "reasons": reasons, "version": AGENT_VERSION}


async def readyz(req: Request) -> Response:
    """
    Public readiness endpoint.

    Returns:
        200 with readiness JSON when ready, else 503.
    """
    status = await readiness_check(req.app)
    return web.json_response(status, status=200 if status["ready"] else 503)


async def entry_point(req: Request) -> Response:
    """
    Bot Framework entry point that forwards incoming activities to the agent.

    The request is validated by the JWT authorization middleware at the API
    sub-app level before reaching this handler.

    Args:
        req: Incoming HTTP request bound for the /messages endpoint.

    Returns:
        The response returned by microsoft_agents.hosting.aiohttp.start_agent_process.
    """
    agent: AgentApplication = req.app["agent_app"]
    adapter: CloudAdapter = req.app["adapter"]
    return await start_agent_process(req, agent, adapter)


# ------------------------------------------------------------------------------
# API sub-application
# ------------------------------------------------------------------------------
def build_api_subapp(config: AppConfig) -> Application:
    """
    Construct the API sub-application.

    Routes:
        GET  {BASE_API}{MESSAGES_PATH} -> readiness-only (returns {'status': 'ok'})
        POST {BASE_API}{MESSAGES_PATH} -> bot entry point (protected by JWT)

    Middlewares:
        - messages_ready_middleware: Treats GET /messages as a lightweight readiness check.
        - jwt_authorization_middleware: Validates Bot Framework JWT on POSTs.

    Args:
        config: The shared AppConfig instance.

    Returns:
        Configured aiohttp Application for the API.
    """

    @web.middleware
    async def messages_ready_middleware(
        request: Request, handler: Callable[[Request], Awaitable[Response]]
    ):
        # Permite GET em /messages como sinal leve de prontidão (para testes locais)
        if request.method == "GET" and request.path.endswith(config.messages_path):
            return web.json_response({"status": "ok", "endpoint": "messages"})
        return await handler(request)

    @web.middleware
    async def auth_guard_mw(request: Request, handler: Callable[[Request], Awaitable[Response]]):
        if request.method == "POST" and request.path.endswith(config.messages_path):
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                return web.json_response({"error": "Unauthorized"}, status=401)
        return await handler(request)

    api_app = web.Application(
        middlewares=[messages_ready_middleware, auth_guard_mw, jwt_authorization_middleware]
    )

    api_app.router.add_post(config.messages_path, entry_point)
    api_app.router.add_get(config.messages_path, lambda _req: web.json_response({"status": "ok"}))

    api_app["agent_configuration"] = CONNECTION_MANAGER.get_default_connection_configuration()
    api_app["agent_app"] = AGENT_APP
    api_app["adapter"] = AGENT_APP.adapter
    return api_app



# ------------------------------------------------------------------------------
# Root app factory
# ------------------------------------------------------------------------------
def create_app(argv: Optional[List[str]] = None) -> Application:
    """
    Build and configure the root aiohttp application.

    Composition:
        - Normalizes paths (no trailing slashes).
        - Logs requests and ensures X-Request-ID.
        - Translates uncaught errors into JSON.
        - Optionally applies CORS.
        - Adds security headers.
        - Serves static files under PUBLIC_MOUNT with soft cache headers.
        - Mounts the API sub-app at BASE_API.
        - Exposes health (/healthz), readiness (/readyz), and liveness (/livez).
        - Optionally starts a compatibility server on port 3978 for local testing.

    Args:
        argv: Reserved for future CLI argument handling (unused).

    Returns:
        Configured aiohttp Application instance.
    """
    config = AppConfig()
    logging.getLogger().setLevel(getattr(logging, config.log_level, logging.INFO))

    root_app = web.Application(
        middlewares=[
            normalize_path_middleware(append_slash=False, remove_slash=True),
            request_logger_middleware,
            error_middleware,
            cors_middleware_factory(config),
            security_headers_middleware,
        ],
        client_max_size=config.client_max_size_bytes(),
    )

    # Basic routes
    root_app.router.add_get("/", handle_root)
    root_app.router.add_get("/healthz", healthz)
    root_app.router.add_get("/readyz", readyz)
    root_app.router.add_get("/livez", livez)

    # Static files with gentle caching (as a middleware to set Cache-Control only when applicable)
    @web.middleware
    async def static_cache_mw(
        request: Request, handler: Callable[[Request], Awaitable[Response]]
    ):
        """
        Append Cache-Control headers for responses under PUBLIC_MOUNT.
        """
        resp = await handler(request)
        if request.path.startswith(config.public_mount):
            resp.headers.setdefault("Cache-Control", f"public, max-age={config.static_cache_seconds}")
        return resp

    root_app.middlewares.append(static_cache_mw)
    root_app.router.add_static(
        config.public_mount, config.public_dir, show_index=False, follow_symlinks=True
    )

    # API sub-application
    api_app = build_api_subapp(config)
    root_app.add_subapp(config.base_api, api_app)

    # Expose shared objects on the root app
    root_app["config"] = config
    root_app["api_app"] = api_app
    root_app["agent_app"] = AGENT_APP
    root_app["adapter"] = AGENT_APP.adapter

    # Lifecycle hooks
    async def on_startup(app: Application):
        """
        Startup hook:
          - Logs startup event/version.
          - Optionally starts a lightweight compatibility server on port 3978
            mounting the same API under BASE_API (helpful for local Bot Framework/Teams).
        """
        logger.info(json.dumps({"event": "startup", "version": AGENT_VERSION}))
        # Start “compat app” on 3978 (no recursion)
        if config.compat_listen_3978:
            try:
                compat_app = web.Application()
                # health
                compat_app.router.add_get("/healthz", healthz)
                # mount the SAME API sub-app on "/api"
                compat_api = build_api_subapp(config)
                compat_app.add_subapp(config.base_api, compat_api)

                runner = web.AppRunner(compat_app)
                await runner.setup()
                site = web.TCPSite(runner, host=config.host, port=3978)
                await site.start()

                app["_compat_runner"] = runner
                logger.info(json.dumps({"event": "compat_listen_started", "port": 3978}))
            except OSError as e:
                logger.warning(
                    json.dumps({"event": "compat_listen_failed", "port": 3978, "error": type(e).__name__})
                )
            except Exception as e:
                logger.warning(
                    json.dumps(
                        {"event": "compat_listen_failed", "port": 3978, "error": f"{type(e).__name__}:{e}"}
                    )
                )

    async def on_cleanup(app: Application):
        """
        Cleanup hook:
          - Shuts down the compatibility runner if it was started.
          - Emits a 'cleanup' log event.
        """
        runner: Optional[web.AppRunner] = app.get("_compat_runner")
        if runner:
            try:
                await runner.cleanup()
            except Exception:
                pass
        logger.info(json.dumps({"event": "cleanup"}))

    root_app.on_startup.append(on_startup)
    root_app.on_cleanup.append(on_cleanup)
    return root_app


# Optional direct execution
if __name__ == "__main__":
    cfg = AppConfig()
    web.run_app(create_app(), host=cfg.host, port=cfg.port, access_log=None)
