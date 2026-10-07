#!/bin/sh

set -x

if [ -z "$TMUX" ]; then
    TMUX=1
fi
if [ -z "$SESSION" ]; then
    SESSION="ue"
fi

session_get() {
    ( tmux list-sessions | grep -q "^${SESSION}:" ) \
	|| tmux new-session -d -s "$SESSION"
}

session_get $SESSION

tmux send-keys -t =$SESSION:0.0 'sudo srsue |& tee /local/logs/srsue.log' C-m
tmux split-window -v
tmux send-keys -t =$SESSION:0.1 'ping 192.168.0.1' C-m
#tmux select-layout even-vertical
tmux split-window -v
tmux send-keys -t =$SESSION:0.2 'while true ; do sleep 2 ; iperf3 -c 192.168.0.1 -t 65536 -i 1 ; done |& tee -a /local/logs/iperf.log' C-m
exec tmux attach-session -d -t $SESSION
