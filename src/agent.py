import os
from pathlib import Path
import re
import json
import uuid
import time
import asyncio
import logging
import random
import hashlib
from dataclasses import dataclass, asdict
from typing import Dict, Optional, Any, Tuple, List, Callable
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from microsoft_agents.hosting.core import (
    Authorization,
    AgentApplication,
    TurnState,
    TurnContext,
    MemoryStorage,
)
from microsoft_agents.activity import (
    load_configuration_from_env,
    Activity,
    ActivityTypes,
    EndOfConversationCodes,
)
from microsoft_agents.authentication.msal import MsalConnectionManager
from microsoft_agents.hosting.aiohttp import CloudAdapter

# === Genie (Databricks) ===
from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import OperationFailed
from databricks.sdk.service.dashboards import GenieAPI

# ------------------------------------------------------------------------------

# Config (load env)

# ------------------------------------------------------------------------------

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=True)
agents_sdk_config = load_configuration_from_env(os.environ)

VERSION = os.getenv("VERSION", "databricks-genie-teams-1.4.1")
STORAGE = MemoryStorage()
CONNECTION_MANAGER = MsalConnectionManager(**agents_sdk_config)
ADAPTER = CloudAdapter(connection_manager=CONNECTION_MANAGER)
AUTHORIZATION = Authorization(STORAGE, CONNECTION_MANAGER, **agents_sdk_config)

logger = logging.getLogger(f"{VERSION}")
logging.basicConfig(level=logging.INFO)

AGENT_APP = AgentApplication[TurnState](
    storage=STORAGE, adapter=ADAPTER, authorization=AUTHORIZATION, **agents_sdk_config
)

# ------------------------------------------------------------------------------

# Databricks / Genie env

# ------------------------------------------------------------------------------

# DATABRICKS_HOST = os.getenv("DATABRICKS_HOST")
# DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN")
# DATABRICKS_SPACE_ID = os.getenv("DATABRICKS_SPACE_ID")

# DBX_ENABLED = bool(DATABRICKS_HOST and DATABRICKS_TOKEN and DATABRICKS_SPACE_ID)

DATABRICKS_HOST = os.getenv("DATABRICKS_HOST")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN")
DATABRICKS_CLIENT_ID = os.getenv("DATABRICKS_CLIENT_ID")
DATABRICKS_CLIENT_SECRET = os.getenv("DATABRICKS_CLIENT_SECRET")
DATABRICKS_SPACE_ID = os.getenv("DATABRICKS_SPACE_ID")

DBX_HAS_PAT = bool(DATABRICKS_TOKEN)
DBX_HAS_OAUTH = bool(DATABRICKS_CLIENT_ID and DATABRICKS_CLIENT_SECRET)
DBX_ENABLED = bool(DATABRICKS_HOST and DATABRICKS_SPACE_ID and (DBX_HAS_PAT or DBX_HAS_OAUTH))

# Safety limits for Teams/Playground render (global hard caps)
MAX_ROWS_DEFAULT = int(os.getenv("GENIE_MAX_ROWS", "50"))
CALL_TIMEOUT_SECONDS_DEFAULT = int(os.getenv("GENIE_TIMEOUT", "60"))
GENIE_MAX_CHARS_DEFAULT = int(os.getenv("GENIE_MAX_CHARS", "12000"))
GENIE_MAX_COLS_DEFAULT = int(os.getenv("GENIE_MAX_COLS", "8"))
GENIE_MAX_CELL_CHARS_DEFAULT = int(os.getenv("GENIE_MAX_CELL_CHARS", "200"))

# Hard clamps to avoid abuse/misconfig
HARD_MAX_ROWS = int(os.getenv("HARD_MAX_ROWS", "500"))
HARD_MAX_COLS = int(os.getenv("HARD_MAX_COLS", "50"))
HARD_MAX_CHARS = int(os.getenv("HARD_MAX_CHARS", "24000"))
HARD_MAX_CELL_CHARS = int(os.getenv("HARD_MAX_CELL_CHARS", "2000"))
HARD_MAX_TIMEOUT = int(os.getenv("HARD_MAX_TIMEOUT", "600"))
HARD_MAX_QUERY_TIMEOUT = int(os.getenv("HARD_MAX_QUERY_TIMEOUT", "1200"))

# Rate limiting & dedup
MIN_INTERVAL_SECONDS = float(os.getenv("MIN_INTERVAL_SECONDS", "2.0"))  # per user
DEDUP_WINDOW_SECONDS = float(os.getenv("DEDUP_WINDOW_SECONDS", "8.0"))  # same text

# Retry policy
MAX_RETRIES = int(os.getenv("GENIE_MAX_RETRIES", "3"))
BASE_DELAY = float(os.getenv("RETRY_BASE_DELAY", "0.8"))

# Timezone for user-facing timestamps
USER_TZ = ZoneInfo(os.getenv("USER_TZ", "America/Sao_Paulo"))

# ------------------------------------------------------------------------------

# Utilities

# ------------------------------------------------------------------------------

def clamp(val: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, val))

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def log_event(level: int, event: str, **kwargs):
    try:
        payload = {"event": event, "v": VERSION, **kwargs}
        logger.log(level, json.dumps(payload, ensure_ascii=False))
    except Exception:
        logger.log(level, f"{event} | {kwargs}")

def truthy(s: str) -> Optional[bool]:
    if s is None:
        return None
    t = s.strip().lower()
    if t in ("1", "true", "on", "yes", "y", "enable", "enabled"):
        return True
    if t in ("0", "false", "off", "no", "n", "disable", "disabled"):
        return False
    return None

def fmt_epoch_ms_to_local(ms_like: Any) -> str:
    """Converts epoch ms (int/str) to a local timestamp string."""
    try:
        ms = int(str(ms_like).strip())
        dt = datetime.fromtimestamp(ms / 1000, tz=USER_TZ)
        return dt.strftime("%Y-%m-%d %H:%M:%S %z")
    except Exception:
        return str(ms_like)

def _is_skill_invocation(activity: Activity) -> bool:
    """
    Returns True if this turn was initiated by a parent bot (Bot Framework Skill).
    Bot Framework sets caller_id to something like 'urn:botframework:skill'
    when invoking a skill.
    """
    caller = (getattr(activity, "caller_id", "") or "").lower()
    return "skill" in caller

