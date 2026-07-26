"""Generate deterministic synthetic load, price and carbon data.

The dataset represents three fictional German manufacturing sites. It contains
no company, employee, supplier or meter data.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "plant_loads_synthetic.csv"
SEED = 42
START = "2026-01-05"
DAYS = 21
INTERVAL_MINUTES = 15

PLANTS = [
    {
        "plant_id": "DE-NORTH",
        "plant_name": "North Plant",
        "process": "Body & Welding",
        "base_kw": 4200,
        "flexible_share": 0.16,
        "phase": 0.2,
    },
    {
        "plant_id": "DE-CENTRAL",
        "plant_name": "Central Plant",
        "process": "Paint & Utilities",
        "base_kw": 5100,
        "flexible_share": 0.22,
        "phase": 1.1,
    },
    {
        "plant_id": "DE-SOUTH",
        "plant_name": "South Plant",
        "process": "Assembly & Charging",
        "base_kw": 3600,
        "flexible_share": 0.19,
        "phase": 2.0,
    },
]


def generate() -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    periods = DAYS * 24 * 60 // INTERVAL_MINUTES
    timestamps = pd.date_range(START, periods=periods, freq=f"{INTERVAL_MINUTES}min")
    hour = timestamps.hour.to_numpy() + timestamps.minute.to_numpy() / 60
    weekday = timestamps.dayofweek.to_numpy()

    daylight = np.clip(np.sin(np.pi * (hour - 6) / 12), 0, None)
    wind_proxy = 0.5 + 0.25 * np.sin(np.arange(periods) / 29)
    evening_peak = np.exp(-0.5 * ((hour - 18.5) / 2.0) ** 2)
    morning_peak = np.exp(-0.5 * ((hour - 8.0) / 2.4) ** 2)

    price = (
        68
        + 24 * evening_peak
        + 11 * morning_peak
        - 29 * daylight
        - 10 * wind_proxy
        + rng.normal(0, 4, periods)
    )
    price = np.clip(price, -12, 145)

    carbon = (
        410
        + 80 * evening_peak
        - 175 * daylight
        - 70 * wind_proxy
        + rng.normal(0, 12, periods)
    )
    carbon = np.clip(carbon, 95, 590)

    temperature = 4 + 5 * np.sin(2 * np.pi * (hour - 14) / 24) + rng.normal(0, 0.7, periods)

    frames: list[pd.DataFrame] = []
    for plant in PLANTS:
        is_workday = weekday < 5
        first_shift = ((hour >= 6) & (hour < 14)).astype(float)
        second_shift = ((hour >= 14) & (hour < 22)).astype(float)
        night = 1 - np.maximum(first_shift, second_shift)
        production_index = (
            is_workday * (0.98 * first_shift + 0.88 * second_shift + 0.38 * night)
            + (~is_workday) * (0.46 * first_shift + 0.38 * second_shift + 0.28 * night)
        )
        process_cycle = 1 + 0.06 * np.sin(np.arange(periods) / 7 + plant["phase"])
        weather_load = np.maximum(0, 12 - temperature) * (24 if plant["process"] == "Paint & Utilities" else 10)
        noise = rng.normal(0, plant["base_kw"] * 0.025, periods)
        load = plant["base_kw"] * (0.48 + 0.58 * production_index) * process_cycle + weather_load + noise
        load = np.clip(load, plant["base_kw"] * 0.35, None)

        frames.append(
            pd.DataFrame(
                {
                    "timestamp": timestamps,
                    "plant_id": plant["plant_id"],
                    "plant_name": plant["plant_name"],
                    "process": plant["process"],
                    "load_kw": np.round(load, 3),
                    "flexible_share": plant["flexible_share"],
                    "price_eur_mwh": np.round(price, 3),
                    "carbon_g_kwh": np.round(carbon, 3),
                    "temperature_c": np.round(temperature, 3),
                    "production_index": np.round(production_index, 3),
                }
            )
        )

    result = pd.concat(frames, ignore_index=True)
    return result.sort_values(["plant_id", "timestamp"]).reset_index(drop=True)


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    data = generate()
    data.to_csv(OUTPUT, index=False)
    print(f"Wrote {len(data):,} rows to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
