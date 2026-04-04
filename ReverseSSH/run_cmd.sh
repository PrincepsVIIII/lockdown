#!/bin/bash
trap 'echo "Interrupted"; kill 0; exit 1' INT

BASE_PORT=1000
HOST="192.168.13.104"
MAX_PARALLEL=16

TARGETS=(
"10.1.1.10" "10.2.1.10" "10.3.1.10" "10.4.1.10" "10.5.1.10" "10.6.1.10" "10.7.1.10" "10.8.1.10" "10.9.1.10" "10.10.1.10" "10.11.1.10" "10.12.1.10" "10.13.1.10"
"10.1.1.20" "10.2.1.20" "10.3.1.20" "10.4.1.20" "10.5.1.20" "10.6.1.20" "10.7.1.20" "10.8.1.20" "10.9.1.20" "10.10.1.20" "10.11.1.20" "10.12.1.20" "10.13.1.20"
"10.1.1.30" "10.2.1.30" "10.3.1.30" "10.4.1.30" "10.5.1.30" "10.6.1.30" "10.7.1.30" "10.8.1.30" "10.9.1.30" "10.10.1.30" "10.11.1.30" "10.12.1.30" "10.13.1.30"
"10.1.1.40" "10.2.1.40" "10.3.1.40" "10.4.1.40" "10.5.1.40" "10.6.1.40" "10.7.1.40" "10.8.1.40" "10.9.1.40" "10.10.1.40" "10.11.1.40" "10.12.1.40" "10.13.1.40"
)

if [ "$#" -eq 0 ]; then
    echo "Usage: $0 \"cmd1\" \"cmd2\" ..."
    exit 1
fi

# Ensure we're inside a tmux session
if [ -z "$TMUX" ]; then
    echo "Not inside tmux. Starting a new tmux session..."
    exec tmux new-session -s main "$0" "$@"
fi

handle_target() {
    local TARGET="$1"
    shift
    local CMDS=("$@")

    SECOND=$(echo "$TARGET" | cut -d'.' -f2)
    FOURTH=$(echo "$TARGET" | cut -d'.' -f4)
    PORT=$(( BASE_PORT + SECOND*100 + FOURTH ))

    local CMD_STR=""
    for cmd in "${CMDS[@]}"; do
        CMD_STR+="echo '=== ${cmd} ==='; ${cmd}; "
    done

    tmux new-window -n "$TARGET" "printf '%s\n' '${CMD_STR}' | nc -lvnp $PORT; read -p 'Done. Press enter to close.'"
}

job_count=0
for TARGET in "${TARGETS[@]}"; do
    handle_target "$TARGET" "$@" &
    (( job_count++ ))

    if (( job_count >= MAX_PARALLEL )); then
        wait -n 2>/dev/null || wait
        (( job_count-- ))
    fi
done

wait
echo "All done."