import asyncio
import json
import os
import re
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
env_file = BASE_DIR / ".env"
if env_file.exists():
    load_dotenv(env_file)
else:
    load_dotenv(BASE_DIR / ".env.example")


def _env_path(name: str, default_rel: str) -> Path:
    return (BASE_DIR / os.getenv(name, default_rel)).resolve()


LIZZIE_EXE = _env_path("LIZZIE_EXE", "../Lizzieyzy-2.5.3-win64.exe")
LIZZIE_CONFIG = _env_path("LIZZIE_CONFIG", "../config.txt")
LIZZIE_WORKDIR = _env_path("LIZZIE_WORKDIR", "..")
SAVE_DIR = _env_path("LIZZIE_SAVE_DIR", "../save")

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4.1-mini")

POSITION_KATAGO_PATH = _env_path("POSITION_KATAGO_PATH", "../katago_eigen/katago.exe")
POSITION_MODEL_PATH = _env_path("POSITION_MODEL_PATH", "../weights/kata15bs167.bin.gz")
POSITION_CONFIG_PATH = _env_path("POSITION_CONFIG_PATH", "../katago_configs/analysis.cfg")
POSITION_RULES = os.getenv("POSITION_RULES", "chinese")
POSITION_MAX_VISITS = int(os.getenv("POSITION_MAX_VISITS", "120"))
POSITION_MAX_TIME = float(os.getenv("POSITION_MAX_TIME", "1.5"))

lizzie_proc: subprocess.Popen | None = None
state_lock = asyncio.Lock()
position_cache_lock = threading.Lock()
position_cache: dict[str, Any] = {"timestamp": 0.0, "sgf_file": "", "sgf_mtime": 0.0, "data": {}}
trend_lock = threading.Lock()
trend_history: list[dict[str, Any]] = []
coach_state_lock = threading.Lock()
coach_state: dict[str, Any] = {
    "last_move_count": -1,
    "last_main_move": "",
    "stability_count": 0,
    "last_advice_ts": 0.0,
}


GTP_COLUMNS = "ABCDEFGHJKLMNOPQRST"


def xy_to_gtp(x: int, y: int, size: int = 19) -> str:
    return f"{GTP_COLUMNS[x]}{size - y}"


def gtp_to_xy(gtp: str, size: int = 19) -> tuple[int, int] | None:
    text = (gtp or "").strip().upper()
    if text in {"PASS", "RESIGN", ""}:
        return None
    if len(text) < 2:
        return None
    col = text[0]
    if col not in GTP_COLUMNS:
        return None
    try:
        row = int(text[1:])
    except ValueError:
        return None
    x = GTP_COLUMNS.index(col)
    y = size - row
    if x < 0 or y < 0 or x >= size or y >= size:
        return None
    return x, y


def user_point_to_xy(point: str, size: int = 19) -> tuple[int, int] | None:
    text = (point or "").strip().upper()
    if len(text) < 2:
        return None
    col = text[0]
    try:
        row = int(text[1:])
    except ValueError:
        return None
    if row < 1 or row > size:
        return None

    # Strict user coordinate style: same as GTP, skip I (A-H, J-T).
    if col not in GTP_COLUMNS:
        return None
    x = GTP_COLUMNS.index(col)
    if x < 0 or x >= size:
        return None
    y = size - row
    return x, y


def sgf_to_xy(sgf_coord: str, size: int = 19) -> tuple[int, int] | None:
    if len(sgf_coord) != 2:
        return None
    x = ord(sgf_coord[0]) - ord("a")
    y = ord(sgf_coord[1]) - ord("a")
    if x < 0 or y < 0 or x >= size or y >= size:
        return None
    return x, y


def parse_moves_from_sgf(sgf_text: str) -> list[dict[str, Any]]:
    import re

    moves: list[dict[str, Any]] = []
    for m in re.finditer(r";\s*([BW])\[([a-s]{2})\]", sgf_text, re.IGNORECASE):
        color = m.group(1).upper()
        xy = sgf_to_xy(m.group(2).lower())
        if not xy:
            continue
        moves.append({"color": color, "x": xy[0], "y": xy[1]})
    return moves


def extract_point_from_text(text: str) -> str | None:
    import re

    m = re.search(r"\b([A-HJ-Ta-hj-t](?:1[0-9]|[1-9]))\b", text)
    if not m:
        return None
    return m.group(1).upper()


def game_phase(move_count: int) -> str:
    if move_count < 40:
        return "布局"
    if move_count < 180:
        return "中盘"
    return "官子"


