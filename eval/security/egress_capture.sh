#!/usr/bin/env bash
# Records every packet the API or the worker sends, from before the container starts until it has done real work, and counts
# any that go to a public address.
#
# The service runs inside the network namespace of an idle container that tcpdump is already watching, so startup is captured
# too. Docker's DNS server listens on 127.0.0.11 inside that namespace, so the capture also shows every name looked up.
#
#   eval/security/egress_capture.sh api      start the API and answer one question
#   eval/security/egress_capture.sh worker   start the worker and ingest one uploaded contract
#
# Needs the stack running (make up), the dev master login in .env, and Ollama for the API run. The raw capture holds a login
# token, so it stays in the git-ignored data/ folder; the summary goes to eval/reports/security_2026-11/.
set -euo pipefail
SERVICE=${1:?usage: egress_capture.sh api|worker}
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"
RAW=$ROOT/data/benchmarks/egress
OUT=$ROOT/eval/reports/security_2026-11/egress_$SERVICE.txt
NETSHOOT=nicolaka/netshoot:v0.13
API=http://localhost:8002
mkdir -p "$RAW"
OVERRIDE=$(mktemp --suffix=.yml)

cleanup() {
  docker rm -f egress-ns egress-cap >/dev/null 2>&1 || true
  docker compose up -d --no-deps --force-recreate "$SERVICE" >/dev/null 2>&1 || true
  rm -f "$OVERRIDE"
}
trap cleanup EXIT

# Docker refuses ports and extra_hosts on a service that shares another container's network, so they move to the idle container.
{
  echo "services:"
  echo "  $SERVICE:"
  echo "    network_mode: \"container:egress-ns\""
  echo "    extra_hosts: !reset []"
  [ "$SERVICE" = api ] && echo "    ports: !reset []"
} >"$OVERRIDE"
PORTS=()
[ "$SERVICE" = api ] && PORTS=(-p 8002:8000)

docker rm -f egress-ns egress-cap >/dev/null 2>&1 || true
docker stop "jurisguard-$SERVICE-1" >/dev/null 2>&1 || true
rm -f "$RAW/$SERVICE.pcap"
docker run -d --name egress-ns --network jurisguard_default --network-alias "$SERVICE" \
  --add-host host.docker.internal:host-gateway "${PORTS[@]}" $NETSHOOT sleep infinity >/dev/null
docker run -d --name egress-cap --network container:egress-ns --cap-add NET_ADMIN --cap-add NET_RAW \
  -v "$RAW:/out" $NETSHOOT tcpdump -i any -n -U -w "/out/$SERVICE.pcap" >/dev/null
sleep 3
STARTED=$(date -u +%FT%TZ)
docker compose -f docker-compose.yml -f "$OVERRIDE" up -d --no-deps --force-recreate "$SERVICE" >/dev/null 2>&1

login() {
  local email password
  email=$(grep '^DEV_MASTER_EMAIL=' .env | cut -d= -f2-)
  password=$(grep '^DEV_MASTER_PASSWORD=' .env | cut -d= -f2-)
  curl -sf -m10 -H 'Content-Type: application/json' -d "{\"email\":\"$email\",\"password\":\"$password\"}" \
    "$API/api/v1/auth/login" | python3 -c 'import json,sys;print(json.load(sys.stdin)["access_token"])'
}

if [ "$SERVICE" = api ]; then
  for _ in $(seq 1 60); do curl -sf -m2 "$API/health" >/dev/null 2>&1 && break; sleep 5; done
  TOKEN=$(login)
  QUESTION="Under Article 17 GDPR, when must a controller erase personal data? (egress check $(date +%s))"
  WORK=$(curl -sf -m300 -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
    -d "{\"message\":\"$QUESTION\",\"use_law_corpus\":true,\"skip_cache\":true}" "$API/api/v1/chat" \
    | python3 -c 'import json,sys;d=json.load(sys.stdin);print(f"answered one question: answer_mode={d[\"answer_mode\"]}, sources={len(d[\"sources\"])}")')
else
  for _ in $(seq 1 60); do docker logs jurisguard-worker-1 2>&1 | grep -q "ready\." && break; sleep 5; done
  TOKEN=$(login)
  MATTER=$(curl -sf -m10 -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
    -d "{\"name\":\"egress check $(date +%s)\"}" "$API/api/v1/matters" | python3 -c 'import json,sys;print(json.load(sys.stdin)["id"])')
  DOC=$(curl -sf -m30 -H "Authorization: Bearer $TOKEN" \
    -F "file=@data/benchmarks/legalbench/data/corpus/contractnli/stony_hill_buyer_nda.txt;type=text/plain" \
    "$API/api/v1/matters/$MATTER/documents" | python3 -c 'import json,sys;print(json.load(sys.stdin)["id"])')
  STATUS=queued
  for _ in $(seq 1 60); do
    STATUS=$(curl -sf -m10 -H "Authorization: Bearer $TOKEN" "$API/api/v1/matters/$MATTER/documents/$DOC/status" \
      | python3 -c 'import json,sys;print(json.load(sys.stdin)["status"])')
    [ "$STATUS" = processed ] || [ "$STATUS" = failed ] && break
    sleep 5
  done
  WORK="ingested one uploaded contract (ContractNLI stony_hill_buyer_nda.txt): status=$STATUS"
fi
sleep 3
docker stop egress-cap >/dev/null

PRIVATE="dst net 10.0.0.0/8 or dst net 172.16.0.0/12 or dst net 192.168.0.0/16 or dst net 127.0.0.0/8 or dst net 169.254.0.0/16"
SUMMARY=$(docker run --rm -v "$RAW:/out" $NETSHOOT sh -c "
  f=/out/$SERVICE.pcap
  echo \"packets captured: \$(tcpdump -n -r \$f 2>/dev/null | wc -l)\"
  echo \"IPv4 packets to a public address: \$(tcpdump -n -r \$f 'ip and not ($PRIVATE)' 2>/dev/null | wc -l)\"
  echo \"IPv6 packets beyond link-local and multicast: \$(tcpdump -n -r \$f 'ip6 and not (dst net fe80::/10 or dst net ff00::/8)' 2>/dev/null | wc -l)\"
  echo 'connections opened (count, destination address.port):'
  tcpdump -n -r \$f 'tcp[tcpflags] & tcp-syn != 0 and tcp[tcpflags] & tcp-ack == 0' 2>/dev/null \
    | grep -oE '> [0-9.]+\.[0-9]+' | sed 's/> //' | sort | uniq -c
  echo 'names looked up (count, name):'
  tcpdump -n -A -r \$f 'dst host 127.0.0.11' 2>/dev/null | grep -aoE '[a-z][a-z0-9-]+\.{5}' | sed 's/\.*\$//' | sort | uniq -c
")
{
  echo "service: $SERVICE"
  echo "commit: $(git rev-parse --short HEAD)"
  echo "capture: $STARTED to $(date -u +%FT%TZ), before container start until the work finished"
  echo "work: $WORK"
  echo "$SUMMARY"
} | tee "$OUT"
