# Desafio Técnico — Estágio em Engenharia de Inteligência Artificial

Este projeto foi desenvolvido para o desafio técnico de estágio em Engenharia de Inteligência Artificial.

A ideia principal foi montar uma solução de triagem de operações financeiras fictícias, usando:

- regras determinísticas com pandas;
- uma LLM para interpretação dos casos;
- ferramentas simples para investigar clientes sinalizados;
- comparação entre o resultado das regras e o resultado do agente.

Eu procurei manter os cálculos fora da LLM. Soma, mediana, contagem e comparação com limites são feitas em pandas. A LLM é usada apenas para interpretar os fatos e produzir um parecer.

---

## Estrutura do projeto

```text
desafio-estagio-ia/
├── README.md
├── ENTREGA.yaml
├── requirements.txt
├── .env.example
├── .gitignore
│
├── dados/
│   ├── dados_nivel_1.json
│   └── dados_nivel_2.json
│
├── nivel_1/
│   └── nivel_1.ipynb
│
├── nivel_2/
│   ├── tools.py
│   ├── agente.py
│   └── confronto.py
│
├── outputs/
│   ├── diagnostico_qualidade.csv
│   ├── nivel_1_operacoes_por_canal.csv
│   ├── nivel_1_operacoes_tratadas.csv
│   ├── nivel_1_validacao_fracionamento.csv
│   ├── nivel_1_volume_por_cliente.csv
│   ├── resumo_deterministico.json
│   ├── sinalizacoes_nivel_2.csv
│   ├── top10_clientes_sinalizados.csv
│   ├── lote.csv
│   ├── lote.jsonl
│   ├── metricas_llm.csv
│   ├── metricas_llm_resumo.json
│   ├── confronto.csv
│   └── confronto_resumo.csv
│
└── docs/
    ├── DECISOES.md
    └── USO_DE_IA.md
```

---

# Nível 1

O Nível 1 está no notebook:

`nivel_1/nivel_1.ipynb`

Nesse nível eu:

- carreguei os dados;
- identifiquei problemas de qualidade;
- removi registros duplicados;
- mantive registros com data ausente sem inventar uma data;
- converti valores em USD para BRL usando a taxa do próprio arquivo;
- criei as agregações pedidas;
- implementei as duas regras;
- validei a Regra 1;
- usei a LLM em um cliente sinalizado;
- comparei duas versões de prompt;
- registrei tokens e tempo de resposta;
- tratei resposta malformada com validação.

## Alguns resultados

A base começou com:

- 20 registros;
- 6 clientes.

Depois da remoção de duplicatas ficaram:

- 19 registros.

Foi identificado o ID duplicado:

`OP-0007`

Também havia uma operação com data ausente, que foi mantida na base e ignorada apenas nas análises que dependiam da data.

---

## Regra 1 — Fracionamento

A regra procura clientes que, no mesmo dia:

- fizeram 3 ou mais operações;
- tiveram soma acima de R$ 50.000;
- sem nenhuma operação individual de R$ 20.000 ou mais.

O caso capturado foi:

```text
CLI-A-1
Data: 2026-03-09
3 operações
Volume total: R$ 54.200
Maior operação: R$ 18.800
```

Também validei um caso parecido que não deveria ser sinalizado:

```text
CLI-A-2
Data: 2026-03-14
2 operações
Volume total: R$ 52.900
Maior operação: R$ 27.000
```

Esse caso não entra na regra porque não possui 3 operações e também possui operação acima de R$ 20 mil.

---

## Regra 2 — Valor atípico

A segunda regra procura operações com valor superior a 5 vezes a mediana das operações do mesmo cliente.

Ela só é aplicada para clientes com 4 ou mais operações.

O principal caso identificado foi:

```text
Operação: OP-0013
Cliente: CLI-A-4
Valor original: USD 12.000
Valor em BRL: R$ 64.800
Mediana do cliente: R$ 5.450
Limite: R$ 27.250
```

---

## Uso da LLM no Nível 1

Usei o modelo:

`gemini-3.5-flash-lite`

A LLM recebeu os fatos que já tinham sido calculados com pandas.

A resposta foi estruturada nos campos:

```text
nivel_risco
tipologia_suspeita
red_flags
justificativa
```

Também foram registradas métricas de tokens e latência.

Foram feitas duas versões de prompt:

