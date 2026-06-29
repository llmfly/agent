import re

with open('/data/intelli/engine/config.yaml', 'r') as f:
    content = f.read()

model_entry = """  - name: doubao-seed-1.8
    display_name: Doubao-Seed-1.8
    use: deerflow.models.patched_deepseek:PatchedChatDeepSeek
    model: doubao-seed-1-8-251228
    api_base: https://ark.cn-beijing.volces.com/api/v3
    api_key: $VOLCENGINE_API_KEY
    timeout: 600.0
    max_retries: 2
    supports_thinking: true
    supports_vision: true
    supports_reasoning_effort: true
    when_thinking_enabled:
      extra_body:
        thinking:
          type: enabled
    when_thinking_disabled:
      extra_body:
        thinking:
          type: disabled

"""

# Check ONLY after the models: line for a non-commented - name:
lines = content.split('\n')
in_models = False
has_active_model = False
for line in lines:
    if line.startswith('models:'):
        in_models = True
        continue
    if in_models:
        if line.startswith('#'):
            continue
        if not line.strip():
            continue
        if line.strip().startswith('- name:'):
            # Check it's not commented
            if not line.lstrip().startswith('#'):
                has_active_model = True
                break
        if not line.startswith((' ', '#')) and line.strip():
            break  # Reached next top-level key

if has_active_model:
    print("Active model already present after models: line")
else:
    # Remove all lines between "models:" and next top-level key
    cleaned = []
    in_models = False
    for line in lines:
        if line.startswith('models:'):
            cleaned.append(line)
            cleaned.append(model_entry)
            in_models = True
            continue
        if in_models:
            if not line.strip():
                continue
            if line.startswith('#'):
                continue
            if line.startswith((' ', '\t')):
                continue
            in_models = False
        if not in_models:
            cleaned.append(line)
    content = '\n'.join(cleaned)
    with open('/data/intelli/engine/config.yaml', 'w') as f:
        f.write(content)
    print("Model entry inserted OK")

# Show models section
with open('/data/intelli/engine/config.yaml', 'r') as f:
    in_models = False
    for line in f:
        if line.startswith('models:'):
            in_models = True
        if in_models:
            print(line.rstrip())
            if not line.startswith(('models:', ' ', '#', '\t')) and not line.startswith('models:'):
                break
