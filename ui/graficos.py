"""Figuras reutilizáveis: recebem dados processados, sem acesso às fontes."""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from matplotlib.colors import ListedColormap
from matplotlib.figure import Figure
from matplotlib.patches import Patch

from ui.tema import CORES, NOMES_DOCUMENTOS, NOMES_SERVICOS, RISCOS, escala_risco

MESES = ("Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez")


def _acabamento(fig, altura):
    fig.update_layout(height=altura, margin=dict(l=12, r=12, t=15, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Arial, sans-serif", color=CORES["texto"]),
                      legend=dict(orientation="h", y=-.23, x=0), hovermode="x unified")
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor=CORES["borda"], zeroline=False)
    return fig


def mapa_perdas(quadro, malhas, cfg, altura):
    exibicao = quadro.copy()
    exibicao["risco"] = exibicao.classe.map(lambda c: f"{RISCOS[c][0]} {RISCOS[c][1]}")
    fig = px.choropleth_map(
        exibicao, geojson=malhas, featureidkey="properties.cod_ibge", locations="cod_ibge",
        color="perda_estimada_pct", range_color=(0, 100), color_continuous_scale=escala_risco(cfg),
        hover_name="municipio", hover_data={"cod_ibge": False, "risco": True,
            "perda_estimada_pct": ":.1f", "chuva_mm": ":.0f", "normal_mm": ":.0f", "pedidos": True},
        labels={"perda_estimada_pct": "Perda estimada (%)", "chuva_mm": "Chuva (mm)",
                "normal_mm": "Normal (mm)", "pedidos": "Pedidos", "risco": "Classe"},
        # base cartográfica neutra (CARTO Positron, sem token): estados, litoral e cidades em cinza claro,
        # para que só a escala de risco tenha cor; sem internet o Plotly cai para fundo branco.
        map_style=cfg["interface"].get("mapa_estilo", "carto-positron"), zoom=cfg["interface"]["mapa_zoom"],
        center=cfg["interface"]["mapa_centro"], opacity=0.85,
    )
    fig.update_traces(marker_line_width=1.2, marker_line_color="#3a3a3a")
    fig.update_layout(coloraxis_colorbar=dict(title="Perda %", thickness=12, len=.75), hovermode="closest")
    return _acabamento(fig, altura)


def grafico_chuva(serie, altura, compacto=False, *, cfg, cultura, limiar, evolucao=None):
    """Chuva/normal em mm, faixa de ETc e perda estimada no eixo percentual.

    O limiar é traçado no eixo de perda: não se confunde perda de produção com
    redução percentual de chuva. ETc=Kc×ET0 usa o Kc já configurado no modelo.
    """
    kc = cfg["modelo_hidrico"]["culturas"][cultura]["kc"]
    etc_ano, etc_normal = serie.et0_acum * kc, serie.et0_normal_acum * kc
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=serie.data, y=np.minimum(etc_ano, etc_normal), mode="lines",
                            line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=serie.data, y=np.maximum(etc_ano, etc_normal), mode="lines",
                            fill="tonexty", fillcolor="rgba(87,99,90,.13)", line=dict(width=0),
                            name="Água necessária · ano/normal", hovertemplate="Água necessária: %{y:.0f} mm<extra></extra>"))
    fig.add_trace(go.Scatter(x=serie.data, y=serie.normal_acum, mode="lines", name="Chuva normal",
                            line=dict(color=CORES["muted"], dash="dash", width=2)))
    fig.add_trace(go.Scatter(x=serie.data, y=serie.chuva_acum, mode="lines", name="Chuva da safra",
                            line=dict(color=CORES["primaria"], width=3)))
    if evolucao is not None and not evolucao.empty:
        classe = evolucao.iloc[-1]["classe"]
        fig.add_trace(go.Scatter(x=evolucao.data, y=evolucao.perda_estimada_pct, yaxis="y2",
                                name="Perda estimada (%)", mode="lines+markers",
                                line=dict(color=CORES[classe], width=2)))
        oficial = cfg["risco"]["criterio_garantia_safra"]
        fig.add_shape(type="line", x0=serie.data.min(), x1=serie.data.max(), y0=oficial, y1=oficial,
                      yref="y2", line=dict(color=CORES["alerta"], width=1.5, dash="dot"))
        fig.add_annotation(x=serie.data.iloc[-1], y=oficial, yref="y2", text=f"Critério oficial {oficial}%",
                           showarrow=False, xanchor="right", yshift=10, font=dict(color=CORES["alerta"], size=10))
        if limiar != oficial:
            fig.add_shape(type="line", x0=serie.data.min(), x1=serie.data.max(), y0=limiar, y1=limiar,
                          yref="y2", line=dict(color=CORES["muted"], width=1, dash="dash"))
            fig.add_annotation(x=serie.data.iloc[0], y=limiar, yref="y2", text=f"Triagem {limiar}%",
                               showarrow=False, xanchor="left", yshift=10, font=dict(size=10))
        fig.update_layout(yaxis2=dict(title=None if compacto else "Perda estimada (%)", overlaying="y",
                                     side="right", range=[0, 105], showgrid=False,
                                     tickmode="array", tickvals=[0, 20, 40, 60, 80, 100], ticksuffix="%"))
    _acabamento(fig, altura)
    fig.update_layout(showlegend=not compacto, hoverlabel=dict(namelength=-1))
    fig.update_xaxes(tickformat="%d/%m", title=None)
    fig.update_layout(yaxis=dict(title=None if compacto else "Acumulado (mm)", rangemode="tozero"))
    if evolucao is not None and not evolucao.empty:
        fig.update_layout(yaxis2=dict(showgrid=False))
    return fig


