"""
analyze_runs.py

Le todos os arquivos run_*.json em runs/,
monta um DataFrame com as principais métricas
e imprime um ranking profissional no terminal.

Uso (a partir da raiz do projeto):

    python engine/analyze_runs.py

Requisitos:
- pandas (já está no requirements.txt)
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT_DIR / "runs"


def load_all_runs() -> pd.DataFrame:
    """Carrega todos os run_*.json de runs/ em um DataFrame."""
    records = []

    if not RUNS_DIR.exists():
        print(f"[WARN] Pasta de runs não existe: {RUNS_DIR}")
        return pd.DataFrame()

    for path in RUNS_DIR.glob("run_*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[WARN] Falha ao ler {path.name}: {e}")
            continue

        rec = {
            "file": path.name,
            "strategy": data.get("strategy", "desconhecida"),
            "total_return": float(data.get("total_return", 0.0)),
            "annualized_return": float(data.get("annualized_return", 0.0)),
            "volatility": float(data.get("volatility", 0.0)),
            "sharpe": float(data.get("sharpe", 0.0)),
            "max_drawdown": float(data.get("max_drawdown", 0.0)),
            "expectancy": float(data.get("expectancy", 0.0)),
            "num_trades": int(data.get("num_trades", 0)),
            "start": data.get("start"),
            "end": data.get("end"),
        }

        # Buy & Hold embutido (se existir)
        bh = data.get("buy_and_hold", {})
        rec["bh_total_return"] = float(bh.get("total_return", 0.0))
        rec["bh_max_drawdown"] = float(bh.get("max_drawdown", 0.0))

        records.append(rec)

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    # Score simples: favorece retorno anualizado e Sharpe, penaliza drawdown
    def score_row(row):
        # evitar divisão por zero
        dd = abs(row["max_drawdown"]) if row["max_drawdown"] != 0 else 0.0001
        return row["annualized_return"] * max(row["sharpe"], 0.0) / (1.0 + dd)

    df["score"] = df.apply(score_row, axis=1)

    return df


def format_and_print(df: pd.DataFrame, top_n: int = 10) -> None:
    """Formata as principais colunas e imprime um ranking enxuto e legível."""
    if df.empty:
        print("[INFO] Nenhum run_*.json encontrado em runs/. Rode alguns backtests primeiro.")
        return

    # Ordenar por score (descendente)
    df_sorted = df.sort_values("score", ascending=False).reset_index(drop=True)

    # Escolher colunas mais importantes
    cols = [
        "strategy",
        "file",
        "total_return",
        "annualized_return",
        "sharpe",
        "max_drawdown",
        "expectancy",
        "num_trades",
        "bh_total_return",
        "score",
    ]

    df_view = df_sorted[cols].copy()

    # Converter para percentuais legíveis
    for col in ["total_return", "annualized_return", "max_drawdown", "bh_total_return"]:
        df_view[col] = df_view[col] * 100.0

    # Arredondar
    df_view["total_return"] = df_view["total_return"].round(2)
    df_view["annualized_return"] = df_view["annualized_return"].round(2)
    df_view["max_drawdown"] = df_view["max_drawdown"].round(2)
    df_view["bh_total_return"] = df_view["bh_total_return"].round(2)
    df_view["sharpe"] = df_view["sharpe"].round(2)
    df_view["expectancy"] = df_view["expectancy"].round(5)
    df_view["score"] = df_view["score"].round(4)

    # Renomear colunas para algo mais amigável
    df_view = df_view.rename(
        columns={
            "strategy": "Estratégia",
            "file": "Run file",
            "total_return": "Ret. Total (%)",
            "annualized_return": "Ret. Anualiz. (%)",
            "sharpe": "Sharpe",
            "max_drawdown": "Max DD (%)",
            "expectancy": "Expectativa",
            "num_trades": "# Trades",
            "bh_total_return": "BH Total (%)",
            "score": "Score",
        }
    )

    # Limitar ao top_n
    df_top = df_view.head(top_n)

    print("\n=== RANKING DE ESTRATÉGIAS (TOP {0}) ===".format(top_n))
    print(df_top.to_string(index=False))

    # Pequeno resumo adicional
    print("\nLegenda:")
    print("- Ret. Total (%): retorno acumulado da estratégia no período.")
    print("- Ret. Anualiz. (%): retorno anualizado aproximado.")
    print("- Sharpe: razão de Sharpe (retorno/risco).")
    print("- Max DD (%): máximo drawdown (queda máxima da curva).")
    print("- BH Total (%): retorno do buy & hold no mesmo período.")
    print("- Expectativa: retorno médio por período (em fração).")
    print("- Score: métrica composta (heurística) usada para o ranking.\n")


def main():
    df = load_all_runs()
    format_and_print(df, top_n=10)


if __name__ == "__main__":
    main()