# ------------------------------------------------------------------------------

# Settings

# ------------------------------------------------------------------------------

@dataclass
class UserSettings:
    rows: int = MAX_ROWS_DEFAULT
    cols: int = GENIE_MAX_COLS_DEFAULT
    chars: int = GENIE_MAX_CHARS_DEFAULT
    cell_chars: int = GENIE_MAX_CELL_CHARS_DEFAULT
    timeout: int = CALL_TIMEOUT_SECONDS_DEFAULT         # text-level operations
    query_timeout: int = max(CALL_TIMEOUT_SECONDS_DEFAULT, 120)  # SQL fetch timeout
    sql_notes: bool = True  # include generated SQL in Notes

    def clamped(self) -> "UserSettings":
        return UserSettings(
            rows=clamp(self.rows, 1, HARD_MAX_ROWS),
            cols=clamp(self.cols, 1, HARD_MAX_COLS),
            chars=clamp(self.chars, 1000, HARD_MAX_CHARS),
            cell_chars=clamp(self.cell_chars, 20, HARD_MAX_CELL_CHARS),
            timeout=clamp(self.timeout, 5, HARD_MAX_TIMEOUT),
            query_timeout=clamp(self.query_timeout, 30, HARD_MAX_QUERY_TIMEOUT),
            sql_notes=self.sql_notes,
        )

    def pretty(self, space_title: str, space_id: str) -> str:
        s = self.clamped()
        return (
            f"**Current Genie Space:** {space_title} (`{space_id}`)\n"
            f"Your current limits → rows={s.rows}, cols={s.cols}, "
            f"chars/activity={s.chars}, cell chars={s.cell_chars}, "
            f"timeout={s.timeout}s, query_timeout={s.query_timeout}s\n"
            f"Extras → sql_notes={'on' if s.sql_notes else 'off'}"
        )

# ------------------------------------------------------------------------------

# GenieBot

# ------------------------------------------------------------------------------

