# Recovery Guide - Scraper Hang/Stop Issues

## 🚨 If Scraper Stops Unexpectedly

### 1. **Check Status**
```powershell
python check_status.py
```

Look for:
- Last log file modification time
- How long ago it stopped
- Last progress logged

### 2. **Kill Hung Process**
```powershell
# Find Python processes
Get-Process python

# Kill specific PID
Stop-Process -Id <PID> -Force

# Or kill all Python
Stop-Process -Name python -Force
```

### 3. **Check What Was Completed**
```powershell
# Count results found so far
(Get-Content results\political_emoji_commits.csv | Measure-Object -Line).Lines - 1

# Check last processed repo from log
Get-Content logs\scraper_*.log -Tail 100 | Select-String "Processing:"
```

### 4. **Resume Options**

#### Option A: Start Fresh (Recommended if early in run)
```powershell
python commitscrapper.py
```

#### Option B: Filter Out Completed Repos
1. Export completed repo list from results CSV
2. Create new input CSV excluding completed ones
3. Update `INPUT_CSV` in script
4. Run again

### 5. **Monitor New Run**

The new version includes:
- **Watchdog thread**: Alerts if no progress for 10 minutes
- **Heartbeat logging**: Shows activity every 30 seconds
- **Enhanced error logging**: More details on failures

Watch for these indicators:

✅ **Healthy Signs:**
- `📊 Progress: X/Y` updates regularly
- `🔍 Watchdog: Progress detected` every 2 minutes
- Thread names appearing in logs
- API requests completing

❌ **Warning Signs:**
- `⚠️ Watchdog: No progress for X minutes`
- Same repo processing for >5 minutes
- No log updates for >2 minutes
- Memory usage climbing steadily

### 6. **Common Hang Causes**

| Symptom | Cause | Solution |
|---------|-------|----------|
| Stops mid-processing | Network timeout hang | ✅ Fixed with better timeout handling |
| High memory then crash | Memory leak | Reduce MAX_WORKERS to 10 |
| Stops after X hours | Connection pool deadlock | ✅ Fixed with HTTPAdapter config |
| Random stops | Thread deadlock | ✅ Fixed with global sleep mode |
| Stops on specific repo | Bad repo data | Check last repo in log, skip it |

### 7. **Reduce Risk of Hangs**

Edit `commitscrapper.py` configuration:

```python
# More conservative settings
MAX_WORKERS = 10  # Fewer concurrent threads
REQUEST_DELAY = 0.1  # Slower requests
```

### 8. **Debug Mode**

To see more details, set console logging to DEBUG:

```python
# In setup_logging() function
console_handler.setLevel(logging.DEBUG)  # Changed from INFO
```

This will show:
- Every API request
- Token rotations
- Retry attempts
- Watchdog checks

⚠️ **Warning**: DEBUG mode generates A LOT of output

### 9. **Emergency Recovery**

If scraper keeps hanging on same repo:

1. Find problem repo:
```powershell
Get-Content logs\scraper_*.log -Tail 200 | Select-String "Processing:"
```

2. Note the last `📂 Processing: owner/repo`

3. Remove from input CSV temporarily

4. Investigate that repo manually on GitHub

### 10. **Get Help**

If issues persist, collect this info:

```powershell
# System info
Get-ComputerInfo | Select-Object WindowsVersion, OsArchitecture, CsTotalPhysicalMemory

# Python info
python --version
pip show requests

# Last 100 log lines
Get-Content logs\scraper_*.log -Tail 100 > debug_output.txt
```

## New Features (Latest Version)

### Watchdog Thread
- Monitors progress every 2 minutes
- Sends Discord alert if stuck for 10+ minutes
- Helps identify hangs quickly

### Enhanced Logging
```
🌐 Making GET request to https://api.github.com/... (attempt 1/5)
✓ Response received: 200
📊 Progress: 45/150 (30.0%) - Found: 1770 commits
🔍 Watchdog: Progress detected (45/150)
```

### Heartbeat System
- Logs progress every 30 seconds OR every 10 repos
- Shows scraper is alive even if processing slow repos

### Better Error Recovery
- 5 retries with progressive backoff: [2, 5, 10, 20, 30] seconds
- Server errors (502/503/504) auto-retry
- Network errors (timeout/connection) auto-retry
- Commit-level error isolation (skip bad commits, continue repo)
- Repo-level retries (3 attempts per repo)

## Prevention Tips

1. **Monitor Regularly**: Check Discord notifications
2. **Use Status Script**: Run `python check_status.py` periodically
3. **Conservative Settings**: Start with MAX_WORKERS=10 for first run
4. **Check Logs**: Look for patterns before hangs
5. **Test Small Batch**: Try with 20 repos first to validate setup

## Success Indicators

✅ Scraper is working when you see:
- Regular progress updates
- Watchdog "Progress detected" messages
- Increasing result count in CSV
- Log file actively growing
- Memory usage stable (not climbing)

⚠️ Scraper needs attention when:
- No progress for 5+ minutes
- Watchdog warns about no progress
- Memory usage >80%
- Same repo processing >10 minutes
- Errors increasing rapidly
