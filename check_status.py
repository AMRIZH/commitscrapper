#!/usr/bin/env python3
"""
Quick diagnostic script to check scraper status
"""

import os
import glob
from datetime import datetime

print("="*60)
print("🔍 GitHub Scraper Status Check")
print("="*60)

# Check if script is running
print("\n1. Process Check:")
try:
    import psutil
    found_scraper = False
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline', [])
            if cmdline and 'commitscrapper.py' in ' '.join(cmdline):
                print(f"   ✓ Scraper is RUNNING (PID: {proc.info['pid']})")
                print(f"     Command: {' '.join(cmdline[:3])}")
                found_scraper = True
        except:
            pass
    
    if not found_scraper:
        print("   ⚠️ Scraper process not found")
except ImportError:
    print("   ⚠️ psutil not installed - cannot check process")
    print("   Install with: pip install psutil")

# Check latest log file
print("\n2. Latest Log File:")
log_files = glob.glob("logs/scraper_*.log")
if log_files:
    latest_log = max(log_files, key=os.path.getmtime)
    mod_time = datetime.fromtimestamp(os.path.getmtime(latest_log))
    time_ago = datetime.now() - mod_time
    
    print(f"   📝 {latest_log}")
    print(f"   ⏰ Last modified: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   ⌛ {time_ago.seconds // 60} minutes ago")
    
    # Check last few lines
    print("\n   Last 10 lines:")
    with open(latest_log, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
        for line in lines[-10:]:
            print(f"   {line.rstrip()}")
else:
    print("   ⚠️ No log files found")

# Check output file
print("\n3. Output File:")
output_file = "results/political_emoji_commits.csv"
if os.path.exists(output_file):
    mod_time = datetime.fromtimestamp(os.path.getmtime(output_file))
    size = os.path.getsize(output_file)
    
    print(f"   ✓ {output_file}")
    print(f"   📊 Size: {size:,} bytes")
    print(f"   ⏰ Last modified: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Count lines
    with open(output_file, 'r', encoding='utf-8') as f:
        line_count = sum(1 for _ in f) - 1  # Subtract header
    print(f"   🎯 Emoji commits found: {line_count}")
else:
    print("   ⚠️ Output file not found yet")

print("\n" + "="*60)
print("💡 Recommendations:")
print("="*60)
if log_files:
    print(f"   • Check full log: {latest_log}")
print("   • Look for ERROR messages or exceptions")
print("   • Check if progress is updating")
print("   • Monitor CPU/memory usage")
print("="*60)
