from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ------------------------------------------------------------
# Konfigurasi aplikasi
# ------------------------------------------------------------
st.set_page_config(
    page_title="London Bike Sharing | Analisis Penyewaan",
    page_icon="🚲",
    layout="wide",
)

_BASE_DIR = Path(__file__).parent
_CANDIDATES = [
    _BASE_DIR / "london_bike_sharing_clean_v2.xlsx",
]
DATA_PATH = next((p for p in _CANDIDATES if p.exists()), _CANDIDATES[0])
SHEET_NAME = "Clean"

SEASON_COLORS = {
    "Musim Semi": "#5FAE7E",
    "Musim Panas": "#E8A33D",
    "Musim Gugur": "#C8693A",
    "Musim Dingin": "#4F7CAC",
}

COLORS = {
    "blue": "#2F6B9A",
    "teal": "#2A8C82",
    "orange": "#D99028",
    "navy": "#233B53",
    "light_blue": "#A9C9DE",
}
SEASON_LABELS = {
    0: "Musim Semi",
    1: "Musim Panas",
    2: "Musim Gugur",
    3: "Musim Dingin",
}
WEEKDAY_LABELS = {
    "Monday": "Senin",
    "Tuesday": "Selasa",
    "Wednesday": "Rabu",
    "Thursday": "Kamis",
    "Friday": "Jumat",
    "Saturday": "Sabtu",
    "Sunday": "Minggu",
}
WEEKDAY_ORDER = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


# ------------------------------------------------------------
# Memuat dan menyiapkan data
# ------------------------------------------------------------
@st.cache_data
def load_data(file_path: str, sheet_name: str) -> pd.DataFrame:
    """Membaca dataset dan menyiapkan kolom untuk analisis dashboard."""
    data = pd.read_excel(file_path, sheet_name=sheet_name)

    required = {
        "timestamp", "cnt", "t1", "t2", "hum", "wind_speed",
        "weather_code", "is_holiday", "is_weekend", "season",
    }
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(
            "Kolom wajib tidak ditemukan: " + ", ".join(sorted(missing))
        )

    data["timestamp"] = pd.to_datetime(data["timestamp"], errors="coerce")
    numeric_cols = [
        "cnt", "t1", "t2", "hum", "wind_speed",
        "weather_code", "is_holiday", "is_weekend", "season",
    ]
    for col in numeric_cols:
        data[col] = pd.to_numeric(data[col], errors="coerce")

    # Kolom cuaca yang kosong tetap dipertahankan agar tidak mengurangi data
    # untuk analisis waktu dan penyewaan.
    data = data.dropna(subset=["timestamp", "cnt"]).copy()
    data = data[data["cnt"] >= 0].copy()
    data["cnt"] = data["cnt"].round().astype("int64")

    data["date"] = data["timestamp"].dt.date
    
    data["hour"] = data["timestamp"].dt.hour
    data["weekday_en"] = data["timestamp"].dt.day_name()
    data["weekday_label"] = data["weekday_en"].map(WEEKDAY_LABELS)
    data["season_label"] = data["season"].map(SEASON_LABELS).fillna("Tidak diketahui")
    data["holiday_label"] = data["is_holiday"].map(
        {0: "Bukan hari libur", 1: "Hari libur"}
    ).fillna("Tidak diketahui")
    data["weekend_label"] = data["is_weekend"].map(
        {0: "Hari kerja", 1: "Akhir pekan"}
    ).fillna("Tidak diketahui")

    return data


if not DATA_PATH.exists():
    st.error(
        f"File dataset tidak ditemukan: `{DATA_PATH.name}`. "
        "Letakkan file Excel di folder yang sama dengan `app.py`, "
        "atau sesuaikan nilai `DATA_PATH`."
    )
    st.stop()

try:
    df = load_data(str(DATA_PATH), SHEET_NAME)
except ValueError as error:
    st.error(str(error))
    st.stop()
except Exception as error:
    st.error(
        "Dataset tidak dapat dibaca. Pastikan file Excel, nama sheet, "
        f"dan format kolom sudah sesuai. Detail: {error}"
    )
    st.stop()

if df.empty:
    st.error("Tidak ada observasi valid untuk dianalisis.")
    st.stop()

valid_dates = df["timestamp"].dropna()
if valid_dates.empty:
    st.error("Kolom `timestamp` tidak memiliki tanggal yang valid.")
    st.stop()


# ------------------------------------------------------------
# Judul
# ------------------------------------------------------------
st.title("London Bike Sharing")
st.caption(
    "Dashboard analisis pola penyewaan sepeda berdasarkan waktu, musim, "
    "dan kondisi cuaca. Gunakan filter untuk melihat periode dan kelompok data tertentu."
)


# ------------------------------------------------------------
# Filter
# ------------------------------------------------------------
st.sidebar.header("Filter Analisis")