def compute_complexity(move_infos: list[dict[str, Any]]) -> dict[str, float]:
    if not move_infos:
        return {"complexity": 0.0, "visit_focus": 1.0, "wr_spread": 0.0, "total_visits": 0.0}
    top = move_infos[:6]
    visits = [float(m.get("visits", 0) or 0) for m in top]
    total_visits = sum(visits)
    focus = (visits[0] / total_visits) if total_visits > 0 else 1.0

    wrs = [float(m.get("winrate", 0.0) or 0.0) for m in top if m.get("winrate") is not None]
    wr_spread = (max(wrs) - min(wrs)) if len(wrs) >= 2 else 0.0

    # Higher spread and lower focus both indicate tactical/strategic uncertainty.
    complexity = max(0.0, min(1.0, wr_spread * 4.0 + (1.0 - focus) * 0.8))
    return {
        "complexity": complexity,
        "visit_focus": focus,
        "wr_spread": wr_spread,
        "total_visits": total_visits,
    }


def parse_illegal_move_error(err_text: str) -> dict[str, Any] | None:
    txt = (err_text or "").strip()
    # Common forms: "illegal move 227: B10" or localized variants.
    m = re.search(r"illegal\s*move\s*(\d+)\s*[:：]\s*([A-HJ-Ta-hj-t][0-9]{1,2})", txt, re.IGNORECASE)
    if not m:
        m = re.search(r"(\d+)\s*[:：]\s*([A-HJ-Ta-hj-t][0-9]{1,2})", txt)
    if not m:
        return None
    idx = int(m.group(1))
    point = m.group(2).upper()
    return {"index_1based": idx, "point": point}


def build_analysis_snapshot(analysis: dict[str, Any], komi: float, phase: str) -> dict[str, Any]:
    root = analysis.get("rootInfo", {})
    move_infos = analysis.get("moveInfos", [])
    infos = move_infos[:5]
    metrics = compute_complexity(move_infos)
    recs: list[dict[str, Any]] = []
    for item in infos:
        recs.append(
            {
                "move": item.get("move", "PASS"),
                "winrate": item.get("winrate"),
                "scoreLead": item.get("scoreLead"),
                "visits": item.get("visits"),
                "pv": item.get("pv", [])[:6],
                "xy": gtp_to_xy(item.get("move", "PASS"), 19),
            }
        )
    return {
        "phase": phase,
        "komi": komi,
        "winrate": root.get("winrate"),
        "scoreLead": root.get("scoreLead"),
        "recommendations": recs,
        "main_pv": recs[0].get("pv", []) if recs else [],
        "total_visits": metrics["total_visits"],
        "visit_focus": metrics["visit_focus"],
        "wr_spread": metrics["wr_spread"],
        "complexity": metrics["complexity"],
        "analysis_ok": True,
    }


def update_trend_history(snapshot: dict[str, Any]) -> None:
    if not snapshot.get("analysis_ok"):
        return
    entry = {
        "ts": time.time(),
        "move_count": int(snapshot.get("move_count", 0)),
        "winrate": float(snapshot.get("winrate", 0.0) or 0.0),
        "scoreLead": float(snapshot.get("scoreLead", 0.0) or 0.0),
        "complexity": float(snapshot.get("complexity", 0.0) or 0.0),
        "total_visits": float(snapshot.get("total_visits", 0.0) or 0.0),
    }
    with trend_lock:
        # If same move count is re-analyzed, replace latest point to keep time series stable.
        if trend_history and int(trend_history[-1].get("move_count", -1)) == entry["move_count"]:
            trend_history[-1] = entry
        else:
            trend_history.append(entry)
            if len(trend_history) > 240:
                del trend_history[0 : len(trend_history) - 240]


def build_trend_signals() -> dict[str, Any]:
    with trend_lock:
        hist = list(trend_history)
    if len(hist) < 2:
        return {
            "samples": len(hist),
            "wr_delta_last": 0.0,
            "wr_volatility": 0.0,
            "complexity_avg": hist[-1]["complexity"] if hist else 0.0,
            "high_volatility": False,
            "volatility_streak": 0,
            "admit_uncertainty": False,
            "admit_misjudge": False,
        }

    recent = hist[-8:]
    deltas = [recent[i]["winrate"] - recent[i - 1]["winrate"] for i in range(1, len(recent))]
    abs_deltas = [abs(d) for d in deltas]
    wr_delta_last = deltas[-1] if deltas else 0.0
    wr_volatility = (sum(abs_deltas) / len(abs_deltas)) if abs_deltas else 0.0
    complexity_avg = sum(float(p.get("complexity", 0.0)) for p in recent) / len(recent)
    # Count how many recent step-to-step swings are "large" (>= 6% absolute).
    volatility_streak = 0
    for d in reversed(abs_deltas):
        if d >= 0.06:
            volatility_streak += 1
        else:
            break

    high_volatility = wr_volatility >= 0.04
    # "看不清" should be tied to continuous large winrate fluctuations, not complexity alone.
    admit_uncertainty = high_volatility and volatility_streak >= 2
    # Large unexpected swing against recent mean: ask model to acknowledge prior misread.
    recent_mean = sum(p["winrate"] for p in recent[:-1]) / max(1, len(recent) - 1)
    admit_misjudge = abs(recent[-1]["winrate"] - recent_mean) >= 0.10

    return {
        "samples": len(hist),
        "wr_delta_last": wr_delta_last,
        "wr_volatility": wr_volatility,
        "complexity_avg": complexity_avg,
        "high_volatility": high_volatility,
        "volatility_streak": volatility_streak,
        "admit_uncertainty": admit_uncertainty,
        "admit_misjudge": admit_misjudge,
        "trend_tail": recent,
    }


