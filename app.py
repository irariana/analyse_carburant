import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st

st.set_page_config(page_title="Marché des carburants", layout="wide")

# Affiche l'en-tête et applique le style des indicateurs.
st.markdown(
    """
    <div style="background:#7e4fc9; padding:8px; border-radius:8px; text-align:center;">
        <h1 style="color:white; margin:0; font-size:1.8rem;">ANALYSE DU MARCHÉ DES CARBURANTS</h1>
    </div>

    <style>
    [data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.10);
        border: 0.5px solid rgba(255, 255, 255, 0.25);
        border-radius: 10px;
        padding: 14px 16px;
    }
    </style>

    """,
    unsafe_allow_html=True,
)

@st.cache_data
def charger_donnees():
    # Charge les quatre sources de données utilisées par l'application.
    prix = pd.read_csv("data/fait_prix.csv", sep=";")
    carburants = pd.read_csv("data/dim_carburant.csv", sep=";")
    stations = pd.read_csv("data/dim_station.csv", sep=";")
    localisations = pd.read_csv("data/dim_localisation.csv", sep=";")

    # Relie les prix aux informations sur les carburants, stations et localisations.
    df = (
        prix
        .merge(carburants, on="id_carburant", how="left")
        .merge(stations, on="id_station", how="left")
        .merge(localisations, on="id_localisation", how="left")
    )
    # Traite les valeurs manquantes et transforme les dates au format exploitable.
    df["region"] = df["region"].fillna("Non renseignée")
    df["date"] = pd.to_datetime(df["id_date"].astype(str), format="%Y%m%d")
    return df


df = charger_donnees()
st.caption(f"Dernière mise à jour des prix : {df['date'].max():%d/%m/%Y}")

col_filtres, col_milieu, col_carte = st.columns([1, 3, 2])

# Permet de sélectionner un carburant et les régions à afficher.
with col_filtres:
    st.subheader("Type de carburant")
    carburant = st.radio(
        "Carburant",
        sorted(df["nom"].unique()),
        index=None,
        label_visibility="collapsed",
    )

    st.subheader("Région")
    toutes_regions = sorted(df["region"].unique())
    regions = st.multiselect(
        "Régions",
        toutes_regions,
        default=toutes_regions,
        label_visibility="collapsed",
    )

    masquer = st.checkbox("Masquer les prix aberrants", value=True)

if carburant is None:
    st.info("Choisis un type de carburant pour commencer.")
    st.stop()

# Sélectionne les stations correspondant au carburant choisi.
df_carb = df[df["nom"] == carburant]

# Écarte les prix supérieurs à 1,5 fois le prix médian.
if masquer:
    seuil = 1.5 * df_carb["prix"].median()
    df_carb = df_carb[df_carb["prix"] <= seuil]

# Applique le filtre des régions aux données sélectionnées.
df_f = df_carb[df_carb["region"].isin(regions)]

if df_f.empty:
    st.warning("Aucune station ne correspond à ces filtres.")
    st.stop()

# Présente les stations les moins chères, les indicateurs et le classement par région.
with col_milieu:
    st.markdown("**Top 5 des adresses les moins chères**")
    top5 = df_f.nsmallest(5, "prix")[["adresse", "ville", "prix"]]
    st.dataframe(
        top5,
        hide_index=True,
        width="stretch",
        column_config={"prix": st.column_config.NumberColumn("Prix", format="%.3f €")},
    )
    k1, k2, k3 = st.columns(3)
    k1.metric("Prix max", f"{df_f['prix'].max():.3f} €")
    k2.metric("Prix min", f"{df_f['prix'].min():.3f} €")

    moyenne_nationale = df_carb["prix"].mean()
    k3.metric(
        "Prix moyen",
        f"{df_f['prix'].mean():.3f} €",
    )

    st.markdown("**Prix moyen par région**")

    par_region = (
        df_f.groupby("region", as_index=False)["prix"].mean()
        .sort_values("prix")
    )

    # Crée un graphique horizontal pour comparer les prix moyens régionaux.
    fig = px.bar(
        par_region,
        x="prix",
        y="region",
        orientation="h",
        text=par_region["prix"].round(3),
        color_discrete_sequence=["#c9a8ff"],
    )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=300,
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis_title="Prix moyen (€)",
        yaxis_title=None,
    )
    st.plotly_chart(fig, width="stretch")

with col_carte:
    st.markdown(f"**Prix du {carburant} par station** (vert = pas cher, rouge = cher)")

    # Normalise les prix afin d'attribuer une couleur à chaque station.
    bas, haut = df_f["prix"].quantile([0.05, 0.95])
    t = ((df_f["prix"] - bas) / (haut - bas)).clip(0, 1)

    df_map = df_f[["adresse", "ville", "latitude", "longitude", "prix"]].copy()
    df_map["couleur"] = [[int(255 * x), int(255 * (1 - x)), 60, 200] for x in t]

    couche = pdk.Layer(
        "ScatterplotLayer",
        data=df_map,
        get_position="[longitude, latitude]",
        get_fill_color="couleur",
        get_radius=2000,
        radius_min_pixels=3,
        radius_max_pixels=10,
        pickable=True,
    )
    vue = pdk.ViewState(latitude=46.6, longitude=2.5, zoom=4.8)
    st.pydeck_chart(
        pdk.Deck(
            layers=[couche],
            initial_view_state=vue,
            map_style="road",
            tooltip={"text": "{adresse}, {ville}\n{prix} €"},
        ),
        height=560,
    )