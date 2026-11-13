# Human Mobility in Yogyakarta

Group project: analytics and visualization of human mobility in DIY Yogyakarta.

## Data sources
1. JogjaPulse (Widyawan et al., 2026), Zenodo, https://doi.org/10.5281/zenodo.23157460 (CC BY 4.0)
2. Google COVID-19 Community Mobility Reports, filtered to DI Yogyakarta
3. Weather and holiday calendar (daily, Dec 2021 - Apr 2022)

## Run
    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    python src/download_data.py
    jupyter notebook

## Structure
- src/ scripts, notebooks/ analysis, figures/ exported plots, data/ (git-ignored)

## Team
- Calvin (add teammates)
