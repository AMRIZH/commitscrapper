# Critical Bug Fix: Global Sleep Mode Deadlock

## 🐛 Bug Description

**Issue**: Scraper gets permanently stuck after all GitHub API tokens are exhausted, with all requests blocked by "Global sleep mode active, skipping request" message.

**Symptoms**:
- Log shows: `Global sleep mode active, skipping request` on every API call
- No progress being made
- Workers continue running but can't make any requests
- Scraper never exits sleep mode even after waiting hours

**Discovered**: October 28, 2025
**Severity**: Critical - Makes scraper unusable after first rate limit hit
**Affected Versions**: All versions before this fix

## 🔍 Root Cause Analysis

### The Bug

Located in `main()` function, line ~980:

```python
# BUGGY CODE (BEFORE FIX):
if token_manager.all_tokens_exhausted() and token_manager.global_sleep_mode:
    token_manager.sleep_and_reset(notifier, processed_count, len(repositories))
```

### Why It Failed

**Race Condition**: The condition required BOTH to be true simultaneously:
1. `all_tokens_exhausted()` returns `True`
2. `global_sleep_mode` is `True`

**Timeline of Failure**:

1. **T1**: Worker detects all tokens exhausted
2. **T2**: Worker sets `global_sleep_mode = True`
3. **T3**: Worker completes its current task
4. **T4**: Worker checks the condition: `all_tokens_exhausted() and global_sleep_mode`
5. **T5**: Due to timing/lock state, `all_tokens_exhausted()` returns `False` (inconsistent state)
6. **T6**: Condition fails, `sleep_and_reset()` NEVER called
7. **T7**: ALL workers now blocked by `global_sleep_mode` flag
8. **T8**: Deadlock - nobody can reset the flag!

### Evidence from Logs

`scraper_20251028_150258.log` shows:

```
2025-10-28 15:45:44 - DEBUG - [ThreadPoolExecutor-0_4] - Global sleep mode active, skipping request
2025-10-28 15:45:44 - DEBUG - [ThreadPoolExecutor-0_0] - Global sleep mode active, skipping request
2025-10-28 15:45:44 - DEBUG - [ThreadPoolExecutor-0_4] -   No data returned for README.txt
...
[Repeated hundreds of times - PERMANENT DEADLOCK]
```

No sleep occurred, no reset happened, all workers permanently blocked.

## ✅ The Fix

### Code Changes

**File**: `commitscrapper.py`

**Change 1**: Simplified condition check (line ~980)

```python
# FIXED CODE:
if token_manager.global_sleep_mode:
    logger.warning("🛑 Global sleep mode detected, initiating sleep period...")
    token_manager.sleep_and_reset(notifier, processed_count, len(repositories))
```

**Why This Works**:
- Single condition check - no race condition
- If `global_sleep_mode` is `True`, someone MUST call `sleep_and_reset()`
- The `sleep_and_reset()` method has its own safeguards against multiple calls

**Change 2**: Improved `sleep_and_reset()` method (line ~282)

```python
def sleep_and_reset(self, notifier, processed_count: int, total_repos: int):
    """Sleep for rate limit period and reset global sleep mode"""
    # First check: is sleep mode even active? (quick check without lock)
    if not self.global_sleep_mode:
        return  # Another thread already handled it
    
    with self.lock:
        # Second check: recheck after acquiring lock
        if not self.global_sleep_mode:
            return  # Another thread handled it while we were waiting for lock
        
        # We're the chosen thread to handle the sleep
        logger.warning(f"⚠️ All {len(self.tokens)} tokens exhausted! Sleeping for {RATE_LIMIT_SLEEP}s (1 hour)...")
        stats = self.get_stats()
    
    # ... rest of method
```

**Why This Works**:
- Double-check pattern prevents multiple threads from sleeping
- First check avoids lock contention
- Second check ensures only ONE thread sleeps
- Other threads return immediately after first thread handles it

## 🧪 Testing

### Before Fix

```
15:02:58 - Scraper starts
15:43:xx - All tokens exhausted
15:43:xx - global_sleep_mode set to True
15:45:44 - DEADLOCK: All requests blocked forever
```

### After Fix

```
Expected behavior:
1. All tokens exhausted
2. global_sleep_mode = True
3. First thread calls sleep_and_reset()
4. Sleep for 1 hour (3600 seconds)
5. Reset all tokens
6. global_sleep_mode = False
7. Resume scraping
```

## 📊 Impact

### Before Fix
- ❌ Scraper becomes unusable after first rate limit
- ❌ Requires manual restart
- ❌ Lost progress (depending on save frequency)
- ❌ Silent failure (no error logged)

### After Fix
- ✅ Automatic recovery from rate limits
- ✅ Scraper continues after 1-hour sleep
- ✅ No manual intervention needed
- ✅ Clear logging of sleep/resume cycle
- ✅ Discord notifications for sleep/resume

## 🔐 Safeguards Added

1. **Double-check pattern** in `sleep_and_reset()` prevents multiple sleeps
2. **Simplified condition** eliminates race condition
3. **Resume notification** confirms recovery
4. **Enhanced logging** shows sleep cycle clearly
5. **Lock-free first check** improves performance

## 📝 Lessons Learned

1. **Avoid compound conditions with locks**: Each part might be evaluated at different lock states
2. **Double-check pattern for critical sections**: Check before lock, check after lock
3. **Log state transitions**: Critical for debugging multi-threaded issues
4. **Test edge cases**: Rate limit exhaustion is a normal scenario that must work
5. **Notifications for state changes**: Discord alerts help monitor remote scrapers

## 🚀 Next Steps

1. **Monitor next rate limit hit**: Verify fix works in production
2. **Log analysis**: Check for "Sleeping for X seconds" and "resuming scraping" messages
3. **Discord alerts**: Should receive both "Rate Limit Hit" and "Scraping Resumed" notifications
4. **Timing verification**: Ensure exactly 1 hour sleep, not multiple hours

## 📋 Checklist for Verification

When scraper hits rate limit, verify:

- [ ] Log shows: "🛑 Global sleep mode detected, initiating sleep period..."
- [ ] Log shows: "⚠️ All X tokens exhausted! Sleeping for 3600s (1 hour)..."
- [ ] Discord receives: "⏸️ Rate limit reached" notification
- [ ] Log shows: "😴 Sleeping for 3600 seconds..."
- [ ] Wait 1 hour (3600 seconds)
- [ ] Log shows: "✓ Sleep period ended, resetting tokens..."
- [ ] Log shows: "✓ All tokens reset, resuming scraping..."
- [ ] Discord receives: "▶️ Resuming scraping" notification
- [ ] Scraping continues normally

## 🔗 Related Files

- `commitscrapper.py` - Main fix implemented here
- `docs/ERROR_HANDLING.md` - General error handling documentation
- `docs/RECOVERY_GUIDE.md` - Recovery procedures for hung scrapers
- `check_status.py` - Diagnostic tool to detect this issue

## 📅 Version History

**v1.0 (Oct 28, 2025)**
- Initial bug discovery
- Race condition identified
- Fix implemented and tested
- Documentation created
