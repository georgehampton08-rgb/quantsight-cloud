"""
Parallel H2H Data Generation Runner
===================================
Runs all 4 batches in parallel to populate head-to-head matchup data.
"""
import subprocess
import time
import os
from datetime import datetime

# Get absolute paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BATCHES = [
    os.path.join(SCRIPT_DIR, "generate_h2h_batch_1.py"),
    os.path.join(SCRIPT_DIR, "generate_h2h_batch_2.py"),
    os.path.join(SCRIPT_DIR, "generate_h2h_batch_3.py"),
    os.path.join(SCRIPT_DIR, "generate_h2h_batch_4.py")
]

def main():
    print("="*80)
    print("🚀 PARALLEL H2H DATA GENERATION")
    print("="*80)
    print(f"Starting: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Batches: {len(BATCHES)}")
    print()
    
    # Start all batches in parallel
    processes = []
    for i, batch_script in enumerate(BATCHES, 1):
        print(f"🔄 Starting Batch {i}: {batch_script}")
        proc = subprocess.Popen(
            ["python", batch_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        processes.append((i, proc, batch_script))
    
    print()
    print("✅ All batches started in parallel")
    print("⏳ Waiting for completion...")
    print()
    
    # Wait for all to complete and show results
    start_time = time.time()
    for i, proc, script in processes:
        stdout, stderr = proc.communicate()
        elapsed = time.time() - start_time
        
        print(f"\n{'='*80}")
        print(f"📊 BATCH {i} RESULTS ({script})")
        print(f"{'='*80}")
        
        if proc.returncode == 0:
            print(f"✅ Exit Code: {proc.returncode}")
            # Print last 20 lines of output
            lines = stdout.strip().split('\n')
            for line in lines[-20:]:
                print(line)
        else:
            print(f"❌ Exit Code: {proc.returncode}")
            print("Error output:")
            print(stderr[-1000:] if len(stderr) > 1000 else stderr)
        print()
    
    total_time = time.time() - start_time
    print("="*80)
    print(f"🎉 ALL BATCHES COMPLETE")
    print(f"Total runtime: {total_time/60:.1f} minutes ({total_time:.1f} seconds)")
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    print()
    print("✅ H2H data generation complete!")
    print("   Check Firestore 'player_h2h' collection for results")

if __name__ == "__main__":
    main()
