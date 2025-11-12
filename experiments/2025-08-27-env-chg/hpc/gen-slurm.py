#!/usr/bin/env python3
"""
Generate slurm job submission scripts (two per condition: P1 & P2),
with batching controls:
  - seeds_per_task: how many replicates each array task will run
  - parallel_per_job: how many replicates run concurrently inside a task
This reduces job count and increases throughput under node-per-user limits.
"""

import argparse, os, sys, pathlib, math
from pyvarco import CombinationCollector

# add scripts dir to path
sys.path.append(
    os.path.join(
        pathlib.Path(os.path.dirname(os.path.abspath(__file__))).parents[2],
        "scripts"
    )
)
import utilities as utils  # noqa: E402

# ------------------ defaults ------------------
default_seed_offset = 1000
default_account = None
default_num_replicates = 30
default_job_time_request = "8:00:00"
default_job_mem_request = "4G"
default_seeds_per_task = 5          # <-- each array task runs 5 replicates
default_parallel_per_job = 2        # <-- run 2 replicates at a time inside a task

executable = "Aagos"
base_slurm_script_fpath = "./base_slurm_script.txt"

# ------------------ combos --------------------
combos = CombinationCollector()

fixed_parameters = {
    "POP_SIZE": "1000",
    "MAX_GENS": "50000",
    "NUM_BITS": "128",
    "NUM_GENES": "16",
    "GENE_SIZE": "8",
    "MAX_SIZE": "1024",
    "MIN_SIZE": "8",
    "GENE_MOVE_PROB": "0.003",
    "BIT_FLIP_PROB": "0.003",
    "BIT_INS_PROB": "0.001",
    "BIT_DEL_PROB": "0.001",
    "SUMMARY_INTERVAL": "10000",
    "SNAPSHOT_INTERVAL": "50000",

    # default to Phase 1 (Phase 2 is set per-phase later)
    "PHASE_2_ACTIVE": "0",
    "PHASE_2_GENE_MOVE_PROB": "0",
    "PHASE_2_BIT_FLIP_PROB": "0.003",
    "PHASE_2_BIT_INS_PROB": "0",
    "PHASE_2_BIT_DEL_PROB": "0"
}

special_decorators = ["__COPY_OVER"]