def barras_servicos(agregado, altura):
    if agregado.empty:
        return None
    totais = agregado.groupby("service_id", as_index=False).pedidos.sum().sort_values("pedidos")
    totais["servico"] = totais.service_id.map(lambda s: NOMES_SERVICOS.get(s, s))
    fig = px.bar(totais, x="pedidos", y="servico", orientation="h", text="pedidos",
                 labels={"pedidos": "Pedidos sintéticos", "servico": ""}, color_discrete_sequence=[CORES["primaria"]])
    return _acabamento(fig, altura)


def barras_documentos(resumo, altura):
    totais = {}
    for docs in resumo.docs_mais_faltantes:
        for documento, quantidade in docs.items():
            totais[documento] = totais.get(documento, 0) + quantidade
    if not totais:
        return None
    quadro = pd.DataFrame(totais.items(), columns=["documento", "pedidos"]).sort_values("pedidos")
    quadro["documento"] = quadro.documento.map(lambda s: NOMES_DOCUMENTOS.get(s, s))
    fig = px.bar(quadro, x="pedidos", y="documento", orientation="h", text="pedidos",
                 labels={"pedidos": "Pedidos com pendência", "documento": ""}, color_discrete_sequence=[CORES["alerta"]])
    return _acabamento(fig, altura)


def calendario_seco(serie, limiar_mm):
    meses = sorted(serie.data.dt.month.unique())
    matriz = np.full((len(meses), 31), np.nan)
    for registro in serie.itertuples(index=False):
        matriz[meses.index(registro.data.month), registro.data.day - 1] = int(registro.chuva < limiar_mm)
    figura = Figure(figsize=(12, 2.9), layout="constrained", facecolor=CORES["fundo"])
    eixo = figura.subplots()
    eixo.imshow(np.ma.masked_invalid(matriz), aspect="auto", vmin=0, vmax=1,
                cmap=ListedColormap([CORES["seguro"], CORES["alerta"]]))
    eixo.set_xticks(range(31), labels=range(1, 32), fontsize=8)
    eixo.set_yticks(range(len(meses)), labels=[MESES[m - 1] for m in meses], fontsize=9)
    eixo.set_xlabel("Dia do mês", fontsize=9)
    eixo.set_title(f"{int(np.nansum(matriz))} dias secos · chuva menor que {limiar_mm:g} mm/dia", loc="left", fontsize=11)
    eixo.legend(handles=[Patch(color=CORES["alerta"], label="Dia seco"),
                         Patch(color=CORES["seguro"], label="Dia com chuva")],
                loc="upper center", bbox_to_anchor=(.5, -.27), ncol=2, frameon=False, fontsize=9)
    for borda in eixo.spines.values():
        borda.set_visible(False)
    return figura
