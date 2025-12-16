from __future__ import annotations

import csv
import json
import hashlib
import platform
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, date
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


# ======================================================
# CONFIG
# ======================================================

@dataclass(frozen=True)
class DatasetConfig:
    seed: int = 42
    n_companies: int = 200
    n_transactions: int = 1_000_000
    anomaly_frac: float = 0.02
    start_date: date = date(2020, 1, 1)
    end_date: date = date(2024, 12, 31)
    currency: str = "USD"
    schema_version: str = "1.0"


# ======================================================
# UTILITIES
# ======================================================

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def write_csv(path: Path, rows: Iterable[dict]) -> None:
    rows = list(rows)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def describe_numeric(series: pd.Series) -> dict:
    return {
        "min": float(series.min()),
        "max": float(series.max()),
        "mean": float(series.mean()),
        "median": float(series.median()),
        "std": float(series.std()),
        "iqr": float(series.quantile(0.75) - series.quantile(0.25)),
        "p01": float(series.quantile(0.01)),
        "p05": float(series.quantile(0.05)),
        "p25": float(series.quantile(0.25)),
        "p75": float(series.quantile(0.75)),
        "p95": float(series.quantile(0.95)),
        "p99": float(series.quantile(0.99)),
        "skewness": float(series.skew()),
        "kurtosis": float(series.kurtosis()),
    }


# ======================================================
# SYNTHETIC DATA GENERATION
# ======================================================

def generate_transactions(cfg: DatasetConfig) -> list[dict]:
    np.random.seed(cfg.seed)
    companies = [f"C{i:03d}" for i in range(cfg.n_companies)]
    date_range = pd.date_range(cfg.start_date, cfg.end_date)

    txns = []
    for i in range(cfg.n_transactions):
        sign = np.random.choice([1, -1], p=[0.6, 0.4])
        amount = round(float(np.random.lognormal(8, 0.7)), 2)

        txns.append({
            "txn_id": f"T{i}",
            "company_id": np.random.choice(companies),
            "date": pd.to_datetime(np.random.choice(date_range)).date().isoformat(),
            "amount": sign * amount,
            "currency": cfg.currency,
            "type": "revenue" if sign > 0 else "expense",
        })
    return txns


def generate_journal_entries(txns: list[dict]) -> list[dict]:
    entries = []
    for t in txns:
        amt = abs(t["amount"])
        tid = t["txn_id"]

        if t["amount"] > 0:
            entries.extend([
                {"txn_id": tid, "account": "Accounts Receivable", "debit": amt, "credit": 0.0},
                {"txn_id": tid, "account": "Revenue", "debit": 0.0, "credit": amt},
            ])
        else:
            entries.extend([
                {"txn_id": tid, "account": "Expense", "debit": amt, "credit": 0.0},
                {"txn_id": tid, "account": "Cash", "debit": 0.0, "credit": amt},
            ])
    return entries


def generate_trial_balance(entries: list[dict]) -> list[dict]:
    df = pd.DataFrame(entries)
    grouped = df.groupby("account")[["debit", "credit"]].sum().reset_index()
    grouped["balance"] = grouped["debit"] - grouped["credit"]
    grouped["balance_pct"] = grouped["balance"] / grouped["balance"].abs().sum()
    return grouped.to_dict(orient="records")


def inject_anomalies(txns: list[dict], frac: float) -> list[dict]:
    n = int(len(txns) * frac)
    idx = np.random.choice(len(txns), n, replace=False)
    anomalies = []

    for i in idx:
        txns[i]["amount"] *= -5
        anomalies.append({
            "txn_id": txns[i]["txn_id"],
            "type": "sign_flip_outlier",
            "severity": "high",
        })
    return anomalies


