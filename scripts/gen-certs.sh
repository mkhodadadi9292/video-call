#!/usr/bin/env bash
# Generate a self-signed TLS certificate for LAN use (Jitsi + main nginx).
# Usage: ./scripts/gen-certs.sh <YOUR-LAN-IP>
# Then set JITSI_PUBLIC_URL=https://<YOUR-LAN-IP>:8443 in .env
set -euo pipefail

IP="${1:?Usage: ./scripts/gen-certs.sh <YOUR-LAN-IP>}"

mkdir -p jitsi-certs

openssl req -new -x509 -days 3650 -nodes \
  -out jitsi-certs/cert.crt \
  -keyout jitsi-certs/cert.key \
  -subj "/C=US/ST=TX/L=Austin/O=video-call-system/CN=${IP}" \
  -addext "subjectAltName=DNS:localhost,DNS:*.localhost,IP:127.0.0.1,IP:${IP}"

echo "Certificates written to jitsi-certs/ (cert.crt, cert.key)"
echo "Set JITSI_PUBLIC_URL=https://${IP}:8443 in .env and restart:"
echo "  docker compose up -d --force-recreate jitsi-web nginx"
