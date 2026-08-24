# DECISOES.md

## Visão geral

Neste desafio eu preferi manter a solução simples e fácil de explicar.

A principal decisão foi separar o que é cálculo do que é interpretação:

- pandas fica responsável por soma, mediana, contagem, conversão de moeda e aplicação das regras;
- a LLM recebe os fatos já calculados e é usada para interpretar o caso e escrever o parecer.

Fiz isso porque os cálculos precisam ser reproduzíveis e fáceis de conferir.

---

## Tratamento dos dados

### Duplicatas

Nos dois arquivos existiam operações duplicadas por `id`.

A decisão foi manter a primeira ocorrência e remover as duplicatas, considerando `id` como identificador da operação.

Isso evita contar a mesma operação duas vezes em volume, mediana, quantidade de operações e regras.

### Datas ausentes

Algumas operações não tinham data.

Eu preferi manter essas operações na base, sem inventar ou preencher uma data.

Elas continuam participando das análises que não dependem de data, mas ficam fora da Regra 1, porque essa regra precisa agrupar as operações por dia.

### Conversão de moeda

Existiam operações em BRL e USD.

Usei a taxa fixa que já estava dentro dos arquivos JSON, sem consultar nenhuma cotação externa.

Também mantive o valor e a moeda originais para facilitar a conferência.

---

## Regra 1 — Fracionamento

A regra foi implementada agrupando por `cliente_id` e `data`.

O cliente é sinalizado quando:

- tem 3 ou mais operações no mesmo dia;
- a soma dessas operações é maior que R$ 50.000;
- nenhuma operação individual chega a R$ 20.000.

Eu também fiz uma validação explícita usando:

- `CLI-A-1` como caso positivo;
- `CLI-A-2` como caso parecido que não atende aos critérios.

A ideia foi mostrar que a regra não está olhando apenas para o volume total.

---

## Regra 2 — Valor atípico

A Regra 2 compara cada operação com 5 vezes a mediana daquele cliente.

Ela só é aplicada a clientes com pelo menos 4 operações.

A mediana e o limite são calculados em pandas.

A LLM não participa dessa decisão.

---

## Escolha do cliente para análise com LLM

No Nível 1 escolhi o `CLI-A-4`, porque ele tinha uma operação sinalizada pela Regra 2.

Esse caso era interessante porque tinha uma operação em USD que, após conversão para BRL, ficou bem acima da mediana do cliente.

---

## Comparação entre os prompts

Foram usadas duas versões de prompt.

A primeira era mais simples e aberta.

A segunda tinha instruções mais claras para:

- usar somente os fatos fornecidos;
- não refazer cálculos;
- não inventar informações;
- separar fatos de interpretação;
- reconhecer quando não existe evidência suficiente.

A segunda versão consumiu mais tokens, mas ficou mais controlada e mais fácil de revisar.

Eu considerei esse aumento de tokens aceitável em troca de uma resposta mais consistente.

---

## Saída estruturada

As respostas da LLM foram validadas com Pydantic.

Os campos usados foram:

- `nivel_risco`;
- `tipologia_suspeita`;
- `red_flags`;
- `justificativa`.

Também foi feito um teste com uma resposta malformada para verificar se o código rejeitava valores fora do formato esperado.

---

## Nível 2 — Reaproveitamento das regras

No Nível 2 reaproveitei a mesma lógica do Nível 1 em uma base maior.

O ranking dos 10 clientes foi feito usando:

1. quantidade total de sinalizações;
2. volume total em BRL como desempate.

Para fracionamento, considerei um alerta por cliente/data sinalizada, e não um alerta para cada linha daquele grupo.

Isso evita inflar artificialmente o número de sinalizações de um mesmo evento.

---

## Ferramentas do agente

Foram implementadas três ferramentas:

- `historico_cliente(cliente_id)`;
- `operacoes_do_dia(cliente_id, data)`;
- `perfil_canal(cliente_id)`.

A ideia foi permitir que o agente busque contexto adicional sem colocar toda a base no prompt.

---

## Escolha dinâmica das ferramentas

Uma decisão importante foi não chamar todas as ferramentas sempre.

O agente primeiro recebe os fatos determinísticos e decide quais consultas são necessárias.

Depois, somente as ferramentas escolhidas são executadas.

Isso deixa o fluxo mais próximo do comportamento de um agente e também evita consultas desnecessárias.

---

## Execução em lote

O agente foi executado para os 10 clientes priorizados.

Foram salvos:

- pareceres em CSV e JSONL;
- tokens de entrada e saída;
- latência;
- custo estimado.

Usei JSONL para preservar melhor as estruturas aninhadas e CSV para facilitar análise com pandas.

---

## Critério usado no confronto

Para comparar regra e agente, usei o seguinte critério de referência:

- duas categorias de regra acionadas = risco alto;
- uma categoria de regra acionada = risco médio;
- nenhuma regra = risco baixo.

Esse critério não representa uma verdade absoluta de risco.

Ele serve apenas como referência para comparar o comportamento do agente com as regras.

---

## Resultado do confronto

Dos 10 clientes analisados:

- 9 tiveram concordância;
- 1 teve divergência;
- taxa de concordância de 90%.

A divergência foi no `CLI-030`.

A regra indicou risco médio porque havia um alerta de valor atípico.

O agente indicou risco baixo porque considerou que havia apenas um alerta isolado, sem fracionamento ou outros sinais mais fortes.

Eu mantive essa divergência porque achei mais interessante mostrar que o agente não precisa repetir exatamente a regra.

As regras servem para triagem e podem gerar falsos positivos.

---

## Limitações

A solução ainda tem algumas limitações.

As regras são simples e foram feitas especificamente para o desafio.

Em um cenário real eu consideraria outros fatores, como:

- perfil cadastral;
- renda;
- setor de atuação;
- relacionamento entre contrapartes;
- histórico maior do cliente;
- origem e destino dos recursos.

Também seria necessário avaliar com mais cuidado custo, limites de requisição, tratamento de falhas da API e observabilidade.

---

## Nível 3

Eu decidi não implementar o Nível 3.

O motivo principal foi priorizar uma entrega mais sólida dos Níveis 1 e 2.

O próprio desafio deixa claro que prefere dois níveis bem feitos e documentados a três níveis pela metade.

Por isso usei o tempo para:

- validar as regras;
- executar a LLM no Nível 1;
- comparar os prompts;
- implementar as ferramentas;
- montar o agente;
- executar os 10 clientes;
- registrar métricas;
- fazer o confronto;
- revisar os outputs e a documentação.

Com mais tempo, eu seguiria pela trilha de interface conversacional, usando Streamlit ou Gradio.

A ideia seria permitir que um analista consultasse os clientes sinalizados, comparasse casos e pedisse explicações usando as ferramentas já criadas no Nível 2.
