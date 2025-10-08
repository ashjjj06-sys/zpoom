# Zoom CPU-bound Simulator (Codespaces)

This repository contains **safe, CPU-only simulator** scripts that mimic multiple Zoom participants joining/staying/leaving — *without contacting Zoom or using Selenium*. You can run this in GitHub Codespaces, GCP VM, or any Linux machine. The simulator generates CPU load by doing prime-ish checks.

---

## Files included

### `simulator.py`

```python
# simulator.py
import time
import random
import argparse
from multiprocessing import Process, Manager, current_process
import math
import json
import os
from datetime import datetime

def cpu_work_for(seconds: float):
    """
    CPU-bound work for approx `seconds` seconds.
    We run repeated prime checks on pseudo-random numbers.
    """
    end = time.time() + seconds
    count = 0
    # keep working until time's up
    while time.time() < end:
        # generate a random-ish large-ish odd number
        n = random.randint(10**5, 10**6) | 1
        # simple primality-ish test (trial division up to sqrt)
        r = int(math.isqrt(n))
        is_prime = True
        for i in range(3, r+1, 2):
            if n % i == 0:
                is_prime = False
                break
        count += 1
    return count

def worker(name: str, meeting_code: str, passcode: str, stay_seconds: int, work_seconds: float,
           status_dict, log_path=None, stagger: float=0.0):
    pid = current_process().pid
    started_at = datetime.utcnow().isoformat() + "Z"
    status_dict[name] = {"state": "connecting", "pid": pid, "started_at": started_at}
    # optional stagger before starting
    if stagger > 0:
        time.sleep(stagger)

    # simulate network delay, connection time
    status_dict[name]["state"] = "connected"
    status_dict[name]["connected_at"] = datetime.utcnow().isoformat() + "Z"

    # CPU work
    status_dict[name]["state"] = "working"
    status_dict[name]["work_started_at"] = datetime.utcnow().isoformat() + "Z"
    jobs_done = cpu_work_for(work_seconds)
    status_dict[name]["work_done"] = jobs_done
    status_dict[name]["work_finished_at"] = datetime.utcnow().isoformat() + "Z"

    # stay in meeting (idle) for remaining time (stay_seconds includes work_seconds)
    remaining = max(0, stay_seconds - work_seconds)
    status_dict[name]["state"] = "idle"
    time.sleep(remaining)

    status_dict[name]["state"] = "left"
    status_dict[name]["left_at"] = datetime.utcnow().isoformat() + "Z"

    # append to logfile if requested
    if log_path:
        record = {
            "name": name,
            "meeting_code": meeting_code,
            "started_at": started_at,
            "left_at": status_dict[name].get("left_at"),
            "work_done": jobs_done,
        }
        try:
            with open(log_path, "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            print(f"Could not write log: {e}")

def generate_names(count):
    # lightweight local name generation (no web requests)
    first = ["Aarav","Vivaan","Aditya","Arjun","Reyansh","Krishna","Kabir","Ishaan","Vihaan","Rohan"]
    last = ["Sharma","Verma","Khan","Patel","Singh","Gupta","Reddy","Nair","Mehta","Joshi"]
    names = []
    for i in range(count):
        names.append(f"{random.choice(first)} {random.choice(last)} #{i+1}")
    return names

def run_simulation(number_of_users:int, meeting_code:str, passcode:str,
                   stay_seconds:int, work_seconds:float, stagger:float,
                   logfile: str = None):
    manager = Manager()
    status = manager.dict()
    processes = []
    names = generate_names(number_of_users)
    print(f"[{datetime.utcnow().isoformat()}Z] Starting simulation: {number_of_users} participants")
    for i, name in enumerate(names):
        p = Process(target=worker, args=(name, meeting_code, passcode, stay_seconds, work_seconds, status, logfile, i*stagger))
        p.start()
        processes.append(p)
    try:
        # simple monitoring loop
        while any(p.is_alive() for p in processes):
            alive = sum(1 for p in processes if p.is_alive())
            print(f"[{datetime.utcnow().isoformat()}Z] Alive workers: {alive}")
            # print a small status sample (upto 5)
            sample = list(status.items())[:5]
            for k,v in sample:
                print(f"  {k}: {v['state']}")
            time.sleep(5)
    except KeyboardInterrupt:
        print("KeyboardInterrupt received: terminating children")
        for p in processes:
            p.terminate()
    finally:
        for p in processes:
            p.join()
    print(f"[{datetime.utcnow().isoformat()}Z] Simulation complete. Logs -> {logfile or 'stdout'}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CPU-bound Zoom participant simulator (no Zoom calls).")
    parser.add_argument("--users", type=int, default=10, help="Number of simulated participants")
    parser.add_argument("--meeting", type=str, default="SIM-MEET-123", help="Meeting code (just for logs)")
    parser.add_argument("--passcode", type=str, default="", help="Passcode (for logs only)")
    parser.add_argument("--stay", type=int, default=120, help="Seconds each participant stays connected (including work)")
    parser.add_argument("--work", type=float, default=20.0, help="Seconds of CPU-bound work per participant")
    parser.add_argument("--stagger", type=float, default=0.5, help="Seconds to stagger start between participants")
    parser.add_argument("--log", type=str, default="simulator.log", help="File to append per-participant JSON logs (optional)")
    args = parser.parse_args()

    # ensure logfile dir
    if args.log:
        d = os.path.dirname(args.log)
        if d and not os.path.exists(d):
            os.makedirs(d, exist_ok=True)

    run_simulation(args.users, args.meeting, args.passcode, args.stay, args.work, args.stagger, args.log)
```

