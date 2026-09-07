# ROI Max

Motor de sinais de assimetria de odds para a Betfair Exchange, com app
sincronizado em desktop e celular.

---

## Leia isto antes de qualquer coisa

**1. Conta brasileira não tem API da Betfair.** Desde 01/01/2025 a Betfair
encerrou o *Personal Direct API access* para clientes do Brasil: as
application keys foram desativadas e `developer.betfair.com` ficou
inacessível para conta/IP BR. O motivo declarado são as exigências de GeoIP
e autenticação da regulamentação brasileira, que restringem bots.

Consequência prática: **este app não envia ordens.** Ele detecta a
assimetria, te avisa em segundos e abre o mercado exato com um toque. A
aposta você confirma na Betfair. Contornar o geobloqueio violaria os termos
e coloca seu saldo em risco — não está implementado e não deve ser.

**2. O dado que as casas usam não está à venda.** Sportradar, Genius Sports
e Stats Perform vendem feeds de scout in-stadium com latência abaixo de um
segundo, sob contrato enterprise. Você não terá paridade de dados com as
casas. O edge, se existir, virá do modelo — e é por isso que o backtest vem
antes do app na ordem de importância.

**3. Com orçamento zero não existe odds ao vivo contínua.** O free tier da
The Odds API são 500 créditos/mês (~16 chamadas por dia); o da OddsPapi, 250.
Por isso o app tem um gestor de créditos que só varre dentro da sua janela de
operação. O que é abundante e gratuito é o **histórico** — e ele é suficiente
para responder a pergunta que importa: *a estratégia tem edge?*

---

## O que está construído

```
backend/roimax/
  config.py                 configuração via .env
  models.py                 Event, Quote, MarketBook, Signal
  db.py                     SQLite (ticks, sinais, créditos, inscrições push)
  engine/math.py            probabilidade, remoção de margem, EV, Kelly
  engine/detectors.py       os cinco detectores de assimetria
  providers/theoddsapi.py   Betfair Exchange back+lay sem app key
  providers/footballdata_uk.py  histórico gratuito, com odds da Exchange
  backtest/replay.py        liquidação, ROI, drawdown e CLV
  budget.py                 gestor dos 500 créditos/mês
  scheduler.py              laço de varredura consciente de orçamento
  hub.py                    WebSocket: a fonte única de verdade
  push.py                   Web Push (VAPID)
  main.py                   API HTTP + WS + serve a PWA
web/                        PWA React/TypeScript (desktop + mobile)
```

### A carta do dia

Uma vez por dia (padrão 16h de Brasília) o motor monta uma carta: as melhores
entradas do dia, ordenadas, com stake calculado e **preço-limite**.

Três coisas que a carta faz e uma varredura crua não faz:

1. **Ordena e corta.** Vinte sinais fracos diluem a banca e enterram o que
   importa. O padrão são 5 entradas.
2. **Diversifica.** Máximo de 1 por jogo e 2 por liga — duas entradas no mesmo
   jogo não são duas apostas, são uma com o dobro do tamanho.
3. **Dá o preço-limite.** O preço se move entre o sinal e o seu toque. Abaixo
   do limite (ou acima dele, num lay) a vantagem já foi embora. O limite vem
   encaixado na escada de preços da Betfair, arredondado sempre a favor da
   vantagem.

A carta sai tarde de propósito: o backtest mostrou que o preço de abertura da
Exchange é pior que o de fechamento, então quanto mais perto dos jogos,
melhor o preço.

### CLV: o painel de controle

O app grava o preço de fechamento de cada palpite — de graça, aproveitando as
varreduras que já acontecem — e mostra o seu **CLV real**.

Isto não é enfeite. Com o volume de um apostador pessoal, o ROI leva anos para
sair do ruído: no backtest, 17 apostas com odd média 4,85 deram ROI de −75%
por puro azar. O CLV dá sinal em dezenas de apostas. Bater o fechamento em
mais de 52% das entradas é o que sustenta lucro no longo prazo.

Se o seu CLV real vier negativo, o remédio é filtro mais apertado, não mais
volume.

### Os cinco detectores

| Sinal | Dispara quando | Como agir |
|---|---|---|
| `VALUE_BACK` | a Exchange paga acima do consenso das casas | back |
| `VALUE_LAY` | a Exchange cobra abaixo do consenso | lay |
| `ARBITRAGE` | melhor preço por resultado soma < 1 | back nas três pernas |
| `STEAM` | o preço se moveu > 6% na janela recente | reavaliar, não entrar cego |
| `WIDE_SPREAD` | book fino demais na Exchange | entrar na frente da fila |

O consenso remove a margem de **cada casa separadamente** (método da
potência) antes de fazer a média. Tirar a média das odds cruas embutiria a
margem no resultado e inventaria valor que não existe.

