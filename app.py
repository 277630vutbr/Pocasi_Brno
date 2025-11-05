# app.py
# Streamlit app for Brno climate analysis & projections
import streamlit as st
from datetime import datetime, date
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO
from matplotlib.backends.backend_pdf import PdfPages

from meteostat import Stations, Daily

st.set_page_config(page_title="Brno Klima: Historie & Scénáře", layout="wide")

CITY_NAME = "Brno"
DEFAULT_STATION_ID = "11723"   # Brno–Tuřany
COORDS = (49.1951, 16.6068)

SCENARIOS = {
    "SSP1-2.6": {"temp_2100": 1.5, "prc_2100_pct": 2,  "wind_2100_pct": 0},
    "SSP2-4.5": {"temp_2100": 2.7, "prc_2100_pct": 4,  "wind_2100_pct": 0},
    "SSP5-8.5": {"temp_2100": 4.4, "prc_2100_pct": 7,  "wind_2100_pct": 0},
}
EXTENSION_MULTIPLIER_2300 = {"SSP1-2.6": 1.1, "SSP2-4.5": 1.6, "SSP5-8.5": 2.5}

@st.cache_data(show_spinner=True, ttl=3600)
def fetch_daily(station_id: str, start: datetime, end: datetime):
    df = Daily(station_id, start, end).fetch()
    # standardize names
    rename = {'wspd':'wind'}
    for old, new in rename.items():
        if old in df.columns:
            df = df.rename(columns={old:new})
    # keep a subset
    keep = [c for c in ['tavg','tmin','tmax','prcp','wind'] if c in df.columns]
    return df[keep].copy()

def aggregate(df: pd.DataFrame):
    m = df.resample('MS').agg({'tavg':'mean','tmin':'mean','tmax':'mean','prcp':'sum','wind':'mean'})
    a = df.resample('YS').agg({'tavg':'mean','tmin':'mean','tmax':'mean','prcp':'sum','wind':'mean'})
    return m, a

def build_projections(annual: pd.DataFrame, base_year: int, scenarios: dict):
    baseline_temp = annual['tavg'].tail(30).mean()
    baseline_prcp = annual['prcp'].tail(30).mean()
    baseline_wind = annual['wind'].tail(30).mean()
    rows = []
    for scen, vals in scenarios.items():
        for h in [10, 100, 1000]:
            target_year = base_year + h
            # temperature
            if target_year <= 2100:
                frac = (target_year - base_year) / (2100 - base_year)
                dT = vals['temp_2100'] * max(0, min(1, frac))
            elif target_year <= 2300:
                dT_2300 = vals['temp_2100'] * EXTENSION_MULTIPLIER_2300[scen]
                frac = (target_year - 2100) / (2300 - 2100)
                dT = vals['temp_2100'] + frac * (dT_2300 - vals['temp_2100'])
            else:
                dT = vals['temp_2100'] * EXTENSION_MULTIPLIER_2300[scen]
            # precipitation
            if target_year <= 2100:
                frac = (target_year - base_year) / (2100 - base_year)
                dP_pct = vals['prc_2100_pct'] * max(0, min(1, frac))
            else:
                dP_pct = vals['prc_2100_pct']
            dW_pct = vals.get('wind_2100_pct', 0)
            rows.append({
                'scenario': scen,
                'target_year': target_year,
                'horizon_years': h,
                'delta_T_C': round(float(dT), 3),
                'delta_P_pct': round(float(dP_pct), 2),
                'delta_W_pct': round(float(dW_pct), 2),
                'proj_tavg_C': round(float(baseline_temp + dT), 3),
                'proj_prcp_mm_y': round(float(baseline_prcp * (1 + dP_pct/100.0)), 1),
                'proj_wind_avg': round(float(baseline_wind * (1 + dW_pct/100.0)), 3)
            })
    return pd.DataFrame(rows).sort_values(['scenario','horizon_years'])

def to_excel_bytes(raw, monthly, annual, projections):
    import io
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine='openpyxl') as xw:
        raw.to_excel(xw, sheet_name='RawHistorical')
        monthly.to_excel(xw, sheet_name='MonthlyAgg')
        annual.to_excel(xw, sheet_name='AnnualAgg')
        projections.to_excel(xw, sheet_name='Projections', index=False)
        methods = pd.DataFrame({
            'Section':[
                'Data source','Station','Period','Variables','Aggregation',
                'Scenarios','Uncertainties','Limitations'
            ],
            'Details':[
                'Meteostat Python library (meteostat.net) – daily observations',
                'Brno–Tuřany, Meteostat/WMO station 11723 (ICAO LKTB)',
                '1950-01-01 to today (as available)',
                'Daily tavg, tmin, tmax (°C), precipitation (mm), wind speed',
                'Monthly mean temperatures & winds; monthly sum precipitation. Annual analogues.',
                'AR6-informed deltas for Central Europe (SSP1-2.6, SSP2-4.5, SSP5-8.5) – simplified',
                'Observational gaps; inhomogeneities; station moves; representativeness; scenario spread',
                '1000-year horizon is illustrative; post-2300 deltas frozen'
            ]
        })
        methods.to_excel(xw, sheet_name='Methods', index=False)
    bio.seek(0)
    return bio

