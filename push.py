import subprocess
import os

env = os.environ.copy()
env['GIT_TERMINAL_PROMPT'] = '0'
env['GCM_INTERACTIVE'] = 'false'

process = subprocess.Popen(
    ['git', 'push', '-u', 'origin', 'main'],
    env=env,
    stdin=subprocess.DEVNULL,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

stdout, stderr = process.communicate()
print("STDOUT:", stdout)
print("STDERR:", stderr)