---

## Colocar no ar

Passo a passo completo em **[DEPLOY.md](DEPLOY.md)** — Vercel para o site e a
API, Neon para o banco, GitHub Actions como agendador. Tudo em camada
gratuita.

Resumo do porquê da arquitetura: a Vercel é serverless, então o laço de
varredura eterno, o WebSocket e o SQLite em arquivo não sobrevivem lá. A
varredura passa a vir de fora por `/api/cron/scan`, o banco vira Postgres e o
app busca estado a cada 90 segundos. Para uma carta por dia, nada disso faz
falta.

## Instalação

Requisitos: **Python 3.11+** e **Node 18+**.

O macOS traz só o Python 3.9, que não serve. A forma mais leve de resolver é
o `uv`, que instala um Python próprio na pasta do usuário sem pedir senha de
administrador e sem tocar no Python do sistema:

```bash
uv python install 3.13
uv venv --python 3.13
uv pip install -e "backend[dev]"
cp .env.example .env
```

Sem `uv`, qualquer Python 3.11+ serve:

```bash
python3 -m venv .venv
./.venv/bin/pip install -e "backend[dev]"
cp .env.example .env
```

Nenhuma chave é obrigatória para rodar o backtest.

### Backtest primeiro

```bash
./scripts/backtest.sh --divs E0 SP1 I1 D1 F1 --seasons 2223 2324 2425 2526
```

Baixa os CSVs gratuitos, reconstrói cada mercado 1X2 como ele estava, roda os
detectores e liquida contra o resultado real, já descontada a comissão.

**Leia o CLV antes do ROI.** O *closing line value* mede se a entrada pegou
preço melhor que o fechamento. É o melhor preditor conhecido de lucro no
longo prazo, porque o preço de fechamento é a estimativa mais eficiente que o
mercado produz. ROI positivo com CLV negativo em amostra pequena é variância,
e evapora. A régua prática: CLV médio positivo e mais de ~52% das entradas
batendo o fechamento.

O relatório inclui um controle (back cego no favorito) para você ter com o
que comparar.

### Rodar o app

```bash
./scripts/start.sh          # produção local
./scripts/dev.sh            # desenvolvimento com reload
```

Desktop em `http://localhost:8000`. Celular na mesma Wi-Fi, no IP que o script
imprime. Os dois assinam o mesmo WebSocket, então mostram o mesmo estado no
mesmo instante — nenhum cliente guarda estado próprio.

### Push no celular

```bash
cd backend && ../.venv/bin/python -m roimax.push --generate-keys   # cole no .env
```

Depois, em Config → Notificações → *Ativar neste dispositivo*.

No **iPhone** o push só funciona com a PWA instalada: Safari → Compartilhar →
Adicionar à Tela de Início, e ativar de dentro do app instalado. A Apple não
expõe push para PWA aberta no Safari comum.

Para receber fora de casa é preciso expor o servidor com HTTPS (Web Push
exige contexto seguro). Um túnel Cloudflare gratuito resolve.

### Odds ao vivo

Crie uma chave em `the-odds-api.com`, coloque em `ODDS_API_KEY` e ajuste a
janela de operação em Config.

Cada varredura custa **1 crédito por campeonato** no padrão (só `h2h`), ou 2
se você ligar `include_lay`. Como as entradas da carta são para deixar rolar,
o lay fica desligado: com 500 créditos/mês e uma varredura diária, isso são
~16 campeonatos por dia em vez de 8.

**Sobre quantas entradas esperar.** O backtest deu a fronteira honesta, com 12
ligas e só o mercado 1X2:

| EV mínimo | entradas/semana | CLV |
|---|---|---|
| 0,02 | 0,58 | +9,55% |
| 0,01 | 1,13 | +5,55% |
| 0,00 | 2,06 | +3,35% |
| −0,02 | 7,21 | +0,35% |

Mais cobertura multiplica isso proporcionalmente. Afrouxar o EV aumenta o
volume e derruba a vantagem — em EV negativo ela desaparece. Não existe
configuração que dê muito volume e muita vantagem ao mesmo tempo com dados
gratuitos; ver `research/README.md`.

---

## Testes

```bash
./.venv/bin/python -m pytest backend/tests -q
```

---

## O que este app não faz

- Não envia apostas, não automatiza execução, não contorna geobloqueio.
- Não garante lucro. A Betfair cobra comissão sobre lucro líquido por mercado,
  e assimetrias óbvias são arbitradas em segundos por bots com colocation.
  O app dá velocidade e disciplina; o edge tem que vir do modelo.
- Não substitui o backtest. Um sinal só merece um push depois de sobreviver ao
  histórico.
