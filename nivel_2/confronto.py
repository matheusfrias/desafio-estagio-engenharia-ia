"""
Confronto entre regras determinísticas e nível de risco atribuído pelo agente.

Critério escolhido:
- 2 tipos de regra acionados -> risco esperado alto
- 1 tipo de regra acionado -> risco esperado médio
- nenhuma regra -> risco esperado baixo

Observação: isso é uma referência de confronto, não "verdade de risco".
A análise das divergências deve considerar o contexto levantado pelo agente.
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUTS = BASE_DIR / "outputs"

ORDEM = {"baixo": 0, "médio": 1, "alto": 2}


def risco_regra(row: pd.Series) -> str:
    tipos = int(row["alertas_fracionamento"] > 0) + int(row["alertas_valor_atipico"] > 0)
    if tipos >= 2:
        return "alto"
    if tipos == 1:
        return "médio"
    return "baixo"


def main() -> None:
    lote_path = OUTPUTS / "lote.csv"
    if not lote_path.exists():
        raise FileNotFoundError(
            "outputs/lote.csv não existe. Rode primeiro: python nivel_2/agente.py"
        )

    df = pd.read_csv(lote_path)
    obrigatorias = {
        "cliente_id", "alertas_fracionamento", "alertas_valor_atipico", "nivel_risco"
    }
    faltantes = obrigatorias - set(df.columns)
    if faltantes:
        raise ValueError(f"Colunas ausentes em lote.csv: {sorted(faltantes)}")

    df["risco_regra"] = df.apply(risco_regra, axis=1)
    df["concorda"] = df["nivel_risco"] == df["risco_regra"]
    df["diferenca_niveis"] = df.apply(
        lambda r: ORDEM.get(str(r["nivel_risco"]), -99) - ORDEM[r["risco_regra"]],
        axis=1,
    )
    df["tipo_divergencia"] = df["diferenca_niveis"].map(
        lambda x: "concordância" if x == 0 else ("agente_mais_conservador" if x > 0 else "agente_menos_conservador")
    )

    taxa = float(df["concorda"].mean()) if len(df) else 0.0
    df.to_csv(OUTPUTS / "confronto.csv", index=False)

    resumo = pd.DataFrame([{
        "clientes_avaliados": len(df),
        "concordancias": int(df["concorda"].sum()),
        "taxa_concordancia": round(taxa, 4),
        "divergencias": int((~df["concorda"]).sum()),
    }])
    resumo.to_csv(OUTPUTS / "confronto_resumo.csv", index=False)

    print(resumo.to_string(index=False))
    if (~df["concorda"]).any():
        print("\nDivergências para revisão humana:")
        print(
            df.loc[~df["concorda"],
                   ["cliente_id", "risco_regra", "nivel_risco", "tipo_divergencia", "justificativa"]]
            .to_string(index=False)
        )


if __name__ == "__main__":
    main()
