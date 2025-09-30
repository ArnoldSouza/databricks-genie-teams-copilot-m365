# main.py
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

# Artefatos do agente
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
# Helpers de env
# ------------------------------------------------------------------------------
def _env_bool(name: str, default: bool = False) -> bool:
    val = environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on", "y"}

def _env_int(name: str, default: int) -> int:
    try:
        return int(environ.get(name, str(default)))
    except Exception:
        return default

def _env_csv(name: str, default: str = "") -> List[str]:
    raw = environ.get(name, default)
    return [x.strip() for x in raw.split(",") if x.strip()]

# ------------------------------------------------------------------------------
# Config
# ------------------------------------------------------------------------------
@dataclass
class AppConfig:
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

    # Compat: também escutar na porta 3978 para o Playground/Teams local
    compat_listen_3978: bool = _env_bool("COMPAT_LISTEN_3978", True)

    def client_max_size_bytes(self) -> int:
        return max(1, self.client_max_size_mb) * 1024 * 1024

# ------------------------------------------------------------------------------
# Middlewares
# ------------------------------------------------------------------------------
@web.middleware
async def error_middleware(request: Request, handler: Callable[[Request], Awaitable[Response]]) -> Response:
    try:
        return await handler(request)
    except web.HTTPException as http_err:
        payload = {"error": http_err.reason or "HTTP error", "status": http_err.status}
        if request.app["config"].debug:
            payload["detail"] = http_err.text or ""
        return web.json_response(payload, status=http_err.status)
    except Exception as e:
        req_id = request.get("request_id", "")
        logger.error(json.dumps({
            "event": "unhandled_exception",
            "request_id": req_id,
            "path": request.path if hasattr(request, "path") else "<no-path>",
            "error": type(e).__name__,
        }))
        payload = {"error": "Internal server error", "status": 500}
        if isinstance(request, Request) and request.app.get("config", None) and request.app["config"].debug:
            payload["detail"] = str(e)
        return web.json_response(payload, status=500)

@web.middleware
async def request_logger_middleware(request: Request, handler: Callable[[Request], Awaitable[Response]]) -> Response:
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

        logger.info(json.dumps({
            "event": "access",
            "request_id": req_id,
            "method": getattr(request, "method", "<no-method>"),
            "path": getattr(request, "path", "<no-path>"),
            "status": status_code,
            "duration_ms": duration_ms,
            "remote": request.remote,
            "user_agent": request.headers.get("User-Agent", ""),
        }))

        try:
            if "resp" in locals():
                resp.headers["X-Request-ID"] = req_id
        except Exception:
            pass

@web.middleware
async def security_headers_middleware(request: Request, handler: Callable[[Request], Awaitable[Response]]) -> Response:
    resp = await handler(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    resp.headers.setdefault("X-XSS-Protection", "0")
    resp.headers.pop("Server", None)
    return resp

def cors_middleware_factory(config: AppConfig):
    @web.middleware
    async def cors_middleware(request: Request, handler: Callable[[Request], Awaitable[Response]]) -> Response:
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
# Handlers
# ------------------------------------------------------------------------------
async def handle_root(request: Request) -> Response:
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
    return web.json_response({"status": "ok"})

async def livez(_req: Request) -> Response:
    return web.json_response({"status": "alive"})

async def readiness_check(app: Application) -> Dict[str, Any]:
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
    status = await readiness_check(req.app)
    return web.json_response(status, status=200 if status["ready"] else 503)

async def entry_point(req: Request) -> Response:
    agent: AgentApplication = req.app["agent_app"]
    adapter: CloudAdapter = req.app["adapter"]
    return await start_agent_process(req, agent, adapter)

# ------------------------------------------------------------------------------
# Subapp da API
# ------------------------------------------------------------------------------
def build_api_subapp(config: AppConfig) -> Application:
    # GET /messages só para readiness do Playground; POST protegido por JWT
    @web.middleware
    async def messages_ready_middleware(request: Request, handler: Callable[[Request], Awaitable[Response]]):
        if request.method == "GET" and request.path.endswith(config.messages_path):
            return web.json_response({"status": "ok", "endpoint": "messages"})
        return await handler(request)

    api_app = web.Application(middlewares=[messages_ready_middleware, jwt_authorization_middleware])
    api_app.router.add_post(config.messages_path, entry_point)
    api_app.router.add_get(config.messages_path, lambda _req: web.json_response({"status": "ok"}))
    # Injeta o agente
    api_app["agent_configuration"] = CONNECTION_MANAGER.get_default_connection_configuration()
    api_app["agent_app"] = AGENT_APP
    api_app["adapter"] = AGENT_APP.adapter
    return api_app

# ------------------------------------------------------------------------------
# Factory principal
# ------------------------------------------------------------------------------
def create_app(argv: Optional[List[str]] = None) -> Application:
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

    # Rotas básicas
    root_app.router.add_get("/", handle_root)
    root_app.router.add_get("/healthz", healthz)
    root_app.router.add_get("/readyz", readyz)
    root_app.router.add_get("/livez", livez)

    # Estático com cache suave (AGORA como middleware de verdade)
    @web.middleware
    async def static_cache_mw(request: Request, handler: Callable[[Request], Awaitable[Response]]):
        resp = await handler(request)
        if request.path.startswith(config.public_mount):
            resp.headers.setdefault("Cache-Control", f"public, max-age={config.static_cache_seconds}")
        return resp

    root_app.middlewares.append(static_cache_mw)
    root_app.router.add_static(config.public_mount, config.public_dir, show_index=False, follow_symlinks=True)

    # Subapp da API
    api_app = build_api_subapp(config)
    root_app.add_subapp(config.base_api, api_app)

    # Exposição no app
    root_app["config"] = config
    root_app["api_app"] = api_app
    root_app["agent_app"] = AGENT_APP
    root_app["adapter"] = AGENT_APP.adapter

    # Hooks de ciclo
    async def on_startup(app: Application):
        logger.info(json.dumps({"event": "startup", "version": AGENT_VERSION}))
        # Sobe “compat app” em 3978 (sem recursão)
        if config.compat_listen_3978:
            try:
                compat_app = web.Application()
                # health
                compat_app.router.add_get("/healthz", healthz)
                # monta a MESMA subapp de API em "/api"
                compat_api = build_api_subapp(config)
                compat_app.add_subapp(config.base_api, compat_api)

                runner = web.AppRunner(compat_app)
                await runner.setup()
                site = web.TCPSite(runner, host=config.host, port=3978)
                await site.start()

                app["_compat_runner"] = runner
                logger.info(json.dumps({"event": "compat_listen_started", "port": 3978}))
            except OSError as e:
                logger.warning(json.dumps({"event": "compat_listen_failed", "port": 3978, "error": type(e).__name__}))
            except Exception as e:
                logger.warning(json.dumps({"event": "compat_listen_failed", "port": 3978, "error": f"{type(e).__name__}:{e}"}))

    async def on_cleanup(app: Application):
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

# Execução direta opcional
if __name__ == "__main__":
    cfg = AppConfig()
    web.run_app(create_app(), host=cfg.host, port=cfg.port, access_log=None)
