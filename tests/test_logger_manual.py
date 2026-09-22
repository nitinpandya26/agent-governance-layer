import sys
sys.path.insert(0, ".")

from audit.logger import verify_chain

run_id = "cf4eb840-5a99-4f9d-867c-48e5a7f1d61c"
print("Chain valid:", verify_chain(run_id))