min_date = valid_dates.min().date()
max_date = valid_dates.max().date()
date_range = st.sidebar.date_input(
    "Periode",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

season_options = sorted(df["season_label"].dropna().unique().tolist())
selected_seasons = st.sidebar.multiselect(
    "Musim",
    options=season_options,
    default=season_options,
)

day_options = ["Hari kerja", "Akhir pekan", "Tidak diketahui"]
selected_days = st.sidebar.multiselect(
    "Jenis hari",
    options=day_options,
    default=day_options,
)

holiday_options = ["Bukan hari libur", "Hari libur", "Tidak diketahui"]
selected_holidays = st.sidebar.multiselect(
    "Status hari libur",
    options=holiday_options,
    default=holiday_options,
)

if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date = end_date = date_range

start_ts = pd.Timestamp(start_date)
end_ts = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)

mask = (
    df["timestamp"].between(start_ts, end_ts)
    & df["season_label"].isin(selected_seasons)
    & df["weekend_label"].isin(selected_days)
    & df["holiday_label"].isin(selected_holidays)
)
fdf = df.loc[mask].copy()

if fdf.empty:
    st.warning("Tidak ada data untuk kombinasi filter tersebut. Perluas periode atau pilihan filter.")
    st.stop()


# ------------------------------------------------------------
# KPI utama
# ------------------------------------------------------------
total_rentals = int(fdf["cnt"].sum())
average_per_observation = float(fdf["cnt"].mean())
observation_count = len(fdf)
active_days = fdf["timestamp"].dt.date.nunique()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Penyewaan", f"{total_rentals:,}")
k2.metric("Rata-rata per Observasi", f"{average_per_observation:,.1f}")
k3.metric("Hari dalam Periode Terpilih", f"{active_days:,}")
k4.metric("Jumlah Observasi", f"{observation_count:,}")
st.divider()


# ------------------------------------------------------------
# Format grafik yang konsisten
# ------------------------------------------------------------
def style_chart(fig, height: int = 360):
    fig.update_layout(
        height=height,
        margin=dict(l=18, r=18, t=65, b=22),
        title_font_size=16,
        font=dict(size=12),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend_title_text="",
        hoverlabel=dict(namelength=-1),
    )
    fig.update_xaxes(showgrid=False, automargin=True)
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.20)", zeroline=False, automargin=True)
    return fig


dated = fdf.dropna(subset=["timestamp"]).copy()
dated["day"] = dated["timestamp"].dt.floor("D")


# ------------------------------------------------------------
# Grafik 1: tren harian dan pola rata-rata per jam
# ------------------------------------------------------------
left, right = st.columns(2)

with left:
    daily = (
        dated.groupby("day", as_index=False)
        .agg(total_rentals=("cnt", "sum"))
        .sort_values("day")
    )
    fig = px.line(
        daily,
        x="day",
        y="total_rentals",
        title="Tren Total Penyewaan Harian",
        labels={"day": "Tanggal", "total_rentals": "Total penyewaan"},
    )
    fig.update_traces(
        line=dict(color=COLORS["blue"], width=2.5),
        hovertemplate="Tanggal: %{x|%d %b %Y}<br>Total penyewaan: %{y:,}<extra></extra>",
    )
    st.plotly_chart(style_chart(fig), use_container_width=True)

with right:
    # Rata-rata dihitung hanya dari observasi yang tersedia pada setiap jam.
    by_hour = (
        fdf.groupby("hour", as_index=False)
        .agg(average_rentals=("cnt", "mean"), observations=("cnt", "size"))
        .sort_values("hour")
    )
    fig = px.line(
        by_hour,
        x="hour",
        y="average_rentals",
        title="Rata-rata Penyewaan Menurut Jam",
        labels={"hour": "Jam dalam sehari", "average_rentals": "Rata-rata penyewaan"},
        markers=True,
        custom_data=["observations"],
    )
    fig.update_traces(
        line=dict(color=COLORS["teal"], width=2.5),
        marker=dict(size=6),
        hovertemplate=(
            "Pukul %{x}:00<br>Rata-rata penyewaan: %{y:,.1f}"
            "<br>Jumlah observasi: %{customdata[0]:,}<extra></extra>"
        ),
    )
    fig.update_xaxes(
        tickmode="array",
        tickvals=list(range(0, 24, 2)),
        ticktext=[f"{hour:02d}:00" for hour in range(0, 24, 2)],
        title="Jam",
    )
    st.plotly_chart(style_chart(fig), use_container_width=True)

st.divider()


# ------------------------------------------------------------
# Grafik 2: penyewaan menurut musim dan distribusi penyewaan
# ------------------------------------------------------------
left, right = st.columns(2)

