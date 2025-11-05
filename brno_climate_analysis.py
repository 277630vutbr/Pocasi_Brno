#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Brno Climate Analysis & Projections
-----------------------------------
- Downloads historical daily data (temperature, wind speed, precipitation) for Brno–Tuřany (Meteostat station 11723)
- Aggregates to monthly & annual
- Builds quantified projection scenarios for 10, 100 and 1000-year horizons
- Exports:
    - Excel workbook with raw data, aggregates, methods, assumptions, and projections
    - PDF summary (methods, key figures & charts)
Requirements (install locally):
    pip install pandas numpy matplotlib meteostat openpyxl reportlab
Run:
    python brno_climate_analysis.py
"""

from datetime import datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from meteostat import Stations, Daily

# ---------------------------
# SETTINGS
# ---------------------------
CITY_NAME = "Brno"
STATION_ID = "11723"  # Brno–Tuřany
COORDS = (49.1951, 16.6068)
START = datetime(1950, 1, 1)     # adjustable
END   = datetime.today()

# Scenario deltas (approx.) for Central Europe based on IPCC AR6 (Europe factsheet & Atlas)
# Values are deliberately simple and documented in the Excel 'Assumptions' sheet.
# Temperature deltas are added to local baseline; precipitation deltas are % multipliers.
SCENARIOS = {
    "SSP1-2.6": {"temp_2100": +1.5, "prc_2100_pct": +2,  "wind_2100_pct": 0},
    "SSP2-4.5": {"temp_2100": +2.7, "prc_2100_pct": +4,  "wind_2100_pct": 0},
    "SSP5-8.5": {"temp_2100": +4.4, "prc_2100_pct": +7,  "wind_2100_pct": 0}
}
# Beyond 2100 (to 2300) AR6 provides ranges; here we extend linearly as a simple what-if, with clear caveats.
EXTENSION_MULTIPLIER_2300 = {"SSP1-2.6": 1.1, "SSP2-4.5": 1.6, "SSP5-8.5": 2.5}

# ---------------------------
# FETCH HISTORICAL DATA
# ---------------------------
def get_station_id():
    # Prefer explicit station; fallback by nearest to coords
    try:
        return STATION_ID
    except Exception:
        stations = Stations().nearby(*COORDS).fetch(1)
        return stations.index[0]

def fetch_daily(station_id):
    data = Daily(station_id, START, END).fetch()
    # Keep relevant columns: tavg (°C), tmin, tmax, prcp (mm), wdir (°), wspd (km/h), pres (hPa), snow (cm)
    cols = ['tavg','tmin','tmax','prcp','wspd']
    keep = [c for c in cols if c in data.columns]
    return data[keep].rename(columns={'wspd':'wind'})

def aggregate(df):
    # Monthly & annual means/sums where appropriate
    m = df.resample('MS').agg({
        'tavg':'mean','tmin':'mean','tmax':'mean',
        'prcp':'sum',
        'wind':'mean'
    })
    a = df.resample('YS').agg({
        'tavg':'mean','tmin':'mean','tmax':'mean',
        'prcp':'sum',
        'wind':'mean'
    })
    return m, a

def trend_lin(x, y):
    # return slope per year and intercept
    t = np.arange(len(y))
    mask = np.isfinite(y.values)
    if mask.sum() < 5:
        return np.nan, np.nan
    coef = np.polyfit(t[mask], y.values[mask], 1)
    return coef[0], coef[1]

# ---------------------------
# BUILD SCENARIO PROJECTIONS
# ---------------------------
def build_projections(annual, scenarios):
    """
    Create projections for +10y, +100y, +1000y from END.year baseline.
    Temperature: add AR6-like delta scaled by horizon.
    Precipitation: multiply by (1 + delta%).
    Wind: low confidence on mean changes; keep 0% unless specified.
    """
    base_year = annual.index[-1].year
    baseline_temp = annual['tavg'].tail(30).mean()  # 30y climatology
    baseline_prcp = annual['prcp'].tail(30).mean()
    baseline_wind = annual['wind'].tail(30).mean()

    rows = []
    for scen, vals in scenarios.items():
        # Map horizon to delta using simple piecewise linear approach: 2100 target, then 2300 extension; 3025 extrapolation
        horizon_years = [10, 100, 1000]
        for h in horizon_years:
            target_year = base_year + h
            # Temp delta
            if target_year <= 2100:
                frac = (target_year - base_year) / (2100 - base_year)
                dT = vals['temp_2100'] * max(0, min(1, frac))
            elif target_year <= 2300:
                dT_2300 = vals['temp_2100'] * EXTENSION_MULTIPLIER_2300[scen]
                frac = (target_year - 2100) / (2300 - 2100)
                dT = vals['temp_2100'] + frac * (dT_2300 - vals['temp_2100'])
            else:
                # 3025: freeze at 2300 level (conservative) to avoid wild extrapolation
                dT = vals['temp_2100'] * EXTENSION_MULTIPLIER_2300[scen]

            # Precipitation delta
            if target_year <= 2100:
                frac = (target_year - base_year) / (2100 - base_year)
                dP_pct = vals['prc_2100_pct'] * max(0, min(1, frac))
            else:
                dP_pct = vals['prc_2100_pct']  # hold

            # Wind delta – keep 0 unless specified
            dW_pct = vals.get('wind_2100_pct', 0)

            proj_temp = baseline_temp + dT
            proj_prcp = baseline_prcp * (1 + dP_pct/100.0)
            proj_wind = baseline_wind * (1 + dW_pct/100.0)

            rows.append({
                'scenario': scen,
                'target_year': target_year,
                'horizon_years': h,
                'delta_T_C': round(float(dT), 3),
                'delta_P_pct': round(float(dP_pct), 2),
                'delta_W_pct': round(float(dW_pct), 2),
                'proj_tavg_C': round(float(proj_temp), 3),
                'proj_prcp_mm_y': round(float(proj_prcp), 1),
                'proj_wind_avg': round(float(proj_wind), 3)
            })
    return pd.DataFrame(rows).sort_values(['scenario','horizon_years'])

# ---------------------------
# EXPORTS
# ---------------------------
def to_excel(raw, monthly, annual, projections, out_path):
    with pd.ExcelWriter(out_path, engine='openpyxl') as xw:
        raw.to_excel(xw, sheet_name='RawHistorical')
        monthly.to_excel(xw, sheet_name='MonthlyAgg')
        annual.to_excel(xw, sheet_name='AnnualAgg')
        projections.to_excel(xw, sheet_name='Projections', index=False)

        # Methods / Assumptions sheets
        methods = pd.DataFrame({
            'Section':[
                'Data source','Station','Period','Variables','Aggregation',
                'Scenarios','Uncertainties','Limitations'
            ],
            'Details':[
                'Meteostat Python library (meteostat.net) – daily observations',
                f'Brno–Tuřany, Meteostat/WMO station {STATION_ID} (ICAO LKTB)',
                f'{START.date()} to {END.date()} (as available)',
                'Daily tavg, tmin, tmax (°C), precipitation (mm), wind speed (m/s or km/h converted to m/s if needed)',
                'Monthly mean temperatures & winds; monthly sum precipitation. Annual analogues.',
                'AR6-informed deltas for Central Europe (SSP1-2.6, SSP2-4.5, SSP5-8.5) – see Assumptions',
                'Observational gaps; inhomogeneities; station moves; spatial representativeness; scenario spread; internal variability',
                '1000-year horizon is illustrative only; we freeze post-2300 deltas to avoid non-physical extrapolation'
            ]
        })
        methods.to_excel(xw, sheet_name='Methods', index=False)

        assumptions = pd.DataFrame({
            'Item':[
                'Temp delta 2100 (°C) – SSP1-2.6','Temp delta 2100 (°C) – SSP2-4.5','Temp delta 2100 (°C) – SSP5-8.5',
                'Precip delta 2100 (%) – SSP1-2.6','Precip delta 2100 (%) – SSP2-4.5','Precip delta 2100 (%) – SSP5-8.5',
                'Wind delta 2100 (%) – all SSPs','Extension to 2300 (multiplier)','Freeze beyond 2300'
            ],
            'Value':[
                1.5, 2.7, 4.4,
                2, 4, 7,
                0, 'SSP1-2.6:1.1, SSP2-4.5:1.6, SSP5-8.5:2.5',
                'Yes – constant deltas after 2300'
            ],
            'Source':[
                'IPCC AR6 WGI Europe factsheet','IPCC AR6 WGI Europe factsheet','IPCC AR6 WGI Europe factsheet',
                'IPCC AR6 WGI Europe factsheet','IPCC AR6 WGI Europe factsheet','IPCC AR6 WGI Europe factsheet',
                'Low confidence in mean wind change','IPCC AR6 WGI Chapter 4 extension ranges','This analysis choice'
            ]
        })
        assumptions.to_excel(xw, sheet_name='Assumptions', index=False)

def to_pdf(annual, projections, out_pdf):
    with PdfPages(out_pdf) as pdf:
        # Title page
        fig = plt.figure(figsize=(8.27, 11.69))
        fig.text(0.5, 0.8, "Brno – Historická data a klimatické scénáře", ha='center', fontsize=18)
        fig.text(0.5, 0.74, "Teplota, vítr, srážky", ha='center', fontsize=12)
        fig.text(0.5, 0.68, f"Data: Meteostat (Brno–Tuřany {STATION_ID})", ha='center', fontsize=10)
        fig.text(0.5, 0.64, f"Zpracování: Python (pandas, matplotlib) – {datetime.now().date()}", ha='center', fontsize=10)
        fig.text(0.1, 0.54, "Soubor shrnuje pozorování (ročně) a jednoduché scénáře (SSP1-2.6, SSP2-4.5, SSP5-8.5)\n"
                             "pro horizonty +10, +100 a +1000 let. Scénáře vycházejí z IPCC AR6 regionálních odhadů\n"
                             "pro střední Evropu. 1000letý horizont je pouze ilustrativní a vykresluje zafixované hodnoty po roce 2300.", fontsize=9)
        pdf.savefig(fig); plt.close(fig)

        # Temperature trend
        fig = plt.figure(figsize=(8.27, 5))
        ax = fig.add_subplot(111)
        annual['tavg'].plot(ax=ax)
        ax.set_title('Roční průměrná teplota – Brno (historie)')
        ax.set_xlabel('Rok'); ax.set_ylabel('°C')
        pdf.savefig(fig); plt.close(fig)

        # Precipitation trend
        fig = plt.figure(figsize=(8.27, 5))
        ax = fig.add_subplot(111)
        annual['prcp'].plot(ax=ax)
        ax.set_title('Roční úhrn srážek – Brno (historie)')
        ax.set_xlabel('Rok'); ax.set_ylabel('mm/rok')
        pdf.savefig(fig); plt.close(fig)

        # Projections table snapshot
        fig = plt.figure(figsize=(8.27, 5))
        ax = fig.add_subplot(111)
        ax.axis('off')
        txt = projections.to_string(index=False)
        ax.text(0.01, 0.99, txt, family='monospace', va='top')
        ax.set_title('Projekce – přehled')
        pdf.savefig(fig); plt.close(fig)

def main():
    station_id = get_station_id()
    raw = fetch_daily(station_id)
    # Ensure DateTimeIndex
    raw.index = pd.to_datetime(raw.index)
    raw = raw.sort_index()

    monthly, annual = aggregate(raw)

    # Build projections
    projections = build_projections(annual, SCENARIOS)

    # Save Excel
    out_xlsx = "brno_climate_excel.xlsx"
    to_excel(raw, monthly, annual, projections, out_xlsx)

    # Save PDF summary
    out_pdf = "brno_climate_summary.pdf"
    to_pdf(annual, projections, out_pdf)

    print("Done. Files written:")
    print("-", out_xlsx)
    print("-", out_pdf)

if __name__ == "__main__":
    main()
