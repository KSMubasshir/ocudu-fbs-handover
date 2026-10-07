#!/bin/sh

set -x

if [ -z "$E2TERM_SCTP" ]; then
    echo "ERROR: set E2TERM_SCTP env var to current value of the e2term service's IP address"
    exit 1
fi

if [ -z "$TMUX" ]; then
    TMUX=1
fi
if [ -z "$SESSION" ]; then
    SESSION="nodeb"
fi

session_get() {
    ( tmux list-sessions | grep -q "^${SESSION}:" ) \
	|| tmux new-session -d -s "$SESSION"
}

session_get $SESSION

tmux new-session -d -s =$SESSION
tmux send-keys -t =$SESSION:0.0 'sudo srsepc |& tee -a /local/logs/srsepc.log' C-m
sleep 1.0
tmux split-window -v -t =$SESSION:0
tmux send-keys -t $SESSION:0.1 "sudo srsenb --ric.agent.remote_ipv4_addr=${E2TERM_SCTP} |& tee -a /local/logs/srsenb.log" C-m
tmux split-window -v -t =$SESSION:0
#tmux select-layout even-vertical
tmux send-keys -t $SESSION:0.2 "iperf3 -s -B 192.168.0.1 -i 1 |& tee -a /local/logs/iperf.log" C-m

exec tmux attach-session -d -t $SESSION
