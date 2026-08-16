#!/usr/bin/env python3
"""Launch htr_cloud.py with .env loaded."""
import os
import sys
import subprocess

# Load .env
env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ[k.strip()] = v.strip()

# Run htr_cloud.py
cmd = [sys.executable, 'htr_cloud.py', '--backend=gemini']
print(f"Starting: {' '.join(cmd)}")
print(f"Keys loaded: {len([k for k in os.environ.get('GEMINI_KEYS', '').split(',') if k])}")

with open('output/htr_batch.log', 'w') as log:
    proc = subprocess.Popen(cmd, stdout=log, stderr=log)
    print(f"Started with PID: {proc.pid}")
    sys.exit(0)
