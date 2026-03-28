rm -f deploy.sh && cat > deploy.sh << 'EOF'
#!/usr/bin/env bash
set -euo pipefail
IP_LIST=""; SSH_USER=""; SSH_PASS=""; SSH_PORT=22
DEPLOY_FILE=""; DEPLOY_FILE_DEST=""; SERVICE_FILE=""; SERVICE_NAME=""
LOG_FILE="deploy_$(date +%Y%m%d_%H%M%S).log"; PARALLEL=false; SSH_TIMEOUT=10
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()   { echo -e "$(date '+%Y-%m-%d %H:%M:%S') [$1] $2" | tee -a "$LOG_FILE"; }
info()  { log "INFO " "${GREEN}$*${NC}"; }
warn()  { log "WARN " "${YELLOW}$*${NC}"; }
error() { log "ERROR" "${RED}$*${NC}"; }
check_deps() {
  for cmd in sshpass ssh scp; do command -v "$cmd" &>/dev/null || { error "Missing: $cmd"; exit 1; }; done
}
validate_config() {
  local err=0
  [[ -z "$IP_LIST" ]]          && { error "-i required"; err=1; }
  [[ -n "$IP_LIST" && ! -f "$IP_LIST" ]] && { error "IP list not found: $IP_LIST"; err=1; }
  [[ -z "$SSH_USER" ]]         && { error "-u required"; err=1; }
  [[ -z "$SSH_PASS" ]]         && { error "Password required"; err=1; }
  [[ -z "$DEPLOY_FILE" ]]      && { error "-f required"; err=1; }
  [[ ! -f "$DEPLOY_FILE" ]]    && { error "File not found: $DEPLOY_FILE"; err=1; }
  [[ -z "$DEPLOY_FILE_DEST" ]] && { error "-d required"; err=1; }
  [[ -z "$SERVICE_FILE" ]]     && { error "-s required"; err=1; }
  [[ ! -f "$SERVICE_FILE" ]]   && { error "Service file not found: $SERVICE_FILE"; err=1; }
  [[ -z "$SERVICE_NAME" ]]     && { error "-n required"; err=1; }
  [[ $err -eq 1 ]] && exit 1
}
SSHOPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10 -o BatchMode=no"
rssh() { local h=$1; shift; sshpass -e ssh $SSHOPTS -p $SSH_PORT "${SSH_USER}@${h}" "$@"; }
rscp() { sshpass -e scp $SSHOPTS -P $SSH_PORT "$1" "${SSH_USER}@${2}:${3}"; }
deploy_host() {
  local ip="$1"
  info "[${ip}] Starting"
  rssh "$ip" "sudo mkdir -p '$(dirname $DEPLOY_FILE_DEST)'"                         || { error "[${ip}] mkdir failed"; return 1; }
  rscp "$DEPLOY_FILE" "$ip" "/tmp/$(basename $DEPLOY_FILE)"                         || { error "[${ip}] scp file failed"; return 1; }
  rssh "$ip" "sudo mv '/tmp/$(basename $DEPLOY_FILE)' '$DEPLOY_FILE_DEST'"          || { error "[${ip}] mv file failed"; return 1; }
  info "[${ip}] ✔ $DEPLOY_FILE_DEST"
  rscp "$SERVICE_FILE" "$ip" "/tmp/${SERVICE_NAME}"                                 || { error "[${ip}] scp service failed"; return 1; }
  rssh "$ip" "sudo mv '/tmp/${SERVICE_NAME}' '/etc/systemd/system/${SERVICE_NAME}'" || { error "[${ip}] mv service failed"; return 1; }
  info "[${ip}] ✔ /etc/systemd/system/${SERVICE_NAME}"
  rssh "$ip" "sudo systemctl daemon-reload && sudo systemctl enable '$SERVICE_NAME' && sudo systemctl start '$SERVICE_NAME'" || { error "[${ip}] systemctl failed"; return 1; }
  info "[${ip}] ✔ enabled and started"
  local s; s=$(rssh "$ip" "systemctl is-active '$SERVICE_NAME'" 2>/dev/null || echo "unknown")
  [[ "$s" == "active" ]] && info "[${ip}] ✔ ACTIVE" || warn "[${ip}] Status: $s"
}
main() {
  while getopts ":i:u:p:P:f:d:s:n:jh" o; do
    case $o in
      i) IP_LIST="$OPTARG";; u) SSH_USER="$OPTARG";; p) SSH_PASS="$OPTARG";;
      P) SSH_PORT="$OPTARG";; f) DEPLOY_FILE="$OPTARG";; d) DEPLOY_FILE_DEST="$OPTARG";;
      s) SERVICE_FILE="$OPTARG";; n) SERVICE_NAME="$OPTARG";; j) PARALLEL=true;;
      h) echo "Usage: $0 -i hosts -u user -f file -d dest -s service -n name [-j]"; exit 0;;
    esac
  done
  SSH_PASS="${DEPLOY_PASS:-$SSH_PASS}"
  check_deps; validate_config
  export SSHPASS="$SSH_PASS"
  HOSTS=(); failed=(); succeeded=()
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line//$'\r'/}"
    [[ "$line" =~ ^\s*# ]] && continue
    [[ -z "${line// }" ]] && continue
    HOSTS+=("$line")
  done < "$IP_LIST"
  [[ ${#HOSTS[@]} -eq 0 ]] && { error "No hosts in $IP_LIST"; exit 1; }
  info "Deploying to ${#HOSTS[@]} host(s)"
  for ip in "${HOSTS[@]}"; do
    if deploy_host "$ip"; then succeeded+=("$ip"); else failed+=("$ip"); fi
  done
  info "=== DONE === OK: ${succeeded[*]:-none}"
  [[ ${#failed[@]} -gt 0 ]] && { error "FAILED: ${failed[*]}"; exit 1; }
}
main "$@"
EOF
chmod +x deploy.sh
wc -l deploy.sh
