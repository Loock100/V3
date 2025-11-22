import pandas as pd
import numpy as np

"""
Estratégia Multi-Timeframe Trend Lab v2

Diferenças em relação à v1:
- Janelas ajustadas para médias móveis:
  * Intraday: 10 períodos (mais suave)
  * Diário: 30 períodos
  * 3 dias: 90 períodos
  * Semanal: 180 períodos
- Critério de sinal combinado: pelo menos 3 de 4 horizontes indicam alta (mais permissivo)

Assinatura da função:
- run_strategy(df: pd.DataFrame) -> (pd.DataFrame, dict)
"""

def run_strategy(df: pd.DataFrame):
    df = df.copy()
    df = df.sort_index()
    df["close"] = df["close"].ffill()


    df['ma_intraday'] = df['close'].rolling(window=10, min_periods=1).mean()
    df['ma_daily'] = df['close'].rolling(window=30, min_periods=1).mean()
    df['ma_3days'] = df['close'].rolling(window=90, min_periods=1).mean()
    df['ma_weekly'] = df['close'].rolling(window=180, min_periods=1).mean()

    df['sig_intraday'] = (df['close'] > df['ma_intraday']).astype(int)
    df['sig_daily'] = (df['close'] > df['ma_daily']).astype(int)
    df['sig_3days'] = (df['close'] > df['ma_3days']).astype(int)
    df['sig_weekly'] = (df['close'] > df['ma_weekly']).astype(int)

    # Sinal combinado: pelo menos 3 de 4 horizontes indicam alta
    df['signal'] = ((df['sig_intraday'] + df['sig_daily'] + df['sig_3days'] + df['sig_weekly']) >= 3).astype(int)

    df['return'] = df['close'].pct_change().fillna(0)
    df['strategy_return'] = df['signal'].shift(1) * df['return']
    df['strategy_return'] = df['strategy_return'].fillna(0)
    df['equity'] = (1 + df['strategy_return']).cumprod()

    df['position_change'] = df['signal'].diff().abs()
    num_trades = int(df['position_change'].sum())

    trades_info = {
        'num_trades': num_trades,
        'final_equity': df['equity'].iloc[-1],
        'total_return': df['equity'].iloc[-1] - 1,
    }

    return df, trades_info
