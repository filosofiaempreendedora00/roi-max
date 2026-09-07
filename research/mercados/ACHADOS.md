# Caça-assimetrias: skins de CS2

Primeira medição, feita com dados gratuitos e públicos, sem chave de API.

## Fontes que funcionam (e as que não)

| Fonte | Status | O que entrega |
|---|---|---|
| `api.waxpeer.com/v1/prices` | ✅ aberta | 22.388 itens: menor preço + nº de anúncios |
| `market.csgo.com/api/v2/prices` | ✅ aberta | 27.580 itens: preço + volume de vendas |
| `steamcommunity.com/market/search/render` | ⚠️ limitada | ~20 requisições/min por IP |
| `api.skinport.com` | ❌ 403 | Cloudflare bloqueia requisição automatizada |
| `csfloat.com/api` | ❌ 403 | exige login |
| `api.dmarket.com` (v1) | ❌ 410 | endpoint aposentado |

Duas fontes abertas com **preço e liquidez** já bastam para medir.

## Arbitragem entre mercados: já foi arbitrada

21.705 itens presentes nos dois mercados. Filtrando por liquidez real dos dois
lados (≥10 anúncios, ≥30 vendas) e preço ≥ US$ 20 — 1.109 itens:

| Custo total (ida e volta) | Itens lucrativos | % | Lucro somado | Capital | Retorno |
|---|---|---|---|---|---|
| 5% (otimista demais) | 626 | 56,4% | US$ 1.494 | US$ 55.723 | 2,7% |
| 10% | 97 | 8,7% | US$ 154 | US$ 6.573 | 2,4% |
| 12% | 34 | 3,1% | US$ 54 | US$ 2.677 | 2,0% |
| 15% (realista) | 6 | 0,5% | US$ 27 | US$ 262 | 10,2% |

**Spread mediano: 5,7%** — e praticamente idêntico em toda faixa de preço, de
US$ 1 a US$ 50+. Essa uniformidade é a evidência mais forte: num mercado com
lacuna de informação, a ineficiência apareceria **concentrada** em algum canto
(itens baratos, ou raros, ou de nicho). Ela estar espalhada uniformemente e
logo abaixo do custo de transação é o retrato de um mercado já trabalhado por
bots.

E o retorno acima é **bruto de tudo que importa**:

- **Trava de 7 dias da Valve**: o item comprado fica preso. Arbitragem vira
  posição de uma semana, e preço de skin se move mais que 2,4% em uma semana.
- O "menor preço" costuma ser anúncio ruim (float ruim, ou isca). O preço que
  de fato executa é mais alto.
- Vender ao preço do outro mercado assume venda instantânea sem precisar
  furar a fila de quem já está anunciando.

## O que ainda não foi testado

A medição acima é de **arbitragem entre praças**. Mas a experiência do
Ragnarok era outra coisa: achar, **dentro de um mercado só**, o vendedor que
anunciou abaixo do preço corrente.

Isso exige série temporal, não uma fotografia. As perguntas são:

1. Anúncios abaixo do mercado aparecem com que frequência?
2. Quanto tempo sobrevivem antes de alguém pegar?
3. Se sobrevivem minutos, dá para automatizar. Se sobrevivem segundos, os
   bots já dominam e não há espaço.

`coletor.py` tira uma foto dos dois mercados a cada 10 minutos. Com algumas
horas de fotos dá para responder as três.

```bash
python research/mercados/coletor.py 10 40   # 40 fotos, ~6,7 horas
```

As fotos ficam em `research/mercados/snapshots/` (fora do repositório).
