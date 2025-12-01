#!/usr/bin/env bash
set -euo pipefail

# ---------- controls ----------
FAST=${FAST:-0}             # 1 = quick smoke test; 0 = full run
NPROC=${NPROC:-4}           # parallel workers; set ~= your CPU cores
SEED_OFFSET=20000
REPO_DIR=/mnt/d/Aagos_2025/Aagos

# Binary candidates (first that exists is used)
CANDIDATES=(
  "/mnt/d/Aagos_2025/Aagos/Aagos"
  "/mnt/d/Aagos_2025/Aagos/build/Aagos"
  "/mnt/d/Aagos_2025/Aagos/build/src/Aagos"
)

# Paths
DATA_ROOT=/mnt/d/Aagos_2025/Aagos/experiments/2025-10-07-mut/hpc/test/data
CONF_DIR=/mnt/d/Aagos_2025/Aagos/experiments/2025-10-07-mut/hpc/config
CFG="$CONF_DIR/Aagos.cfg"
MIRROR_ROOT=/mnt/d/Aagos_2025/Aagos/experiments/2025-10-07-mut/analysis/from_log
AGG_SCRIPT=/mnt/d/Aagos_2025/Aagos/experiments/2025-10-07-mut/analysis/aggregate_mutation.R

# ---------- experiment presets ----------
if [[ "$FAST" -eq 1 ]]; then
  # super quick: a few rates, few reps, small updates
  RATES=(0.0003 0.003 0.03)
  REPLICATES=3
  MAX_GENS=5000
  PHASE2_MAX=1000          # requires binary to accept this flag; if not, leave to cfg
  AGG_UPDATES="5000,6000"
else
  # paper-ish
  RATES=(0.0003 0.001 0.003 0.01 0.03 0.1)
  REPLICATES=10
  MAX_GENS=50000
  PHASE2_MAX=10000
  AGG_UPDATES="50000,60000"
fi

mkdir -p "$DATA_ROOT" "$MIRROR_ROOT"

# ---------- find binary ----------
EXEC=""
for c in "${CANDIDATES[@]}"; do
  [[ -x "$c" ]] && EXEC="$c" && break
done
[[ -z "$EXEC" ]] && EXEC=$(find "$REPO_DIR" -maxdepth 3 -type f -perm -111 -iname 'Aagos*' | head -n1 || true)
[[ -z "${EXEC:-}" || ! -x "$EXEC" ]] && { echo "Aagos binary not found"; exit 1; }
echo "Using EXEC: $EXEC"

# ---------- tiny semaphore for parallel ----------
run_bg() {  # run_bg <cmd_string> <workdir>
  local cmd="$1" wd="$2"
  while [[ $(jobs -rp | wc -l) -ge $NPROC ]]; do sleep 0.2; done
  ( cd "$wd"; bash -lc "$cmd" > run.log 2>&1 ) &
}

# ---------- sweep ----------
cond=0
for rate in "${RATES[@]}"; do
  echo "=== C${cond}: rate=$rate, reps=$REPLICATES, MAX_GENS=$MAX_GENS ==="
  for rep in $(seq 1 "$REPLICATES"); do
    seed=$((SEED_OFFSET + cond*REPLICATES + rep))
    run_dir="$DATA_ROOT/RUN_C${cond}_${seed}"
    mkdir -p "$run_dir"
    cp -f "$CFG" "$run_dir"/Aagos.cfg 2>/dev/null || true

    RUN_PARAMS="-POP_SIZE 1000 -MAX_GENS ${MAX_GENS} -NUM_BITS 128 -NUM_GENES 16 -GENE_SIZE 8 \
                -MAX_SIZE 1024 -MIN_SIZE 8 \
                -GENE_MOVE_PROB 0.003 \
                -BIT_FLIP_PROB ${rate} -PHASE_2_BIT_FLIP_PROB ${rate} \
                -BIT_INS_PROB 0.001 -BIT_DEL_PROB 0.001 \
                -SUMMARY_INTERVAL 1000 -SNAPSHOT_INTERVAL ${MAX_GENS} \
                -PHASE_2_ACTIVE 1 -PHASE_2_GENE_MOVE_PROB 0 \
                -PHASE_2_BIT_INS_PROB 0 -PHASE_2_BIT_DEL_PROB 0 \
                -SEED ${seed}"
    # If your binary honors this flag, uncomment:
    # RUN_PARAMS="${RUN_PARAMS} -PHASE_2_MAX_GENS ${PHASE2_MAX}"

    echo "$EXEC $RUN_PARAMS" > "$run_dir/cmd.log"
    echo "[RUN] C${cond} seed=${seed} rate=${rate}"
    run_bg "$(cat "$run_dir/cmd.log")" "$run_dir"
  done
  ((cond++))
done
wait

# ---------- mirror to analysis/from_log ----------
python3 - <<'PY'
import re, os, csv, glob, shutil
ROOT="/mnt/d/Aagos_2025/Aagos/experiments/2025-10-07-mut/hpc/test/data"
OUT ="/mnt/d/Aagos_2025/Aagos/experiments/2025-10-07-mut/analysis/from_log"
pat=re.compile(r'^\s*(\d+): .*?(?:max|best)\s+fitness=([0-9eE+\.-]+);\s*size=([0-9]+)')
for d in sorted(glob.glob(os.path.join(ROOT,"RUN_C*_*"))):
    name=os.path.basename(d)
    logp=os.path.join(d,"run.log")
    cmdp=os.path.join(d,"cmd.log")
    if not os.path.isfile(logp): continue
    outdir=os.path.join(OUT,name); os.makedirs(outdir, exist_ok=True)
    rows=[]
    with open(logp,'r',errors='ignore') as f:
        for line in f:
            m=pat.match(line)
            if m: rows.append((int(m.group(1)),float(m.group(2)),int(m.group(3))))
    with open(os.path.join(outdir,"summary_from_log.csv"),'w',newline='') as out:
        w=csv.writer(out); w.writerow(["update","fitness","size"]); w.writerows(rows)
    for src in (logp, cmdp):
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(outdir, os.path.basename(src)))
PY

# ---------- aggregate in R ----------
if [[ -f "$AGG_SCRIPT" ]]; then
  Rscript "$AGG_SCRIPT" \
    --root "$MIRROR_ROOT" \
    --summary_glob "summary_from_log.csv" \
    --updates "$AGG_UPDATES" || true
  echo "Check: $(dirname "$AGG_SCRIPT")/mutation_agg.csv and mutation_plot.pdf"
else
  echo "Aggregation script not found: $AGG_SCRIPT (skipped)."
fi