def update_coach_state(snapshot: dict[str, Any]) -> None:
    if not snapshot.get("analysis_ok"):
        return
    main_move = ""
    recs = snapshot.get("recommendations", [])
    if recs and isinstance(recs[0], dict):
        main_move = str(recs[0].get("move", "") or "")
    move_count = int(snapshot.get("move_count", 0))
    now = time.time()
    with coach_state_lock:
        if coach_state.get("last_move_count") == move_count and coach_state.get("last_main_move") == main_move:
            coach_state["stability_count"] = int(coach_state.get("stability_count", 0)) + 1
        else:
            coach_state["stability_count"] = 1
        coach_state["last_move_count"] = move_count
        coach_state["last_main_move"] = main_move
        coach_state["last_advice_ts"] = now


def read_coach_state() -> dict[str, Any]:
    with coach_state_lock:
        return dict(coach_state)


def load_current_game_state() -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    latest = find_latest_sgf()
    if latest is None:
        raise RuntimeError("未找到可用棋谱，无法试下")
    sgf_text = latest.read_text(encoding="utf-8", errors="replace")
    moves = parse_moves_from_sgf(sgf_text)
    to_play = "B" if len(moves) % 2 == 0 else "W"
    snapshot = get_realtime_position(force=True)
    return moves, to_play, snapshot


def evaluate_try_move(point: str | None = None) -> dict[str, Any]:
    candidate = (point or "").strip().upper()
    if candidate.startswith("I"):
        raise RuntimeError("坐标列跳过 I，请改用 J 列及之后（例如 J10）。")

    moves, to_play, snapshot = load_current_game_state()
    if not snapshot.get("analysis_ok"):
        raise RuntimeError("当前局势分析不可用，无法试下")

    auto_selected = False
    if not candidate:
        recs = snapshot.get("recommendations", [])
        if recs and isinstance(recs[0], dict):
            candidate = str(recs[0].get("move", "") or "").upper()
            auto_selected = True
    if candidate in {"", "PASS", "RESIGN"}:
        raise RuntimeError("未找到可试下的点位")

    xy = user_point_to_xy(candidate, 19)
    if not xy:
        xy = gtp_to_xy(candidate, 19)
    if not xy:
        raise RuntimeError(f"点位格式无效: {candidate}")

    candidate_gtp = xy_to_gtp(xy[0], xy[1], 19)

    occupied = {(int(m["x"]), int(m["y"])) for m in moves}
    if (xy[0], xy[1]) in occupied:
        raise RuntimeError(f"点位 {candidate_gtp} 已有棋子")

    trial_moves = list(moves)
    trial_moves.append({"color": to_play, "x": xy[0], "y": xy[1]})
    next_to_play = "W" if to_play == "B" else "B"

    try:
        cfg = load_config()
        komi = float(cfg.get("ui", {}).get("new-game-komi", 7.5))
    except Exception:
        komi = 7.5

    after = position_analyzer.analyze(trial_moves, next_to_play, komi=komi)
    root_after = after.get("rootInfo", {})
    after_infos = after.get("moveInfos", [])[:3]
    after_recs = [
        {
            "move": item.get("move", "PASS"),
            "winrate": item.get("winrate"),
            "scoreLead": item.get("scoreLead"),
            "visits": item.get("visits"),
            "pv": item.get("pv", [])[:6],
        }
        for item in after_infos
    ]

    curr_wr = snapshot.get("winrate")
    curr_sl = snapshot.get("scoreLead")
    after_wr_opp = root_after.get("winrate")
    after_sl_opp = root_after.get("scoreLead")

    after_wr_for_player = None
    if isinstance(after_wr_opp, (int, float)):
        after_wr_for_player = 1.0 - float(after_wr_opp)

    after_sl_for_player = None
    if isinstance(after_sl_opp, (int, float)):
        after_sl_for_player = -float(after_sl_opp)

    wr_delta = None
    if isinstance(curr_wr, (int, float)) and isinstance(after_wr_for_player, (int, float)):
        wr_delta = float(after_wr_for_player) - float(curr_wr)

    sl_delta = None
    if isinstance(curr_sl, (int, float)) and isinstance(after_sl_for_player, (int, float)):
        sl_delta = float(after_sl_for_player) - float(curr_sl)

    verdict = "中性"
    if isinstance(wr_delta, (int, float)):
        if wr_delta >= 0.03:
            verdict = "较优"
        elif wr_delta <= -0.03:
            verdict = "偏亏"

    return {
        "point": candidate_gtp,
        "point_gtp": candidate_gtp,
        "auto_selected": auto_selected,
        "player_to_move": to_play,
        "current_winrate": curr_wr,
        "current_scoreLead": curr_sl,
        "after_winrate_for_player": after_wr_for_player,
        "after_scoreLead_for_player": after_sl_for_player,
        "winrate_delta": wr_delta,
        "score_delta": sl_delta,
        "verdict": verdict,
        "after_recommendations": after_recs,
    }


