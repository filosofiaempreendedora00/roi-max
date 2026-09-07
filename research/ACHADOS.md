# O que os dados dizem — e o que eles não dizem

Base: **28.615 partidas** de 12 ligas europeias, das quais **8.023 com preço
real da Betfair Exchange** (as colunas BFE existem desde 2024/25). Comissão de
6,5% aplicada em tudo. Todo número vem com erro padrão — sem isso, ROI é
adivinhação.

---

## 1. Quantas apostas são precisas para provar lucro

| ROI real | odd 1.5 | odd 2.0 | odd 3.0 | odd 5.0 |
|---|---|---|---|---|
| 2% | 4.896 | 9.996 | 20.196 | 40.596 |
| 5% | 756 | 1.596 | 3.276 | 6.636 |
| 10% | 176 | 396 | 836 | 1.716 |
| 20% | 36 | 96 | 216 | 456 |
| 30% | 12 | 40 | 98 | 214 |

**Para provar lucro em algumas dezenas de apostas, o ROI real precisa passar de
30%.** Edge de verdade em futebol vive entre 2% e 10%. Não existe atalho: é
aritmética da variância, não limitação de método.

O CLV é a exceção, porque compara preços e não resultados — com CLV de 3% e
desvio de 5%, bastam 11 apostas. É por isso que ele existe.

---

## 2. O sinal de divergência está errado, e o erro é significativo

A regra "fazer back onde a Exchange paga acima do consenso das casas":

| Estratégia | n | ROI | t | CLV | Bateu o fecho |
|---|---|---|---|---|---|
| **BACK acima do justo** | 1.196 | **−12,78% ±5,00** | **−2,55** | −0,09% | 43% |
| BACK abaixo do justo | 5.696 | −5,00% ±2,12 | −2,36 | −2,97% | 37% |
| LAY abaixo do justo | 5.696 | −4,13% ±2,19 | −1,89 | +5,72% | 53% |
| LAY acima do justo | 1.196 | +3,40% ±5,20 | 0,65 | +1,40% | 50% |

Não é ruído: t=−2,55 significa perda sistemática.

**Explicação:** a Betfair é o mercado mais afiado que existe em futebol. Quando
o preço dela diverge do consenso das casas, quem está errado são as casas. O
filtro não encontra valor — encontra **cotação fina**, oferta pequena e sem
lastro na abertura. Por isso o ROI piora conforme a divergência aumenta.

**Armadilha:** aquele CLV de +5,72% no lay parece ótimo e é artefato. As odds
se alongam da abertura para o fechamento, então qualquer lay na abertura
parece bater o fechamento. É o espelho do −2,97% da linha acima.

---

## 3. Viés favorito-azarão: existe, mas é frágil

Fazer LAY em toda seleção com odd ≤ 1,50 ao preço de **abertura**:

| Recorte | n | ROI | t |
|---|---|---|---|
| Tudo | 1.721 | +4,78% ±1,38 | 3,46 |
| 2024/25 | 938 | +7,25% ±1,89 | 3,84 |
| **2025/26** | **725** | **+2,39% ±2,11** | **1,13** |
| Ao preço de **fechamento** | 1.480 | **−3,44% ±1,39** | −2,48 |

Três coisas a notar:

1. **Decai fora da amostra.** De t=3,84 para t=1,13.
2. **Some no fechamento.** Logo é efeito de **deriva de preço**, não de
   precificação errada. Depende inteiramente de conseguir a abertura.
3. **A seleção por liga não sobrevive.** Primeira Liga deu +27,00% (t=5,33) em
   2024/25; as mesmas ligas em 2025/26 deram +4,29% ±3,82 (t=1,12). Com 12
   ligas testadas, alguma sempre parece excelente por sorte.

---

## 4. O que a média esconde

Mesmo na versão mais favorável (todas as ligas, preço de abertura):

- **71,1%** das entradas **perdem** (é lay em favorito: você perde quando ele ganha)
- Maior sequência de perdas seguidas: **23**
- Pior queda acumulada: **18,5 unidades** — com stake de R$ 100, uma queda de
  **R$ 1.852** do topo
- Lucro final: +82,3 unidades em 1.721 entradas

---

## Conclusão honesta

**Não há, nestes dados, uma estratégia com edge validado que eu possa
recomendar para dinheiro real.**

- O sinal que o app usa hoje é significativamente negativo. Deve ser desligado.
- O único efeito estrutural encontrado é pequeno, decai fora da amostra,
  desaparece no fechamento e exige aguentar 23 derrotas seguidas.
- A meta de "lucro comprovado em dezenas de apostas" é aritmeticamente
  incompatível com edges dessa magnitude.

O que os dados **sustentam** é usar o app como **instrumento de medição** — ele
registra o preço que você pegou e o de fechamento — e não como gerador de
palpites. É o único caminho que dá sinal em dezenas de entradas em vez de
milhares.

## Reproduzir

```bash
./.venv/bin/python research/segmentos.py 2.0    # por mercado, odd, liga
./.venv/bin/python research/direcao.py          # o sinal está invertido?
./.venv/bin/python research/vies_favorito.py    # viés favorito-azarão
./.venv/bin/python research/fora_amostra.py     # validação e sequências
```
