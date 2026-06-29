"""Run database migration on remote server."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('172.16.0.242', username='root', password='admin@001', timeout=15)

ini_path = '/data/intelli/engine/backend/packages/harness/deerflow/persistence/migrations/alembic.ini'

# alembic.ini has script_location=%(here)s so -c flag is needed
stdin, stdout, stderr = ssh.exec_command(
    'cd /data/intelli/engine/backend && .venv/bin/alembic -c ' + ini_path + ' upgrade head',
    timeout=30,
)
out = stdout.read().decode()
err = stderr.read().decode()
print("Migration stdout:", out[:2000])
if err:
    print("Migration stderr:", err[:2000])

# Restart service
stdin, stdout, stderr = ssh.exec_command('systemctl restart intelli-engine-gateway')
print("Restart exit code:", stdout.channel.recv_exit_status())

import time
time.sleep(2)

stdin, stdout, stderr = ssh.exec_command('systemctl is-active intelli-engine-gateway')
print("Service:", stdout.read().decode().strip())

ssh.close()