combos.register_var("environment__COPY_OVER")
combos.add_val(
    "environment__COPY_OVER",
    [
        # gradient + nk (same as before)
        "-GRADIENT_MODEL 1 -CHANGE_MAGNITUDE 0 -CHANGE_FREQUENCY 0 -TOURNAMENT_SIZE 8",
        "-GRADIENT_MODEL 1 -CHANGE_MAGNITUDE 1 -CHANGE_FREQUENCY 1 -TOURNAMENT_SIZE 8",
        "-GRADIENT_MODEL 1 -CHANGE_MAGNITUDE 1 -CHANGE_FREQUENCY 2 -TOURNAMENT_SIZE 8",
        "-GRADIENT_MODEL 1 -CHANGE_MAGNITUDE 1 -CHANGE_FREQUENCY 4 -TOURNAMENT_SIZE 8",
        "-GRADIENT_MODEL 1 -CHANGE_MAGNITUDE 1 -CHANGE_FREQUENCY 8 -TOURNAMENT_SIZE 8",
        "-GRADIENT_MODEL 1 -CHANGE_MAGNITUDE 1 -CHANGE_FREQUENCY 16 -TOURNAMENT_SIZE 8",
        "-GRADIENT_MODEL 1 -CHANGE_MAGNITUDE 1 -CHANGE_FREQUENCY 32 -TOURNAMENT_SIZE 8",
        "-GRADIENT_MODEL 1 -CHANGE_MAGNITUDE 1 -CHANGE_FREQUENCY 64 -TOURNAMENT_SIZE 8",
        "-GRADIENT_MODEL 1 -CHANGE_MAGNITUDE 1 -CHANGE_FREQUENCY 128 -TOURNAMENT_SIZE 8",
        "-GRADIENT_MODEL 1 -CHANGE_MAGNITUDE 1 -CHANGE_FREQUENCY 256 -TOURNAMENT_SIZE 8",
        "-GRADIENT_MODEL 1 -CHANGE_MAGNITUDE 0 -CHANGE_FREQUENCY 0 -TOURNAMENT_SIZE 1",
        "-GRADIENT_MODEL 0 -CHANGE_MAGNITUDE 0 -CHANGE_FREQUENCY 0 -TOURNAMENT_SIZE 8",
        "-GRADIENT_MODEL 0 -CHANGE_MAGNITUDE 1 -CHANGE_FREQUENCY 1 -TOURNAMENT_SIZE 8",
        "-GRADIENT_MODEL 0 -CHANGE_MAGNITUDE 2 -CHANGE_FREQUENCY 1 -TOURNAMENT_SIZE 8",
        "-GRADIENT_MODEL 0 -CHANGE_MAGNITUDE 4 -CHANGE_FREQUENCY 1 -TOURNAMENT_SIZE 8",
        "-GRADIENT_MODEL 0 -CHANGE_MAGNITUDE 8 -CHANGE_FREQUENCY 1 -TOURNAMENT_SIZE 8",
        "-GRADIENT_MODEL 0 -CHANGE_MAGNITUDE 16 -CHANGE_FREQUENCY 1 -TOURNAMENT_SIZE 8",
        "-GRADIENT_MODEL 0 -CHANGE_MAGNITUDE 32 -CHANGE_FREQUENCY 1 -TOURNAMENT_SIZE 8",
        "-GRADIENT_MODEL 0 -CHANGE_MAGNITUDE 64 -CHANGE_FREQUENCY 1 -TOURNAMENT_SIZE 8",
        "-GRADIENT_MODEL 0 -CHANGE_MAGNITUDE 128 -CHANGE_FREQUENCY 1 -TOURNAMENT_SIZE 8",
        "-GRADIENT_MODEL 0 -CHANGE_MAGNITUDE 256 -CHANGE_FREQUENCY 1 -TOURNAMENT_SIZE 8",
        "-GRADIENT_MODEL 0 -CHANGE_MAGNITUDE 0 -CHANGE_FREQUENCY 0 -TOURNAMENT_SIZE 1"
    ]
)

