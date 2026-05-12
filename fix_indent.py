with open('reset_gpt_accounts_parallel.py', 'r') as f:
    lines = f.readlines()

for i in range(206, 456):
    if lines[i].strip(): # 비어있지 않은 줄만 들여쓰기
        lines[i] = "    " + lines[i]

with open('reset_gpt_accounts_parallel.py', 'w') as f:
    f.writelines(lines)
