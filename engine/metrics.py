import math
from datetime import datetime, timezone
from typing import Dict, Any, Tuple

import numpy as np
import pandas as pd


def _compute_drawdown(equity: pd.Series) -> Tuple[float, int]:
    """Retorna (max_drawdown, max_duration_em_barras)."""
    equity = equity.astype(float)
    running_max = equity.cummax()
    dd = equity / running_max - 1.0

    max_dd = float(dd.min())
    # duração: maior sequência contínua em que dd < 0
    duration = 0
    max_duration = 0
    for v in dd:
        if v < 0:
            duration += 1
            if duration > max_duration:
                max_duration = duration
        else:
            duration = 0
    return max_dd, max_duration


def calculate_metrics(
    equity_curve: pd.Series,
    buy_and_hold_curve: pd.Series,
    trades_info: Dict[str, Any] | None,
    start: str,
    end: str,
    strategy_name: str,
) -> Dict[str, Any]:
    """Calcula métricas padrão a partir da curva de equity."""
    equity_curve = equity_curve.astype(float)
    returns = equity_curve.pct_change().fillna(0.0)

    if len(equity_curve) < 2:
        total_return = 0.0
        annualized_return = 0.0
        volatility = 0.0
        sharpe = 0.0
        expectancy = 0.0
    else:
        total_return = float(equity_curve.iloc[-1] / equity_curve.iloc[0] - 1.0)

        periods = len(equity_curve)
        # assume ~252 pregões por ano
        annualized_return = float((1.0 + total_return) ** (252.0 / periods) - 1.0)

        volatility = float(returns.std(ddof=0) * math.sqrt(252.0))
        if volatility > 1e-12:
            sharpe = float((returns.mean() * 252.0) / volatility)
        else:
            sharpe = 0.0

        expectancy = float(returns.mean())

    max_drawdown, max_dd_dur = _compute_drawdown(equity_curve)

    # Buy & hold
    bh_curve = buy_and_hold_curve.astype(float)
    bh_total_return = float(bh_curve.iloc[-1] / bh_curve.iloc[0] - 1.0)
    bh_max_dd, _ = _compute_drawdown(bh_curve)

    metrics: Dict[str, Any] = {
        "total_return": total_return,
        "annualized_return": annualized_return,
        "volatility": volatility,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "max_drawdown_duration": float(max_dd_dur),
        "expectancy": expectancy,
        "buy_and_hold": {
            "total_return": bh_total_return,
            "max_drawdown": bh_max_dd,
        },
        "strategy": strategy_name,
        "num_trades": int(trades_info.get("num_trades", 0) if trades_info else 0),
        "trades_info": trades_info or {},
        "start": str(start),
        "end": str(end),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return metrics
