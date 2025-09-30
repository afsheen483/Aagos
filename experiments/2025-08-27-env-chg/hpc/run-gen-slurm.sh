#!/usr/bin/env bash

# ---------------------------
# Experiment configuration
# ---------------------------
REPLICATES=100
EXP_SLUG=2025-08-27-env-chg
SEED_OFFSET=100000
JOB_TIME=8:00:00
JOB_MEM=8G
PROJECT_NAME=Aagos_2025/Aagos
RUNS_PER_SUBDIR=950
USERNAME=afsheen_ghuman

# ---------------------------
# Paths
# ---------------------------
# Your repository location in WSL
REPO_DIR="/mnt/d/Aagos_2025/Aagos"
REPO_SCRIPTS_DIR="${REPO_DIR}/scripts"
HOME_EXP_DIR="${REPO_DIR}/experiments/${EXP_SLUG}"

# Output directories for jobs
DATA_DIR="/mnt/d/Aagos_2025/Aagos/experiments/${EXP_SLUG}/jobs"   # You can adjust
JOB_DIR="${DATA_DIR}/jobs"
CONFIG_DIR="${HOME_EXP_DIR}/hpc/config"

# ---------------------------
# Activate Python virtual environment
# ---------------------------
# Comment out HPC-specific env
# source ${REPO_DIR}/hpc-env/clipper-hpc-env.sh

# Activate your local venv
source "${REPO_DIR}/pyenv/bin/activate"

# ---------------------------
# Generate Slurm scripts
# ---------------------------
python3 gen-slurm.py \
  --runs_per_subdir ${RUNS_PER_SUBDIR} \
  --time_request ${JOB_TIME} \
  --mem ${JOB_MEM} \
  --data_dir ${DATA_DIR} \
  --config_dir ${CONFIG_DIR} \
  --repo_dir ${REPO_DIR} \
  --replicates ${REPLICATES} \
  --job_dir ${JOB_DIR} \
  --seed_offset ${SEED_OFFSET}
