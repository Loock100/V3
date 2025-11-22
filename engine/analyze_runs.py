import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT_DIR / "runs"


def load_all_runs() -> List[Dict[str, Any]]:
    if not RUNS_DIR.exists():
        return []

    runs: List[Dict[str, Any]] = []
    for path in sorted(RUNS_DIR.glob("run_*.json")):
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            data["_file"] = path.name
            runs.append(data)
        except Exception:
            continue
    return runs


def main() -> None:
    runs = load_all_runs()
    if not runs:
        print("Nenhum run válido encontrado para análise.")
        return

    df = pd.DataFrame(runs)

    if "sharpe" not in df.columns:
        print("Nenhuma coluna 'sharpe' encontrada.")
        return

    df_sorted = df.sort_values("sharpe", ascending=False).reset_index(drop=True)

    print("===== TOP ESTRATÉGIAS (por Sharpe) =====")
    top = df_sorted.head(10)
    for _, row in top.iterrows():
        strat = str(row.get("strategy", "???"))
        sharpe = float(row.get("sharpe", 0.0))
        total_ret = float(row.get("total_return", 0.0)) * 100.0
        max_dd = float(row.get("max_drawdown", 0.0)) * 100.0
        file_name = str(row.get("_file", ""))
        print(f"{strat:28} | Sharpe: {sharpe:5.2f} | Ret: {total_ret:7.2f}% | MaxDD: {max_dd:7.2f}% | Arquivo: {file_name}")


if __name__ == "__main__":
    main()
