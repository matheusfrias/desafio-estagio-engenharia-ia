# USO_DE_IA.md

Durante o desafio usei ferramentas de IA como apoio no desenvolvimento.

## ChatGPT

Usei o ChatGPT principalmente para:

- ajudar a interpretar o enunciado;
- revisar a estrutura do projeto;
- discutir decisões de implementação;
- ajudar a encontrar erros durante a execução no Google Colab;
- revisar código;
- organizar o README e a documentação;
- ajudar a explicar os resultados encontrados.

Eu não tratei as respostas como corretas automaticamente.

Os códigos foram executados e os resultados foram conferidos antes de entrar na versão final.

Um exemplo de correção foi o modelo do Gemini.

A configuração inicial usava `gemini-2.5-flash-lite`, mas esse modelo retornou erro de indisponibilidade para novos usuários.

Depois do erro, a configuração foi alterada e testada com:

`gemini-3.5-flash-lite`

Outro ponto importante foi evitar colocar cálculos nas mãos da LLM.

Durante a implementação, mantive soma, mediana, contagens e regras em pandas e deixei a IA apenas para interpretação.

## Gemini

Usei o `gemini-3.5-flash-lite` como LLM da solução.

No Nível 1 ele foi usado para analisar um cliente sinalizado e gerar um parecer estruturado.

Também comparei duas versões de prompt.

No Nível 2 o Gemini foi usado em duas etapas:

1. escolher quais ferramentas consultar para cada cliente;
2. produzir o parecer final usando os fatos determinísticos e os resultados das ferramentas.

As respostas foram validadas com Pydantic.

Também foram registradas métricas de tokens e latência.

## Google Colab

Usei o Google Colab para executar o notebook e os scripts sem precisar configurar todo o ambiente localmente.

A chave do Gemini foi colocada em `Secrets` do Colab e não foi salva no repositório.

## O que ficou sob minha responsabilidade

A IA foi usada como ferramenta de apoio.

As decisões finais da solução, a execução dos códigos, a validação dos resultados e a escolha do que incluir na entrega foram feitas a partir dos testes do próprio projeto.
