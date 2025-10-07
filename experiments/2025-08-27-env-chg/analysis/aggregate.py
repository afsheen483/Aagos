'''
Aggregate data.
This script generates the following output files:
- A summary file with one line per-replicate.
'''

import argparse
import os
import sys
import pathlib

# Add scripts directory to path, import utilities from scripts directory.
sys.path.append(
    os.path.join(
        pathlib.Path(os.path.dirname(os.path.abspath(__file__))).parents[2],
        "scripts"
    )
)
import utilities as utils

# All runs will have this in their name:
run_identifier = "RUN_"

# Configuration parameters to exclude in summary output
config_exclude = {
    "LOAD_ANCESTOR_FILE",
    "PHASE_2_ENV_FILE",
    "DATA_FILEPATH",
    "SNAPSHOT_INTERVAL",
    "PRINT_INTERVAL",
    "SUMMARY_INTERVAL"
}
gene_stats_exclude = {}
rep_org_exclude = {
    f"site_cnt_{i}_gene_occupancy" for i in range(0, 128)
}
rep_org_exclude.add("gene_neighbors")




def main():
    # Setup the command line argument parser
    parser = argparse.ArgumentParser(description="Data aggregation script")
    parser.add_argument("--data", type=str, help="Where should we pull data from?")
    parser.add_argument("--dump", type=str, help="Where to dump this?", default=".")
    parser.add_argument("--updates", type=int, nargs="+", help="Which updates should we pull?")

    # Parse command line arguments
    args = parser.parse_args()
    data_dir = args.data
    dump_dir = args.dump
    updates = args.updates

    # Does the data directory exist?
    if not os.path.exists(data_dir):
        print("Unable to find data directory.")
        exit(-1)

    # Is there at least one update in updates?
    # updates = set(updates)
    if len(updates) == 0:
        print("No target updates provided.")
        exit(-1)

    # Make directory to write aggregated data.
    utils.mkdir_p(dump_dir)

    # Collect run directories.
    run_dirs = [run_dir for run_dir in os.listdir(data_dir) if run_identifier in run_dir]
    # Not necessary to sort, but forces directory processing in fixed order
    run_dirs.sort()
    print(f"Found {len(run_dirs)} run directories.")

    summary_content_lines = []
    incomplete_runs = []
    for run_dir_i in range(len(run_dirs)):
        run_dir = run_dirs[run_dir_i]
        print(f"...({run_dir_i + 1}/{len(run_dirs)}) aggregating from {run_dir}")
        run_path = os.path.join(data_dir, run_dir)

        # Hold summary info for this run for each update
        updates = list(map(str, updates))
        info_by_update = {update: {"update": update} for update in updates}
        ########################################
        # Extract run parameters
        ########################################
        run_cfg_path = os.path.join(run_path, "output", "run_config.csv")
        # Config file exists?
        if not os.path.isfile(run_cfg_path):
            print("  Failed to find run cfg snapshot, skipping")
            incomplete_runs.append(run_dir)
            continue

        run_cfg_data = utils.read_csv(run_cfg_path)
        run_params = {}
        for line in run_cfg_data:
            param = line["parameter"]
            value = line["value"]
            run_params[param] = value
            # Add parameter value to summary info for each target update
            if param in config_exclude:
                continue
            for update in info_by_update:
                info_by_update[update][param] = value

        ########################################
        # Aggregate gene stats data
        ########################################
        gene_stats_path = os.path.join(run_path, "output", "gene_stats.csv")
        gene_stats_data = utils.read_csv(gene_stats_path)
        # Filter data to just rows w/target updates and add to info by update
        for row in gene_stats_data:
            row_update = row["update"]
            if row_update in updates:
                info_by_update[row_update].update(
                    {field:row[field] for field in row if (field not in gene_stats_exclude) and (field not in info_by_update[row_update])}
                )

        ########################################
        # Aggregate representative organism content
        ########################################
        rep_org_path = os.path.join(run_path, "output", "representative_org.csv")
        rep_org_data = utils.read_csv(rep_org_path)
        # Filter data to just rows w/target updates
        for row in rep_org_data:
            row_update = row["update"]
            if row_update in updates:
                # Surround any lists with quotes
                for field in row:
                    if any([s in field for s in ["gene_starts", "gene_neighbors"]]):
                        row[field] = f"\"{row[field]}\""
                row_summary_info = {field:row[field] for field in row if (field not in rep_org_exclude) and (field not in info_by_update[row_update])}
                info_by_update[row_update].update(
                    row_summary_info
                )

        ########################################
        # Add summaries for each update to output content
        ########################################
        for update in info_by_update:
            summary_content_lines.append(info_by_update[update])

    # Write summary info out
    summary_path = os.path.join(dump_dir, "summary.csv")
    utils.write_csv(summary_path, summary_content_lines)

    # print incomplete runs
    if len(incomplete_runs) > 0:
        print("Incomplete runs:")
        print("\n".join(incomplete_runs))
    else:
        print("All runs completed.")


if __name__ == "__main__":
    main()