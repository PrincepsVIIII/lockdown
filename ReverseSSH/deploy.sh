#!/usr/bin/env bash
# =============================================================================
# deploy.sh — Deploy a file and systemd service to multiple Linux hosts via SSH
# Requirements: sshpass, ssh, scp
# Usage: ./deploy.sh [options]
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
# CONFIGURATION — edit these or override via CLI flags
# -----------------------------------------------------------------------------
IP_LIST=""            # Path to file containing one IP per line
SSH_USER=""           # Remote username
SSH_PASS=""           # Password (or set DEPLOY_PASS env var)
SSH_PORT=22           # SSH port

DEPLOY_FILE=""        # Local path to the file to deploy
DEPLOY_FILE_DEST=""   # Remote destination path (e.g. /opt/myapp/myfile.conf)

SERVICE_FILE=""       # Local path to the .service unit file
SERVICE_NAME=""       # Service name (e.g. myapp.service)
# SERVICE_FILE_DEST is always /etc/systemd/system/$SERVICE_NAME

LOG_FILE="deploy_$(date +%Y%m%d_%H%M%S).log"
PARALLEL=false        # Set to true to deploy to all hosts concurrently
SSH_TIMEOUT=10        # Seconds before SSH connection times out

# Colours
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------
usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  -i  PATH     File containing target IPs (one per line)
  -u  USER     SSH username
  -p  PASS     SSH password (insecure; prefer DEPLOY_PASS env var)
  -P  PORT     SSH port (default: 22)
  -f  FILE     Local file to deploy
  -d  DEST     Remote destination path for the file
  -s  SERVICE  Local .service unit file
  -n  NAME     Service name (e.g. myapp.service)
  -j           Run deployments in parallel
  -h           Show this help

Environment variables:
  DEPLOY_PASS  SSH password (preferred over -p flag)

Example:
  DEPLOY_PASS='s3cr3t' ./deploy.sh \\
    -i hosts.txt -u admin \\
    -f ./myapp.conf -d /etc/myapp/myapp.conf \\
    -s ./myapp.service -n myapp.service
EOF
  exit 0
}

log() {
  local level="$1"; shift
  local msg="$*"
  local ts; ts="$(date '+%Y-%m-%d %H:%M:%S')"
  echo -e "${ts} [${level}] ${msg}" | tee -a "$LOG_FILE"
}

info()    { log "INFO " "${GREEN}$*${NC}"; }
warn()    { log "WARN " "${YELLOW}$*${NC}"; }
error()   { log "ERROR" "${RED}$*${NC}"; }

check_deps() {
  local missing=()
  for cmd in sshpass ssh scp; do
    command -v "$cmd" &>/dev/null || missing+=("$cmd")
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    error "Missing required tools: ${missing[*]}"
    echo "  Install with: sudo apt install sshpass openssh-client"
    exit 1
  fi
}

validate_config() {
  local err=0
  [[ -z "$IP_LIST" ]]           && { error "-i IP list file is required";        err=1; }
  [[ -n "$IP_LIST" && ! -f "$IP_LIST" ]] && { error "IP list not found: $IP_LIST"; err=1; }
  [[ -z "$SSH_USER" ]]          && { error "-u SSH user is required";            err=1; }
  [[ -z "$SSH_PASS" ]]          && { error "SSH password required (-p or DEPLOY_PASS)"; err=1; }
  [[ -z "$DEPLOY_FILE" ]]       && { error "-f deploy file is required";         err=1; }
  [[ ! -f "$DEPLOY_FILE" ]]     && { error "Deploy file not found: $DEPLOY_FILE"; err=1; }
  [[ -z "$DEPLOY_FILE_DEST" ]]  && { error "-d remote destination is required";  err=1; }
  [[ -z "$SERVICE_FILE" ]]      && { error "-s service file is required";        err=1; }
  [[ ! -f "$SERVICE_FILE" ]]    && { error "Service file not found: $SERVICE_FILE"; err=1; }
  [[ -z "$SERVICE_NAME" ]]      && { error "-n service name is required";        err=1; }
  [[ $err -eq 1 ]] && exit 1
}

# Shared SSH/SCP options
ssh_opts() {
  echo "-o StrictHostKeyChecking=no \
        -o ConnectTimeout=${SSH_TIMEOUT} \
        -o BatchMode=no \
        -p ${SSH_PORT}"
}

run_ssh() {
  local host="$1"; shift
  sshpass -e ssh $(ssh_opts) "${SSH_USER}@${host}" "$@"
}

run_scp() {
  local src="$1" host="$2" dest="$3"
  sshpass -e scp $(ssh_opts) "$src" "${SSH_USER}@${host}:${dest}"
}