def to_pdf_bytes(annual, projections):
    buf = BytesIO()
    with PdfPages(buf) as pdf:
        # TAVG plot
        fig = plt.figure(figsize=(8.27, 5))
        ax = fig.add_subplot(111)
        annual['tavg'].plot(ax=ax)
        ax.set_title('Roční průměrná teplota – Brno (historie)')
        ax.set_xlabel('Rok'); ax.set_ylabel('°C')
        pdf.savefig(fig); plt.close(fig)
        # PRCP plot
        fig = plt.figure(figsize=(8.27, 5))
        ax = fig.add_subplot(111)
        annual['prcp'].plot(ax=ax)
        ax.set_title('Roční úhrn srážek – Brno (historie)')
        ax.set_xlabel('Rok'); ax.set_ylabel('mm/rok')
        pdf.savefig(fig); plt.close(fig)
        # Projections table
        fig = plt.figure(figsize=(8.27, 5))
        ax = fig.add_subplot(111); ax.axis('off')
        txt = projections.to_string(index=False)
        ax.text(0.01, 0.99, txt, family='monospace', va='top')
        ax.set_title('Projekce – přehled')
        pdf.savefig(fig); plt.close(fig)
    buf.seek(0)
    return buf

# Sidebar
st.sidebar.header("Nastavení dat")
start = st.sidebar.date_input("Začátek období", value=date(1950,1,1))
end = st.sidebar.date_input("Konec období", value=date.today())
station = st.sidebar.text_input("Meteostat Station ID", value=DEFAULT_STATION_ID)
run = st.sidebar.button("Načíst a zpracovat")

st.title("Brno — Historická data & klimatické scénáře")
st.caption("Teplota, srážky a vítr • Meteostat (Brno–Tuřany 11723) • Scénáře (IPCC AR6)")

if run:
    with st.spinner("Stahuji a zpracovávám data…"):
        raw = fetch_daily(station, datetime.combine(start, datetime.min.time()), datetime.combine(end, datetime.min.time()))
        raw = raw.sort_index()
        monthly, annual = aggregate(raw)
        base_year = annual.index[-1].year
        projections = build_projections(annual, base_year, SCENARIOS)

    col1, col2 = st.columns([2,1])
    with col1:
        st.subheader("Roční průměrná teplota")
        fig = plt.figure(figsize=(8,4)); ax = fig.add_subplot(111)
        annual['tavg'].plot(ax=ax)
        ax.set_xlabel("Rok"); ax.set_ylabel("°C")
        st.pyplot(fig); plt.close(fig)

        st.subheader("Roční úhrn srážek")
        fig = plt.figure(figsize=(8,4)); ax = fig.add_subplot(111)
        annual['prcp'].plot(ax=ax)
        ax.set_xlabel("Rok"); ax.set_ylabel("mm/rok")
        st.pyplot(fig); plt.close(fig)

    with col2:
        st.subheader("Projekce (shrnutí)")
        st.dataframe(projections, use_container_width=True)

        # Downloads
        xls = to_excel_bytes(raw, monthly, annual, projections)
        st.download_button("Stáhnout Excel", data=xls, file_name="brno_climate_excel.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        pdf = to_pdf_bytes(annual, projections)
        st.download_button("Stáhnout PDF", data=pdf, file_name="brno_climate_summary.pdf", mime="application/pdf")

else:
    st.info("V levém panelu zvol období a klikni **Načíst a zpracovat**.")

st.markdown("---")
with st.expander("Metodika, nejistoty a omezení"):
    st.write("""
- **Data:** Meteostat (denní) pro Brno–Tuřany (11723). Může obsahovat mezery, změny stanice apod.
- **Agregace:** měsíční/roční; T a vítr = průměry, srážky = součty.
- **Scénáře:** IPCC AR6 (Evropa) – zjednodušené roční delty (SSP1-2.6, SSP2-4.5, SSP5-8.5).
- **2100–2300:** lineární rozšíření; **po 2300 fix** (pro 1000letý horizont pouze ilustrativně).
- **Vítr:** nízká jistota změny průměru → 0 %.
""")