def find_latest_sgf() -> Path | None:
    if not SAVE_DIR.exists():
        return None
    sgfs = list(SAVE_DIR.glob("*.sgf"))
    if not sgfs:
        return None
    return max(sgfs, key=lambda p: p.stat().st_mtime)


class PositionAnalyzer:
    def __init__(self) -> None:
        self.proc: subprocess.Popen[str] | None = None
        self.lock = threading.Lock()
        self.stderr_lines: list[str] = []
        self.stderr_lock = threading.Lock()

    def _stderr_worker(self) -> None:
        assert self.proc is not None and self.proc.stderr is not None
        for line in self.proc.stderr:
            clean = line.rstrip("\n")
            with self.stderr_lock:
                self.stderr_lines.append(clean)
                if len(self.stderr_lines) > 120:
                    self.stderr_lines.pop(0)

    def start(self) -> None:
        if self.proc and self.proc.poll() is None:
            return
        if not POSITION_KATAGO_PATH.exists() or not POSITION_MODEL_PATH.exists() or not POSITION_CONFIG_PATH.exists():
            raise RuntimeError("position analyzer resources missing")
        self.proc = subprocess.Popen(
            [
                str(POSITION_KATAGO_PATH),
                "analysis",
                "-config",
                str(POSITION_CONFIG_PATH),
                "-model",
                str(POSITION_MODEL_PATH),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        t = threading.Thread(target=self._stderr_worker, daemon=True)
        t.start()

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None

    def analyze(self, moves: list[dict[str, Any]], to_play: str, komi: float = 7.5) -> dict[str, Any]:
        with self.lock:
            if self.proc is None or self.proc.poll() is not None:
                self.start()
            assert self.proc is not None and self.proc.stdin is not None and self.proc.stdout is not None

            req_id = str(uuid.uuid4())
            req = {
                "id": req_id,
                "rules": POSITION_RULES,
                "komi": komi,
                "boardXSize": 19,
                "boardYSize": 19,
                "moves": [[m["color"], xy_to_gtp(int(m["x"]), int(m["y"]), 19)] for m in moves],
                "initialPlayer": "B",
                "analyzeTurns": [len(moves)],
                "maxVisits": POSITION_MAX_VISITS,
                "maxTime": POSITION_MAX_TIME,
                "includeOwnership": False,
                "includePVVisits": True,
                "reportDuringSearchEvery": 0.05,
            }
            self.proc.stdin.write(json.dumps(req, ensure_ascii=True) + "\n")
            self.proc.stdin.flush()

            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                line = self.proc.stdout.readline()
                if not line:
                    break
                text = line.strip()
                if not text:
                    continue
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if data.get("id") != req_id:
                    continue
                if data.get("error"):
                    raise RuntimeError(str(data.get("error")))
                if data.get("isDuringSearch"):
                    continue
                return data

            with self.stderr_lock:
                stderr_tail = "\n".join(self.stderr_lines[-20:])
            raise RuntimeError("position analyzer timeout" + (f": {stderr_tail}" if stderr_tail else ""))


position_analyzer = PositionAnalyzer()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1200)


class CommandResult(BaseModel):
    ok: bool
    message: str
    action: str
    data: dict[str, Any] = Field(default_factory=dict)


class WSManager:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.clients.discard(ws)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for c in self.clients:
            try:
                await c.send_json(payload)
            except Exception:
                dead.append(c)
        for c in dead:
            self.clients.discard(c)


ws_manager = WSManager()
app = FastAPI(title="Lizziezy LLM Control")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "frontend")), name="static")


