# Desafio Técnico — Estágio em Engenharia de Inteligência Artificial

Solução organizada para o desafio de triagem de operações financeiras fictícias com **regras determinísticas em pandas** e **LLM apenas para interpretação/redação**.

> **Status atual deste pacote:** toda a parte determinística dos Níveis 1 e 2 está calculada e os outputs correspondentes já foram gerados. A integração com Gemini está implementada, mas as chamadas externas não foram executadas aqui porque nenhuma chave de API foi fornecida. Não foram inventados tokens, latência ou pareceres.

## Estrutura

```text
desafio-estagio-ia/
├── README.md
├── ENTREGA.yaml
├── requirements.txt
├── .env.example
├── .gitignore
├── dados/
│   ├── dados_nivel_1.json
│   └── dados_nivel_2.json
├── nivel_1/
│   └── nivel_1.ipynb
├── nivel_2/
│   ├── tools.py
│   ├── agente.py
│   └── confronto.py
├── nivel_3/
│   └── README.md
├── outputs/
└── docs/
    ├── DECISOES.md
    └── USO_DE_IA.md
```

## Resultados determinísticos principais

### Nível 1
- Registros recebidos: **20**
- Registros após deduplicação por `id`: **19**
- ID duplicado detectado: **OP-0007**
- Datas ausentes após limpeza: **1**
- Regra 1 (fracionamento): **CLI-A-1 em 2026-03-09**, 3 operações, R$ 54.200 no dia e maior operação de R$ 18.800.
- Caso parecido corretamente não sinalizado: **CLI-A-2 em 2026-03-14** (apenas 2 operações e ambas acima de R$ 20 mil).
- Regra 2 (valor atípico): **OP-0013 / CLI-A-4**. US$ 12.000 × 5,4 = **R$ 64.800**; mediana do cliente = R$ 5.450 e limite = R$ 27.250.

### Nível 2
- Registros recebidos: **322**
- Registros após deduplicação por `id`: **317**
- Duplicatas exatas removidas: **5**
- Datas ausentes após limpeza: **6**
- Clientes: **30**
- Ranking dos 10 clientes sinalizados já salvo em `outputs/top10_clientes_sinalizados.csv`.

## Como rodar

### 1. Criar ambiente (opcional)

```bash
python -m venv .venv
```

Ativar no Windows:
```bash
.venv\Scripts\activate
```

Ativar no macOS/Linux:
```bash
source .venv/bin/activate
```

### 2. Instalar dependências

```bash
pip install -r requirements.txt
```

### 3. Configurar LLM

Copie `.env.example` para `.env` e preencha:

```env
GEMINI_API_KEY=sua_chave_aqui
GEMINI_MODEL=gemini-2.5-flash-lite
```

**Nunca commite `.env`.**

### 4. Notebook do Nível 1

Abra:

```bash
jupyter notebook nivel_1/nivel_1.ipynb
```

As células determinísticas já estão executadas. Para gerar os dois pareceres reais da LLM, configure a chave e execute as células da seção **Parte B — LLM**.

### 5. Nível 2 — lote

```bash
python nivel_2/agente.py
```

Isso gera:
- `outputs/lote.jsonl`
- `outputs/lote.csv`
- `outputs/metricas_llm.csv`
- `outputs/metricas_llm_resumo.json`

### 6. Confronto regra × agente

```bash
python nivel_2/confronto.py
```

Isso gera:
- `outputs/confronto.csv`
- `outputs/confronto_resumo.csv`

## Ferramentas do agente

O agente pode escolher dinamicamente entre:

- `historico_cliente(cliente_id)`
- `operacoes_do_dia(cliente_id, data)`
- `perfil_canal(cliente_id)`

Ele **não chama todas automaticamente**. Primeiro planeja quais evidências são necessárias e somente então executa as ferramentas selecionadas.

## Commits sugeridos

Não faça um único commit no final. Uma sequência segura é:

```text
chore: cria estrutura inicial do desafio
feat: adiciona limpeza e normalizacao do nivel 1
feat: implementa regras deterministicas e validacao
feat: adiciona analise estruturada com LLM
feat: aplica regras em escala e gera ranking top 10
feat: implementa ferramentas e agente de investigacao
feat: adiciona execucao em lote e metricas
feat: implementa confronto entre regras e agente
docs: finaliza README e documentacao de decisoes
```

## Segurança

- `.env` está no `.gitignore`.
- `.env.example` contém somente nomes de variáveis.
- Nenhuma chave de API deve ser versionada.

## Observação sobre o Nível 3

O Nível 3 foi deliberadamente deixado como **não feito** neste primeiro pacote para priorizar dois níveis sólidos e auditáveis. Há um plano em `nivel_3/README.md` e `docs/DECISOES.md`.
