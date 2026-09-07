#!/usr/bin/env bash
# Imprime as variáveis para colar na Vercel, lendo do seu .env.
# Nada é gravado nem enviado: só formata o que você já tem em disco.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || { echo "Sem .env nesta pasta."; exit 1; }

# pega o valor mesmo se a linha estiver comentada (é o caso do DATABASE_URL,
# que fica comentado para o servidor local usar SQLite)
get() { grep -E "^#? *$1=" .env | head -1 | sed -E "s/^#? *$1=//" ; }

echo "Vercel -> Settings -> Environment Variables"
echo "Marque Production, Preview e Development em todas."
echo "------------------------------------------------------------------"
for k in DATABASE_URL ODDS_API_KEY ROIMAX_TOKEN CRON_SECRET \
         VAPID_PUBLIC_KEY VAPID_PRIVATE_KEY VAPID_SUBJECT BETFAIR_DOMAIN; do
  v="$(get "$k" || true)"
  [ -z "$v" ] && v="(vazio - preencha)"
  printf '%s\n  %s\n\n' "$k" "$v"
done
echo "------------------------------------------------------------------"
echo "Depois, no GitHub -> Settings -> Secrets and variables -> Actions:"
echo "  APP_URL       https://SEU-APP.vercel.app"
echo "  CRON_SECRET   (o mesmo de cima)"
