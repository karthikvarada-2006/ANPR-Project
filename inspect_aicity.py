import os
root = r"E:\AIC21_Track1_Vehicle_Counting"
print("== Tree (3 levels) ==")
for dp, dn, fn in os.walk(root):
    depth = dp[len(root):].count(os.sep)
    if depth > 3: continue
    print(("  " * depth) + os.path.basename(dp) + "/", len(fn), "files")
print()
print("== Video files ==")
for dp, dn, fn in os.walk(root):
    for f in fn:
        if f.lower().endswith((".mp4", ".avi", ".mov")):
            p = os.path.join(dp, f)
            print(os.path.relpath(p, root), round(os.path.getsize(p)/1e6, 1), "MB")
print()
print("== Small text-like files: first 15 lines ==")
for dp, dn, fn in os.walk(root):
    for f in fn:
        p = os.path.join(dp, f)
        if f.lower().endswith((".txt", ".json", ".csv", ".md", ".xml")) and os.path.getsize(p) < 2_000_000:
            print("-----", os.path.relpath(p, root), os.path.getsize(p), "bytes")
            with open(p, errors="ignore") as fh:
                for i, line in enumerate(fh):
                    if i >= 15: break
                    print(line.rstrip()[:200])
