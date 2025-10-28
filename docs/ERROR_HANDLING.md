# Enhanced Error Handling & Reliability

## Summary of Improvements

This document describes the comprehensive error handling and failsafe mechanisms added to the scraper to handle GitHub API issues, network errors, and rate limiting.

## Key Enhancements

### 1. Connection Pool Management

**Problem**: "Connection pool is full" warnings causing request failures

**Solution**:
```python
adapter = requests.adapters.HTTPAdapter(
    pool_connections=MAX_WORKERS,
    pool_maxsize=MAX_WORKERS * 2,
    max_retries=0
)
```

- Connection pool sized to handle all concurrent workers
- Max pool size doubled for buffer
- Manual retry handling for better control

### 2. Server Error Retry Logic

**Problem**: 502 Bad Gateway, 503 Service Unavailable, 504 Gateway Timeout causing failures

**Solution**:
- Increased retries from 3 to **5 attempts**
- Progressive backoff delays: `[2, 5, 10, 20, 30]` seconds
- Specific handling for each server error type
- Detailed logging for each retry attempt

```python
elif response.status_code in [502, 503, 504]:
    error_name = {502: "Bad Gateway", 503: "Service Unavailable", 504: "Gateway Timeout"}
    logger.warning(
        f"🔄 {response.status_code} {error_name.get(response.status_code)} - "
        f"Retrying in {retry_delays[attempt]}s (attempt {attempt + 1}/{max_retries})"
    )
    time.sleep(retry_delays[attempt])
    continue
```

### 3. Network Error Handling

**New error types handled**:
- `Timeout` - 30 second timeout with retry
- `ConnectionError` - Network connection issues with retry
- `RequestException` - Generic request failures with retry

Each error type:
- Logs the specific error
- Shows retry attempt number
- Uses progressive backoff
- Returns `None` after max retries

### 4. Repository-Level Retry

**Problem**: Entire repository fails on single error

**Solution**: 3-attempt retry at repository level
```python
max_retries = 3  # Retry failed repos

for repo_attempt in range(max_retries):
    try:
        # Process repository
        return results
    except Exception as e:
        if repo_attempt < max_retries - 1:
            logger.info(f"  🔄 Retrying {owner}/{name} in 3 seconds...")
            time.sleep(3)
```

### 5. Commit-Level Error Isolation

**Problem**: One bad commit crashes entire repository processing

**Solution**: Try-except around each commit
```python
for edge in edges:
    try:
        # Process commit
    except Exception as commit_error:
        logger.warning(f"  ⚠️ Error processing commit: {str(commit_error)[:100]}")
        continue  # Skip bad commit, continue with others
```

### 6. Enhanced Logging

**New log levels and messages**:
- `🔄` - Retry attempts (server errors, network issues)
- `⏱️` - Timeout errors
- `🔌` - Connection errors
- `⚠️` - Warnings (low token quota, consecutive errors)
- `🛑` - Critical issues (all tokens exhausted)

**Token quota warnings**:
```python
if remaining < 100:
    logger.warning(f"⚠️ Token running low: {remaining} requests remaining")
```

### 7. Error Rate Monitoring

**Problem**: No visibility when errors spike

**Solution**: Consecutive error tracking with notifications
```python
consecutive_errors = 0

# On success
if results or consecutive_errors > 0:
    consecutive_errors = 0

# On error
consecutive_errors += 1
if consecutive_errors >= 10:
    # Send Discord alert every 5 minutes
    notifier.send("⚠️ High Error Rate Detected")
```

### 8. Improved Progress Logging

**Enhanced progress messages** every 10 repos:
```
📊 Progress: 120/150 (80.0%) - Found: 45 commits - Errors: 3 - Tokens: 15 available, 5 exhausted
```

Now includes:
- Error count
- Token availability status

### 9. HTTP Error Code Handling

**Comprehensive error code coverage**:

| Code | Type | Action |
|------|------|--------|
| 403 | Rate Limit | Switch token or sleep |
| 403 | Other Forbidden | Log and skip |
| 404 | Not Found | Log and skip (expected) |
| 400-499 | Client Error | Log and skip (no retry) |
| 502 | Bad Gateway | Retry with backoff |
| 503 | Service Unavailable | Retry with backoff |
| 504 | Gateway Timeout | Retry with backoff |

### 10. Global Sleep Mode Improvements

**Enhanced sleep behavior**:
- Check at every request (not just after repo completion)
- Skip requests during sleep mode
- Single-threaded sleep handling (prevents duplicate sleeps)
- Automatic token reset after sleep

## Error Notification Strategy

### Discord Notifications

**Progress Updates** (every 50 repos):
- Processed count & percentage
- Emoji commits found
- **Error count** (new)
- Token availability