with left:
    by_season = (
        fdf.groupby("season_label", as_index=False)
        .agg(total_rentals=("cnt", "sum"))
        .sort_values("total_rentals", ascending=False)
    )
    fig = px.pie(
        by_season,
        names="season_label",
        values="total_rentals",
        hole=0.45,
        title="Proporsi Total Penyewaan Menurut Musim",
        color="season_label",
        color_discrete_map=SEASON_COLORS,
    )
    fig.update_traces(
        sort=False,
        direction="clockwise",
        textinfo="percent",
        textposition="inside",
        textfont=dict(size=13, color="white"),
        marker=dict(line=dict(color="white", width=2)),
        hovertemplate="%{label}<br>Total penyewaan: %{value:,}<br>Proporsi: %{percent}<extra></extra>",
    )
    fig.add_annotation(
        text=f"<b>{total_rentals:,}</b><br><span style='font-size:12px'>total penyewaan</span>",
        x=0.5, y=0.5, showarrow=False, font=dict(size=18),
    )
    fig = style_chart(fig)
    fig.update_layout(
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)

with right:
    fig = px.histogram(
        fdf,
        x="cnt",
        nbins=30,
        title="Distribusi Jumlah Penyewaan per Observasi",
        labels={"cnt": "Jumlah penyewaan pada satu observasi", "count": "Frekuensi observasi"},
        color_discrete_sequence=[COLORS["orange"]],
    )
    fig.update_layout(yaxis_title="Jumlah observasi", bargap=0.06)
    st.plotly_chart(style_chart(fig), use_container_width=True)

st.divider()


# ------------------------------------------------------------
# Grafik 3: suhu dan pola hari-jam
# ------------------------------------------------------------
left, right = st.columns(2)

with left:
    # Kelompok suhu membuat pola lebih mudah dibaca daripada scatter plot padat.
    temp_df = fdf.dropna(subset=["t1", "cnt"]).copy()
    if not temp_df.empty:
        temp_df["rentang_suhu"] = pd.cut(
            temp_df["t1"],
            bins=[-float("inf"), 0, 5, 10, 15, 20, 25, 30, float("inf")],
            labels=[
                "≤ 0°C", "0–5°C", "5–10°C", "10–15°C",
                "15–20°C", "20–25°C", "25–30°C", "> 30°C",
            ],
            right=False,
            ordered=True,
        )
        by_temp = (
            temp_df.groupby("rentang_suhu", observed=False, as_index=False)
            .agg(
                average_rentals=("cnt", "mean"),
                observations=("cnt", "size"),
            )
            .dropna(subset=["average_rentals"])
        )
        fig = px.bar(
            by_temp,
            x="rentang_suhu",
            y="average_rentals",
            title="Rata-rata Penyewaan Menurut Rentang Suhu",
            labels={
                "rentang_suhu": "Rentang suhu (°C)",
                "average_rentals": "Rata-rata penyewaan",
            },
            color_discrete_sequence=[COLORS["blue"]],
            custom_data=["observations"],
        )
        fig.update_traces(
            hovertemplate=(
                "Rentang suhu: %{x}<br>Rata-rata penyewaan: %{y:,.1f}"
                "<br>Jumlah observasi: %{customdata[0]:,}<extra></extra>"
            )
        )
        st.plotly_chart(style_chart(fig, 390), use_container_width=True)
    else:
        st.info("Tidak ada data suhu yang valid pada filter saat ini.")

with right:
    heat = fdf.pivot_table(
        index="weekday_label",
        columns="hour",
        values="cnt",
        aggfunc="mean",
        observed=False,
    )
    heat = heat.reindex(index=WEEKDAY_ORDER, columns=range(24))
    fig = go.Figure(
        go.Heatmap(
            z=heat.values,
            x=[f"{h:02d}" for h in heat.columns],
            y=heat.index.tolist(),
            colorscale="YlGnBu",
            xgap=2,
            ygap=2,
            hoverongaps=False,
            colorbar=dict(title="Rata-rata<br>penyewaan", thickness=12, len=0.9),
            hovertemplate=(
                "%{y}, pukul %{x}:00<br>Rata-rata penyewaan: %{z:,.0f}<extra></extra>"
            ),
        )
    )
    fig.update_layout(title="Pola Rata-rata Penyewaan: Hari dan Jam")
    fig = style_chart(fig, 390)
    fig.update_xaxes(title="Jam dalam sehari", dtick=2, showgrid=False, side="bottom")
    fig.update_yaxes(title="", autorange="reversed", showgrid=False)
    st.plotly_chart(fig, use_container_width=True)

st.divider()


# ------------------------------------------------------------
# Data terfilter
# ------------------------------------------------------------
st.subheader("Data Penyewaan")
st.caption("Tabel berikut mengikuti seluruh filter yang dipilih pada panel samping.")

display_cols = [
    "timestamp", "cnt", "t1", "t2", "hum", "wind_speed",
    "weather_code", "is_holiday", "is_weekend", "season",
]
display_cols = [col for col in display_cols if col in fdf.columns]

st.dataframe(
    fdf[display_cols].sort_values("timestamp", ascending=False),
    use_container_width=True,
    hide_index=True,
)

st.download_button(
    "Unduh Data Terfilter (CSV)",
    data=fdf[display_cols].to_csv(index=False).encode("utf-8"),
    file_name="london_bike_sharing_filtered.csv",
    mime="text/csv",
)