import subprocess, os

# Run a shell command
result = subprocess.run(["bash", "-c", "echo 'hello'; which pdftotext; which pdftotext"], capture_output=True, text=True)
print("STDOUT:", result.stdout)
print("STDERR:", result.stderr)