**Error Alerts** (every 5 minutes when errors >= 10):
```
⚠️ High Error Rate Detected
Consecutive errors: 12
Total errors: 45
Progress: 120/150
Last error: 502 Bad Gateway
```

**Rate Limit Alerts**:
```
⏸️ Rate limit reached
All 20 tokens exhausted
Sleeping for 1 hour...
Progress: 120/150
```

## Retry Strategy Summary

### Request Level (5 attempts)
1. **Attempt 1**: Immediate
2. **Attempt 2**: Wait 2s
3. **Attempt 3**: Wait 5s
4. **Attempt 4**: Wait 10s
5. **Attempt 5**: Wait 20s
6. **Final**: Wait 30s → Give up

### Repository Level (3 attempts)
1. **Attempt 1**: Process normally
2. **Attempt 2**: Wait 3s → Retry
3. **Attempt 3**: Wait 3s → Retry
4. **Final**: Log error, move to next repo

### Commit Level (No retry)
- Skip bad commit
- Continue with other commits
- Prevents single commit from blocking repo

## Monitoring Recommendations

### During Execution

Watch for these log patterns:

**Good**:
```
✓ Found 15 commits for README.md
🎯 Found emoji commit: abc12345 - 🇺🇦, 💙
```

**Warning**:
```
⚠️ Token running low: 87 requests remaining
🔄 502 Bad Gateway - Retrying in 5s (attempt 2/5)
```

**Critical**:
```
🛑 All tokens exhausted, initiating sleep period...
❌ Failed to process owner/repo after 3 attempts
```

### Log File Analysis

After completion, check log file for:
```bash
# Count errors
grep "❌" logs/scraper_*.log | wc -l

# Count retries
grep "🔄" logs/scraper_*.log | wc -l

# Count token warnings
grep "Token running low" logs/scraper_*.log | wc -l

# Count server errors
grep "502\|503\|504" logs/scraper_*.log | wc -l
```

## Best Practices

### For Stable Operation

1. **Monitor initial run**: Watch first 50 repos for error patterns
2. **Check Discord**: Enable webhook for real-time alerts
3. **Log review**: Check logs after 1 hour for issues
4. **Token monitoring**: Watch for "running low" warnings
5. **Error threshold**: Investigate if error rate > 10%

### If Errors Spike

1. **Check GitHub Status**: https://www.githubstatus.com/
2. **Reduce workers**: Lower `MAX_WORKERS` from 20 to 10
3. **Increase delays**: Raise `REQUEST_DELAY` from 0.05 to 0.1
4. **Review logs**: Look for specific error patterns

### Recovery Actions

**Too many 502/503 errors**:
- GitHub API is unstable
- Wait 15-30 minutes and restart
- Reduce `MAX_WORKERS` to 10

**Connection pool errors**:
- Should now be fixed with adapter
- If persists, reduce `MAX_WORKERS`

**Timeout errors**:
- Network/API slow
- Errors are now retried automatically
- If persistent, increase timeout from 30s to 60s

## Configuration Tuning

### Conservative (Most Stable)
```python
MAX_WORKERS = 10
REQUEST_DELAY = 0.1
RATE_LIMIT_SLEEP = 3600
```

### Balanced (Recommended)
```python
MAX_WORKERS = 20
REQUEST_DELAY = 0.05
RATE_LIMIT_SLEEP = 3600
```

### Aggressive (Fastest but riskier)
```python
MAX_WORKERS = 20
REQUEST_DELAY = 0.01
RATE_LIMIT_SLEEP = 1800
```

## Testing

To test error handling:

1. **Test with 1 worker**: Easier to debug
   ```python
   MAX_WORKERS = 1
   ```

2. **Monitor first 10 repos**: Check logs carefully
   ```bash
   tail -f logs/scraper_*.log
   ```

3. **Check error recovery**: Should see retry attempts succeed

## Known Limitations

1. **Maximum 5 retries per request** - After this, request fails
2. **Maximum 3 retries per repository** - After this, repo skipped
3. **Discord rate limits** - Error notifications limited to every 5 minutes
4. **No checkpoint/resume** - If stopped, must restart from beginning

## Future Enhancements

Potential improvements:
- [ ] Checkpoint system to resume from failures
- [ ] Dynamic worker adjustment based on error rate
- [ ] Automatic fallback to slower mode on errors
- [ ] Per-error-type statistics tracking
- [ ] Automatic GitHub status page checking

---

For more information:
- [Advanced Configuration](ADVANCED_CONFIG.md)
- [Quick Start Guide](QUICKSTART.md)
- [Implementation Summary](IMPLEMENTATION_SUMMARY.md)
