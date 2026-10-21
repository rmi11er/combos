"""Stop a specifically identified runtime supervisor at an absolute deadline."""
import argparse
import datetime as dt
import os
import signal
import subprocess
import time

p = argparse.ArgumentParser()
p.add_argument('--pid', type=int, required=True)
p.add_argument('--db', required=True)
p.add_argument('--at', required=True)
a = p.parse_args()
deadline = dt.datetime.fromisoformat(a.at).timestamp()
while time.time() < deadline:
    time.sleep(min(1, deadline-time.time()))
command = subprocess.check_output(['ps','-p',str(a.pid),'-o','command='],text=True)
if a.db not in command or ' run --seconds' not in command:
    raise SystemExit('Supervisor identity mismatch; no signal sent')
os.kill(a.pid, signal.SIGINT)
print('SIGINT sent to supervisor', a.pid, dt.datetime.now().isoformat(), flush=True)
