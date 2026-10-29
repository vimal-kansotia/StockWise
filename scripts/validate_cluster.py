"""Validate Spark Master and Spark Workers registration."""

import urllib.request
import json
import sys

def check_spark_cluster(master_ui_url: str = "http://localhost:8080/json/"):
    print(f"Connecting to Spark Master UI API at {master_ui_url}...")
    try:
        req = urllib.request.Request(master_ui_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            
            status = data.get("status")
            alive_workers = data.get("aliveworkers", 0)
            workers = data.get("workers", [])

            print(f"Master Status: {status}")
            print(f"Alive Workers Count: {alive_workers}")
            for idx, w in enumerate(workers, 1):
                print(f"  Worker {idx}: ID={w.get('id')} Host={w.get('host')} Cores={w.get('cores')} Memory={w.get('memory')}")

            if alive_workers >= 2:
                print("SUCCESS: Both Spark workers are registered and alive.")
                return True
            else:
                print(f"WARNING: Expected at least 2 registered workers, found {alive_workers}.")
                return False
    except Exception as e:
        print(f"Could not connect to Spark Master UI: {e}")
        print("Note: If running outside Docker, start services with 'docker compose up -d spark-master spark-worker-1 spark-worker-2'.")
        return False

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080/json/"
    check_spark_cluster(url)