def load_config() -> dict[str, Any]:
    if not LIZZIE_CONFIG.exists():
        raise RuntimeError(f"config not found: {LIZZIE_CONFIG}")
    text = LIZZIE_CONFIG.read_text(encoding="utf-8", errors="replace")
    return json.loads(text)


def save_config(cfg: dict[str, Any]) -> None:
    LIZZIE_CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def is_running() -> bool:
    return lizzie_proc is not None and lizzie_proc.poll() is None


def launch_lizzie() -> str:
    global lizzie_proc
    if is_running():
        return "Lizziezy 已在运行。"
    if not LIZZIE_EXE.exists():
        raise RuntimeError(f"未找到 Lizziezy 可执行文件: {LIZZIE_EXE}")

    lizzie_proc = subprocess.Popen([str(LIZZIE_EXE)], cwd=str(LIZZIE_WORKDIR))
    return "Lizziezy 启动成功。"


def stop_lizzie() -> str:
    global lizzie_proc
    if not is_running():
        return "Lizziezy 当前未运行。"
    assert lizzie_proc is not None
    lizzie_proc.terminate()
    try:
        lizzie_proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        lizzie_proc.kill()
    lizzie_proc = None
    return "Lizziezy 已停止。"


def _set_cfg_path(cfg: dict[str, Any], path: str, value: Any) -> None:
    parts = [p for p in path.split(".") if p]
    cur: Any = cfg
    for p in parts[:-1]:
        if not isinstance(cur, dict) or p not in cur:
            raise RuntimeError(f"配置项不存在: {path}")
        cur = cur[p]
    if not isinstance(cur, dict) or parts[-1] not in cur:
        raise RuntimeError(f"配置项不存在: {path}")
    cur[parts[-1]] = value


def _to_bool(text: str) -> bool:
    t = text.lower()
    return t in {"1", "true", "yes", "on", "开", "开启", "是"}


def read_status_data() -> dict[str, Any]:
    try:
        cfg = load_config()
        ui = cfg.get("ui", {})
        leelaz = cfg.get("leelaz", {})
        return {
            "running": is_running(),
            "default_engine": ui.get("default-engine"),
            "analysis_visits": ui.get("analysis-max-visits"),
            "move_time": leelaz.get("max-game-thinking-time-seconds"),
            "play_ponder": leelaz.get("play-ponder"),
        }
    except Exception:
        return {"running": is_running()}


def get_realtime_position(force: bool = False) -> dict[str, Any]:
    now = time.time()
    latest = find_latest_sgf()
    if latest is None:
        return {"available": False, "reason": "未找到棋谱文件"}

    mtime = latest.stat().st_mtime
    with position_cache_lock:
        if (
            not force
            and position_cache.get("sgf_file") == str(latest)
            and float(position_cache.get("sgf_mtime", 0.0)) == mtime
            and now - float(position_cache.get("timestamp", 0.0)) < 2.0
        ):
            return dict(position_cache.get("data", {}))

    sgf_text = latest.read_text(encoding="utf-8", errors="replace")
    moves = parse_moves_from_sgf(sgf_text)
    to_play = "B" if len(moves) % 2 == 0 else "W"

    phase = game_phase(len(moves))
    base: dict[str, Any] = {
        "available": True,
        "sgf_file": str(latest),
        "move_count": len(moves),
        "to_play": to_play,
        "phase": phase,
    }

    try:
        cfg = load_config()
        komi = float(cfg.get("ui", {}).get("new-game-komi", 7.5))
    except Exception:
        komi = 7.5

    try:
        analysis = position_analyzer.analyze(moves, to_play, komi=komi)
        base.update(build_analysis_snapshot(analysis, komi, phase))
        base["recovered_from_illegal"] = False
        update_trend_history(base)
        base["trend"] = build_trend_signals()
        update_coach_state(base)
        base["coach_state"] = read_coach_state()
    except Exception as exc:
        err_text = str(exc)
        illegal = parse_illegal_move_error(err_text)
        recovered = False
        if illegal:
            idx = int(illegal.get("index_1based", 0))
            cutoff = max(0, min(len(moves), idx - 1))
            legal_moves = moves[:cutoff]
            legal_to_play = "B" if len(legal_moves) % 2 == 0 else "W"
            try:
                recovered_analysis = position_analyzer.analyze(legal_moves, legal_to_play, komi=komi)
                legal_phase = game_phase(len(legal_moves))
                base.update(build_analysis_snapshot(recovered_analysis, komi, legal_phase))
                base["recovered_from_illegal"] = True
                base["illegal_move"] = {
                    "index_1based": idx,
                    "point": illegal.get("point"),
                    "original_move_count": len(moves),
                    "effective_move_count": len(legal_moves),
                }
                base["analysis_warning"] = f"检测到非法着法 {idx}:{illegal.get('point')}，已回退到最后合法局面分析。"
                recovered = True
                update_trend_history(base)
            except Exception as sub_exc:
                err_text = f"{err_text} | recovery failed: {sub_exc}"

        if not recovered:
            base.update(
                {
                    "analysis_ok": False,
                    "analysis_error": err_text,
                    "recommendations": [],
                }
            )
        base["trend"] = build_trend_signals()
        base["coach_state"] = read_coach_state()

    with position_cache_lock:
        position_cache["timestamp"] = now
        position_cache["sgf_file"] = str(latest)
        position_cache["sgf_mtime"] = mtime
        position_cache["data"] = dict(base)
    return base


