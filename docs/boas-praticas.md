# Boas práticas de sistemas com IA neste projeto

Este documento lista as práticas de engenharia para sistemas com LLM que o Cardápio Agente segue, **onde cada uma está no código** e **o que ainda falta**. A ideia é que qualquer afirmação aqui possa ser conferida abrindo o arquivo indicado.

Resumo: o projeto trata o LLM como um componente que **erra**, então cerca cada chamada de contratos, validação, alternativas e medição.

---

## 1. Usar a solução mais simples que resolve: workflow, não agente autônomo

**Prática:** só dar autonomia ao modelo (escolher ferramentas, decidir os próximos passos) quando o problema exige. Quando os passos são conhecidos, um fluxo fixo é mais previsível, barato e fácil de testar.

**Aqui:** a ordem é sempre a mesma: Extrator → Normalizador → Enriquecedor → Validador. O LLM não decide o fluxo; ele executa duas tarefas bem delimitadas.
→ [`pipeline/orquestrador.py`](../pipeline/orquestrador.py)

## 2. Cada etapa com uma responsabilidade só

**Prática:** quebrar a tarefa em passos pequenos, cada um com entrada e saída claras, para saber de onde vem cada erro.

**Aqui:** o Extrator só **copia** o texto da foto, sem interpretar. Converter "R$ 1.200,00" em número é trabalho do Normalizador. Se um preço sai errado, dá para saber se foi a leitura (Extrator) ou a conversão (Normalizador).
→ [`pipeline/extrator.py`](../pipeline/extrator.py), [`pipeline/normalizador.py`](../pipeline/normalizador.py)

## 3. Código onde a regra é fixa, IA só onde precisa de julgamento

**Prática:** não usar LLM para o que uma regra resolve. Código é determinístico, barato, rápido e testável.

**Aqui:** 2 das 4 etapas são código puro: conversão de preço, ajuste de maiúsculas, remoção de duplicados e todas as regras de validação (faixa de preço, tags conflitantes, nomes repetidos).
→ [`pipeline/normalizador.py`](../pipeline/normalizador.py), [`pipeline/validador.py`](../pipeline/validador.py)

## 4. Saída estruturada com contrato validado

**Prática:** pedir ao modelo uma saída em formato definido (JSON Schema) e **validar** antes de usar. Nunca fazer parsing de texto livre.

**Aqui:** cada etapa entrega um modelo Pydantic. O Gemini recebe o esquema em `response_schema`; o Claude, como uma ferramenta obrigatória com `input_schema`. Se a resposta não bate com o esquema, a chamada falha com `ErroLLM`, em vez de seguir com dado errado.
→ [`pipeline/schemas.py`](../pipeline/schemas.py), [`pipeline/llm.py`](../pipeline/llm.py)

## 5. Vocabulário fechado: a IA sugere, o código decide

**Prática:** quando a saída deve vir de um conjunto conhecido, restringir no esquema, não só no prompt.

**Aqui:** as tags são um `Enum` com 14 valores. Uma tag inventada pelo modelo (como `"saudavel"`) é recusada pelo Pydantic. Há um teste para isso.
→ [`pipeline/schemas.py`](../pipeline/schemas.py), [`tests/test_llm.py`](../tests/test_llm.py)

## 6. Prompts que proíbem inventar

**Prática:** dizer explicitamente o que o modelo **não** deve fazer e dar exemplos do formato esperado.

**Aqui:** o Extrator manda copiar nomes e preços exatamente como estão escritos e proíbe inventar itens, preços ou descrições e traduzir. O Enriquecedor proíbe inventar ingredientes, modo de preparo e adjetivos de propaganda, mantém a descrição original quando ela existe na foto e traz dois exemplos. Esse prompt foi ajustado depois que o primeiro teste real produziu descrições como "crocantes e douradas por fora".
→ [`pipeline/extrator.py`](../pipeline/extrator.py), [`pipeline/enriquecedor.py`](../pipeline/enriquecedor.py)

## 7. Humano no circuito quando há incerteza

**Prática:** o sistema deve saber dizer "não tenho certeza" e passar o caso para uma pessoa, em vez de chutar.

**Aqui:** se o preço tem mais de um número (P/M/G, "R$ 75,00 / 100 unidades"), o Normalizador não escolhe um: o item fica sem preço e o Validador marca `revisao_humana`, mostrando o texto original. Nos evals, isso aconteceu com 6 itens do cardápio de salgados.
→ [`pipeline/validador.py`](../pipeline/validador.py)

## 8. Degradação controlada

**Prática:** uma etapa opcional que falha não deve derrubar o resultado inteiro.

**Aqui:** se o Enriquecedor falha, o cardápio sai sem tags, com `enriquecido: false`, e um aviso aparece na tela e no log. Isso aconteceu de verdade quando a cota acabou no meio de uma rodada de evals.
→ [`pipeline/enriquecedor.py`](../pipeline/enriquecedor.py)

## 9. Resiliência: tempo limite, tentativas curtas e modelo reserva

**Prática:** toda chamada externa precisa de tempo limite e de um plano B para erros passageiros.

