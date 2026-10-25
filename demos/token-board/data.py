"""数据源：优先读本机 Token Monitor 的归档，读不到就退回内置样本。

Token Monitor 把一个会话一条记录存在 SQLite 里
（`%APPDATA%\\Token Monitor\\session-usage-archive.sqlite`，表 `sessions`，
列 `entry_json` 是 JSON 文本）。每个 entry 的 `periods.today` 里有
`totalTokens` / `costUsd` / `messageCount` / `models` / `modelCosts`。

两个必须注意的点：

1. **只读副本**。原程序在跑的时候是 WAL 模式，直接连上去会跟它抢锁。
   所以这里把 `*.sqlite` / `-wal` / `-shm` 三件套复制到临时目录再查。
2. **字段可能缺失**。不同版本字段略有出入，全部用 `.get()` 兜默认值，
   缺数据时宁愿显示 0 也不要抛异常 —— 屏上崩了比数字不准更糟。

这个模块只依赖标准库，可以单独拿去改。
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_NAME = "session-usage-archive.sqlite"
LOCAL_TZ = timezone(timedelta(hours=8))
SAMPLE_PATH = Path(__file__).resolve().parent / "sample-data.json"


def archive_dir() -> Path:
    base = os.environ.get("APPDATA") or os.path.expanduser("~/AppData/Roaming")
    return Path(base) / "Token Monitor"


def _snapshot_db(source: Path) -> Path:
    """把主库 + WAL + SHM 复制到临时目录，返回临时库路径。"""
    tmp = Path(tempfile.mkdtemp(prefix="tm_"))
    for suffix in ("", "-wal", "-shm"):
        src = source.with_name(source.name + suffix)
        if src.exists():
            shutil.copy2(src, tmp / (source.name + suffix))
    return tmp / source.name


def from_token_monitor(top_n: int = 2) -> dict | None:
    """读本机归档。找不到库 / 表结构不对时返回 None（交给调用方降级）。"""
    src = archive_dir() / DB_NAME
    if not src.exists():
        return None

    tmp_db = None
    try:
        tmp_db = _snapshot_db(src)
        con = sqlite3.connect(str(tmp_db))
        try:
            rows = [json.loads(ej) for (ej,) in con.execute("select entry_json from sessions")]
        finally:
            con.close()
    except (sqlite3.Error, ValueError) as exc:
        print("[warn] 读取归档失败（%s），改用演示数据" % exc, file=sys.stderr)
        return None
    finally:
        if tmp_db is not None:
            shutil.rmtree(tmp_db.parent, ignore_errors=True)

    return _aggregate(rows, top_n)


def _aggregate(rows: list[dict], top_n: int = 2) -> dict:
    """把逐会话的记录汇总成「一屏能显示的那几个数」。"""

    def totals(period: str) -> dict:
        def s(field: str) -> float:
            return sum(r.get("periods", {}).get(period, {}).get(field, 0) or 0 for r in rows)
        return {"tokens": int(s("totalTokens")), "cost": float(s("costUsd")),
                "messages": int(s("messageCount"))}

    # 今日模型用量：跨会话按模型聚合 token 与费用
    tokens: dict[str, int] = {}
    costs: dict[str, float] = {}
    for r in rows:
        p = r.get("periods", {}).get("today", {})
        for name, tok in (p.get("models") or {}).items():
            tokens[name] = tokens.get(name, 0) + int(tok or 0)
        for name, c in (p.get("modelCosts") or {}).items():
            costs[name] = costs.get(name, 0.0) + float(c or 0)

    top_models = [
        {"name": name, "tokens": tok, "cost": costs.get(name, 0.0)}
        for name, tok in sorted(tokens.items(), key=lambda kv: -kv[1])
    ][:top_n]

    return {
        "generated_at": datetime.now(LOCAL_TZ).isoformat(timespec="seconds"),
        "source": "token-monitor",
        "today": totals("today"),
        "month": totals("month"),
        "all_time": totals("allTime"),
        "top_models": top_models,
    }


def sample() -> dict:
    """内置演示数据，用来在没有 Token Monitor 的机器上调版式。"""
    data = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    data.pop("_comment", None)
    data["source"] = "sample"
    return data


def load(source: str = "auto", top_n: int = 2) -> dict:
    """source: auto | token-monitor | sample"""
    if source == "sample":
        return sample()
    if source == "token-monitor":
        data = from_token_monitor(top_n)
        if data is None:
            print("[warn] 本机没有可读的 Token Monitor 归档，退回演示数据", file=sys.stderr)
            return sample()
        return data
    return from_token_monitor(top_n) or sample()


if __name__ == "__main__":
    print(json.dumps(load(), ensure_ascii=False, indent=2))
