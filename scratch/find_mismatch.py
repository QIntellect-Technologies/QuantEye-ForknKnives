import sys

with open('scratch/triples.txt', 'r', encoding='utf-16') as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if not line.strip(): continue
    # odd indices in python (0-based) means even 'total' (closer)
    try:
        total_num = int(line.split("(total: ")[1].split("):")[0])
    except:
        continue
    content = line.split("): ", 1)[1]
    is_open = "cursor.execute" in content or "query =" in content or "executemany" in content or "f'''" in content or "INSERT" in content or "UPDATE" in content or "DELETE" in content or "SELECT" in content
    
    if total_num % 2 == 1:
        # expected OPENER
        if not is_open:
            print(f"Mismatch at total={total_num}! Expected OPENER, found: {line.strip()}")
            sys.exit(1)
    else:
        # expected CLOSER
        if is_open:
            print(f"Mismatch at total={total_num}! Expected CLOSER, found: {line.strip()}")
            sys.exit(1)

print("No mismatch found by heuristic.")
