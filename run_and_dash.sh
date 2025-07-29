#!/bin/bash
python3 cybersnake.pygame &
PID=$!
sleep 5
kill $PID
