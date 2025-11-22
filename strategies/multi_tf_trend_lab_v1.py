import pandas as pd
import numpy as np

"""
Estratégia Multi-Timeframe Trend Lab v1

Esta estratégia calcula sinais de tendência em múltiplos horizontes de tempo a partir do mesmo dataframe de preços.

Horizontes considerados:
- Intraday: média móvel curta (5 períodos)
- Diário: média móvel média (20 períodos)
- 3 dias: média móvel longa (60 períodos)
- Semanal: média móvel muito longa (120 períodos)

Sinal final:
- 1 (posição comprada) quando todas as médias móveis indicam tendência de alta (close > média móvel)
- 0 (fora do mercado) caso contrário

Retornos e equity são calculados com base no sinal gerado.

Função principal:
- run_strategy(df: pd.DataFrame) -> (pd.DataFrame, dict)

Parâmetros:
- df: DataFrame com índice datetime e coluna 'close'

Retorna:
- df modificado com colunas de sinais, retornos e equity
- trades_info: dict com número de trades e outras métricas
"""

def run_strategy(df: pd.DataFrame):
    df = df.copy()
    # Garantir índice datetime ordenado
    df = df.sort_index()

    # Preencher NaNs se houver
    df["close"] = df["close"].ffill()


    # Definir médias móveis para diferentes horizontes
    # Intraday (curto prazo): 5 períodos
    df['ma_intraday'] = df['close'].rolling(window=5, min_periods=1).mean()

    # Diário (médio prazo): 20 períodos
    df['ma_daily'] = df['close'].rolling(window=20, min_periods=1).mean()

    # 3 dias (lento): 60 períodos
    df['ma_3days'] = df['close'].rolling(window=60, min_periods=1).mean()

    # Semanal (muito lento): 120 períodos
    df['ma_weekly'] = df['close'].rolling(window=120, min_periods=1).mean()

    # Sinais de tendência: 1 se close > média móvel, 0 caso contrário
    df['sig_intraday'] = (df['close'] > df['ma_intraday']).astype(int)
    df['sig_daily'] = (df['close'] > df['ma_daily']).astype(int)
    df['sig_3days'] = (df['close'] > df['ma_3days']).astype(int)
    df['sig_weekly'] = (df['close'] > df['ma_weekly']).astype(int)

    # Sinal combinado: 1 se todas as tendências indicam alta
    df['signal'] = ((df['sig_intraday'] + df['sig_daily'] + df['sig_3days'] + df['sig_weekly']) == 4).astype(int)

    # Calcular retorno do período
    df['return'] = df['close'].pct_change().fillna(0)

    # Retorno da estratégia
    df['strategy_return'] = df['signal'].shift(1) * df['return']  # Usar sinal do período anterior para evitar look-ahead
    df['strategy_return'] = df['strategy_return'].fillna(0)

    # Curva de capital
    df['equity'] = (1 + df['strategy_return']).cumprod()

    # Contar número de trades (mudanças de posição)
    df['position_change'] = df['signal'].diff().abs()
    num_trades = int(df['position_change'].sum())

    trades_info = {
        'num_trades': num_trades,
        'final_equity': df['equity'].iloc[-1],
        'total_return': df['equity'].iloc[-1] - 1,
    }

    return df, trades_info
