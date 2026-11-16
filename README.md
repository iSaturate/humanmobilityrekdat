# Human Mobility in Yogyakarta

Group project (Universitas Gadjah Mada): analytics and visualization of human mobility in the Special Region of Yogyakarta (DIY), Dec 2021 – Apr 2022.

## Data sources
1. **JogjaPulse** (Widyawan et al., 2026), Zenodo, https://doi.org/10.5281/zenodo.23157460 (CC BY 4.0). Aggregated, k-anonymized (k=5) device presence at 500 m grid-day and kapanewon-hour level, plus monthly home-based OD flows.
2. **Google COVID-19 Community Mobility Reports**, filtered to DI Yogyakarta. Daily % change in visits by place category.
3. **Weather and holiday calendar** (daily, Dec 2021 – Apr 2022).

## How to run (Google Colab)
Open a notebook from `notebooks/` in Colab, then run this in the first cell:

```python
!git clone https://github.com/iSaturate/humanmobilityrekdat.git
%cd humanmobilityrekdat
!pip install -q geopandas folium plotly pyproj
!python src/download_data.py
```

Raw data is not stored in the repo. `src/download_data.py` downloads it into `data/raw/`.

Local alternative:
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python src/download_data.py
jupyter notebook
```

## Structure
```
src/         scripts (data download)
notebooks/   analysis notebooks
figures/     exported plots
data/        raw/processed data (git-ignored)
```

## Notebooks
| Notebook | Owner | Content |
|---|---|---|
| `02_person_a_eda.ipynb` | Person A | Cleaning and EDA of grid and hourly presence |
| `03_...` | Person B | Maps and OD flows |
| `04_...` | Person C | Merge with Google Mobility, weather, holidays |

## Limitations
- Rows with fewer than 5 devices are suppressed, so missing rows are not true zeros.
- March and April 2022 are flagged by the dataset authors as reduced quality (small device panel).
- Presence counts devices, not people, and the panel is not a random sample of the population.

## Team
- Calvin
- (add teammates' names)

## Citation
Widyawan, Pratama, A. R., Ariansyah, A., Farda, N. M., Pramana, S., & Miller, O. (2026). *JogjaPulse: An Aggregated Spatio-Temporal Mobility Dataset for Yogyakarta, Indonesia* (v1). Zenodo. https://doi.org/10.5281/zenodo.23157460
