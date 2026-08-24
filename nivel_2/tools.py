"""
Ferramentas de consulta para o agente do Nível 2.

As funções públicas exigidas pelo desafio são:
- historico_cliente(cliente_id)
- operacoes_do_dia(cliente_id, data)
- perfil_canal(cliente_id)

Os cálculos permanecem em pandas. A LLM recebe apenas fatos já calculados.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
DADOS_PATH = BASE_DIR / "dados" / "dados_nivel_2.json"


@lru_cache(maxsize=1)
def carregar_base() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Carrega, limpa, normaliza e adiciona as flags determinísticas."""
    with open(DADOS_PATH, encoding="utf-8") as f:
        payload = json.load(f)

    taxa = float(payload["taxa_cambio_usd_brl"])
    bruto = pd.DataFrame(payload["operacoes"]).copy()

    # Decisão: ID é chave de operação. Duplicatas exatas são removidas.
    df = bruto.drop_duplicates(subset=["id"], keep="first").copy()
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df["valor_brl"] = np.where(
        df["moeda"].astype(str).str.upper().eq("USD"),
        df["valor"].astype(float) * taxa,
        df["valor"].astype(float),
    )

    # Regra 1
    dia = (
        df.dropna(subset=["data"])
        .groupby(["cliente_id", "data"], as_index=False)
        .agg(
            qtd_operacoes_dia=("id", "size"),
            volume_dia_brl=("valor_brl", "sum"),
            maior_operacao_dia_brl=("valor_brl", "max"),
        )
    )
    dia["flag_fracionamento_grupo"] = (
        (dia["qtd_operacoes_dia"] >= 3)
        & (dia["volume_dia_brl"] > 50_000)
        & (dia["maior_operacao_dia_brl"] < 20_000)
    )
    df = df.merge(dia, on=["cliente_id", "data"], how="left")
    df["flag_fracionamento"] = df["flag_fracionamento_grupo"].eq(True)

    # Regra 2
    stats = (
        df.groupby("cliente_id", as_index=False)
        .agg(
            qtd_operacoes_cliente=("id", "size"),
            mediana_cliente_brl=("valor_brl", "median"),
        )
    )
    df = df.merge(stats, on="cliente_id", how="left")
    df["limite_atipico_brl"] = 5 * df["mediana_cliente_brl"]
    df["flag_valor_atipico"] = (
        (df["qtd_operacoes_cliente"] >= 4)
        & (df["valor_brl"] > df["limite_atipico_brl"])
    )
    return df, dia


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].dt.strftime("%Y-%m-%d")
    out = out.replace({np.nan: None, pd.NaT: None})
    return out.to_dict(orient="records")


def historico_cliente(cliente_id: str) -> dict[str, Any]:
    """Resumo agregado das operações do cliente."""
    df, dia = carregar_base()
    c = df[df["cliente_id"] == cliente_id].copy()
    if c.empty:
        return {"erro": f"cliente {cliente_id} não encontrado"}

    dias_fracionamento = dia[
        (dia["cliente_id"] == cliente_id) & dia["flag_fracionamento_grupo"]
    ].copy()
    atipicas = c[c["flag_valor_atipico"]].copy()

    return {
        "cliente_id": cliente_id,
        "qtd_operacoes": int(len(c)),
        "volume_total_brl": round(float(c["valor_brl"].sum()), 2),
        "valor_medio_brl": round(float(c["valor_brl"].mean()), 2),
        "mediana_brl": round(float(c["valor_brl"].median()), 2),
        "valor_maximo_brl": round(float(c["valor_brl"].max()), 2),
        "data_min": None if c["data"].isna().all() else c["data"].min().strftime("%Y-%m-%d"),
        "data_max": None if c["data"].isna().all() else c["data"].max().strftime("%Y-%m-%d"),
        "qtd_datas_ausentes": int(c["data"].isna().sum()),
        "alertas_fracionamento": int(len(dias_fracionamento)),
        "alertas_valor_atipico": int(len(atipicas)),
        "dias_fracionamento": _records(
            dias_fracionamento[
                ["data", "qtd_operacoes_dia", "volume_dia_brl", "maior_operacao_dia_brl"]
            ]
        ),
        "operacoes_atipicas": _records(
            atipicas[
                ["id", "data", "valor_brl", "mediana_cliente_brl", "limite_atipico_brl", "canal", "tipo"]
            ]
        ),
    }


def operacoes_do_dia(cliente_id: str, data: str) -> dict[str, Any]:
    """Recorte das operações de um cliente numa data específica."""
    df, _ = carregar_base()
    dt = pd.to_datetime(data, errors="coerce")
    if pd.isna(dt):
        return {"erro": f"data inválida: {data}"}

    c = df[(df["cliente_id"] == cliente_id) & (df["data"] == dt)].copy()
    if c.empty:
        return {
            "cliente_id": cliente_id,
            "data": data,
            "qtd_operacoes": 0,
            "volume_total_brl": 0.0,
            "operacoes": [],
        }

    cols = ["id", "data", "valor_brl", "canal", "tipo", "contraparte",
            "flag_fracionamento", "flag_valor_atipico"]
    return {
        "cliente_id": cliente_id,
        "data": data,
        "qtd_operacoes": int(len(c)),
        "volume_total_brl": round(float(c["valor_brl"].sum()), 2),
        "operacoes": _records(c[cols]),
    }


def perfil_canal(cliente_id: str) -> dict[str, Any]:
    """Distribuição de uso por canal, em quantidade e volume."""
    df, _ = carregar_base()
    c = df[df["cliente_id"] == cliente_id].copy()
    if c.empty:
        return {"erro": f"cliente {cliente_id} não encontrado"}

    p = (
        c.groupby("canal", as_index=False)
        .agg(qtd_operacoes=("id", "size"), volume_brl=("valor_brl", "sum"))
        .sort_values(["qtd_operacoes", "volume_brl"], ascending=False)
    )
    p["percentual_operacoes"] = (100 * p["qtd_operacoes"] / len(c)).round(2)
    p["volume_brl"] = p["volume_brl"].round(2)

    return {
        "cliente_id": cliente_id,
        "total_operacoes": int(len(c)),
        "distribuicao": _records(p),
    }


def ranking_sinalizados(top_n: int = 10) -> pd.DataFrame:
    """Ranking por alertas distintos, com volume total como desempate."""
    df, dia = carregar_base()

    r1 = (
        dia[dia["flag_fracionamento_grupo"]]
        .groupby("cliente_id")
        .size()
        .rename("alertas_fracionamento")
    )
    r2 = (
        df[df["flag_valor_atipico"]]
        .groupby("cliente_id")
        .size()
        .rename("alertas_valor_atipico")
    )
    volume = df.groupby("cliente_id")["valor_brl"].sum().rename("volume_total_brl")

    ranking = pd.concat([r1, r2, volume], axis=1).fillna(0)
    ranking["alertas_fracionamento"] = ranking["alertas_fracionamento"].astype(int)
    ranking["alertas_valor_atipico"] = ranking["alertas_valor_atipico"].astype(int)
    ranking["total_sinalizacoes"] = (
        ranking["alertas_fracionamento"] + ranking["alertas_valor_atipico"]
    )
    return (
        ranking.reset_index()
        .query("total_sinalizacoes > 0")
        .sort_values(["total_sinalizacoes", "volume_total_brl"], ascending=[False, False])
        .head(top_n)
        .reset_index(drop=True)
    )