class GenieBot:
    # Precompiled regex
    RE_CONFIG_CMD = re.compile(r"^\s*(config|settings?|set)\b", re.IGNORECASE)
    RE_PAIR_NUM = re.compile(
        r"(?i)\b(rows|cols|columns|timeout|chars|cell|cell_chars|query_timeout|qt)\s*[:=]\s*(\d+)"
    )
    RE_PAIR_BOOL = re.compile(
        r"(?i)\b(sql|sql_notes)\s*[:=]\s*(on|off|true|false|yes|no|enable|disable|enabled|disabled|0|1)\b"
    )
    RE_RESET = re.compile(r"^(?:/)?(?:reset|restart|clear|start\s+over)\b", re.IGNORECASE)

    # Spaces / conversations commands
    RE_SPACES = re.compile(r"^spaces\b", re.IGNORECASE)  # plural only
    RE_SPACE = re.compile(r"^space\b", re.IGNORECASE)    # singular
    RE_CONVERSATIONS = re.compile(r"^(conversations?)\b", re.IGNORECASE)
    RE_MESSAGES = re.compile(r"^(messages?)\b", re.IGNORECASE)

    KEYMAP_NUM = {
        "rows": "rows",
        "cols": "cols", "columns": "cols",
        "timeout": "timeout",
        "chars": "chars",
        "cell": "cell_chars", "cell_chars": "cell_chars",
        "query_timeout": "query_timeout", "qt": "query_timeout",
    }

    def __init__(self):
        self._workspace_client: Optional[WorkspaceClient] = None
        self._genie_api: Optional[GenieAPI] = None

        self._user_settings: Dict[str, UserSettings] = {}
        self._user_conversation: Dict[str, str] = {}
        self._user_locks: Dict[str, asyncio.Lock] = {}
        self._user_next_allowed: Dict[str, float] = {}
        self._user_dedup: Dict[str, Dict[str, Any]] = {}
        self._user_space: Dict[str, str] = {}  # per-user space override; default is env
        self._space_title_cache: Dict[str, str] = {}

        # if DBX_ENABLED:
        #     try:
        #         self._workspace_client = WorkspaceClient(host=DATABRICKS_HOST, token=DATABRICKS_TOKEN)
        #         self._genie_api = GenieAPI(self._workspace_client.api_client)
        #         log_event(logging.INFO, "✅ genie_init_ok", host=bool(DATABRICKS_HOST), space=bool(DATABRICKS_SPACE_ID))
        #     except Exception as e:
        #         log_event(logging.ERROR, "⛔ genie_init_failed", error=str(e.__class__.__name__))
        #         self._workspace_client = None
        #         self._genie_api = None

        if DBX_ENABLED:
            client_kwargs = {"host": DATABRICKS_HOST}

            if DBX_HAS_PAT:
                client_kwargs["token"] = DATABRICKS_TOKEN
            else:
                client_kwargs["client_id"] = DATABRICKS_CLIENT_ID
                client_kwargs["client_secret"] = DATABRICKS_CLIENT_SECRET
                client_kwargs["auth_type"] = "oauth-m2m"

            self._workspace_client = WorkspaceClient(**client_kwargs)
            self._genie_api = self._workspace_client.genie

            try:
                self._genie_api.list_spaces()
                log_event(logging.INFO, "✅ genie_init_ok", auth="pat" if DBX_HAS_PAT else "oauth")
            except Exception as e:
                log_event(logging.ERROR, "⛔ genie_init_failed", stage="genie_ping", error=str(e))
                self._workspace_client = None
                self._genie_api = None


    # -------------------- Space helpers --------------------

    def get_user_space_id(self, user_id: str) -> str:
        return self._user_space.get(user_id) or DATABRICKS_SPACE_ID

    def set_user_space_id(self, user_id: str, space_id: str):
        self._user_space[user_id] = space_id
        # reset conversation when changing spaces
        self._user_conversation.pop(user_id, None)

    async def _fetch_spaces(self) -> List[Dict[str, Any]]:
        """Returns a list of spaces as dicts with {id, title}."""
        assert self._genie_api is not None

        def _list_spaces():
            resp = self._genie_api.list_spaces()  # GenieListSpacesResponse
            items = getattr(resp, "spaces", None) or []
            out = []
            for s in items:
                sid = getattr(s, "space_id", None)
                title = getattr(s, "title", None) or f"Space {sid}"
                if sid:
                    out.append({"id": sid, "title": title})
            return out

        return await asyncio.to_thread(_list_spaces)

    async def _ensure_space_title(self, space_id: str) -> str:
        if not space_id:
            return "(no space)"
        if space_id in self._space_title_cache:
            return self._space_title_cache[space_id]
        title = "(unknown space)"
        try:
            s = await asyncio.to_thread(self._genie_api.get_space, space_id)
            title = getattr(s, "title", None) or title
        except Exception:
            pass
        self._space_title_cache[space_id] = title
        return title

    # -------------------- Health / Help / Welcome --------------------

    def health_summary(self) -> str:
        if self._genie_api and self._workspace_client and DBX_ENABLED:
            return "Genie is enabled and configured."
        return "⚠️ The data connection isn’t set up yet. Please contact your admin."

    async def help_text(self, user_id: str) -> str:
        space_id = self.get_user_space_id(user_id)
        space_title = await self._ensure_space_title(space_id)
        return (
            f"**Databricks Genie Help** ({VERSION}) • **Current Space:** {space_title} (`{space_id}`)\n"
            "\n"
            "**Basics**\n"
            "- Type your question directly\n"
            "- `help` → show this help\n"
            "- `version` → show version\n"
            "- `reset` → start a fresh conversation (keeps your config)\n"
            "\n"
            "**Settings** (`config ...`)\n"
            "- `config show` → display current settings (including current Genie Space)\n"
            "- `config defaults` → restore default limits\n"
            "- `config rows=100 cols=20 timeout=90 query_timeout=180` → adjust numeric limits\n"
            "- `config sql=on` → include the **generated SQL** in table replies (default: on)\n"
            "  Fields: rows, cols/columns, chars, cell/cell_chars, timeout, query_timeout (qt), sql/sql_notes\n"
            "\n"
            "**Spaces**\n"
            "- `spaces list` → list available Genie Spaces\n"
            "- `space show` → show current Genie Space\n"
            "- `space set <space-id or title>` → switch to another Genie Space\n"
            "  _(Default remains the one in `DATABRICKS_SPACE_ID` until you switch.)_\n"
            "\n"
            "**Conversations (in current space)**\n"
            "- `conversations list` → list your conversations in this Genie Space\n"
            "- `messages <conversation-id> [N]` → list the last messages of a conversation (default N=3)\n"
        )

    async def welcome_text(self, user_id: str) -> str:
        space_id = self.get_user_space_id(user_id)
        space_title = await self._ensure_space_title(space_id)
        return (
            f"Hi! I’m Genie — your data assistant in **{space_title}**.\n"
            "- Try questions like:\n"
            "    - `Which tables do you have?`\n"
            "    - `Show me the list of columns and what they mean for the first table you have`\n"
            "    - `Show me the first 5 lines of the first table you have`.\n"
            "- Need a fresh start? Type `reset`.\n"
            "- For tips, type `help`."
        )

    # -------------------- State / Settings --------------------

    def get_lock(self, user_id: str) -> asyncio.Lock:
        lock = self._user_locks.get(user_id)
        if not lock:
            lock = asyncio.Lock()
            self._user_locks[user_id] = lock
        return lock

    def get_settings(self, user_id: str) -> UserSettings:
        s = self._user_settings.get(user_id)
        if not s:
            s = UserSettings()
            self._user_settings[user_id] = s
        return s.clamped()

    def apply_overrides(self, user_id: str, overrides: Dict[str, Any]) -> UserSettings:
        current = self.get_settings(user_id)
        updated = UserSettings(**{**asdict(current), **overrides}).clamped()
        self._user_settings[user_id] = updated
        return updated

    def parse_config_overrides(self, text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        if not (self.RE_CONFIG_CMD.search(text) or self.RE_PAIR_NUM.search(text) or self.RE_PAIR_BOOL.search(text)):
            return None

        out: Dict[str, Any] = {}
        for k, v in self.RE_PAIR_NUM.findall(text):
            nk = self.KEYMAP_NUM.get(k.lower())
            if nk:
                try:
                    out[nk] = max(1, int(v))
                except Exception:
                    pass
        for _k, v in self.RE_PAIR_BOOL.findall(text):
            val = truthy(v)
            if val is not None:
                out["sql_notes"] = val
        return out if out else {}

    # -------------------- Rate limiting / Dedup --------------------

    def check_rate_limit(self, user_id: str) -> Optional[float]:
        now = time.monotonic()
        nxt = self._user_next_allowed.get(user_id, 0.0)
        if now < nxt:
            return round(nxt - now, 2)
        return None

    def note_rate(self, user_id: str):
        self._user_next_allowed[user_id] = time.monotonic() + MIN_INTERVAL_SECONDS

    def check_dedup(self, user_id: str, text: str) -> Optional[str]:
        norm = " ".join((text or "").split())
        h = sha256_hex(norm)
        now = time.monotonic()
        entry = self._user_dedup.get(user_id)
        if entry and entry.get("hash") == h and (now - entry.get("ts", 0.0)) <= DEDUP_WINDOW_SECONDS:
            return entry.get("md")
        return None

    def store_dedup(self, user_id: str, text: str, md: str):
        norm = " ".join((text or "").split())
        self._user_dedup[user_id] = {"hash": sha256_hex(norm), "ts": time.monotonic(), "md": md}

    # -------------------- Conversation --------------------

    def reset_conversation(self, user_id: str):
        self._user_conversation.pop(user_id, None)
        self._user_dedup.pop(user_id, None)

    def get_conversation_id(self, user_id: str) -> Optional[str]:
        return self._user_conversation.get(user_id)

    def set_conversation_id(self, user_id: str, conv_id: str):
        self._user_conversation[user_id] = conv_id

    # -------------------- Markdown rendering --------------------

    @staticmethod
    def _escape_cell(value: Any) -> str:
        s = "" if value is None else str(value)
        s = s.replace("|", r"\|").replace("\r", " ").replace("\n", " ")
        s = s.replace("`", "ʼ")
        return s

    @staticmethod
    def _truncate_text(s: str, limit: int) -> str:
        if s is None:
            return ""
        if len(s) <= limit:
            return s
        return s[: max(0, limit - 1)] + "…"

    def _fmt_cell(self, value: Any, type_name: str, cell_limit: int) -> str:
        t = (type_name or "").upper()
        if value is None:
            return "NULL"
        try:
            if t in ("DECIMAL", "DOUBLE", "FLOAT"):
                return self._truncate_text(f"{float(value):,.2f}", cell_limit)
            if t in ("INT", "BIGINT", "LONG"):
                return self._truncate_text(f"{int(value):,}", cell_limit)
            return self._truncate_text(self._escape_cell(value), cell_limit)
        except Exception:
            return self._truncate_text(self._escape_cell(value), cell_limit)

    @staticmethod
    def _truncate_rows(rows: List[List[Any]], max_rows: int) -> Tuple[List[List[Any]], Optional[int]]:
        if not rows:
            return [], None
        if len(rows) <= max_rows:
            return rows, None
        return rows[:max_rows], len(rows) - max_rows

    @staticmethod
    def _limit_cols(cols_meta: Any, rows: List[List[Any]], max_cols: int) -> Tuple[List[Dict[str, Any]], List[List[Any]], Optional[int]]:
        meta_cols = []
        if isinstance(cols_meta, dict):
            meta_cols = cols_meta.get("columns", []) or []
        elif isinstance(cols_meta, list):
            meta_cols = cols_meta
        else:
            meta_cols = []

        if len(meta_cols) <= max_cols:
            fixed_rows = [r[:len(meta_cols)] for r in rows]
            return meta_cols, fixed_rows, None

        kept = meta_cols[:max_cols]
        new_rows = [r[:max_cols] for r in rows]
        hidden = len(meta_cols) - max_cols
        return kept, new_rows, hidden

    @staticmethod
    def _rows_from_result_dict(data_dict: Dict[str, Any]) -> List[List[Any]]:
        """Accept both 'data_array' and 'data_typed_array' shapes."""
        if not data_dict:
            return []
        if "data_array" in data_dict and isinstance(data_dict["data_array"], list):
            return data_dict["data_array"]
        if "data_typed_array" in data_dict and isinstance(data_dict["data_typed_array"], list):
            rows = []
            for row in data_dict["data_typed_array"]:
                if isinstance(row, list):
                    rows.append([cell.get("v") if isinstance(cell, dict) else cell for cell in row])
            return rows
        return data_dict.get("data_array") or []

    def format_genie_answer_md(
        self,
        answer_json: Dict,
        *,
        rows_limit: int,
        cols_limit: int,
        cell_limit: int,
        show_sql: bool,
    ) -> str:
        if "error" in answer_json:
            return f"⚠️ {answer_json['error']}"

        parts: List[str] = []

        query_text = (answer_json.get("query_description") or "").strip()
        sql_text = (answer_json.get("sql") or "").strip()

        if query_text:
            parts.append("## Query Description:\n\n")
            parts.append(query_text + "\n\n")

        if "columns" in answer_json and "data" in answer_json:
            cols_meta = (answer_json.get("columns") or {})
            data_dict = (answer_json.get("data") or {})
            raw_rows = self._rows_from_result_dict(data_dict)

            rows, hidden_rows = self._truncate_rows(raw_rows, rows_limit)
            meta_cols, rows, hidden_cols = self._limit_cols(cols_meta, rows, cols_limit)

            parts.append("## Query Results:\n\n")

            if meta_cols:
                table_lines: List[str] = []
                headers = [c.get("name", f"col{i+1}") for i, c in enumerate(meta_cols)]
                table_lines.append("| " + " | ".join(headers) + " |")
                table_lines.append("|" + "|".join(["---"] * len(headers)) + "|")

                for row in rows:
                    formatted: List[str] = []
                    for value, col in zip(row, meta_cols):
                        formatted.append(self._fmt_cell(value, col.get("type_name") or "", cell_limit))
                    table_lines.append("| " + " | ".join(formatted) + " |")

                parts.append("\n".join(table_lines) + "\n")

                notes_bits: List[str] = []
                if hidden_rows:
                    notes_bits.append(f"{hidden_rows} hidden row(s)")
                if hidden_cols:
                    notes_bits.append(f"{hidden_cols} hidden column(s)")
                if notes_bits or (show_sql and sql_text):
                    parts.append("\n### Notes:\n\n")
                    if notes_bits:
                        parts.append("_" + " • ".join(notes_bits) + ". Refine your question to see fewer rows/columns._\n")
                        parts.append("_To see more, send: `config cols=20 rows=200` (example)._")
                    if show_sql and sql_text:
                        parts.append(f"\n> SQL: ```{sql_text}```\n")
            else:
                parts.append("\n_No columns to display._")

        elif "message" in answer_json:
            content = str((answer_json.get("message") or "_No content._")).strip()
            parts.append(content)
        else:
            parts.append("_No data available._")

        return "\n".join(parts)

    @staticmethod
    def chunk_markdown(md: str, limit: int) -> List[str]:
        if not md:
            return []
        md = md.strip()
        if len(md) <= limit:
            return [md]
        blocks = [b.strip() for b in md.split("\n\n") if b.strip()]
        chunks: List[str] = []
        current = ""

        def flush():
            nonlocal current
            if current:
                chunks.append(current.rstrip())
                current = ""

        for b in blocks:
            candidate = (current + "\n\n" + b).strip() if current else b
            if len(candidate) <= limit:
                current = candidate
            else:
                if not current:
                    lines = b.splitlines()
                    tmp = ""
                    for ln in lines:
                        cand2 = (tmp + ("\n" if tmp else "") + ln)
                        if len(cand2) <= limit:
                            tmp = cand2
                        else:
                            if tmp:
                                chunks.append(tmp)
                                tmp = ln if len(ln) <= limit else ln[:limit-1] + "…"
                            else:
                                chunks.append(ln[:limit-1] + "…")
                                tmp = ""
                    if tmp:
                        chunks.append(tmp)
                    current = ""
                else:
                    flush()
                    lines = b.splitlines()
                    tmp = ""
                    for ln in lines:
                        cand2 = (tmp + ("\n" if tmp else "") + ln)
                        if len(cand2) <= limit:
                            tmp = cand2
                        else:
                            if tmp:
                                chunks.append(tmp)
                            chunks.append(ln[:limit-1] + "…")
                            tmp = ""
                    if tmp:
                        chunks.append(tmp)
        flush()
        return chunks

    async def send_markdown(self, context: TurnContext, md: str, *, max_chars: int):
        parts = self.chunk_markdown(md, max_chars)
        total = len(parts)
        for idx, part in enumerate(parts, 1):
            suffix = f"\n\n_{idx}/{total}_" if total > 1 else ""
            await context.send_activity(part + suffix)

    # -------------------- Genie Calls with Retry --------------------

    @staticmethod
    def _is_retryable_error(e: Exception) -> bool:
        s = f"{type(e).__name__} {str(e)}".lower()
        non_retry_signals = ("401", "403", "unauthorized", "forbidden", "invalid schema", "bad request")
        return not any(sig in s for sig in non_retry_signals)

    async def _with_retry(self, func: Callable[[], Any], *, retries: int, timeout: Optional[float]) -> Any:
        last_exc: Optional[Exception] = None
        _timeout = timeout if timeout and timeout > 0 else CALL_TIMEOUT_SECONDS_DEFAULT
        for attempt in range(retries):
            try:
                return await asyncio.wait_for(func(), timeout=_timeout)
            except Exception as e:
                last_exc = e
                if not self._is_retryable_error(e) or attempt == retries - 1:
                    break
                delay = (BASE_DELAY * (2 ** attempt)) + random.uniform(0, BASE_DELAY)
                await asyncio.sleep(delay)
        if last_exc:
            raise last_exc
        raise RuntimeError("Unexpected retry without exception")

    async def ask_genie(
        self,
        question: str,
        space_id: str,
        conversation_id: Optional[str],
        *,
        timeout_text: int,
        timeout_query: int
    ) -> Tuple[str, str]:
        assert self._genie_api is not None and self._workspace_client is not None

        # 1) Create/continue the conversation and wait
        async def _create_waiter():
            if conversation_id is None:
                return await asyncio.to_thread(self._genie_api.start_conversation, space_id, question)
            return await asyncio.to_thread(self._genie_api.create_message, space_id, conversation_id, question)

        waiter = await self._with_retry(_create_waiter, retries=MAX_RETRIES, timeout=timeout_text)
        conversation_id = waiter.conversation_id
        message_id = waiter.message_id

        async def _failure_detail(fallback: str) -> str:
            detail = fallback
            try:
                failed_message = await asyncio.to_thread(
                    self._genie_api.get_message,
                    space_id,
                    conversation_id,
                    message_id,
                )
                err_obj = getattr(failed_message, "error", None)
                err_text = getattr(err_obj, "error", None) if err_obj else None
                if err_text:
                    detail = err_text
            except Exception as fetch_err:
                log_event(
                    logging.WARNING,
                    "genie_failure_detail_lookup_failed",
                    space_id=space_id,
                    conversation_id=conversation_id,
                    message_id=message_id,
                    error=str(fetch_err),
                )
            return detail

        wait_timeout = max(5, timeout_text)
        try:
            initial_message = await asyncio.wait_for(
                asyncio.to_thread(waiter.result, timeout=timedelta(seconds=wait_timeout)),
                timeout=wait_timeout + 5,
            )
        except OperationFailed as op_err:
            detail = await _failure_detail(str(op_err))
            friendly = f"Genie couldn't complete the request: {detail}"
            if DBX_HAS_OAUTH:
                friendly += " Please verify that the Databricks service principal has access to the Genie space and underlying data."
            log_event(
                logging.ERROR,
                "genie_conversation_failed",
                space_id=space_id,
                conversation_id=conversation_id,
                message_id=message_id,
                error=detail,
            )
            return json.dumps({"error": friendly}), conversation_id
        except asyncio.TimeoutError:
            friendly = (
                "Genie timed out before completing the request. Try increasing your "
                "`timeout` or `query_timeout` limits with `config timeout=120 query_timeout=300`."
            )
            log_event(
                logging.ERROR,
                "genie_conversation_timeout",
                space_id=space_id,
                conversation_id=conversation_id,
                message_id=message_id,
            )
            return json.dumps({"error": friendly}), conversation_id
        except Exception as wait_err:
            detail = await _failure_detail(str(wait_err))
            friendly = f"Genie couldn't complete the request: {detail}"
            if DBX_HAS_OAUTH:
                friendly += " Please verify that the Databricks service principal has access to the Genie space and underlying data."
            log_event(
                logging.ERROR,
                "genie_conversation_wait_failed",
                space_id=space_id,
                conversation_id=conversation_id,
                message_id=message_id,
                error=str(wait_err),
            )
            return json.dumps({"error": friendly}), conversation_id

        conversation_id = initial_message.conversation_id

        # 2) Get the full message (attachments, status, etc.)
        async def _get_msg():
            return await asyncio.to_thread(
                self._genie_api.get_message,
                space_id,
                conversation_id,
                initial_message.id  # legacy field still populated
            )
        message = await self._with_retry(_get_msg, retries=MAX_RETRIES, timeout=timeout_text)

        # Prefer QUERY attachments over TEXT
        query_attachment = None
        text_attachment = None
        if getattr(message, "attachments", None):
            for att in message.attachments or []:
                if getattr(att, "query", None):
                    query_attachment = att
                    break
            if not query_attachment:
                for att in message.attachments or []:
                    if getattr(att, "text", None) and getattr(att.text, "content", None):
                        text_attachment = att
                        break

        # Pure text only?
        if text_attachment and not query_attachment:
            return json.dumps({"message": text_attachment.text.content}), conversation_id

        # Query path
        if not query_attachment:
            # No attachments we can handle; fall back to message content
            return json.dumps({"message": getattr(message, "content", "") or ""}), conversation_id

        q = query_attachment.query
        attachment_id = getattr(query_attachment, "attachment_id", None)
        query_description = getattr(q, "description", "") or ""
        statement_id = getattr(q, "statement_id", None)
        sql_text_found = getattr(q, "query", None)  # AI-generated SQL

        async def _fetch_statement(stmt_id: str):
            return await self._with_retry(
                lambda: asyncio.to_thread(self._workspace_client.statement_execution.get_statement, stmt_id),
                retries=MAX_RETRIES,
                timeout=timeout_query,
            )

        results = None
        fetch_errors: List[str] = []

        async def _safe_fetch_statement(stmt_id: str):
            try:
                return await _fetch_statement(stmt_id)
            except Exception as stmt_err:
                fetch_errors.append(f"{type(stmt_err).__name__}: {stmt_err}")
                log_event(
                    logging.WARNING,
                    "genie_stmt_fetch_failed",
                    space_id=space_id,
                    statement_id=stmt_id,
                    error=str(stmt_err),
                )
                return None

        if statement_id:
            results = await _safe_fetch_statement(statement_id)

        if results is None:
            if not attachment_id:
                details = fetch_errors[0] if fetch_errors else "missing attachment"
                return json.dumps({"error": f"Query result unavailable ({details}). Please try again."}), conversation_id

            async def _get_qr():
                return await asyncio.to_thread(
                    self._genie_api.get_message_attachment_query_result,
                    space_id,
                    conversation_id,
                    initial_message.id,
                    attachment_id,
                )

            try:
                qr = await self._with_retry(_get_qr, retries=MAX_RETRIES, timeout=timeout_query)
            except Exception as qr_err:
                fetch_errors.append(f"{type(qr_err).__name__}: {qr_err}")
                log_event(
                    logging.WARNING,
                    "genie_attachment_fetch_failed",
                    space_id=space_id,
                    attachment_id=attachment_id,
                    error=str(qr_err),
                )
                qr = None

            stmt_resp = getattr(qr, "statement_response", None) if qr else None
            stmt_from_qr = getattr(stmt_resp, "statement_id", None)

            if stmt_from_qr:
                results = await _safe_fetch_statement(stmt_from_qr)

            if results is None:
                async def _exec_qr():
                    return await asyncio.to_thread(
                        self._genie_api.execute_message_attachment_query,
                        space_id,
                        conversation_id,
                        initial_message.id,
                        attachment_id,
                    )

                try:
                    rerun = await self._with_retry(_exec_qr, retries=MAX_RETRIES, timeout=timeout_query)
                except Exception as rerun_err:
                    fetch_errors.append(f"{type(rerun_err).__name__}: {rerun_err}")
                    log_event(
                        logging.ERROR,
                        "genie_attachment_rerun_failed",
                        space_id=space_id,
                        attachment_id=attachment_id,
                        error=str(rerun_err),
                    )
                    details = ", ".join(fetch_errors) if fetch_errors else "unknown error"
                    return json.dumps({"error": f"Query result unavailable ({details}). Please try again."}), conversation_id

                stmt_resp2 = getattr(rerun, "statement_response", None)
                stmt_from_rerun = getattr(stmt_resp2, "statement_id", None)

                if not stmt_from_rerun:
                    details = ", ".join(fetch_errors) if fetch_errors else "no statement id"
                    return json.dumps({"error": f"Query result unavailable ({details}). Please try again."}), conversation_id

                results = await _safe_fetch_statement(stmt_from_rerun)

                if results is None:
                    details = ", ".join(fetch_errors) if fetch_errors else "statement fetch failed"
                    return json.dumps({"error": f"Query result unavailable ({details}). Please try again."}), conversation_id

        # Try to extract SQL text from the statement if not already found
        sql_from_stmt = None
        try:
            sql_from_stmt = getattr(results, "statement", None) or getattr(results, "origin_body", None)
        except Exception:
            sql_from_stmt = None

        # Build payload (accept schema/result variants)
        schema_dict = {}
        data_dict = {}
        try:
            schema_dict = results.manifest.schema.as_dict()
        except Exception:
            schema = getattr(getattr(results, "manifest", None), "schema", None)
            schema_dict = schema.as_dict() if schema else {}

        try:
            data_dict = results.result.as_dict()
        except Exception:
            data = getattr(results, "result", None)
            data_dict = data.as_dict() if data else {}

        payload = {
            "columns": schema_dict,
            "data": data_dict,
            "query_description": query_description
        }
        sql_final = sql_text_found or sql_from_stmt
        if sql_final:
            payload["sql"] = str(sql_final)

        return json.dumps(payload), conversation_id

    # -------------------- Space / conversations UX --------------------

    async def list_spaces_md(self) -> str:
        try:
            spaces = await self._fetch_spaces()
            if not spaces:
                return "_No spaces found._"
            lines = ["**Available Genie Spaces:**", ""]
            for s in spaces:
                sid = s["id"]
                title = s["title"]
                self._space_title_cache[sid] = title
                lines.append(f"- **{title}**  (`{sid}`)")
            return "\n".join(lines)
        except Exception as e:
            return f"⚠️ Couldn't list spaces: {type(e).__name__}"

    async def space_title(self, space_id: str) -> str:
        return await self._ensure_space_title(space_id)

    async def list_conversations_md(self, space_id: str) -> str:
        assert self._genie_api is not None

        def _list():
            resp = self._genie_api.list_conversations(space_id)
            items = getattr(resp, "conversations", None) or []
            out = []
            for c in items:
                cid = getattr(c, "conversation_id", None) or getattr(c, "id", None)
                title = getattr(c, "title", None) or "(no title)"
                created = getattr(c, "created_timestamp", None)
                out.append({"id": cid, "title": title, "created": created})
            return out

        try:
            convs = await asyncio.to_thread(_list)
            if not convs:
                return "_No conversations found in this space._"
            lines = [f"**Conversations in this space:**", ""]
            for c in convs:
                created_str = fmt_epoch_ms_to_local(c["created"])
                lines.append(f"- **{c['title']}**  (`{c['id']}`) • created: {created_str}")
            return "\n".join(lines)
        except Exception as e:
            return f"⚠️ Couldn't list conversations: {type(e).__name__}"

    async def list_messages_md(self, space_id: str, conversation_id: str, limit: int = 3) -> str:
        """Render messages as USER → ASSISTANT pairs."""
        assert self._genie_api is not None

        def _list_msgs():
            resp = self._genie_api.list_conversation_messages(space_id, conversation_id)
            items = getattr(resp, "messages", None) or []
            out = []
            for m in items:
                mid = getattr(m, "message_id", None) or getattr(m, "id", None)
                user_text = getattr(m, "content", None) or ""
                atts = getattr(m, "attachments", None) or []

                assistant_bits: List[Dict[str, Optional[str]]] = []
                for att in atts:
                    if getattr(att, "text", None) and getattr(att.text, "content", None):
                        assistant_bits.append({"desc": att.text.content.strip(), "sql": None})
                    elif getattr(att, "query", None):
                        q = att.query
                        desc = getattr(q, "description", "") or "Query"
                        sql_snip = getattr(q, "query", None)
                        assistant_bits.append({"desc": desc, "sql": sql_snip})
                out.append({
                    "id": mid,
                    "user": user_text,
                    "assistant_replies": assistant_bits
                })
            return out

        try:
            msgs = await asyncio.to_thread(_list_msgs)
            if not msgs:
                return "_No messages found in this conversation._"

            msgs = msgs[-limit:]
            lines = [f"**Last {len(msgs)} message(s):**"]
            for m in msgs:
                uid = m["id"]
                u = (m["user"] or "").strip()
                if len(u) > 1000:
                    u = u[:1000] + "…"
                lines.append(f"- **user** · `{uid}`:")
                lines.append(f"> {u if u else '(empty)'}")
                if m["assistant_replies"]:
                    lines.append(f"- **assistant**")
                    for idx, rep in enumerate(m["assistant_replies"], 1):
                        desc = (rep.get("desc") or "").strip()
                        sql = (rep.get("sql") or "").strip() or None
                        snippet = f"{desc} — SQL: ```{sql}```" if sql else desc
                        if len(snippet) > 1200:
                            snippet = snippet[:1200] + "…"
                        lines.append(f"  - reply {idx}:")
                        lines.append(f"> {snippet}")
            return "\n".join(lines)
        except Exception as e:
            return f"⚠️ Couldn't list messages: {type(e).__name__}"

# Singleton bot instance
BOT = GenieBot()

# ------------------------------------------------------------------------------

# Handlers

# ------------------------------------------------------------------------------

@AGENT_APP.conversation_update("membersAdded")
async def on_members_added(context: TurnContext, _state: TurnState):
    if _is_skill_invocation(context.activity):
        return  # avoid welcome messages in skill conversations
    msg = await BOT.welcome_text(context.activity.from_property.id)
    if not (DBX_ENABLED and BOT._genie_api and BOT._workspace_client):
        msg += "\n\n⚠️ Note: the data connection isn’t set up yet. Please contact your admin."
    await context.send_activity(msg)

@AGENT_APP.activity("message")
async def on_message(context: TurnContext, _state: TurnState):
    # Do not generate a free-form reply when acting as a Skill
    if _is_skill_invocation(context.activity):
        return
    text = (context.activity.text or "").strip()
    if not text:
        await context.send_activity("Send a message to get started. 🙂")
        return

    user_id = context.activity.from_property.id
    corr_id = getattr(context.activity, "id", "") or str(uuid.uuid4())
    conv_id_bf = getattr(getattr(context.activity, "conversation", None), "id", "") or ""

    text_hash = sha256_hex(" ".join(text.split()))
    log_event(logging.INFO, "msg_received", user_id=user_id, correlation_id=corr_id, conv_id=conv_id_bf, text_hash=text_hash)

    lower = text.lower()

    # Basic utility commands
    if lower == "version":
        await context.send_activity(f"Running on version {VERSION}")
        return

    if lower in ("help", "/help"):
        await context.send_activity(await BOT.help_text(user_id))
        return

    # ----- Space (singular) management FIRST -----
    if GenieBot.RE_SPACE.match(text):
        if re.search(r"\bshow\b", text, flags=re.I):
            sid = BOT.get_user_space_id(user_id)
            title = await BOT.space_title(sid)
            await context.send_activity(f"**Current Genie Space:** {title} (`{sid}`)")
            return
        m = re.search(r"\bset\b\s+(.+)$", text, flags=re.I)
        if m:
            wanted = m.group(1).strip()
            spaces = await BOT._fetch_spaces()
            chosen = None
            for s in spaces:
                if s["id"] == wanted:
                    chosen = s
                    break
            if not chosen:
                wl = wanted.lower()
                for s in spaces:
                    if (s["title"] or "").lower() == wl:
                        chosen = s
                        break
            if not chosen:
                await context.send_activity(f"Space `{wanted}` not found. Use `spaces list` to see options.")
                return
            BOT.set_user_space_id(user_id, chosen["id"])
            BOT._space_title_cache[chosen["id"]] = chosen["title"]
            await context.send_activity(f"✅ Switched to **{chosen['title']}** (`{chosen['id']}`). Conversation context cleared.")
            return
        await context.send_activity("Use `space show` or `space set <space-id or title>`.")
        return

    # Spaces (plural)
    if GenieBot.RE_SPACES.match(text):
        if re.search(r"\blist\b", text, flags=re.I):
            md = await BOT.list_spaces_md()
            await context.send_activity(md)
            return
        await context.send_activity("Try `spaces list`.")
        return

    # Conversations listing
    if GenieBot.RE_CONVERSATIONS.match(text):
        if re.search(r"\blist\b", text, flags=re.I):
            sid = BOT.get_user_space_id(user_id)
            md = await BOT.list_conversations_md(sid)
            await context.send_activity(md)
            return
        await context.send_activity("Try `conversations list`.")
        return

    # Messages listing for a conversation: supports optional limit (default 3)
    if GenieBot.RE_MESSAGES.match(text):
        m = re.search(r"messages?\s+([A-Za-z0-9\-\_]+)(?:\s+(\d+))?", text, flags=re.I)
        if not m:
            await context.send_activity("Usage: `messages <conversation-id> [N]`")
            return
        conv_id = m.group(1)
        try:
            limit = int(m.group(2)) if m.group(2) else 3
        except Exception:
            limit = 3
        limit = max(1, min(limit, 20))
        sid = BOT.get_user_space_id(user_id)
        md = await BOT.list_messages_md(sid, conv_id, limit=limit)
        await context.send_activity(md)
        return

    # Settings / config
    if GenieBot.RE_CONFIG_CMD.match(text) or BOT.parse_config_overrides(text):
        if re.search(r"\bdefaults\b", text, flags=re.I):
            BOT._user_settings[user_id] = UserSettings()
            sid = BOT.get_user_space_id(user_id)
            title = await BOT.space_title(sid)
            await context.send_activity("✅ Defaults restored.")
            await context.send_activity(BOT.get_settings(user_id).pretty(title, sid))
            return
        if re.search(r"\bshow\b", text, flags=re.I):
            sid = BOT.get_user_space_id(user_id)
            title = await BOT.space_title(sid)
            await context.send_activity(BOT.get_settings(user_id).pretty(title, sid))
            return

        overrides = BOT.parse_config_overrides(text) or {}
        if overrides:
            s = BOT.apply_overrides(user_id, overrides)
            sid = BOT.get_user_space_id(user_id)
            title = await BOT.space_title(sid)
            await context.send_activity("✅ Settings updated.")
            await context.send_activity(s.pretty(title, sid))
        else:
            sid = BOT.get_user_space_id(user_id)
            title = await BOT.space_title(sid)
            await context.send_activity(BOT.get_settings(user_id).pretty(title, sid))
            await context.send_activity(
                "To adjust: `config rows=100 cols=20 timeout=90 query_timeout=180 sql=on` • "
                "Fields: rows, cols/columns, chars, cell/cell_chars, timeout, query_timeout (qt), sql/sql_notes"
            )
        return

    # Reset conversation
    if GenieBot.RE_RESET.match(text):
        BOT.reset_conversation(user_id)
        await context.send_activity("🔄 New conversation started. Send your next question.")
        return

    # Health
    if not (DBX_ENABLED and BOT._genie_api and BOT._workspace_client):
        await context.send_activity(BOT.health_summary())
        return

    # Rate limit
    remaining = BOT.check_rate_limit(user_id)
    if remaining is not None:
        await context.send_activity(f"⏱️ You're sending too fast. Try again in ~{remaining}s.")
        return

    # Dedup
    cached_md = BOT.check_dedup(user_id, text)
    if cached_md:
        await BOT.send_markdown(
            context,
            f"↩️ Reusing previous response (duplicate message within {int(DEDUP_WINDOW_SECONDS)}s):\n\n{cached_md}",
            max_chars=BOT.get_settings(user_id).chars
        )
        return

    # Call Genie
    async with BOT.get_lock(user_id):
        BOT.note_rate(user_id)
        question = text
        settings = BOT.get_settings(user_id)
        space_id = BOT.get_user_space_id(user_id)

        start_ts = time.time()
        try:
            answer_json_str, new_conv = await BOT.ask_genie(
                question,
                space_id,
                BOT.get_conversation_id(user_id),
                timeout_text=settings.timeout,
                timeout_query=settings.query_timeout
            )
            if new_conv:
                BOT.set_conversation_id(user_id, new_conv)

            try:
                parsed = json.loads(answer_json_str)
            except Exception:
                parsed = {"message": answer_json_str}

            md = BOT.format_genie_answer_md(
                parsed,
                rows_limit=settings.rows,
                cols_limit=settings.cols,
                cell_limit=settings.cell_chars,
                show_sql=settings.sql_notes,
            )

            BOT.store_dedup(user_id, text, md)
            await BOT.send_markdown(context, md, max_chars=settings.chars)

            dur_ms = int((time.time() - start_ts) * 1000)
            log_event(logging.INFO, "genie_ok", user_id=user_id, correlation_id=corr_id, conv_id=new_conv, duration_ms=dur_ms, space_id=space_id)
        except Exception as e:
            error_id = str(uuid.uuid4())[:8]
            dur_ms = int((time.time() - start_ts) * 1000)
            log_event(
                logging.ERROR,
                "genie_error",
                user_id=user_id,
                correlation_id=corr_id,
                error_class=type(e).__name__,
                error_message=str(e),
                duration_ms=dur_ms,
                error_id=error_id,
            )
            hint = (
                "- Try fewer columns/rows: `config cols=10 rows=50`\n"
                "- Increase timeouts: `config timeout=120 query_timeout=300`\n"
                "- Ask a more specific question"
            )
            await context.send_activity(
                f"⚠️ Sorry, I couldn't process that (error `{error_id}`).\n{hint}"
            )



@AGENT_APP.activity("event")
async def on_event(context: TurnContext, _state: TurnState):
    if (getattr(context.activity, "name", "") or "").lower() != "runprompt":
        return

    trace_id = str(uuid.uuid4())
    started_ns = time.monotonic_ns()

    def _elapsed_ms() -> float:
        return (time.monotonic_ns() - started_ns) / 1_000_000

    # ✅ Always include all fields required by Copilot Studio output binding
    def _end_of_conversation(value: Dict[str, Any], code: EndOfConversationCodes) -> Activity:
        """
        Builds an EndOfConversation activity with a payload that ALWAYS includes:
          response, traceId, elapsedMs, status, error
        Copilot Studio will fail the action if any bound property is missing.
        """
        result = {
            "response": value.get("response", "") or "",
            "traceId": trace_id,
            # send integer milliseconds (safer for some clients)
            "elapsedMs": int(_elapsed_ms()),
            # make sure status is always present
            "status": value.get("status", "ok"),
            # 🔴 KEY FIX: always include 'error' (empty on success)
            "error": value.get("error") or ""
        }
        return Activity(
            # keep EndOfConversation (Python flavor is snake_case in the Agents SDK)
            type=ActivityTypes.end_of_conversation,
            value=result,
            code=code,
        )

    payload: Dict[str, Any] = getattr(context.activity, "value", {}) or {}
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        # ⬇️ this call stays the same; 'error' now is guaranteed by _end_of_conversation()
        await context.send_activity(_end_of_conversation(
            {"response": "", "status": "error", "error": "No prompt provided."},
            code=EndOfConversationCodes.unknown
        ))
        return

    prompt = prompt.strip()
    user_id = context.activity.from_property.id
    space_id = BOT.get_user_space_id(user_id)
    text_timeout = CALL_TIMEOUT_SECONDS_DEFAULT
    query_timeout = CALL_TIMEOUT_SECONDS_DEFAULT

    try:
        reply_json, _ = await BOT.ask_genie(
            prompt, space_id,
            conversation_id=None,
            timeout_text=text_timeout,
            timeout_query=query_timeout
        )
        # ⬇️ success path; 'error' will be "" because _end_of_conversation sets it.
        await context.send_activity(_end_of_conversation(
            {"response": reply_json or "", "status": "ok"},
            code=EndOfConversationCodes.completed_successfully
        ))
    except Exception as ex:
        err_msg = f"{type(ex).__name__}: {ex}"
        log_event(logging.ERROR, "runprompt_error", user_id=user_id, space_id=space_id, traceId=trace_id, error=err_msg)
        # ⬇️ error path; we pass the message and status=error (and _end_of_conversation includes empty-safe fields)
        await context.send_activity(_end_of_conversation(
            {"response": "", "status": "error", "error": err_msg},
            code=EndOfConversationCodes.unknown
        ))
