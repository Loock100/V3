# strategies/example_ma_crossover.py

from __future__ import annotations

from typing import Dict, Any, Tuple

import numpy as np
import pandas as pd


def run_strategy(
    df: pd.DataFrame,
    fast_window: int = 10,
    slow_window: int = 50,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    if "close" not in df.columns:
        raise ValueError("DataFrame não contém coluna 'close' necessária para a estratégia.")

    df = df.copy().reset_index(drop=True)

    # Médias móveis
    df["ma_fast"] = df["close"].rolling(window=fast_window, min_periods=fast_window).mean()
    df["ma_slow"] = df["close"].rolling(window=slow_window, min_periods=slow_window).mean()

    # Sinal: 1 comprado, 0 zerado
    df["signal"] = 0
    df.loc[df["ma_fast"] > df["ma_slow"], "signal"] = 1

    # Posição efetiva: sinal da barra anterior
    df["position"] = df["signal"].shift(1).fillna(0)

    # Retorno por barra
    df["ret"] = df["close"].pct_change().fillna(0.0)

    # Retorno da estratégia
    df["strategy_ret"] = df["position"] * df["ret"]

    # Curva de capital
    df["equity"] = (1.0 + df["strategy_ret"]).cumprod()

    # “Trades”: mudanças na posição
    position_changes = df["position"].diff().fillna(0.0)
    num_trades = int((position_changes != 0).sum())

    trades_info: Dict[str, Any] = {
        "num_trades": num_trades,
        "fast_window": fast_window,
        "slow_window": slow_window,
    }

    return df, trades_info
