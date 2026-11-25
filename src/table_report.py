# -*- coding: utf-8 -*-
"""Compact table-first report (REPORT_TYPE=table).

Every stock's key numbers are laid out in one table instead of long prose:
signal, score, trend, price levels, entry / stop / target and position size,
followed by a one-line conclusion and the top risk per stock.

Two renderings share the same rows:
- ``generate_table_markdown``: Markdown, used for saved reports and as the text
  fallback for channels that cannot receive images.
- ``render_table_png``: a PNG table via imgkit/wkhtmltoimage, used for Telegram
  (Telegram cannot render Markdown tables). Returns ``None`` when the renderer
  or a CJK font is unavailable, so callers can fall back to text.
"""

from __future__ import annotations

import html
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.zh_variant import to_report_variant

logger = logging.getLogger(__name__)

# Above this many stocks, stocks become rows instead of columns.
_TRANSPOSE_MAX_STOCKS = 4

_LABELS = {
    "zh": {
        "title": "持股决策表",
        "stock": "股票",
        "signal": "信号",
        "score": "评分",
        "trend": "趋势",
        "price": "现价",
        "ma5": "MA5",
        "ma20": "MA20",
        "support": "支撑",
        "resistance": "压力",
        "ideal_buy": "理想买点",
        "stop_loss": "止损",
        "take_profit": "目标",
        "position": "建议仓位",
        "notes_title": "结论与风险",
        "conclusion": "一句话结论",
        "risk": "主要风险",
        "generated": "生成时间",
        "summary": "共 {n} 档 | 买入 {buy} · 观望 {hold} · 卖出 {sell}",
    },
    "en": {
        "title": "Decision Table",
        "stock": "Stock",
        "signal": "Signal",
        "score": "Score",
        "trend": "Trend",
        "price": "Price",
        "ma5": "MA5",
        "ma20": "MA20",
        "support": "Support",
        "resistance": "Resistance",
        "ideal_buy": "Entry",
        "stop_loss": "Stop",
        "take_profit": "Target",
        "position": "Position",
        "notes_title": "Conclusion & Risk",
        "conclusion": "Conclusion",
        "risk": "Top Risk",
        "generated": "Generated",
        "summary": "{n} stocks | Buy {buy} · Hold {hold} · Sell {sell}",
    },
}


def _labels(language: str) -> Dict[str, str]:
    return _LABELS["zh"] if language == "zh" else _LABELS["en"]


def _clip(value: Any, limit: int) -> str:
    text = "" if value is None else str(value)
    text = " ".join(text.replace("|", "/").split())
    if not text or text.lower() in {"n/a", "none", "null"}:
        return "—"
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _dashboard(result: Any) -> Dict[str, Any]:
    dashboard = getattr(result, "dashboard", None)
    return dashboard if isinstance(dashboard, dict) else {}


def _sub(mapping: Dict[str, Any], *keys: str) -> Dict[str, Any]:
    current: Any = mapping
    for key in keys:
        current = current.get(key) if isinstance(current, dict) else None
    return current if isinstance(current, dict) else {}