def generate_claims(txns: list[dict], anomalies: list[dict]) -> list[dict]:
    claims = []

    total_rev = round(sum(t["amount"] for t in txns if t["amount"] > 0), 2)
    claims.append({
        "claim_id": str(uuid.uuid4()),
        "type": "numeric",
        "text": f"Total revenue equals {total_rev} USD",
        "value": total_rev,
        "evidence": ["transactions.csv:amount>0"],
        "truth": True,
    })

    for a in anomalies:
        claims.append({
            "claim_id": str(uuid.uuid4()),
            "type": "anomaly",
            "text": f"Transaction {a['txn_id']} is anomalous",
            "value": None,
            "evidence": [f"transactions.csv:txn_id={a['txn_id']}"],
            "truth": True,
        })

    return claims


# ======================================================
# EDA TABLES
# ======================================================

def eda_tables(txns, journals, tb, anomalies, claims, cfg):
    tx_df = pd.DataFrame(txns)
    je_df = pd.DataFrame(journals)
    tb_df = pd.DataFrame(tb)
    cl_df = pd.DataFrame(claims)

    return {
        "overview": {
            "n_companies": cfg.n_companies,
            "n_transactions": len(tx_df),
            "date_start": tx_df["date"].min(),
            "date_end": tx_df["date"].max(),
        },
        "transactions": {
            "amount_stats": describe_numeric(tx_df["amount"]),
            "type_counts": tx_df["type"].value_counts().to_dict(),
            "company_concentration_top5_pct": float(
                tx_df["company_id"].value_counts().head(5).sum() / len(tx_df)
            ),
        },
        "ledger_integrity": {
            "total_debits": float(je_df["debit"].sum()),
            "total_credits": float(je_df["credit"].sum()),
            "balanced": bool(round(je_df["debit"].sum() - je_df["credit"].sum(), 2) == 0.0),
        },
        "trial_balance": {
            "accounts": tb_df[["account", "debit", "credit", "balance", "balance_pct"]]
            .to_dict(orient="records")
        },
        "anomalies": {
            "count": len(anomalies),
            "rate": len(anomalies) / len(tx_df),
            "types": pd.DataFrame(anomalies)["type"].value_counts().to_dict() if anomalies else {},
        },
        "claims": {
            "total": len(cl_df),
            "by_type": cl_df["type"].value_counts().to_dict(),
            "with_evidence_pct": float(cl_df["evidence"].apply(bool).mean()),
        },
    }


# ======================================================
# MAIN
# ======================================================

def main():
    cfg = DatasetConfig()
    run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out = Path("data") / f"synth_run_{run_id}"
    out.mkdir(parents=True, exist_ok=True)

    np.random.seed(cfg.seed)

    txns = generate_transactions(cfg)
    anomalies = inject_anomalies(txns, cfg.anomaly_frac)
    journals = generate_journal_entries(txns)
    tb = generate_trial_balance(journals)
    claims = generate_claims(txns, anomalies)

    write_csv(out / "transactions.csv", txns)
    write_csv(out / "journal_entries.csv", journals)
    write_csv(out / "trial_balance.csv", tb)
    write_csv(out / "anomalies.csv", anomalies)

    with (out / "claims_truth.jsonl").open("w") as f:
        for c in claims:
            f.write(json.dumps(c) + "\n")

    manifest = {
        "generated_at": datetime.utcnow().isoformat(),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
        },
        "config": {
            **asdict(cfg),
            "start_date": cfg.start_date.isoformat(),
            "end_date": cfg.end_date.isoformat(),
        },
        "files": {p.name: sha256_file(p) for p in out.iterdir()},
        "eda": eda_tables(txns, journals, tb, anomalies, claims, cfg),
    }

    with (out / "manifest.json").open("w") as f:
        json.dump(manifest, f, indent=2)

    with (out / "README.md").open("w") as f:
        f.write(
            "# Synthetic Finance Dataset\n\n"
            "Includes full EDA tables, ledger integrity checks, anomaly catalog, "
            "and claim ground truth for the Praxis project.\n"
        )

    latest = Path("data") / "latest"
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.symlink_to(out.name)

    print("OK: dataset written to", out)


if __name__ == "__main__":
    main()