- uma mais simples;
- outra com mais regras para evitar que a LLM inventasse informações ou refizesse cálculos.

A segunda versão ficou mais controlada e mais fácil de auditar, apesar de usar mais tokens.

---

# Nível 2

No Nível 2, a ideia foi aplicar as mesmas regras em uma base maior e depois usar um agente para analisar os clientes mais sinalizados.

A base do Nível 2 possui:

- 322 registros;
- 317 registros após remoção de duplicatas;
- 5 duplicatas removidas;
- 7 datas ausentes;
- 30 clientes.

Foi criado um ranking dos 10 clientes mais sinalizados, usando o volume total como critério de desempate.

O ranking está em:

`outputs/top10_clientes_sinalizados.csv`

---

## Ferramentas

As ferramentas estão em:

`nivel_2/tools.py`

Foram criadas três funções:

```python
historico_cliente(cliente_id)
operacoes_do_dia(cliente_id, data)
perfil_canal(cliente_id)
```

A função `historico_cliente` traz um resumo geral do cliente.

A função `operacoes_do_dia` permite olhar as operações de um cliente em uma data específica.

A função `perfil_canal` mostra como o cliente distribui suas operações entre os diferentes canais.

---

## Agente

O agente está em:

`nivel_2/agente.py`

A ideia foi fazer o agente decidir quais ferramentas precisava usar em cada caso.

Ele não chama todas as ferramentas automaticamente.

Primeiro ele recebe os fatos do cliente, decide quais consultas são necessárias e depois usa somente essas ferramentas.

No final, produz um parecer estruturado para o cliente.

---

## Execução em lote

O agente foi executado para os 10 clientes do ranking.

Os resultados foram salvos em:

```text
outputs/lote.csv
outputs/lote.jsonl
```

As métricas das chamadas foram salvas em:

```text
outputs/metricas_llm.csv
outputs/metricas_llm_resumo.json
```

---

# Confronto entre regra e agente

Também foi feita uma comparação entre o risco sugerido pelas regras e o risco atribuído pelo agente.

O critério usado foi:

```text
2 tipos de regra acionados = risco alto
1 tipo de regra acionado = risco médio
0 regras acionadas = risco baixo
```

O resultado foi:

```text
10 clientes analisados
9 concordâncias
1 divergência
90% de concordância
```

A única divergência foi no cliente:

`CLI-030`

Nesse caso, a regra indicou risco médio e o agente indicou risco baixo.

O cliente tinha um alerta de valor atípico, mas não tinha fracionamento nem outros sinais fortes.

Por isso o agente foi menos conservador.

Eu mantive essa divergência porque o objetivo das regras é fazer triagem, e não necessariamente definir o risco final de forma absoluta.

---

# Como rodar

Instalar as dependências:

```bash
pip install -r requirements.txt
```

Criar um arquivo `.env` a partir do `.env.example` e preencher:

```env
GEMINI_API_KEY=sua_chave
GEMINI_MODEL=gemini-3.5-flash-lite
```

O arquivo `.env` não deve ser enviado para o GitHub.

Para executar o Nível 2:

```bash
python nivel_2/agente.py
```

Depois:

```bash
python nivel_2/confronto.py
```

---

# Segurança

A chave da API não foi colocada no repositório.

O arquivo `.env` está no `.gitignore`.

O `.env.example` contém apenas o nome das variáveis necessárias.

---

# Por que não fiz o Nível 3

Eu decidi não implementar o Nível 3 porque preferi concentrar o tempo em deixar os Níveis 1 e 2 funcionando de forma correta e com os resultados salvos.

O próprio enunciado diz que é melhor entregar dois níveis sólidos do que três níveis pela metade.

Por isso priorizei:

- tratamento correto dos dados;
- validação das regras;
- uso da LLM apenas para interpretação;
- comparação entre dois prompts;
- agente com seleção de ferramentas;
- execução em lote;
- métricas;
- confronto entre regra e modelo;
- documentação das decisões.

Com mais tempo, eu seguiria para uma interface conversacional usando as ferramentas já criadas no Nível 2, permitindo consultar e comparar clientes sinalizados.

---

# Considerações finais

O objetivo principal foi manter a solução simples e explicável.

Os cálculos ficam em pandas e a LLM é usada apenas quando existe necessidade de interpretação.

A solução não tenta substituir uma análise humana. A ideia é usar regras e IA para ajudar a priorizar os casos que merecem mais atenção.