def generate_chat_reply(user_text: str) -> str:
    q = (user_text or "").strip()
    ql = q.lower()
    status = read_status_data()
    position = get_realtime_position(force=False)
    cstate = read_coach_state()

    if position.get("recovered_from_illegal"):
        warn = str(position.get("analysis_warning", "检测到棋谱问题，已回退分析。"))
        if not LLM_API_KEY:
            return warn + " 当前结论基于最后合法局面。"

    if not LLM_API_KEY:
        if any(k in ql for k in ["你好", "hello", "hi", "嗨"]):
            if position.get("available") and position.get("analysis_ok"):
                wr = position.get("winrate")
                sl = position.get("scoreLead")
                msg = "你好，我在线。"
                if isinstance(wr, (int, float)):
                    msg += f" 当前胜率约 {float(wr)*100:.1f}%"
                if isinstance(sl, (int, float)):
                    msg += f"，目差约 {float(sl):.1f}。"
                return msg + " 你可以让我继续讲解这盘棋。"
            return "你好，我在线。你可以让我做两类事：1) 直接聊天；2) 控制 Lizziezy（如：启动、难度困难、每手4秒）。"
        if "我的" in q or "我" == q.strip():
            return "我在。你可以继续说完整需求，比如：把难度调到困难并把每手设为4秒。"
        return "我可以一边聊天一边帮你控制 Lizziezy。你可以直接说你的目标，我会自动判断是对话还是执行操作。"

    system = (
        "你是 Lizziezy 的实时陪练助手，必须具备全局观。"
        "你会持续参考：胜率趋势、波动、复杂度、主变化图(PV)、计算量(visits)，不只看单点。"
        "当 admit_uncertainty 为 true（来自连续较大胜率波动）时，明确承认看不清并给稳健计划。"
        "当 admit_misjudge 为 true 时，明确承认之前判断偏差并给修正思路。"
        "若波动信号不大且局面手数未变，不要频繁推翻上一判断，保持建议一致性。"
        "回复中文，3-6句，避免机械模板。"
    )
    prompt = json.dumps({"user": q, "status": status, "position": position, "coach_state": cstate}, ensure_ascii=False)
    body = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.6,
    }
    try:
        resp = requests.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
            json=body,
            timeout=18,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"].strip()
        return text or "我在，继续说你的想法。"
    except Exception:
        return "我在。你可以直接说要做什么，我会边聊边执行。"


