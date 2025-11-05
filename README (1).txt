
Brno Climate Project — Quick Start
==================================

Co dostáváte v tomto balíčku:
- brno_climate_analysis.py — hlavní skript, který:
  • stáhne historická denní data pro Brno–Tuřany (Meteostat 11723),
  • vyrobí roční & měsíční agregace,
  • vytvoří scénáře pro +10, +100, +1000 let (SSP1-2.6, SSP2-4.5, SSP5-8.5),
  • uloží Excel (brno_climate_excel.xlsx) a PDF (brno_climate_summary.pdf).

Jak spustit (lokálně):
1) Nainstalujte Python 3.10+.
2) Vytvořte prostředí a nainstalujte závislosti:
   pip install pandas numpy matplotlib meteostat openpyxl reportlab
3) Spusťte skript:
   python brno_climate_analysis.py
4) Výstupy najdete ve stejné složce.

Poznámky k metodám a nejistotám:
- Meteostat agreguje data z národních služeb (vč. ČHMÚ) — mohou existovat mezery a změny stanice.
- Trendy jsou lineární; pro robustnost lze doplnit Theil–Sen či LOESS.
- Scénáře vycházejí z IPCC AR6 (Evropa): teplota do 2100 dle SSP, srážky v %; vítr — nízká jistota v průměrné změně.
- 2300: AR6 uvádí rozšířené projekce; zde lineárně roztaženo s multiplikátory a po 2300 zafixováno (pro 3025).
- 1000 let = ilustrace; skutečná predikce vyžaduje paleoklimatické a složité modely s obří nejistotou.

Upravy:
- Časové období (START, END) ve skriptu.
- Stanici lze změnit na nejbližší pomocí geo-koord. v get_station_id().
- Doplňte si regresní metody, sezónní členění (DJF/JJA), extrémy (Rx1day), return levels, atd.


---
## GitHub & Streamlit nasazení

### 1) Struktura repozitáře
```
brno-climate/
├─ app.py                    # Streamlit UI
├─ brno_climate_analysis.py  # batch skript (Excel + PDF)
├─ requirements.txt          # závislosti pro Streamlit/CI
├─ .gitignore
├─ .github/workflows/build-data.yml  # CI, generuje /data artefakty
└─ (volitelně) /data/        # Excel+PDF (CI je sem uloží)
```

### 2) Nasazení na GitHub
1. Vytvoř GitHub repo a nahraj všechny soubory.
2. V Settings → Actions nech povolené GitHub Actions (default OK).
3. Workflow `Build data` poběží na push a týdně. Artefakty najdeš v `/data`.

### 3) Nasazení na Streamlit Cloud
1. Na share.streamlit.io propojit GitHub účet a vybrat repo.
2. Jako hlavní soubor nastav `app.py`. Požadavky bere z `requirements.txt`.
3. Po deploy otevři aplikaci. V levém panelu zvol období a spusť výpočet.
4. Stahování Excel/PDF je dostupné v pravém panelu aplikace.

Tipy:
- Pokud chceš fixní data bez online dotazu, můžeš do `/data` uložit předpočítané CSV a v `app.py` přidat přepínač „použít lokální /data“.
- Caching ve Streamlit (`@st.cache_data`) omezuje počet dotazů na Meteostat.
