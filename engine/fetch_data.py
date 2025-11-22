import argparse
from pathlib import Path

import pandas as pd
import yfinance as yf

# Raiz do projeto (…/agente-estrategias)
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_CSV = DATA_DIR / "sample_prices.csv"


def fetch_last_n_years(symbol: str, years: int = 5, interval: str = "1d") -> pd.DataFrame:
    """
    Baixa dados históricos do yfinance e devolve dataframe normalizado.

    Saída SEMPRE com colunas:
        datetime (UTC), open, high, low, close, volume
    """
    ticker = yf.Ticker(symbol)
    period_str = f"{years}y"

    # history() evita MultiIndex chato do download()
    df = ticker.history(period=period_str, interval=interval)

    if df is None or df.empty:
        raise ValueError(f"Nenhum dado retornado para {symbol} (period={period_str}, interval={interval}).")

    # Index Date -> coluna
    df = df.reset_index()

    # Normaliza nomes
    rename_map = {
        "Date": "datetime",
        "Datetime": "datetime",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Adj Close": "adj_close",
        "Volume": "volume",
    }
    df = df.rename(columns=rename_map)

    if "datetime" not in df.columns:
        raise ValueError(f"Coluna 'datetime' não encontrada. Colunas: {list(df.columns)}")

    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)

    # Garante colunas numéricas básicas
    for col in ["open", "high", "low", "close", "volume"]:
        if col not in df.columns:
            raise ValueError(
                f"Coluna obrigatória '{col}' não encontrada. Colunas disponíveis: {list(df.columns)}"
            )
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values("datetime").reset_index(drop=True)

    # Mantém apenas o essencial
    df = df[["datetime", "open", "high", "low", "close", "volume"]]

    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Baixa dados de preço e salva em data/sample_prices.csv")
    parser.add_argument("symbol", type=str, help="Símbolo (ex: BTC-USD)")
    parser.add_argument("--years", type=int, default=5, help="Número de anos para trás (default: 5)")
    parser.add_argument("--interval", type=str, default="1d", help="Intervalo do yfinance (ex: 1d, 1h)")

    args = parser.parse_args()

    print(f"[INFO] Iniciando fetch_data para símbolo: {args.symbol}")
    print(f"[INFO] Período: últimos {args.years} anos, intervalo {args.interval}")

    df = fetch_last_n_years(symbol=args.symbol, years=args.years, interval=args.interval)
    df.to_csv(DEFAULT_CSV, index=False)

    print(f"[INFO] Dados salvos em: {DEFAULT_CSV}")
    print("[INFO] Primeiras linhas:")
    print(df.head())


if __name__ == "__main__":
    main()
