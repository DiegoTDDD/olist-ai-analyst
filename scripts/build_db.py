"""Build data/olist.duckdb from the nine CSV files in data/raw/ (see scripts/download_data.sh)."""

from analyst.data import DATABASE, build

if __name__ == "__main__":
    counts = build()
    print(f"built {DATABASE.name}: " + ", ".join(f"{t} {n:,}" for t, n in counts.items()))
