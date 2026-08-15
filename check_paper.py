import io
import re

with io.open("paper.txt", encoding="utf-8") as f:
    lines = f.readlines()

issues = []
in_listing = 0
labels = {}
refs = []

for i, ln in enumerate(lines, 1):
    in_listing += ln.count("\\begin{lstlisting}")
    in_listing -= ln.count("\\end{lstlisting}")

    if in_listing:
        continue

    for c, name in (("%", "percent"), ("#", "hash")):
        for m in re.finditer(re.escape(c), ln):
            prev = ln[: m.start()]
            if prev.rstrip().endswith("\\"):
                continue
            issues.append(f"line {i}: unescaped {name}")

    for m in re.finditer(r"(?<!\\)_", ln):
        prev = ln[: m.start()]
        if "\\texttt{" in prev and prev.count("{") > prev.count("}"):
            continue
        if re.search(r"\\textless|\\textgreater|\\includegraphics", prev):
            continue
        issues.append(f"line {i}: possible unescaped underscore: ...{ln[max(0,m.start()-30):m.start()+10]}")

    for m in re.finditer(r"\\label\{([^}]+)\}", ln):
        labels[m.group(1)] = i
    for m in re.finditer(r"\\ref\{([^}]+)\}", ln):
        refs.append(m.group(1))

print("non-ascii:", [i for i, ln in enumerate(lines, 1) if any(ord(c) > 0x7F for c in ln)])
print("unresolved refs:", [r for r in sorted(set(refs)) if r not in labels])
print("labels:", sorted(labels))
print("issues:")
for issue in issues:
    print(" ", issue)