# -----------------------------------------------------------------------------
# DEPLOY SINGLE HOST
# -----------------------------------------------------------------------------
deploy_host() {
  local ip="$1"
  local status=0

  info "[${ip}] Starting deployment"

  # 1. Create parent directory for the deploy file (if needed)
  local dest_dir; dest_dir="$(dirname "$DEPLOY_FILE_DEST")"
  if ! run_ssh "$ip" "sudo mkdir -p '${dest_dir}'"; then
    error "[${ip}] Failed to create directory ${dest_dir}"
    return 1
  fi

  # 2. Copy deploy file to a temp location, then sudo move it into place
  local tmp_file="/tmp/$(basename "$DEPLOY_FILE")"
  if ! run_scp "$DEPLOY_FILE" "$ip" "$tmp_file"; then
    error "[${ip}] Failed to SCP deploy file"
    return 1
  fi
  if ! run_ssh "$ip" "sudo mv '${tmp_file}' '${DEPLOY_FILE_DEST}'"; then
    error "[${ip}] Failed to move deploy file to ${DEPLOY_FILE_DEST}"
    return 1
  fi
  info "[${ip}] ✔ Deploy file → ${DEPLOY_FILE_DEST}"

  # 3. Copy service unit file
  local tmp_svc="/tmp/${SERVICE_NAME}"
  if ! run_scp "$SERVICE_FILE" "$ip" "$tmp_svc"; then
    error "[${ip}] Failed to SCP service file"
    return 1
  fi
  if ! run_ssh "$ip" "sudo mv '${tmp_svc}' '/etc/systemd/system/${SERVICE_NAME}'"; then
    error "[${ip}] Failed to install service unit file"
    return 1
  fi
  info "[${ip}] ✔ Service file → /etc/systemd/system/${SERVICE_NAME}"

  # 4. Reload systemd, enable, start
  if ! run_ssh "$ip" "sudo systemctl daemon-reload"; then
    error "[${ip}] systemctl daemon-reload failed"
    return 1
  fi

  if ! run_ssh "$ip" "sudo systemctl enable '${SERVICE_NAME}'"; then
    error "[${ip}] systemctl enable failed"
    return 1
  fi
  info "[${ip}] ✔ Service enabled"

  if ! run_ssh "$ip" "sudo systemctl start '${SERVICE_NAME}'"; then
    error "[${ip}] systemctl start failed"
    return 1
  fi
  info "[${ip}] ✔ Service started"

  # 5. Verify service is active
  local svc_status
  svc_status="$(run_ssh "$ip" "systemctl is-active '${SERVICE_NAME}'" 2>/dev/null || true)"
  if [[ "$svc_status" == "active" ]]; then
    info "[${ip}] ✔ Deployment complete — service is ACTIVE"
  else
    warn "[${ip}] Service status: ${svc_status} (expected 'active')"
  fi
}

# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
main() {
  # Parse CLI args
  while getopts ":i:u:p:P:f:d:s:n:jh" opt; do
    case $opt in
      i) IP_LIST="$OPTARG"          ;;
      u) SSH_USER="$OPTARG"         ;;
      p) SSH_PASS="$OPTARG"         ;;
      P) SSH_PORT="$OPTARG"         ;;
      f) DEPLOY_FILE="$OPTARG"      ;;
      d) DEPLOY_FILE_DEST="$OPTARG" ;;
      s) SERVICE_FILE="$OPTARG"     ;;
      n) SERVICE_NAME="$OPTARG"     ;;
      j) PARALLEL=true              ;;
      h) usage                      ;;
      :) error "Option -$OPTARG requires an argument"; exit 1 ;;
      \?) error "Unknown option: -$OPTARG"; exit 1 ;;
    esac
  done

  # Password: CLI flag < environment variable
  SSH_PASS="${DEPLOY_PASS:-$SSH_PASS}"

  check_deps
  validate_config

  # Expose password to sshpass via environment
  export SSHPASS="$SSH_PASS"

  # Read IP list (skip blank lines and # comments)
  mapfile -t HOSTS < <(grep -v '^\s*#' "$IP_LIST" | grep -v '^\s*$')

  if [[ ${#HOSTS[@]} -eq 0 ]]; then
    error "No hosts found in $IP_LIST"
    exit 1
  fi

  info "Deploying to ${#HOSTS[@]} host(s) — parallel=${PARALLEL}"
  info "Log file: ${LOG_FILE}"

  local pids=()
  local failed=()
  local succeeded=()

  for ip in "${HOSTS[@]}"; do
    if [[ "$PARALLEL" == true ]]; then
      deploy_host "$ip" &
      pids+=("$!:$ip")
    else
      if deploy_host "$ip"; then
        succeeded+=("$ip")
      else
        failed+=("$ip")
        warn "[${ip}] Deployment FAILED — continuing to next host"
      fi
    fi
  done

  # Wait for parallel jobs and collect results
  if [[ "$PARALLEL" == true ]]; then
    for entry in "${pids[@]}"; do
      local pid="${entry%%:*}"
      local ip="${entry##*:}"
      if wait "$pid"; then
        succeeded+=("$ip")
      else
        failed+=("$ip")
      fi
    done
  fi

  # Summary
  echo ""
  info "===== DEPLOYMENT SUMMARY ====="
  info "Succeeded (${#succeeded[@]}): ${succeeded[*]:-none}"
  [[ ${#failed[@]} -gt 0 ]] && error "Failed    (${#failed[@]}): ${failed[*]}"
  info "Full log: ${LOG_FILE}"

  [[ ${#failed[@]} -gt 0 ]] && exit 1
  exit 0
}

main "$@"