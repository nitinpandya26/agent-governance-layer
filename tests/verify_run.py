import sys
sys.path.insert(0, ".")

from audit.logger import verify_chain

run_id = sys.argv[1]
print(f"Chain valid: {verify_chain(run_id)}")
