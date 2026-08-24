"""
Agente do Nível 2 com seleção dinâmica de ferramentas.

Uso:
    python nivel_2/agente.py

Pré-requisito:
    copie .env.example para .env e preencha GEMINI_API_KEY.

O agente faz duas etapas:
1) a LLM seleciona quais ferramentas são necessárias para o caso;
2) somente as ferramentas escolhidas são executadas e a LLM redige o parecer.

Cálculos e comparações com limites permanecem em pandas.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Literal

import pandas as pd
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

from tools import (
    historico_cliente,
    operacoes_do_dia,
    perfil_canal,
    ranking_sinalizados,
)

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUTS = BASE_DIR / "outputs"
load_dotenv(BASE_DIR / ".env")


class ChamadaFerramenta(BaseModel):
    ferramenta: Literal["historico_cliente", "operacoes_do_dia", "perfil_canal"]
    data: str | None = None
    motivo: str


class PlanoInvestigacao(BaseModel):
    chamadas: list[ChamadaFerramenta] = Field(min_length=1, max_length=3)


class ParecerPLD(BaseModel):
    nivel_risco: Literal["baixo", "médio", "alto"]
    tipologia_suspeita: str
    red_flags: list[str]
    justificativa: str


def _cliente_genai():
    from google import genai
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY não configurada. Copie .env.example para .env e preencha a chave."
        )
    return genai.Client(api_key=api_key)


def _usage(response) -> tuple[int | None, int | None]:
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return None, None
    entrada = getattr(usage, "prompt_token_count", None)
    saida = getattr(usage, "candidates_token_count", None)
    return entrada, saida


def _custo(entrada: int | None, saida: int | None) -> float | None:
    if entrada is None or saida is None:
        return None
    pin = float(os.getenv("COST_PER_1M_INPUT_USD", "0"))
    pout = float(os.getenv("COST_PER_1M_OUTPUT_USD", "0"))
    return round((entrada / 1_000_000) * pin + (saida / 1_000_000) * pout, 8)


def _resumo_alertas(linha: pd.Series) -> dict:
    return {
        "cliente_id": linha["cliente_id"],
        "alertas_fracionamento": int(linha["alertas_fracionamento"]),
        "alertas_valor_atipico": int(linha["alertas_valor_atipico"]),
        "total_sinalizacoes": int(linha["total_sinalizacoes"]),
        "volume_total_brl": round(float(linha["volume_total_brl"]), 2),
    }


def _datas_fracionamento(cliente_id: str) -> list[str]:
    h = historico_cliente(cliente_id)
    return [x["data"] for x in h.get("dias_fracionamento", []) if x.get("data")]


def planejar(cliente_id: str, fatos: dict) -> tuple[PlanoInvestigacao, dict]:
    """LLM escolhe ferramentas; não faz cálculos."""
    from google.genai import types

    client = _cliente_genai()
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

    prompt = f"""
Você é um agente de triagem PLD.
Os fatos determinísticos abaixo JÁ FORAM CALCULADOS por pandas. Não recalcule limites,
não decida se um número ultrapassa um limiar e não invente dados.

Cliente: {cliente_id}
Fatos: {json.dumps(fatos, ensure_ascii=False)}

Ferramentas disponíveis:
- historico_cliente: use para contexto geral e histórico de alertas.
- operacoes_do_dia: use quando um alerta de fracionamento exigir inspeção do dia.
- perfil_canal: use apenas se a distribuição de canais for relevante para interpretar o caso.

Escolha SOMENTE as ferramentas necessárias. Não chame todas por padrão.
Para operacoes_do_dia, informe uma data ISO presente nos fatos/histórico.
"""

    t0 = time.perf_counter()
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=PlanoInvestigacao,
        ),
    )
    lat = time.perf_counter() - t0

    try:
        plano = PlanoInvestigacao.model_validate_json(response.text)
    except ValidationError as e:
        raise RuntimeError(f"Plano malformado mesmo com schema: {e}") from e

    ent, sai = _usage(response)
    meta = {
        "etapa": "planejamento",
        "tokens_entrada": ent,
        "tokens_saida": sai,
        "latencia_s": round(lat, 4),
        "custo_estimado_usd": _custo(ent, sai),
    }
    return plano, meta


def executar_ferramentas(cliente_id: str, plano: PlanoInvestigacao) -> list[dict]:
    resultados = []
    for chamada in plano.chamadas:
        if chamada.ferramenta == "historico_cliente":
            dados = historico_cliente(cliente_id)
        elif chamada.ferramenta == "perfil_canal":
            dados = perfil_canal(cliente_id)
        elif chamada.ferramenta == "operacoes_do_dia":
            if not chamada.data:
                resultados.append({
                    "ferramenta": chamada.ferramenta,
                    "erro": "data não fornecida pelo planejador",
                    "motivo": chamada.motivo,
                })
                continue
            dados = operacoes_do_dia(cliente_id, chamada.data)
        else:  # proteção adicional
            continue

        resultados.append({
            "ferramenta": chamada.ferramenta,
            "motivo": chamada.motivo,
            "dados": dados,
        })
    return resultados


def redigir_parecer(cliente_id: str, fatos: dict, evidencias: list[dict]) -> tuple[ParecerPLD, dict]:
    """Produz somente interpretação/redação a partir de fatos já calculados."""
    from google.genai import types

    client = _cliente_genai()
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

    prompt = f"""
