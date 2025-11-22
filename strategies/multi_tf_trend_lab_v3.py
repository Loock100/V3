import pandas as pd
import numpy as np

"""
Estratégia Multi-Timeframe Trend Lab v3

Diferenças em relação à v1 e v2:
- Janelas médias móveis intermediárias:
  * Intraday: 7 períodos
  * Diário: 25 períodos
  * 3 dias: 75 períodos
  * Semanal: 150 períodos
- Critério de sinal combinado: todas as médias móveis devem estar em alta, mas com filtro adicional:
  * Intraday e Diário devem ter fechamento acima da média móvel + desvio padrão (mais rigoroso)

Assinatura da função:
- run_strategy(df: pd.DataFrame) -> (pd.DataFrame, dict)
"""

def run_strategy(df: pd.DataFrame):
    df = df.copy()
    df = df.sort_index()
    df["close"] = df["close"].ffill()


    df['ma_intraday'] = df['close'].rolling(window=7, min_periods=1).mean()
    df['std_intraday'] = df['close'].rolling(window=7, min_periods=1).std().fillna(0)
    df['ma_daily'] = df['close'].rolling(window=25, min_periods=1).mean()
    df['std_daily'] = df['close'].rolling(window=25, min_periods=1).std().fillna(0)
    df['ma_3days'] = df['close'].rolling(window=75, min_periods=1).mean()
    df['ma_weekly'] = df['close'].rolling(window=150, min_periods=1).mean()

    # Sinais com filtro de desvio padrão para intraday e diário
    df['sig_intraday'] = ((df['close'] > df['ma_intraday'] + df['std_intraday']).astype(int))
    df['sig_daily'] = ((df['close'] > df['ma_daily'] + df['std_daily']).astype(int))
    df['sig_3days'] = (df['close'] > df['ma_3days']).astype(int)
    df['sig_weekly'] = (df['close'] > df['ma_weekly']).astype(int)

    # Sinal combinado: todas as condições devem ser verdadeiras
    df['signal'] = ((df['sig_intraday'] + df['sig_daily'] + df['sig_3days'] + df['sig_weekly']) == 4).astype(int)

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
