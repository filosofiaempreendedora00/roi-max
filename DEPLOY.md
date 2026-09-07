# Colocar o ROI Max no ar

Objetivo: sair do `localhost` e ter um endereço que abre no celular de
qualquer lugar. **Tudo abaixo é gratuito.**

## Por que não dá para simplesmente "subir na Vercel"

A Vercel é *serverless*: cada requisição acorda uma função, ela responde e
morre. Três coisas do app não sobrevivem a isso:

| O que | Por quê | Solução |
|---|---|---|
| Laço de varredura eterno | Nada fica rodando entre requisições | GitHub Actions chama `/api/cron/scan` no horário |
| SQLite em arquivo | O disco é apagado a cada invocação | Postgres na Neon (grátis) |
| WebSocket | Funções serverless não mantêm conexão aberta | O app busca sozinho a cada 90s |

Nada disso te custa nada em prática: seu produto é uma carta por dia, que não
precisa de socket aberto nem de processo eterno.

Peças finais: **Vercel** (site + API) · **Neon** (banco) · **GitHub Actions**
(agendador).

---

## Passo 1 — Banco de dados na Neon

1. Entre em <https://neon.com> e crie conta com o GitHub.
2. **Create project** → nome `roi-max`, região **AWS us-east-1** (mesma região
   padrão da Vercel; banco longe da função é latência à toa).
3. Copie a **connection string**. É parecida com:
   `postgresql://usuario:senha@ep-algo-123.us-east-1.aws.neon.tech/neondb?sslmode=require`

Guarde: é o seu `DATABASE_URL`. O app cria as tabelas sozinho na primeira vez.

## Passo 2 — Suas chaves

Já estão geradas no seu `.env`. Para ver:

```bash
cd "/Users/roberto/Projetos do Claude/ROI Max" && cat .env
```

Você vai precisar de cinco valores: `ODDS_API_KEY`, `ROIMAX_TOKEN`,
`CRON_SECRET`, `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`.

> O `.env` está no `.gitignore` e nunca vai para o GitHub. Na nuvem esses
> valores viram variáveis de ambiente, que também não aparecem no código.

## Passo 3 — Vercel

1. <https://vercel.com> → entre com o GitHub.
2. **Add New → Project** → importe `filosofiaempreendedora00/roi-max`.
3. Não mexa em build nem em output: o `vercel.json` já define tudo.
4. Antes de clicar em Deploy, abra **Environment Variables** e adicione:

   | Nome | Valor |
   |---|---|
   | `DATABASE_URL` | a string da Neon (passo 1) |
   | `ODDS_API_KEY` | sua chave da The Odds API |
   | `ROIMAX_TOKEN` | do seu `.env` |
   | `CRON_SECRET` | do seu `.env` |
   | `VAPID_PUBLIC_KEY` | do seu `.env` |
   | `VAPID_PRIVATE_KEY` | do seu `.env` |
   | `VAPID_SUBJECT` | `mailto:seu-email@exemplo.com` |
   | `BETFAIR_DOMAIN` | `www.betfair.bet.br` |

5. **Deploy**. Ao terminar você recebe um endereço tipo
   `https://roi-max.vercel.app` — **esse é o seu link**.

Teste antes de comemorar:

```bash
curl https://SEU-APP.vercel.app/api/health
```

Deve responder `{"ok":true,"live_odds":true,...}`. Se `live_odds` vier
`false`, a `ODDS_API_KEY` não chegou.

## Passo 4 — Agendador

O conteúdo do agendador está em **`deploy/scan-workflow.yml`**. Ele não pode
ser publicado direto pelo terminal: o GitHub exige a permissão `workflow` no
token, que o seu não tem. Duas saídas — a segunda leva 30 segundos:

**Opção A (pelo site, mais rápida).** No GitHub, aba **Actions** → *New
workflow* → *set up a workflow yourself*. Nomeie o arquivo `scan.yml`, apague
o conteúdo de exemplo, cole o de `deploy/scan-workflow.yml` e clique em
**Commit changes**.

**Opção B (destravar o terminal).** Em <https://github.com/settings/tokens>,
edite o token que você usa e marque a permissão **`workflow`**. Depois, aqui:

```bash
mkdir -p .github/workflows && cp deploy/scan-workflow.yml .github/workflows/scan.yml && git add -A && git commit -m "Agendador de varredura" && git push
```

Feito isso, falta dar ao workflow o endereço e o segredo.

No GitHub: **Settings → Secrets and variables → Actions → New repository
secret**, duas vezes:

| Nome | Valor |
|---|---|
| `APP_URL` | `https://SEU-APP.vercel.app` (sem barra no fim) |
| `CRON_SECRET` | o mesmo do `.env` e da Vercel |

Para testar sem esperar o horário: aba **Actions** → *Varredura de odds* →
**Run workflow**. Ele imprime quantos sinais achou e quantos créditos sobraram.

Os três horários (11h, 16h e 19h de Brasília) gastam **3 créditos por
campeonato por dia**. Com 14 campeonatos são 42/dia, o que estoura os 500 do
mês. Comece com **4 ou 5 campeonatos** em Config e vá ajustando pelo medidor
de créditos.

## Passo 5 — No celular

1. Abra o link no **Safari** (iPhone) ou Chrome (Android).
2. Digite o `ROIMAX_TOKEN`.
3. **Compartilhar → Adicionar à Tela de Início**.
4. Abra pelo ícone da tela inicial e vá em **Config → Notificações → Ativar
   neste dispositivo**.

No iPhone o push só funciona pelo app instalado — o Safari comum não recebe.
É limitação da Apple, não do app.

---

## Depois de no ar

**O backtest continua rodando na sua máquina**, não na nuvem: ele depende do
pandas, que estoura o limite de tamanho da função serverless. E faz sentido —
backtest é pesquisa, não operação diária:

```bash
./scripts/backtest.sh --divs E0 SP1 I1 D1 F1 --seasons 2324 2425
```

**Levar os dados locais para a nuvem** (opcional, se quiser preservar o
histórico de créditos e cotações já coletados):

```bash
./scripts/db_copy.py "postgresql://...sua-url-da-neon..."
```

## Se der problema

| Sintoma | Causa provável |
|---|---|
| `FUNCTION_INVOCATION_FAILED` | `DATABASE_URL` errada ou banco da Neon suspenso — abra o painel da Neon uma vez para acordar |
| `live_odds: false` | `ODDS_API_KEY` não chegou nas variáveis da Vercel |
| Login não aceita o token | O `ROIMAX_TOKEN` da Vercel é diferente do que você digitou |
| Actions falha com 401 | `CRON_SECRET` diferente entre GitHub e Vercel |
| Carta sempre vazia | Normal com filtro forte. Confira em **Sinais** se está chegando dado |
| Push não chega no iPhone | Precisa estar instalado na Tela de Início, não aberto no Safari |
