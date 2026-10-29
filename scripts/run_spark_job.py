"""Submit PySpark ETL job to local Spark or Docker standalone Spark master."""

import argparse
import subprocess
import sys
from inventory_forecasting.config import settings

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Submit Spark ETL job.")
    parser.add_argument("--master", type=str, default=settings.spark_local_master, help="Spark Master URL")
    args = parser.parse_args()

    print(f"Submitting Spark ETL job to {args.master}...")
    cmd = [
        sys.executable,
        "-m", "inventory_forecasting.processing.spark_pipeline",
        str(settings.bronze_dir),
        str(settings.silver_dir),
        str(settings.gold_dir),
        args.master,
    ]
    res = subprocess.run(cmd)
    if res.returncode == 0:
        print("Spark ETL execution finished successfully.")
    else:
        print(f"Spark ETL execution failed with returncode {res.returncode}")
        sys.exit(res.returncode)
