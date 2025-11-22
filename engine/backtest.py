import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any, Dict, Tuple

import pandas as pd

from metrics import calculate_metrics


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH_DEFAULT = ROOT_DIR / "data" / "sample_prices.csv"
RUNS_DIR = ROOT_DIR / "runs"


def load_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo de dados não encontrado: {path}")

    df = pd.read_csv(path)
    expected = {"datetime", "close"}
    missing = expected - set(df.columns)
    if missing:
        raise RuntimeError(f"[ERRO] Faltam colunas em {path}: {missing}")

    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    df = df.sort_values("datetime").reset_index(drop=True)
    return df


def load_strategy(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Estratégia não encontrada: {path}")

    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    assert spec and spec.loader
    spec.loader.exec_module(module)  # type: ignore[arg-type]
    if not hasattr(module, "run_strategy"):
        raise AttributeError(f"Estratégia {path} não possui função run_strategy(df).")
    return module


def run_backtest(data_path: Path, strategy_path: Path) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    df = load_data(data_path)
    module = load_strategy(strategy_path)

    run_strategy = getattr(module, "run_strategy")
    result = run_strategy(df.copy())

    if isinstance(result, tuple):
        df_result, trades_info = result
    else:
        df_result, trades_info = result, {}

    if "equity" in df_result.columns:
        equity_curve = df_result["equity"].astype(float)
    elif "strategy_return" in df_result.columns:
        equity_curve = (1.0 + df_result["strategy_return"].fillna(0.0)).cumprod()
    else:
        # fallback: buy & hold
        equity_curve = df_result["close"].astype(float) / float(df_result["close"].iloc[0])

    buy_and_hold_curve = df_result["close"].astype(float) / float(df_result["close"].iloc[0])

    metrics = calculate_metrics(
        equity_curve=equity_curve,
        buy_and_hold_curve=buy_and_hold_curve,
        trades_info=trades_info,
        start=df_result["datetime"].iloc[0],
        end=df_result["datetime"].iloc[-1],
        strategy_name=strategy_path.name,
    )

    return df_result, metrics


def save_metrics(metrics: Dict[str, Any], strategy_name: str) -> Path:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = metrics["timestamp"].replace(":", "").replace("-", "").replace("+", "_").replace("T", "_")
    out_name = f"run_{timestamp}_{strategy_name}"
    out_path = RUNS_DIR / f"{out_name}.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    return out_path


def print_summary(strategy_name: str, metrics: Dict[str, Any]) -> None:
    print("Resumo do Backtest:")
    print(f"  Estratégia: {strategy_name}")
    print(f"  Retorno total: {metrics['total_return'] * 100:6.2f}%")
    print(f"  Retorno anualizado (aprox.): {metrics['annualized_return'] * 100:6.2f}%")
    print(f"  Sharpe: {metrics['sharpe']:.2f}")
    print(f"  Máximo drawdown: {metrics['max_drawdown'] * 100:6.2f}%")
    print(f"  Expectativa (por período): {metrics['expectancy']:.5f}")
    print(f"  Buy & Hold total: {metrics['buy_and_hold']['total_return'] * 100:6.2f}%")


def main() -> None:
    parser = argparse.ArgumentParser(description="Engine simples de backtest.")
    parser.add_argument("strategy", help="Caminho da estratégia, ex.: strategies/example_ma_crossover.py")
    parser.add_argument(
        "--data",
        default=str(DATA_PATH_DEFAULT),
        help="CSV de preços (default=data/sample_prices.csv)",
    )
    args = parser.parse_args()

    data_path = Path(args.data)
    strat_path = Path(args.strategy)

    df_result, metrics = run_backtest(data_path, strat_path)
    print_summary(strat_path.name, metrics)
    out_path = save_metrics(metrics, strat_path.name)
    print(f"Métricas salvas em: {out_path}")


if __name__ == "__main__":
    main()