def apply_action(action: str, args: dict[str, Any]) -> CommandResult:
    if action == "launch":
        return CommandResult(ok=True, message=launch_lizzie(), action=action)
    if action == "stop":
        return CommandResult(ok=True, message=stop_lizzie(), action=action)
    if action == "restart":
        stop_lizzie()
        return CommandResult(ok=True, message=launch_lizzie(), action=action)

    if action == "chat":
        reply = generate_chat_reply(str(args.get("text", "")))
        return CommandResult(ok=True, message=reply, action=action, data=read_status_data())

    if action == "try_move":
        result = evaluate_try_move(str(args.get("point", "")).strip().upper() if args.get("point") else None)
        p = result.get("point", "")
        verdict = result.get("verdict", "中性")
        wrd = result.get("winrate_delta")
        sld = result.get("score_delta")
        wr_txt = f"{float(wrd)*100:+.1f}%" if isinstance(wrd, (int, float)) else "-"
        sl_txt = f"{float(sld):+.2f}" if isinstance(sld, (int, float)) else "-"
        msg = f"试下 {p} 评估：{verdict}（胜率变化 {wr_txt}，目差变化 {sl_txt}）。"
        return CommandResult(ok=True, message=msg, action=action, data=result)

    cfg = load_config()

    if action == "set_default_engine":
        idx = int(args.get("index", 0))
        cfg.setdefault("ui", {})["default-engine"] = idx
        save_config(cfg)
        return CommandResult(ok=True, message=f"默认引擎已切到 {idx}。", action=action, data={"index": idx})

    if action == "set_difficulty":
        level = str(args.get("level", "normal"))
        visits_map = {"beginner": 80, "easy": 200, "normal": 800, "hard": 2500, "pro": 6000}
        think_map = {"beginner": 0.6, "easy": 1.2, "normal": 2.5, "hard": 5.0, "pro": 9.0}
        visits = visits_map.get(level, 800)
        think = think_map.get(level, 2.5)
        cfg.setdefault("ui", {})["analysis-max-visits"] = visits
        cfg.setdefault("leelaz", {})["max-game-thinking-time-seconds"] = think
        save_config(cfg)
        return CommandResult(
            ok=True,
            message=f"难度已设为 {level}（visits={visits}, 每手用时={think}s）。",
            action=action,
            data={"level": level, "visits": visits, "think": think},
        )

    if action == "set_move_time":
        sec = float(args.get("seconds", 2.0))
        sec = max(0.2, min(60.0, sec))
        cfg.setdefault("leelaz", {})["max-game-thinking-time-seconds"] = sec
        save_config(cfg)
        return CommandResult(ok=True, message=f"每手用时已设为 {sec:.1f} 秒。", action=action, data={"seconds": sec})

    if action == "set_visits":
        visits = int(args.get("visits", 800))
        visits = max(1, min(200000, visits))
        cfg.setdefault("ui", {})["analysis-max-visits"] = visits
        save_config(cfg)
        return CommandResult(ok=True, message=f"分析 visits 已设为 {visits}。", action=action, data={"visits": visits})

    if action == "set_option":
        key = str(args.get("path", ""))
        value = args.get("value")
        _set_cfg_path(cfg, key, value)
        save_config(cfg)
        return CommandResult(ok=True, message=f"已更新配置 {key}。", action=action, data={"path": key, "value": value})

    if action == "status":
        return CommandResult(
            ok=True,
            message="已读取当前状态。",
            action=action,
            data=read_status_data(),
        )

    raise RuntimeError(f"不支持的 action: {action}")


def fallback_parse(text: str) -> tuple[str, dict[str, Any], str]:
    q = text.strip()
    ql = q.lower()

    if "启动" in q or "打开" in q or "launch" in ql or "start lizzie" in ql:
        return "launch", {}, "正在启动 Lizziezy。"
    if "停止" in q or "关闭" in q or "stop" in ql or "close lizzie" in ql:
        return "stop", {}, "正在停止 Lizziezy。"
    if "重启" in q or "restart" in ql:
        return "restart", {}, "正在重启 Lizziezy。"
    if "状态" in q or "status" in ql:
        return "status", {}, "正在读取状态。"

    if "难度" in q or "difficulty" in ql or "level" in ql:
        if "入门" in q:
            return "set_difficulty", {"level": "beginner"}, "已切到入门难度。"
        if "简单" in q or "easy" in ql:
            return "set_difficulty", {"level": "easy"}, "已切到简单难度。"
        if "困难" in q or "hard" in ql:
            return "set_difficulty", {"level": "hard"}, "已切到困难难度。"
        if "大师" in q or "专家" in q or "pro" in ql or "expert" in ql:
            return "set_difficulty", {"level": "pro"}, "已切到大师难度。"
        return "set_difficulty", {"level": "normal"}, "已切到普通难度。"

    import re

    p = extract_point_from_text(q)
    if ("试" in q or "尝试" in q or "评估" in q or "test move" in ql or "try move" in ql) and p:
        return "try_move", {"point": p}, f"正在试下 {p} 并评估。"
    if "试下" in q or "尝试落子" in q or "帮我试" in q or "try move" in ql or "test move" in ql or "simulate move" in ql:
        return "try_move", {}, "正在按当前局势自动试下并评估。"

    t = re.search(r"(每手|每步|用时|思考)?\s*(\d+(?:\.\d+)?)\s*(秒|s|sec|分钟|min)", ql)
    if t:
        v = float(t.group(2))
        unit = t.group(3)
        sec = v * 60 if unit in {"分钟", "min"} else v
        return "set_move_time", {"seconds": sec}, f"已设置每手用时 {sec:.1f} 秒。"

    v = re.search(r"visits?\s*(\d+)", ql)
    if v:
        return "set_visits", {"visits": int(v.group(1))}, "已更新 visits。"

    e = re.search(r"默认引擎\s*(\d+)", q)
    if e:
        return "set_default_engine", {"index": int(e.group(1))}, "已更新默认引擎。"

    o = re.search(r"设置\s+([a-zA-Z0-9_.\-]+)\s*=\s*(.+)$", q)
    if o:
        key = o.group(1)
        raw = o.group(2).strip()
        val: Any = raw
        if raw.lower() in {"true", "false", "on", "off", "yes", "no", "1", "0", "开", "关"}:
            val = _to_bool(raw)
        else:
            try:
                if "." in raw:
                    val = float(raw)
                else:
                    val = int(raw)
            except Exception:
                pass
        return "set_option", {"path": key, "value": val}, f"已尝试设置 {key}。"

    return "chat", {"text": q}, ""


