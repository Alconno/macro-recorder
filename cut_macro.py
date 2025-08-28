import os
import pickle

# -------- CONFIG --------
MACRO_DIR = "macros"
MACRO_FILE = "macro_001.pkl"
OUTPUT_FILE = "macro_001_trimmed.pkl"
TRIM_PERCENT = 0.1

# -------- Load macro --------
path = os.path.join(MACRO_DIR, MACRO_FILE)
if not os.path.exists(path):
    print(f"Macro {MACRO_FILE} not found in {MACRO_DIR}")
    exit(1)

with open(path, "rb") as f:
    events = pickle.load(f)

# -------- Trim last TRIM_PERCENT --------
if events:
    cut_index = int(len(events) * (1 - TRIM_PERCENT))
    events_trimmed = events[:cut_index]
else:
    events_trimmed = []

# -------- Save trimmed macro --------
output_path = os.path.join(MACRO_DIR, OUTPUT_FILE)
with open(output_path, "wb") as f:
    pickle.dump(events_trimmed, f)

print(f"Trimmed macro saved as {OUTPUT_FILE} ({len(events_trimmed)} events, removed {len(events)-len(events_trimmed)} events)")
