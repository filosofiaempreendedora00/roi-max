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
janela de operação em Config. Cada varredura custa 2 créditos por campeonato
(mercados `h2h` + `h2h_lay`). Menos campeonatos selecionados significa
varreduras mais frequentes.

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