def main():
    ap = argparse.ArgumentParser(description="Generate SLURM submission scripts.")
    ap.add_argument("--data_dir", required=True)
    ap.add_argument("--config_dir", required=True)
    ap.add_argument("--replicates", type=int, default=default_num_replicates)
    ap.add_argument("--job_dir", default=None)
    ap.add_argument("--seed_offset", type=int, default=default_seed_offset)
    ap.add_argument("--hpc_account", default=default_account)
    ap.add_argument("--time_request", default=default_job_time_request)
    ap.add_argument("--mem", default=default_job_mem_request)
    ap.add_argument("--runs_per_subdir", type=int, default=-1)
    ap.add_argument("--repo_dir", required=True)

    # NEW: batching/parallel knobs
    ap.add_argument("--seeds_per_task", type=int, default=default_seeds_per_task)
    ap.add_argument("--parallel_per_job", type=int, default=default_parallel_per_job)

    args = ap.parse_args()

    with open(base_slurm_script_fpath, "r") as fp:
        base = fp.read()

    combo_list = combos.get_combos()
    num_jobs = args.replicates * len(combo_list)
    if args.job_dir is None:
        args.job_dir = os.path.join(args.data_dir, "jobs")

    print(f"Generating {num_jobs} replicates across {len(combo_list)} conditions")
    print(f"Seeds per task: {args.seeds_per_task} | Parallel per job: {args.parallel_per_job}")

    cur_job_id = 0
    cond_i = 0
    cur_subdir_run_cnt = 0
    cur_run_subdir_id = 0

    for condition_info in combo_list:
        cur_seed_offset = args.seed_offset + (cur_job_id * args.replicates)
        filename_prefix = f"RUN_C{cond_i}"

        # prepare common template fields
        tpl = base
        tpl = tpl.replace("<<TIME_REQUEST>>", args.time_request)
        # array size = ceil(replicates / seeds_per_task)
        array_len = math.ceil(args.replicates / args.seeds_per_task)
        tpl = tpl.replace("<<ARRAY_ID_RANGE>>", f"1-{array_len}")
        tpl = tpl.replace("<<MEMORY_REQUEST>>", args.mem)
        tpl = tpl.replace("<<CONFIG_DIR>>", args.config_dir)
        tpl = tpl.replace("<<REPO_DIR>>", args.repo_dir)
        tpl = tpl.replace("<<EXEC>>", executable)
        tpl = tpl.replace("<<JOB_SEED_OFFSET>>", str(cur_seed_offset))
        tpl = tpl.replace("<<SEEDS_PER_TASK>>", str(args.seeds_per_task))
        tpl = tpl.replace("<<PARALLEL_PER_JOB>>", str(args.parallel_per_job))
        tpl = tpl.replace("<<CPUS_PER_TASK>>", str(args.parallel_per_job))
        tpl = tpl.replace("<<REPLICATES>>", str(args.replicates))
        if args.hpc_account is None:
            tpl = tpl.replace("<<HPC_ACCOUNT_INFO>>", "")
        else:
            tpl = tpl.replace("<<HPC_ACCOUNT_INFO>>", f"#SBATCH --account {args.hpc_account}")

        # base params (phase-independent)
        base_params = {k: fixed_parameters[k] for k in fixed_parameters}
        base_params["SEED"] = "${SEED}"
        for param in condition_info:
            if any(dec in param for dec in special_decorators):
                continue
            base_params[param] = condition_info[param]
        copy_over = [condition_info[k] for k in condition_info if "__COPY_OVER" in k]

        for phase_flag, phase_label, phase_val in [(0, "P1", "1"), (1, "P2", "2")]:
            params = dict(base_params)
            params["PHASE_2_ACTIVE"] = str(phase_flag)
            keyz = sorted(params.keys())
            set_params = [f"-{k} {params[k]}" for k in keyz]
            run_param_str = " ".join(set_params + copy_over)

            job_name = f"C{cond_i}_{phase_label}"
            run_dir_prefix = os.path.join(args.data_dir, f"{filename_prefix}_{phase_label}_")

            t = tpl
            t = t.replace("<<JOB_NAME>>", job_name)
            t = t.replace("<<RUN_DIR_PREFIX>>", run_dir_prefix)

            run_cmds = []
            run_cmds.append(f'RUN_PARAMS="{run_param_str}"')
            run_cmds.append('echo "./${EXEC} ${RUN_PARAMS}" > cmd.log')
            run_cmds.append('./${EXEC} ${RUN_PARAMS} > run.log')
            # add a phase column if a simple summary exists
            run_cmds.append(
                f"if [ -f summary.csv ]; then awk -v phase_val='{phase_val}' "
                "'BEGIN{FS=OFS=\",\"} NR==1{$0=$0\",phase\"} NR>1{$0=$0\",\"phase_val} 1' "
                "summary.csv > summary_with_phase.csv; fi"
            )
            t = t.replace("<<RUN_CMDS>>", "\n".join(run_cmds))

            # write job
            cur_job_dir = args.job_dir if args.runs_per_subdir == -1 else os.path.join(args.job_dir, f"job-set-{cur_run_subdir_id}")
            utils.mkdir_p(cur_job_dir)
            out_name = f"{filename_prefix}_{phase_label}.sb"
            with open(os.path.join(cur_job_dir, out_name), "w") as fp:
                fp.write(t)

        # counters
        cur_job_id += 1
        cond_i += 1
        cur_subdir_run_cnt += args.replicates
        if args.runs_per_subdir > -1 and cur_subdir_run_cnt > (args.runs_per_subdir - args.replicates):
            cur_subdir_run_cnt = 0
            cur_run_subdir_id += 1

if __name__ == "__main__":
    main()

