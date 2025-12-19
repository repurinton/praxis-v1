from __future__ import annotations

import datetime as dt
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SynthConfig:
    seed: int = 42
    n_rows: int = 50000000
    n_companies: int = 20000
    start_date: dt.date = dt.date(2018, 1, 1)
    end_date: dt.date = dt.date(2024, 12, 31)
    macro_freq: str = "ME"  # month end
    include_stocks: bool = True
    anomaly_frac: float = 0.02


def set_seed(seed: int) -> None:
    np.random.seed(seed)
    random.seed(seed)


def make_company_meta(cfg: SynthConfig) -> pd.DataFrame:
    industries = [
        "Manufacturing", "Retail", "Technology", "Healthcare",
        "Services", "Energy", "Finance", "Logistics",
    ]
    sizes = ["Micro", "Small", "Medium", "Large"]

    rows: list[dict] = []
    for i in range(cfg.n_companies):
        cid = f"C{1000 + i}"
        rows.append(
            {
                "company_id": cid,
                "company_name": f"Company_{i}",
                "industry": np.random.choice(industries),
                "size_bucket": np.random.choice(sizes, p=[0.1, 0.4, 0.35, 0.15]),
                "fiscal_year_end": int(np.random.choice([12, 3, 6, 9])),
                "created_date": (
                    cfg.start_date
                    - dt.timedelta(days=int(np.random.randint(0, 365 * 5)))
                ).isoformat(),
            }
        )
    return pd.DataFrame(rows)


def generate_macro_series(cfg: SynthConfig) -> pd.DataFrame:
    dates = pd.date_range(start=cfg.start_date, end=cfg.end_date, freq=cfg.macro_freq)
    n = len(dates)

    inflation = 0.02 + 0.005 * np.random.randn(n) + 0.001 * np.linspace(0, 1, n)
    gdp_growth = (
        0.004 + 0.01 * np.sin(np.linspace(0, 6 * np.pi, n)) + 0.008 * np.random.randn(n)
    )
    base_rate = (
        0.01 + 0.004 * np.cos(np.linspace(0, 3 * np.pi, n)) + 0.002 * np.random.randn(n)
    )

    macro = pd.DataFrame(
        {
            "period_start": dates,
            "inflation": np.round(inflation, 5),
            "gdp_growth": np.round(gdp_growth, 5),
            "base_interest_rate": np.round(base_rate, 5),
        }
    )
    macro["period"] = macro["period_start"].dt.strftime("%Y-%m")
    return macro


def _random_dates(n: int, start: dt.date, end: dt.date) -> list[dt.date]:
    start_ord = start.toordinal()
    end_ord = end.toordinal()
    ords = np.random.randint(start_ord, end_ord + 1, size=n)
    return [dt.date.fromordinal(int(o)) for o in ords]


def generate_transactions(
    cfg: SynthConfig,
    companies_df: pd.DataFrame,
    macro_df: pd.DataFrame,
) -> pd.DataFrame:
    txn_types = np.array(
        ["invoice", "payment", "payroll", "journal_adjustment", "refund", "purchase"]
    )
    txn_probs = np.array([0.35, 0.25, 0.15, 0.10, 0.05, 0.10])
    currencies = np.array(["USD", "EUR", "GBP", "KES", "ZAR"])

    company_scales = {
        cid: max(10_000, int(100_000 * (0.5 + np.random.rand())))
        for cid in companies_df["company_id"]
    }

    company_choices = np.random.choice(companies_df["company_id"], size=cfg.n_rows)
    date_list = _random_dates(cfg.n_rows, cfg.start_date, cfg.end_date)

    macro_map = macro_df.set_index("period").to_dict(orien
