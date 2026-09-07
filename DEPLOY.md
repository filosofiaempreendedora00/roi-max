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

## Passo 1 — Banco de dados (Supabase ou Neon)

Qualquer Postgres serve. Se você já tem conta no Supabase, use ele.

### Supabase

1. **New project** → nome `roi-max`, região **South America (São Paulo)** ou
   **East US**. Guarde a senha do banco que ele pedir.
2. No projeto: **Connect** (botão no topo) → aba **Connection string**.
3. **Escolha a `Transaction pooler`** — porta **6543**. Fica assim:

   ```
   postgresql://postgres.SEUREF:SENHA@aws-0-REGIAO.pooler.supabase.com:6543/postgres
   ```

4. Troque `[YOUR-PASSWORD]` pela senha real do passo 1.

> **Não use a conexão direta** (`db.SEUREF.supabase.co:5432`). Ela responde só
> em IPv6 e a Vercel não fala IPv6 — o deploy sobe e a primeira consulta
> falha, sem mensagem que ajude.
>
> O pooler em modo transação, por sua vez, quebra *prepared statements*, que é
> o padrão do driver do Postgres. O app **já detecta** a URL do pooler e
> desliga isso sozinho, então você não precisa fazer nada — só escolher a
> string certa.

### Neon (alternativa)

1. <https://neon.com> → **Create project**, região **AWS us-east-1**.
2. Copie a connection string:
   `postgresql://usuario:senha@ep-algo.us-east-1.aws.neon.tech/neondb?sslmode=require`

Nos dois casos, essa string é o seu `DATABASE_URL`. O app cria as tabelas
sozinho na primeira vez.

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

## Diagnóstico rápido

`/api/health` responde sem token e diz o que está errado:

```bash
curl https://SEU-APP.vercel.app/api/health
```

```json
{"ok": true, "banco": "postgres/pooler", "banco_ok": true, "erro": null,
 "live_odds": true, "push_configurado": true, "serverless": true,
 "regiao": "iad1", "interface_compilada": true}
```

- `banco_ok: false` → veja `erro`, quase sempre é a `DATABASE_URL`
- `live_odds: false` → a `ODDS_API_KEY` não chegou
- `interface_compilada: false` → o build do frontend não rodou
- `regiao` → confirme que é a mesma do banco; longe dele é latência à toa

## Se der problema

| Sintoma | Causa provável |
|---|---|
| `FUNCTION_INVOCATION_FAILED` logo após o deploy | Algo estourou durante o import do módulo. Em serverless o disco é somente leitura: qualquer escrita fora de `/tmp` derruba a função antes do app carregar, e o erro sai mudo |
| `FUNCTION_INVOCATION_FAILED` em uso | `DATABASE_URL` errada, ou banco suspenso — abra o painel uma vez para acordar |
| `Failed to load Builders` no build | Versão de builder fixada no `vercel.json`. Não fixe: a Vercel resolve o runtime sozinha |
| A Vercel ignora suas rewrites e o diretório `/api` | Ela detectou um preset de framework Python pelo `requirements.txt`, e o preset tem precedência sobre funções em arquivo. Use o entrypoint na raiz (`app.py`) |
| Timeout ou "connection refused" no Supabase | Você usou a conexão direta (IPv6). Troque pela `Transaction pooler`, porta 6543 |
| `prepared statement ... does not exist` | URL do pooler não reconhecida. Confira que ela tem `:6543` ou `pooler.supabase.com` |
| `live_odds: false` | `ODDS_API_KEY` não chegou nas variáveis da Vercel |
| Login não aceita o token | O `ROIMAX_TOKEN` da Vercel é diferente do que você digitou |
| Actions falha com 401 | `CRON_SECRET` diferente entre GitHub e Vercel |
| Carta sempre vazia | Normal com filtro forte. Confira em **Sinais** se está chegando dado |
| Push não chega no iPhone | Precisa estar instalado na Tela de Início, não aberto no Safari |


---

# App de Mac

Para não depender de digitar endereço no navegador. Ele é a mesma interface
numa casca nativa: ícone no Dock, janela própria, sem barra de endereço.

## Usar

O app já está montado em `desktop/dist/mac-arm64/ROI Max.app`. Arraste para
**Aplicativos**. Na primeira abertura o macOS reclama que o app não é de
desenvolvedor identificado — é esperado, ele não tem certificado da Apple
(que custa US$ 99/ano). Clique com o **botão direito → Abrir**, e confirme.
Só na primeira vez.

Ao abrir, ele pergunta onde está o servidor:

- **Nuvem:** cole o endereço da Vercel
- **Local:** botão "Usar servidor local"

Dá para trocar depois em **Arquivo → Configurar servidor** (`Cmd+,`).

O link "Abrir na Betfair" abre no seu **navegador padrão**, de propósito:
dentro do app você estaria deslogado da Betfair.

## Reconstruir depois de mudar a interface

```bash
cd web && npm run build && cd ../desktop && npx electron-builder --mac
```

## Rodar sem empacotar (desenvolvimento)

```bash
cd desktop && npm start
```
