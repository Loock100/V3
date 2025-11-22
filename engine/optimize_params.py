import argparse
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

from metrics import calculate_metrics
from backtest import load_data, load_strategy


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH_DEFAULT = ROOT_DIR / "data" / "sample_prices.csv"


def parse_range(spec: str) -> List[int]:
    """Converte 'inicio:fim:passo' em lista de inteiros."""
    parts = spec.split(":")
    if len(parts) != 3:
        raise ValueError(f"Formato inválido de range: {spec}. Use inicio:fim:passo, ex.: 5:30:5")
    start, stop, step = map(int, parts)
    if step <= 0:
        raise ValueError("step deve ser > 0")
    values: List[int] = []
    x = start
    while x <= stop:
        values.append(x)
        x += step
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description="Grid search simples de parâmetros para a estratégia.")
    parser.add_argument("strategy", help="Caminho da estratégia, ex.: strategies/example_ma_crossover.py")
    parser.add_argument("--data", default=str(DATA_PATH_DEFAULT), help="CSV de preços (default=data/sample_prices.csv)")
    parser.add_argument("--fast", required=True, help="Range para fast_window, ex.: 5:30:5")
    parser.add_argument("--slow", required=True, help="Range para slow_window, ex.: 50:200:10")
    args = parser.parse_args()

    data_path = Path(args.data)
    strat_path = Path(args.strategy)

    fast_range = parse_range(args.fast)
    slow_range = parse_range(args.slow)

    print(f"[INFO] Otimizando {strat_path.name}")
    print(f"[INFO] fast_window em {fast_range}")
    print(f"[INFO] slow_window em {slow_range}")

    df = load_data(data_path)
    module = load_strategy(strat_path)
    run_strategy = getattr(module, "run_strategy")

    best_by_sharpe: Tuple[Dict[str, Any] | None, float, int, int] = (None, float("-inf"), 0, 0)
    # aqui "melhor" drawdown = menos negativo
    best_by_dd: Tuple[Dict[str, Any] | None, float, int, int] = (None, -1e9, 0, 0)

    for fast in fast_range:
        for slow in slow_range:
            if fast >= slow:
                continue
            print(f"[INFO] Testando fast={fast}, slow={slow}...")
            try:
                result = run_strategy(df.copy(), fast_window=fast, slow_window=slow)
                if isinstance(result, tuple):
                    df_res, trades_info = result
                else:
                    df_res, trades_info = result, {}

                if "equity" in df_res.columns:
                    equity = df_res["equity"].astype(float)
                elif "strategy_return" in df_res.columns:
                    equity = (1.0 + df_res["strategy_return"].fillna(0.0)).cumprod()
                else:
                    equity = df_res["close"].astype(float) / float(df_res["close"].iloc[0])

                bh_curve = df_res["close"].astype(float) / float(df_res["close"].iloc[0])

                metrics = calculate_metrics(
                    equity_curve=equity,
                    buy_and_hold_curve=bh_curve,
                    trades_info=trades_info,
                    start=df_res["datetime"].iloc[0],
                    end=df_res["datetime"].iloc[-1],
                    strategy_name=strat_path.name,
                )

                sharpe = float(metrics["sharpe"])
                max_dd = float(metrics["max_drawdown"])

                if sharpe > best_by_sharpe[1]:
                    best_by_sharpe = (metrics, sharpe, fast, slow)
                if max_dd > best_by_dd[1]:  # menos negativo = melhor
                    best_by_dd = (metrics, max_dd, fast, slow)

            except Exception as e:
                print(f"[WARN] Falha em fast={fast}, slow={slow}: {e}")

    print("\n===== MELHOR POR SHARPE =====")
    if best_by_sharpe[0] is None:
        print("Nenhuma combinação válida encontrada.")
    else:
        m, sharpe, fast, slow = best_by_sharpe
        print(f"fast={fast}, slow={slow}, Sharpe={sharpe:.2f}, Ret={m['total_return']*100:7.2f}% MaxDD={m['max_drawdown']*100:7.2f}%")

    print("\n===== MELHOR POR MENOR DRAWDOWN =====")
    if best_by_dd[0] is None:
        print("Nenhuma combinação válida encontrada.")
    else:
        m, max_dd, fast, slow = best_by_dd
        print(f"fast={fast}, slow={slow}, MaxDD={max_dd*100:7.2f}% Sharpe={m['sharpe']:.2f}, Ret={m['total_return']*100:7.2f}%")


if __name__ == "__main__":
    main()