---

### `monitor_streamlit.py`

```python
# monitor_streamlit.py
import streamlit as st
import subprocess
import sys
import os
import signal
from pathlib import Path
import time

st.set_page_config(page_title="Simulator Controller", layout="wide")
st.title("Zoom CPU Simulator Controller")

# Sidebar controls
with st.sidebar:
    users = st.number_input("Users", min_value=1, max_value=1000, value=20)
    meeting = st.text_input("Meeting code (logs only)", value="SIM-MEET-123")
    stay = st.number_input("Stay seconds", min_value=1, max_value=86400, value=120)
    work = st.number_input("Work seconds", min_value=0.1, max_value=86400.0, value=20.0)
    stagger = st.number_input("Stagger seconds", min_value=0.0, max_value=60.0, value=0.5)
    log_path = st.text_input("Log file path", value="simulator.log")

# Session-state for process PID
if "proc_pid" not in st.session_state:
    st.session_state.proc_pid = None

def is_pid_running(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True

col1, col2 = st.columns(2)
with col1:
    if st.button("Start Simulation"):
        if is_pid_running(st.session_state.proc_pid):
            st.warning(f"Simulation already running (pid={st.session_state.proc_pid})")
        else:
            cmd = [sys.executable, "simulator.py", "--users", str(users), "--meeting", meeting, "--stay", str(stay), "--work", str(work), "--stagger", str(stagger), "--log", log_path]
            # ensure log dir exists
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            f = open(log_path, "a")
            proc = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT)
            st.session_state.proc_pid = proc.pid
            st.success(f"Started simulation (pid={proc.pid})")

with col2:
    if st.button("Stop Simulation"):
        pid = st.session_state.proc_pid
        if is_pid_running(pid):
            os.kill(pid, signal.SIGTERM)
            st.session_state.proc_pid = None
            st.success("Stopped simulation")
        else:
            st.warning("No running simulation detected")

# Show process status & log tail
st.markdown("---")
if is_pid_running(st.session_state.proc_pid):
    st.info(f"Simulation running (pid={st.session_state.proc_pid})")
else:
    st.info("No simulation running")

st.subheader("Log tail")
if Path(log_path).exists():
    try:
        with open(log_path, "r") as f:
            lines = f.readlines()[-400:]
        st.text_area("Last log lines", value="".join(lines), height=400)
    except Exception as e:
        st.error(f"Could not read log: {e}")
else:
    st.info("Log file not found yet. Start a simulation to create it.")
```

---

### `requirements.txt`

```
streamlit
```

---

### `.gitignore`

```
.venv/
__pycache__/
*.pyc
simulator.log
```

---

### `README.md`

````markdown
# Zoom CPU-bound Simulator (safe)

This repo contains a CPU-only simulator that mimics Zoom participants for load/testing purposes — it does NOT contact Zoom or automate browsers.

## Files
- `simulator.py` - main CLI simulator (multiprocessing)
- `monitor_streamlit.py` - optional Streamlit controller to start/stop the simulator and view log tail
- `requirements.txt` - Streamlit (for the monitor UI)

## Quick start (GitHub Codespaces)
1. Open this repository in GitHub Codespaces (or any Linux VM).
2. Create and activate a Python virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
````

3. Run simulator (example):

   ```bash
   python simulator.py --users 50 --meeting TEST123 --stay 60 --work 15 --stagger 0.3 --log simulator.log
   ```
4. (Optional) Run Streamlit controller:

   ```bash
   streamlit run monitor_streamlit.py --server.address 0.0.0.0 --server.port 8080
   ```

   Then forward port 8080 in Codespaces and open the UI.

## Notes

* Monitor CPU with `top` or `htop`.
* Start small and scale up; Codespaces machine types have resource limits.

```

---

End of repository contents.

```