def llm_parse(text: str) -> tuple[str, dict[str, Any], str, str]:
    fb_action, fb_args, fb_msg = fallback_parse(text)
    if not LLM_API_KEY:
        return fb_action, fb_args, fb_msg, "fallback"

    system = (
        "你是 Lizziezy 控制中枢。把用户话术转成 JSON。"
        "只输出 JSON，不要解释。"
        "action 仅可为: chat, launch, stop, restart, status, set_default_engine, set_difficulty, set_move_time, set_visits, set_option, try_move。"
        "args 字段按 action 需求给出。"
        "chat 时 args 可给 text。try_move 时 args 可给 point(如 D4, Q16)。"
        "message 是简短中文反馈。"
    )
    prompt = json.dumps({"text": text}, ensure_ascii=False)
    body = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
    }
    try:
        resp = requests.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
            json=body,
            timeout=18,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = content.strip("`")
            content = content.replace("json", "", 1).strip()
        obj = json.loads(content)
        action = str(obj.get("action", fb_action))
        args = obj.get("args", {}) if isinstance(obj.get("args"), dict) else {}
        message = str(obj.get("message", fb_msg))
        allowed = {
            "chat",
            "launch",
            "stop",
            "restart",
            "status",
            "set_default_engine",
            "set_difficulty",
            "set_move_time",
            "set_visits",
            "set_option",
            "try_move",
        }
        if action not in allowed:
            action = fb_action
            args = fb_args
        if fb_action != "chat" and action in {"chat", "status"}:
            action = fb_action
            args = fb_args
            message = fb_msg
        return action, args, message, "llm"
    except Exception:
        return fb_action, fb_args, fb_msg, "fallback"


@app.get("/")
def index() -> FileResponse:
    return FileResponse(BASE_DIR / "frontend" / "index.html")


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "running": is_running(),
        "exe": str(LIZZIE_EXE),
        "config": str(LIZZIE_CONFIG),
        "llm_configured": bool(LLM_API_KEY),
        "llm_base_url": LLM_BASE_URL,
        "llm_model": LLM_MODEL,
    }


@app.get("/api/position")
def position() -> dict[str, Any]:
    return get_realtime_position(force=True)


@app.on_event("shutdown")
def on_shutdown() -> None:
    try:
        position_analyzer.stop()
    except Exception:
        pass


@app.post("/api/chat-command", response_model=CommandResult)
async def chat_command(req: ChatRequest) -> CommandResult:
    async with state_lock:
        action, args, pre_msg, source = llm_parse(req.message)
        if action == "chat" and not args.get("text"):
            args["text"] = req.message
        try:
            result = apply_action(action, args)
            msg = result.message if action == "chat" else f"{pre_msg} {result.message}".strip()
            payload = {"type": "assistant", "source": source, "action": action, "text": msg, "data": result.data}
            await ws_manager.broadcast(payload)
            return CommandResult(ok=True, message=msg, action=action, data={"source": source, **result.data})
        except Exception as exc:
            fail = CommandResult(ok=False, message=f"执行失败: {exc}", action=action)
            await ws_manager.broadcast({"type": "assistant", "source": source, "action": action, "text": fail.message, "data": {}})
            return fail


@app.websocket("/ws/chat")
async def ws_chat(ws: WebSocket) -> None:
    await ws_manager.connect(ws)
    try:
        await ws.send_json({"type": "assistant", "text": "已连接 Lizziezy 控制中枢。你可以直接聊天或发指令。"})
        while True:
            data = await ws.receive_json()
            text = str(data.get("text", "")).strip()
            if not text:
                continue
            await ws_manager.broadcast({"type": "user", "text": text})
            async with state_lock:
                action, args, pre_msg, source = llm_parse(text)
                if action == "chat" and not args.get("text"):
                    args["text"] = text
                try:
                    result = apply_action(action, args)
                    msg = result.message if action == "chat" else f"{pre_msg} {result.message}".strip()
                    await ws_manager.broadcast(
                        {
                            "type": "assistant",
                            "source": source,
                            "action": action,
                            "text": msg,
                            "data": result.data,
                        }
                    )
                except Exception as exc:
                    await ws_manager.broadcast(
                        {
                            "type": "assistant",
                            "source": source,
                            "action": action,
                            "text": f"执行失败: {exc}",
                            "data": {},
                        }
                    )
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)