**Aqui:** cada chamada desiste em 30 s e tenta de novo no máximo 1 vez. Erro 503 (modelo lotado) ou 429 (cota) troca para o modelo reserva. Erro de chave inválida **não** troca, porque não adiantaria. Isso veio de um problema medido: sem esses limites, a biblioteca repetia sozinha por mais de 3 minutos.
→ [`pipeline/llm.py`](../pipeline/llm.py), [`tests/test_llm.py`](../tests/test_llm.py)

## 10. Independência de provedor

**Prática:** o resto do sistema não deve depender de um fornecedor de LLM específico.

**Aqui:** todas as etapas usam a mesma interface, `ClienteLLM.gerar(prompt, esquema, imagem)`. Trocar Gemini por Claude é mudar a variável `PROVEDOR`, sem tocar nas etapas.
→ [`pipeline/llm.py`](../pipeline/llm.py)

## 11. Avaliação com gabarito, não impressão

**Prática:** medir a qualidade em dados rotulados, com métricas definidas, antes de afirmar que funciona.

**Aqui:** 6 cardápios com gabarito. Métricas de cobertura, precisão, preço certo e categoria certa, com pareamento de nomes por similaridade. As saídas ficam salvas, então o relatório é reproduzível sem chamar a API.
→ [`evals/metricas.py`](../evals/metricas.py), [`evals/rodar_evals.py`](../evals/rodar_evals.py), [`evals/saidas/relatorio.json`](../evals/saidas/relatorio.json)

## 12. Honestidade na avaliação

**Prática:** não ajustar o gabarito depois de ver o resultado, declarar como os dados foram feitos e mostrar os erros.

**Aqui:** cada gabarito diz como foi feito (campo `fonte`). O tempo manual é uma estimativa a partir de uma amostra cronometrada, e isso está escrito. O README mostra os erros, incluindo o mais grave: itens que somem sem o sistema avisar.
→ [`evals/gabaritos/`](../evals/gabaritos/), [`evals/medicao_manual.json`](../evals/medicao_manual.json), [README](../README.md#onde-o-sistema-errou)

## 13. Testes sem chamar a API

**Prática:** a lógica em volta do LLM deve ser testável sem rede, sem custo e sem resultados que variam.

**Aqui:** 86 testes com um LLM falso, que devolve respostas prontas. Antes de cada teste, as chaves são apagadas do ambiente, então nenhum teste consegue chamar a API, nem por engano. Rodam no GitHub Actions a cada push e pull request.
→ [`tests/conftest.py`](../tests/conftest.py), [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)

## 14. Custo e cota sob controle

**Prática:** saber quanto cada uso custa e limitar o gasto.

**Aqui:** cada foto custa 2 chamadas. A demo abre em exemplos já processados (zero chamadas), reaproveita o resultado de uma foto repetida e limita 5 fotos novas por visitante e 15 por dia, dentro da cota gratuita de ~20 chamadas diárias por modelo. As imagens são reduzidas para no máximo 1568 px antes do envio.
→ [`streamlit_app.py`](../streamlit_app.py), [`pipeline/imagem.py`](../pipeline/imagem.py)

## 15. Segredos e privacidade

**Prática:** chaves fora do código e do histórico; usuário avisado sobre o destino dos dados.

**Aqui:** a chave fica no `.env` (ignorado pelo git) ou nos Secrets do Streamlit Cloud. A demo avisa que, na camada gratuita, o Google pode usar as imagens e pede só fotos de cardápio.
→ [`.gitignore`](../.gitignore), [`.env.example`](../.env.example)

## 16. Observabilidade básica

**Prática:** medir onde o tempo é gasto e registrar falhas.

**Aqui:** o orquestrador cronometra cada etapa (`tempos` no JSON e no gráfico da demo), e as falhas do Enriquecedor vão para o log. Foi com essa medição que se descobriu que a lentidão vinha do modelo sobrecarregado, não do raciocínio.
→ [`pipeline/orquestrador.py`](../pipeline/orquestrador.py)

---

## O que ainda falta

Estas práticas são conhecidas, mas o projeto ainda **não** as segue. Ficam como próximos passos:

| Lacuna | Risco | Como resolver |
|---|---|---|
| **Itens que somem não são detectados** | Um item esquecido não aparece em nenhum aviso | Segunda leitura barata só para contar itens por seção e comparar |
| **Texto da foto não é tratado como entrada hostil** | Uma foto com "ignore as instruções" escrito poderia tentar desviar o modelo | Hoje o esquema fechado limita o estrago (só saem campos de cardápio); falta um teste com uma imagem assim |
| **Prompts sem versão registrada** | Não dá para comparar resultados entre versões de prompt | Gravar a versão do prompt junto de cada saída dos evals |
| **Apenas 6 cardápios** | Números mostram onde olhar, não a taxa de erro em produção | Mais cardápios, de tipos e qualidades de foto variados |
| **Logs sem rastreio por requisição** | Difícil investigar um erro específico na demo | Log estruturado com um ID por foto processada |