def _build_table(notifier: Any, results: Sequence[Any]) -> Tuple[str, Dict[str, str], List[str], List[Tuple[str, List[str]]], List[Tuple[str, str, str]], Tuple[int, int, int]]:
    language = notifier._get_report_language(list(results))
    labels = _labels(language)
    sorted_results = sorted(results, key=lambda r: getattr(r, "sentiment_score", 0) or 0, reverse=True)

    from src.report_language import localize_trend_prediction

    stock_names: List[str] = []
    columns: Dict[str, List[str]] = {key: [] for key in (
        "signal", "score", "trend", "price", "ma5", "ma20", "support", "resistance",
        "ideal_buy", "stop_loss", "take_profit", "position",
    )}
    notes: List[Tuple[str, str, str]] = []

    for result in sorted_results:
        dashboard = _dashboard(result)
        price = _sub(dashboard, "data_perspective", "price_position")
        sniper = _sub(dashboard, "battle_plan", "sniper_points")
        position = _sub(dashboard, "battle_plan", "position_strategy")
        core = _sub(dashboard, "core_conclusion")
        intel = _sub(dashboard, "intelligence")

        signal_text, signal_emoji, _ = notifier._get_signal_level(result)
        name = notifier._get_display_name(result, language).replace("\\*", "*")
        stock_label = f"{name} ({result.code})"
        stock_names.append(stock_label)

        columns["signal"].append(f"{signal_emoji} {_clip(signal_text, 8)}")
        columns["score"].append(_clip(getattr(result, "sentiment_score", None), 6))
        columns["trend"].append(_clip(localize_trend_prediction(getattr(result, "trend_prediction", ""), language), 8))
        columns["price"].append(_clip(price.get("current_price"), 12))
        columns["ma5"].append(_clip(price.get("ma5"), 12))
        columns["ma20"].append(_clip(price.get("ma20"), 12))
        columns["support"].append(_clip(price.get("support_level"), 14))
        columns["resistance"].append(_clip(price.get("resistance_level"), 14))
        columns["ideal_buy"].append(_clip(notifier._clean_sniper_value(sniper.get("ideal_buy")), 16))
        columns["stop_loss"].append(_clip(notifier._clean_sniper_value(sniper.get("stop_loss")), 16))
        columns["take_profit"].append(_clip(notifier._clean_sniper_value(sniper.get("take_profit")), 16))
        columns["position"].append(_clip(position.get("suggested_position"), 14))

        conclusion = core.get("one_sentence") or getattr(result, "analysis_summary", "")
        risks = intel.get("risk_alerts") if isinstance(intel.get("risk_alerts"), list) else []
        risk = risks[0] if risks else getattr(result, "risk_warning", "")
        notes.append((stock_label, _clip(conclusion, 60), _clip(risk, 50)))

    rows = [(labels[key], values) for key, values in columns.items()]
    counts = notifier._count_display_decisions(list(results), language)
    return language, labels, stock_names, rows, notes, counts


def _summary_line(labels: Dict[str, str], total: int, counts: Tuple[int, int, int]) -> str:
    buy, sell, hold = counts
    return labels["summary"].format(n=total, buy=buy, hold=hold, sell=sell)


def generate_table_markdown(notifier: Any, results: Sequence[Any], report_date: Optional[str] = None) -> str:
    """Markdown version of the table report."""
    if not results:
        return ""
    report_date = report_date or datetime.now().strftime("%Y-%m-%d")
    _, labels, stocks, rows, notes, counts = _build_table(notifier, results)

    lines = [
        f"# 📊 {report_date} {labels['title']}",
        "",
        f"> {_summary_line(labels, len(results), counts)}",
        "",
    ]
    if len(stocks) <= _TRANSPOSE_MAX_STOCKS:
        lines.append("| | " + " | ".join(stocks) + " |")
        lines.append("|---" * (len(stocks) + 1) + "|")
        for label, values in rows:
            lines.append(f"| **{label}** | " + " | ".join(values) + " |")
    else:
        lines.append(f"| {labels['stock']} | " + " | ".join(label for label, _ in rows) + " |")
        lines.append("|---" * (len(rows) + 1) + "|")
        for idx, stock in enumerate(stocks):
            lines.append(f"| **{stock}** | " + " | ".join(values[idx] for _, values in rows) + " |")

    lines.extend([
        "",
        f"## {labels['notes_title']}",
        "",
        f"| {labels['stock']} | {labels['conclusion']} | {labels['risk']} |",
        "|---|---|---|",
    ])
    for stock, conclusion, risk in notes:
        lines.append(f"| {stock} | {conclusion} | {risk} |")
    lines.extend([
        "",
        f"*{labels['generated']}: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
    ])
    return to_report_variant("\n".join(lines))


