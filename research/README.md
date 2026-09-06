# Pesquisa: existe edge?

Protótipos em Node para responder a pergunta que precede o produto inteiro:
**o que dá para bater na Betfair com dados gratuitos?**

Estão em Node, e não em Python, por um motivo prático: o Mac só tem Python
3.9.6 e a instalação de uma versão moderna está pendente. Node roda hoje.
São protótipos de validação, não código de produção — o backend definitivo
é o `backend/` em Python.

## Como rodar

Os CSVs vêm do football-data.co.uk. O site estava devolvendo 503 em HTTPS
durante estes testes; em HTTP puro funciona, e há espelhos no GitHub.

```bash
mkdir fd && cd fd
for s in 1920 2021 2122 2223 2324 2425; do
  for d in E0 E1 SP1 I1 D1 F1 N1 P1 B1 T1 SC0 G1; do
    curl -sL -o "${d}_${s}.csv" "http://football-data.co.uk/mmz4281/$s/$d.csv"
  done
done
cd .. && node diag.mjs && node diverg.mjs && node big.mjs
```

## O que cada arquivo faz

| Arquivo | Pergunta que responde |
|---|---|
| `proto.mjs` | Dixon-Coles: ajuste com decaimento temporal, correção de placar baixo, matriz de placares |
| `diag.mjs` | O modelo prevê melhor que o mercado? (log-loss e Brier) |
| `bt.mjs` | Apostar nas discordâncias do modelo dá lucro? |
| `diverg.mjs` | E apostar onde a Exchange discorda do consenso? |
| `big.mjs` | O mesmo, em amostra 7x maior (melhor preço vs consenso) |

## Resultados

Amostra: 16.981 jogos, 12 ligas europeias, temporadas 2019/20 a 2024/25.
Backtest walk-forward — o modelo só enxerga jogos anteriores à data da
aposta, com refit a cada 30 dias.

### 1. O modelo funciona, mas perde do mercado

Log-loss no 1X2 (menor é melhor), 13.654 jogos:

| | log-loss | Brier |
|---|---|---|
| Taxas-base (44/26/30) | 1,0750 | — |
| **Dixon-Coles** | **0,9940** | 0,5926 |
| **Mercado** | **0,9688** | 0,5759 |

O modelo bate as taxas-base com folga, então está ajustado e converge
(300 e 900 iterações dão o mesmo resultado). Ele simplesmente é pior que o
preço de mercado. Apostar onde ele discorda é apostar no próprio erro:

| Peso do modelo | n | ROI | CLV |
|---|---|---|---|
| 0,20 | 307 | −18,92% | −10,02% |
| 0,50 | 5.533 | −15,56% | −7,23% |
| 1,00 | 15.335 | −13,36% | −6,83% |

**Conclusão: modelo de gols não é o caminho.** Nenhum peso salva. O CLV
negativo em todos eles diz que a seleção é ativamente ruim, não apenas
neutra.

### 2. Divergência de preço mostra sinal real

Melhor preço do mercado contra o consenso das casas, 1X2:

| Divergência | n | ROI | t | CLV | Bateu o fecho |
|---|---|---|---|---|---|
| ≥ 2% | 2.331 | +3,37% ±3,87 | 0,87 | +2,42% | 56,2% |
| ≥ 4% | 621 | +9,53% ±9,18 | 1,04 | +4,72% | 59,6% |
| ≥ 6% | 226 | +24,58% ±19,10 | 1,29 | +8,84% | 66,8% |
| ≥ 8% | 91 | +8,96% ±23,02 | 0,39 | +11,62% | 72,5% |
| ≥ 12% | 31 | −42,42% ±28,80 | −1,47 | +20,67% | 74,2% |

Over/Under 2.5 repete o padrão: CLV +3,73% → +8,53% → +16,78%, com taxa de
acerto contra o fechamento subindo de 66,8% para 83,3%.

**O CLV sobe de forma monótona com o filtro.** Isso é assinatura de sinal
verdadeiro. O ROI, não: `t` nunca passa de 1,3, ou seja, nenhum dos números
de ROI é estatisticamente distinguível de zero. A amostra é pequena demais
para afirmar lucro — mas grande o bastante para afirmar que a seleção pega
preços melhores que o fechamento.

### 3. Controles

- **Apostar em todo favorito pelo melhor preço:** ROI −0,23% ±0,76 (t=−0,30)
  em 16.980 apostas. Praticamente zero, que é o esperado quando se toma o
  melhor preço entre 20 casas. Isso valida o arcabouço: não há bug inflando
  resultado.
- **Apostar cego no preço de abertura da Exchange:** ROI −9% a −14%, com CLV
  de **−4% a −7%**. As odds da Betfair se alongam da abertura para o
  fechamento, então entrar cedo sem filtro custa caro por construção.

## O que isso significa para o produto

1. A seleção tem que vir de **divergência de preço**, não de modelo próprio.
2. **CLV é a métrica de controle**, não ROI. Com o volume de um apostador
   pessoal, o ROI leva anos para sair do ruído; o CLV dá sinal em semanas.
3. Entrar de manhã e deixar rolar paga um pedágio: o preço de abertura é
   pior que o de fechamento. Quanto mais perto do jogo, melhor.
4. Filtro forte (≥6%) seleciona ~1,3% dos jogos. Para chegar a 5–10 entradas
   por dia sem afrouxar o filtro, o caminho é **mais mercados**, não mais
   tolerância.

## Limites destes testes

- Preço de Exchange só existe em 2024/25 no histórico gratuito (2.457 jogos).
  Os testes maiores usam o melhor preço entre casas tradicionais — que
  limitam e fecham conta de ganhador, coisa que a Exchange não faz.
- Não modela liquidez. Um preço fora de linha na Exchange muitas vezes tem
  pouco dinheiro disponível: aparece no gráfico e não se materializa na
  aposta.
- Não cobre outros esportes nem mercados além de 1X2, O/U 2.5 e handicap
  asiático, que é o que o histórico gratuito traz.
