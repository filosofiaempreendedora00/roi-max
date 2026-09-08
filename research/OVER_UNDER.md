# ⚠️ ESTE DOCUMENTO ESTÁ ERRADO — ver correção no fim

O achado descrito abaixo era artefato de um erro meu de medição. A regra
**perde dinheiro** quando calculada com preços executáveis. Mantive o texto
original para registro do erro, com a correção ao final.

---

# A regra que sobreviveu

Depois de derrubar o modelo de gols, o sinal de divergência no 1X2 e o viés
favorito-azarão, esta resistiu a todos os testes que consegui inventar.

## A regra

> No mercado **Over/Under 2.5** da Betfair Exchange, faça **LAY** quando o
> preço da Exchange estiver **8% ou mais abaixo** do preço justo calculado
> pela média das casas. Odds entre 1,30 e 6,00.

Em português claro: quando a Betfair diz que um resultado é mais provável do
que as casas dizem, aposte contra a Betfair.

## Por que faz sentido

No mercado de **resultado** (1X2), a Betfair é o mercado mais afiado que
existe — testei e apostar contra ela perde (ROI −12,78%, t=−2,55).

No mercado de **gols** o quadro se inverte. O Over/Under da Betfair é bem
menos líquido, e o preço de abertura lá é fino. Já a linha de gols da
Pinnacle é uma das mais afiadas do mundo. Nesse mercado específico, **as
casas sabem mais que a Exchange.**

A regra explora exatamente essa inversão.

## Números

Amostra: 15.048 oportunidades de Over/Under 2.5 com preço de Exchange,
12 ligas europeias, 3 temporadas. Comissão de 6,5% aplicada.

| Limiar | n | ROI | ± | t | CLV | Frequência |
|---|---|---|---|---|---|---|
| −4% | 3.732 | +2,46% | 1,74 | 1,41 | +7,55% | 4,7/dia |
| −6% | 1.855 | +5,31% | 2,45 | 2,17 | +11,13% | 2,3/dia |
| **−8%** | **1.069** | **+10,22%** | **3,16** | **3,23** | **+14,86%** | **1,3/dia** |
| −10% | 584 | +11,47% | 4,12 | 2,78 | +20,38% | 0,7/dia |
| −15% | 199 | +27,00% | 6,13 | 4,40 | +36,96% | 0,25/dia |

**A curva é monótona.** Quanto mais apertado o filtro, maior o retorno e maior
a significância. Garimpagem de dados produz uma célula sortuda isolada, não
uma curva dose-resposta limpa.

## O que tentei para derrubar

**Fora da amostra** (treino 2024/25 escolhe, teste 2025/26+ julga):

| Limiar | Treino | Teste |
|---|---|---|
| −6% | +4,34% (t=1,37) | +6,63% (t=1,73) |
| −8% | +10,87% (t=2,71) | **+9,23% (t=1,79)** |
| −10% | +12,81% (t=2,40) | +9,48% (t=1,46) |

**Jackknife por liga** (limiar −8%): removendo qualquer liga uma por vez, o
ROI fica entre **+8,37% e +14,43%**, com t entre 2,43 e 3,88. Nenhuma liga
sustenta o resultado sozinha.

**Por temporada:** 2024/25 +4,34%, 2025/26 +5,52%, 2026/27 +16,84%. Todas
positivas, com CLV de ~11% em cada.

**Por lado:** Over +5,01%, Under +5,54%. Funciona nos dois.

**Múltiplos testes:** 74 regras foram avaliadas. Para sobreviver a isso, t
precisa passar de ~3,2 (Bonferroni). O limiar −8% dá t=3,23 e o −15% dá
t=4,40. Passam, o primeiro no limite.

## Risco

| | |
|---|---|
| Entradas perdedoras | 44,3% |
| Maior sequência de perdas | **7** |
| Pior queda acumulada | 36,7 unidades |
| Odd média | 2,22 (liability de 1,22 por 1 de stake) |
| Lucro final | +98,5 unidades em 1.855 entradas |

Muito mais suportável que o lay em favoritos, que tinha 71% de perdas e 23
derrotas seguidas.

## Quantas apostas para validar

| Limiar | ROI | Apostas necessárias (t=2) | A amostra já tem |
|---|---|---|---|
| −8% | +10,22% | 410 | 1.069 ✅ |
| −10% | +11,47% | 302 | 584 ✅ |
| −15% | +27,00% | **41** | 199 ✅ |