_CSS = """
body { margin:0; padding:24px; background:#ffffff; color:#1f2328;
       font-family:'Noto Sans CJK TC','Noto Sans CJK SC','PingFang TC','Microsoft JhengHei',sans-serif; }
h1 { font-size:26px; margin:0 0 4px 0; }
.sub { color:#57606a; font-size:16px; margin-bottom:16px; }
h2 { font-size:20px; margin:22px 0 8px 0; }
table { border-collapse:collapse; width:100%; font-size:17px; }
th, td { border:1px solid #d0d7de; padding:7px 10px; text-align:center; vertical-align:middle; }
th { background:#f0f3f6; font-weight:700; }
td.k { background:#f6f8fa; font-weight:700; white-space:nowrap; }
tr.hl td { background:#fff8c5; }
td.l { text-align:left; }
.foot { color:#8c959f; font-size:13px; margin-top:14px; }
"""

_HIGHLIGHT_KEYS = {"signal", "ideal_buy", "stop_loss", "take_profit"}


def _build_table_html(notifier: Any, results: Sequence[Any], report_date: str) -> str:
    _, labels, stocks, rows, notes, counts = _build_table(notifier, results)
    esc = html.escape
    highlight_labels = {labels[key] for key in _HIGHLIGHT_KEYS}

    parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        f"<style>{_CSS}</style></head><body>",
        f"<h1>📊 {esc(report_date)} {esc(labels['title'])}</h1>",
        f"<div class='sub'>{esc(_summary_line(labels, len(results), counts))}</div>",
        "<table>",
    ]
    if len(stocks) <= _TRANSPOSE_MAX_STOCKS:
        parts.append("<tr><th></th>" + "".join(f"<th>{esc(s)}</th>" for s in stocks) + "</tr>")
        for label, values in rows:
            cls = " class='hl'" if label in highlight_labels else ""
            parts.append(
                f"<tr{cls}><td class='k'>{esc(label)}</td>"
                + "".join(f"<td>{esc(v)}</td>" for v in values)
                + "</tr>"
            )
    else:
        parts.append(
            f"<tr><th>{esc(labels['stock'])}</th>"
            + "".join(f"<th>{esc(label)}</th>" for label, _ in rows)
            + "</tr>"
        )
        for idx, stock in enumerate(stocks):
            parts.append(
                f"<tr><td class='k'>{esc(stock)}</td>"
                + "".join(f"<td>{esc(values[idx])}</td>" for _, values in rows)
                + "</tr>"
            )
    parts.append("</table>")

    parts.extend([
        f"<h2>{esc(labels['notes_title'])}</h2>",
        "<table>",
        f"<tr><th>{esc(labels['stock'])}</th><th>{esc(labels['conclusion'])}</th><th>{esc(labels['risk'])}</th></tr>",
    ])
    for stock, conclusion, risk in notes:
        parts.append(
            f"<tr><td class='k'>{esc(stock)}</td><td class='l'>{esc(conclusion)}</td>"
            f"<td class='l'>{esc(risk)}</td></tr>"
        )
    parts.extend([
        "</table>",
        f"<div class='foot'>{esc(labels['generated'])}: {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>",
        "</body></html>",
    ])
    return to_report_variant("".join(parts))


def render_table_png(notifier: Any, results: Sequence[Any], report_date: Optional[str] = None) -> Optional[bytes]:
    """Render the table report to PNG. Returns None if rendering is unavailable."""
    if not results:
        return None
    try:
        import imgkit
    except ImportError:
        logger.warning("imgkit not installed; table image unavailable")
        return None
    report_date = report_date or datetime.now().strftime("%Y-%m-%d")
    width = 1080 if len(results) <= _TRANSPOSE_MAX_STOCKS else 1600
    try:
        page = _build_table_html(notifier, results, report_date)
        out = imgkit.from_string(
            page,
            False,
            options={
                "format": "png",
                "encoding": "UTF-8",
                "width": width,
                "disable-smart-width": "",
                "quality": 90,
                "quiet": "",
            },
        )
        if isinstance(out, bytes) and out:
            return out
        logger.warning("Table image rendering returned empty output")
    except Exception as exc:
        logger.warning("Table image rendering failed: %s", exc)
    return None
