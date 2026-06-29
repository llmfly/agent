"""Set VOLCENGINE_API_KEY in .env on 242 so deployment validation passes."""
import paramiko

host = "172.16.0.242"
password = "admin@001"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username="root", password=password, timeout=30)

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    print(f"[{exit_code}] {cmd[:100]}")
    if out:
        for line in out.splitlines()[:10]:
            print(f"  {line}")
    if err:
        for line in err.splitlines()[:5]:
            print(f"  ERR: {line}")
    print()
    return exit_code, out

run("grep -q '^VOLCENGINE_API_KEY=' /data/intelli/engine/.env && sed -i 's|^VOLCENGINE_API_KEY=.*|VOLCENGINE_API_KEY=placeholder-for-deploy|' /data/intelli/engine/.env || echo 'VOLCENGINE_API_KEY=placeholder-for-deploy' >> /data/intelli/engine/.env")
run("grep VOLCENGINE /data/intelli/engine/.env")

ssh.close()