Isto responde a pergunta que originou toda a busca: **com ROI de 27%, bastam
41 apostas.** Não milhares.

## O obstáculo, e como contornar

**A The Odds API não entrega preço de Exchange no mercado de gols.** Verifiquei:
0 de 20 eventos. As chaves `betfair_ex_*` cobrem só resultado (h2h).

Ou seja: o app **não consegue detectar a oportunidade sozinho.**

Mas consegue fazer melhor. Ele tem o consenso das casas para Over/Under
(mediana de 5 casas por evento), então pode calcular o **preço justo** e dizer:

> *Under 2.5 em Bournemouth x Brentford — justo 2,26.*
> *Faça LAY se a Betfair oferecer **2,08 ou menos**.*

Você abre a Betfair, olha, e entra se o preço estiver lá.

Isso tem duas vantagens sobre a detecção automática:

1. **Custa zero crédito de Exchange** — só o mercado `totals`, que é barato.
2. **A checagem manual é também uma checagem de liquidez.** O maior risco
   desta regra é o preço existir no papel e não ter dinheiro atrás. Quando
   você olha a Betfair, vê o volume disponível na hora.

## O que continua desconhecido

**Liquidez.** É o risco central e não dá para medir com dado histórico
gratuito. O mercado de gols da Betfair é mais fino que o de resultado — e é
provavelmente **por isso** que a ineficiência existe. Se o dinheiro disponível
for pequeno demais, a vantagem existe no papel e não no bolso.

Só a operação real responde isso, e é por isso que a checagem manual importa.


---

# CORREÇÃO: a regra não funciona

## O erro

Na Betfair, **fazer lay em Over 2.5 é exatamente a mesma coisa que fazer back
em Under 2.5**. São o mesmo negócio.

Eu calculei o lucro do "lay em Over" usando o preço de **back do Over** — um
preço no qual ninguém consegue executar um lay. Para fazer lay você precisa de
alguém do outro lado, e esse preço é o de back do Under.

A diferença entre os dois é o **spread**, e o spread é exatamente o que você
**paga** para operar, não o que você ganha.

## Os números corrigidos

Over/Under 2.5:

| Limiar | Como eu calculei (errado) | Executável |
|---|---|---|
| −6% | +5,31% (t=2,17) | **−10,28% (t=−5,22)** |
| −8% | +10,22% (t=3,23) | **−8,80% (t=−3,46)** |
| −10% | +11,47% (t=2,78) | **−13,51% (t=−4,12)** |
| −15% | +27,00% (t=4,40) | **−12,63% (t=−2,54)** |

Handicap asiático, mesmo padrão:

| Limiar | Errado | Executável |
|---|---|---|
| −6% | +7,43% | **−8,45% (t=−2,33)** |
| −8% | +8,11% | **−11,23% (t=−2,42)** |
| −10% | +7,28% | **−14,88% (t=−2,54)** |

## O controle que explica tudo

Apostar na Betfair **sem filtro nenhum**, no Over/Under 2.5:

| Estratégia | n | ROI | t |
|---|---|---|---|
| Sempre Over 2.5 | 7.495 | −5,79% | −5,41 |
| Sempre Under 2.5 | 7.553 | −6,37% | −5,42 |

Esse é o **custo de jogar**: comissão mais spread. Qualquer estratégia precisa
superar isso antes de lucrar um centavo.

E aqui está o veredito: **todas as minhas regras filtradas (−8,8% a −14,9%)
são PIORES que apostar às cegas (−5,8%).** O filtro não seleciona preço bom —
seleciona livro largo, e livro largo significa spread caro.

Foi por isso que os jogos selecionados tinham overround mediano de 1,089
contra 1,019 do mercado normal, e por isso que em 29% dos casos a regra
disparava nos dois lados ao mesmo tempo, o que é logicamente impossível como
sinal de valor.

## A lição

Num mercado de duas pontas, "o preço está abaixo do justo de um lado" quase
nunca é oportunidade. Geralmente é só a metade barata do spread — e o spread
é o preço da liquidez, que você paga, não recebe.

Toda medição de estratégia precisa usar o preço que **executa**, não o que
aparece na tabela.
