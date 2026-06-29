"""Check AuthMiddleware path coverage."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('172.16.0.242', username='root', password='admin@001', timeout=15)

cmd = """
grep -n 'class AuthMiddleware\\|def dispatch\\|_current_user\\|contextvar\\|exclude_path\\|skip_path' /data/intelli/engine/backend/app/gateway/langgraph_auth.py | head -30
echo "==="
cat /data/intelli/engine/backend/app/gateway/langgraph_auth.py
"""

stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
print(stdout.read().decode()[:2000])
ssh.close()