Atue como analista de Prevenção à Lavagem de Dinheiro.
Não faça cálculos e não aplique limiares numéricos: isso já foi feito em pandas.
Use exclusivamente os fatos e evidências fornecidos. Se uma conclusão não for suportada,
diga que faltam evidências. Um alerta determinístico não prova ilícito.

Cliente: {cliente_id}
Fatos determinísticos:
{json.dumps(fatos, ensure_ascii=False, default=str)}

Evidências consultadas pelo agente:
{json.dumps(evidencias, ensure_ascii=False, default=str)}

Produza um parecer conciso e auditável.
"""

    t0 = time.perf_counter()
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ParecerPLD,
        ),
    )
    lat = time.perf_counter() - t0

    try:
        parecer = ParecerPLD.model_validate_json(response.text)
    except ValidationError as e:
        # Tratamento explícito de resposta malformada: 1 retry corretivo.
        retry_prompt = prompt + "\nA resposta anterior não validou. Retorne SOMENTE o JSON do schema exigido."
        t1 = time.perf_counter()
        retry = client.models.generate_content(
            model=model,
            contents=retry_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ParecerPLD,
            ),
        )
        lat += time.perf_counter() - t1
        try:
            parecer = ParecerPLD.model_validate_json(retry.text)
            response = retry
        except ValidationError as e2:
            raise RuntimeError(f"Resposta malformada após retry: {e2}") from e

    ent, sai = _usage(response)
    meta = {
        "etapa": "parecer",
        "tokens_entrada": ent,
        "tokens_saida": sai,
        "latencia_s": round(lat, 4),
        "custo_estimado_usd": _custo(ent, sai),
    }
    return parecer, meta


def investigar_cliente(linha: pd.Series) -> dict:
    cliente_id = linha["cliente_id"]
    fatos = _resumo_alertas(linha)

    # Enriquecimento mínimo determinístico para permitir ao planejador escolher datas corretas.
    if fatos["alertas_fracionamento"]:
        fatos["datas_fracionamento"] = _datas_fracionamento(cliente_id)

    plano, meta_plano = planejar(cliente_id, fatos)
    evidencias = executar_ferramentas(cliente_id, plano)
    parecer, meta_parecer = redigir_parecer(cliente_id, fatos, evidencias)

    return {
        "cliente_id": cliente_id,
        **fatos,
        "ferramentas_chamadas": [c.ferramenta for c in plano.chamadas],
        "plano": plano.model_dump(),
        **parecer.model_dump(),
        "metricas": [meta_plano, meta_parecer],
    }


def main() -> None:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    ranking = ranking_sinalizados(10)
    ranking.to_csv(OUTPUTS / "top10_clientes_sinalizados.csv", index=False)

    resultados = []
    metricas = []

    for _, linha in ranking.iterrows():
        try:
            r = investigar_cliente(linha)
            resultados.append(r)
            for m in r["metricas"]:
                metricas.append({"cliente_id": r["cliente_id"], **m})
            print(f"[OK] {r['cliente_id']} -> {r['nivel_risco']}")
        except Exception as e:
            print(f"[ERRO] {linha['cliente_id']}: {e}", file=sys.stderr)
            resultados.append({
                "cliente_id": linha["cliente_id"],
                "status": "erro",
                "erro": str(e),
            })

    # JSONL preserva estruturas aninhadas; CSV facilita análise em pandas.
    with open(OUTPUTS / "lote.jsonl", "w", encoding="utf-8") as f:
        for r in resultados:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")

    flat = []
    for r in resultados:
        if "nivel_risco" in r:
            flat.append({
                "cliente_id": r["cliente_id"],
                "total_sinalizacoes": r["total_sinalizacoes"],
                "alertas_fracionamento": r["alertas_fracionamento"],
                "alertas_valor_atipico": r["alertas_valor_atipico"],
                "volume_total_brl": r["volume_total_brl"],
                "ferramentas_chamadas": "|".join(r["ferramentas_chamadas"]),
                "nivel_risco": r["nivel_risco"],
                "tipologia_suspeita": r["tipologia_suspeita"],
                "red_flags": " | ".join(r["red_flags"]),
                "justificativa": r["justificativa"],
            })
        else:
            flat.append({
                "cliente_id": r["cliente_id"],
                "nivel_risco": "",
                "justificativa": f"ERRO: {r.get('erro', '')}",
            })
    pd.DataFrame(flat).to_csv(OUTPUTS / "lote.csv", index=False)

    mdf = pd.DataFrame(metricas)
    mdf.to_csv(OUTPUTS / "metricas_llm.csv", index=False)
    if not mdf.empty:
        resumo = {
            "chamadas": int(len(mdf)),
            "tokens_entrada_total": int(mdf["tokens_entrada"].fillna(0).sum()),
            "tokens_saida_total": int(mdf["tokens_saida"].fillna(0).sum()),
            "latencia_total_s": round(float(mdf["latencia_s"].sum()), 4),
            "latencia_media_s": round(float(mdf["latencia_s"].mean()), 4),
            "custo_estimado_usd_total": round(float(mdf["custo_estimado_usd"].fillna(0).sum()), 8),
        }
        (OUTPUTS / "metricas_llm_resumo.json").write_text(
            json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
