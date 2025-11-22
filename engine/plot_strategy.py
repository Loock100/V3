"""
engine/plot_strategy.py

Script para visualizar o resultado de UMA estratégia de forma gráfica.

O que ele faz:
- Lê um CSV de preços (por padrão: data/sample_prices.csv);
- Importa um módulo de estratégia (ex.: strategies/example_ma_crossover.py);
- Chama run_strategy(df) -> (df_result, trades_info);
- Calcula métricas básicas;
- Plota:
    1) Preço vs. Equity da estratégia;
    2) Drawdown da estratégia.

Uso (no PowerShell, com venv ativo):

    python engine/plot_strategy.py strategies/multi_tf_trend_lab_v1.py

Você pode trocar o caminho da estratégia ou do CSV com parâmetros.
"""

import argparse
import importlib.util
from pathlib import Path
from typing import Tuple, Dict, Any

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_PATH = ROOT_DIR / "data" / "sample_prices.csv"


def load_data(data_path: Path) -> pd.DataFrame:
    """
    Carrega dados de preços de um CSV.

    Espera, no mínimo, uma coluna 'close'.
    Opcionalmente, uma coluna 'datetime' para índice temporal.
    """
    if not data_path.exists():
        raise FileNotFoundError(
            f"Arquivo de dados não encontrado: {data_path}.\n"
            "Crie um CSV em data/sample_prices.csv com colunas, por exemplo: "
            "datetime, open, high, low, close, volume."
        )

    # Tenta detectar automaticamente se existe coluna datetime
    df = pd.read_csv(data_path)

    if "datetime" in df.columns:
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.sort_values("datetime")
        df = df.set_index("datetime")

    if "close" not in df.columns:
        raise KeyError(
            "O CSV precisa ter, no mínimo, uma coluna 'close' para permitir o backtest."
        )

    return df


def load_strategy_module(strategy_path: Path):
    """
    Importa um módulo de estratégia a partir de um caminho de arquivo .py.

    O módulo deve ter uma função:
        run_strategy(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]
    """
    if not strategy_path.exists():
        raise FileNotFoundError(f"Estratégia não encontrada em: {strategy_path}")

    spec = importlib.util.spec_from_file_location(
        strategy_path.stem, strategy_path
    )
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise ImportError(f"Não foi possível carregar o módulo de {strategy_path}")
    spec.loader.exec_module(module)  # type: ignore

    if not hasattr(module, "run_strategy"):
        raise AttributeError(
            f"O módulo {strategy_path} não possui a função run_strategy(df)."
        )

    return module


def compute_basic_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calcula métricas básicas a partir de um DataFrame com colunas:
    - 'equity' (curva de capital)
    - 'strategy_return' (retornos por período, se existir)
    """
    metrics: Dict[str, Any] = {}

    if "equity" not in df.columns:
        raise KeyError(
            "O DataFrame retornado pela estratégia precisa ter coluna 'equity'."
        )

    equity = df["equity"].astype(float)
    metrics["equity_final"] = float(equity.iloc[-1])
    metrics["total_return_pct"] = (metrics["equity_final"] - 1.0) * 100.0

    # Estima número de períodos por ano a partir da frequência do índice
    # Se não houver índice datetime, assume 252 períodos por ano
    periods_per_year = 252
    if isinstance(df.index, pd.DatetimeIndex) and len(df) > 1:
        # diferença média em dias
        diffs = df.index.to_series().diff().dropna().dt.total_seconds() / 86400.0
        avg_days = diffs.mean()
        if avg_days > 0:
            periods_per_year = int(round(365.0 / avg_days))

    n_periods = len(df)
    if n_periods > 1:
        total_return = metrics["equity_final"]
        try:
            annualized = total_return ** (periods_per_year / n_periods) - 1.0
            metrics["annualized_return_pct"] = annualized * 100.0
        except Exception:
            metrics["annualized_return_pct"] = float("nan")
    else:
        metrics["annualized_return_pct"] = float("nan")

    # Máximo drawdown
    running_max = equity.cummax()
    drawdown = (equity / running_max) - 1.0
    metrics["max_drawdown_pct"] = drawdown.min() * 100.0

    return metrics


def plot_results(
    df: pd.DataFrame,
    title: str = "Equity Curve & Drawdown",
) -> None:
    """
    Plota:
    - Preço (se coluna 'close' existir) e equity (normalizada) no gráfico superior;
    - Drawdown no gráfico inferior.
    """
    if "equity" not in df.columns:
        raise KeyError("DataFrame precisa ter coluna 'equity' para plotar.")

    # Garante ordem temporal
    if isinstance(df.index, pd.DatetimeIndex):
        df = df.sort_index()

    equity = df["equity"].astype(float)
    drawdown = (equity / equity.cummax()) - 1.0

    has_price = "close" in df.columns
    if has_price:
        price = df["close"].astype(float)
        # Normaliza o preço para começar em 1, para ficar comparável à equity
        price_norm = price / price.iloc[0]
    else:
        price_norm = None

    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(12, 8), sharex=True,
        gridspec_kw={"height_ratios": [3, 1]}
    )

    # Gráfico superior: preço normalizado (se houver) + equity
    if has_price and price_norm is not None:
        ax1.plot(df.index, price_norm, label="Preço normalizado")
    ax1.plot(df.index, equity, label="Equity estratégia")
    ax1.set_title(title)
    ax1.set_ylabel("Valor normalizado")
    ax1.grid(True)
    ax1.legend(loc="best")

    # Gráfico inferior: drawdown
    ax2.plot(df.index, drawdown, label="Drawdown")
    ax2.set_ylabel("Drawdown")
    ax2.set_xlabel("Tempo")
    ax2.grid(True)

    plt.tight_layout()
    plt.show()


def main():
    parser = argparse.ArgumentParser(
        description="Plota o resultado de uma estratégia usando o motor atual."
    )
    parser.add_argument(
        "strategy_path",
        type=str,
        help="Caminho para o arquivo de estratégia .py (ex.: strategies/multi_tf_trend_lab_v1.py)",
    )
    parser.add_argument(
        "--data",
        type=str,
        default=str(DEFAULT_DATA_PATH),
        help=f"Caminho para o CSV de dados (padrão: {DEFAULT_DATA_PATH})",
    )

    args = parser.parse_args()

    strategy_path = (ROOT_DIR / args.strategy_path).resolve()
    data_path = (ROOT_DIR / args.data).resolve()

    print(f"Carregando dados de: {data_path}")
    df = load_data(data_path)

    print(f"Carregando estratégia: {strategy_path}")
    module = load_strategy_module(strategy_path)

    print("Executando run_strategy(df)...")
    df_result, trades_info = module.run_strategy(df)

    print("\n=== Métricas básicas ===")
    metrics = compute_basic_metrics(df_result)
    for k, v in metrics.items():
        print(f"{k}: {v:.4f}" if isinstance(v, (int, float)) else f"{k}: {v}")

    print("\n=== Trades info (raw) ===")
    print(trades_info)

    title = f"Estratégia: {strategy_path.name}"
    plot_results(df_result, title=title)


if __name__ == "__main__":
    main()
