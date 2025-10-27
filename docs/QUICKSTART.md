# Quick Start Guide

## ✅ Setup Complete!

Your GitHub Political Emoji Scraper is ready to run with:
- **20 GitHub tokens** loaded
- **Discord webhook** configured  
- **118 repositories** to process from CSV
- All directories created

## 🚀 Running the Scraper

### Option 1: Run with default settings
```bash
python commitscrapper.py
```

### Option 2: Run in background (recommended for long runs)
```bash
# Windows PowerShell
Start-Process python -ArgumentList "commitscrapper.py" -NoNewWindow -RedirectStandardOutput "logs\stdout.log" -RedirectStandardError "logs\stderr.log"

# Or use nohup on Linux/Mac
nohup python commitscrapper.py &
```

## 📊 What Will Happen

1. **Initialization** (5-10 seconds)
   - Load 20 GitHub tokens
   - Read and filter CSV (118 repos)
   - Set up logging and Discord notifications

2. **Processing** (variable time)
   - 20 concurrent workers processing repositories
   - Each repo: GraphQL query → REST API calls → Emoji detection
   - Progress updates every 10 repos
   - Discord notifications every 50 repos

3. **Rate Limit Handling**
   - 50ms delay between each API request
   - Automatic token rotation
   - If all 20 tokens exhausted: 1-hour sleep, then resume

4. **Output Generation**
   - Results saved to `results/political_emoji_commits.csv`
   - Detailed logs in `logs/scraper_YYYYMMDD_HHMMSS.log`
   - Final summary sent to Discord

## ⏱️ Estimated Time

With 118 repositories and 20 tokens:
- **Best case**: 5-15 minutes (if repos have few commits)
- **Average case**: 30-60 minutes
- **Worst case**: 2-3 hours (if many large repos with rate limits)

## 📈 Monitoring Progress

### Console Output
```
2025-10-27 14:30:00 - INFO - ✓ Loaded 20 GitHub tokens
2025-10-27 14:30:01 - INFO - 📖 Loading repositories from github_affiliation_combined.csv...
2025-10-27 14:30:02 - INFO - ✓ Loaded 118 repositories with affiliation
2025-10-27 14:30:02 - INFO - 🎯 Processing 118 repositories with 20 workers
2025-10-27 14:30:05 - INFO - 📂 Processing: apache/dubbo
2025-10-27 14:30:10 - INFO - 📊 Progress: 10/118 (8.5%) - Found: 3 commits - Tokens available: 20/20
```

### Discord Notifications
You'll receive:
- ✅ Start notification
- 📊 Progress updates (every 50 repos)
- ⚠️ Rate limit warnings
- ✅ Completion summary

### Log Files
Check `logs/scraper_YYYYMMDD_HHMMSS.log` for detailed debugging info

## 🛑 Stopping the Scraper

**Safe stop** (recommended):
- Press `Ctrl+C` once
- Scraper will finish current repository and save partial results

**Force stop**:
- Press `Ctrl+C` twice
- May lose results for repositories in progress

## 📁 Output Files

After completion, you'll have:

```
results/
  └─ political_emoji_commits.csv    # Main results

logs/
  └─ scraper_20251027_143000.log    # Detailed logs
```

## 🔍 Checking Results

```bash
# Count total emoji commits found
python -c "import csv; print(sum(1 for _ in csv.reader(open('results/political_emoji_commits.csv'))) - 1)"

# View first few results
head -n 10 results/political_emoji_commits.csv

# Or open in Excel/LibreOffice
start results\political_emoji_commits.csv  # Windows
```

## 🐛 Troubleshooting

### No results found?
```bash
# Check if repositories have README files
# Check logs for errors
cat logs/scraper_*.log | grep "ERROR"
```

### Rate limit errors?
- Normal! The scraper automatically handles this
- It will sleep for 1 hour when all 20 tokens are exhausted
- Check Discord for notifications

### Script crashes?
```bash
# Check the error in logs
tail -n 50 logs/scraper_*.log

# Common fixes:
# 1. Verify .env has valid tokens
# 2. Check internet connection
# 3. Ensure CSV file is not corrupted
```

## 📊 Sample Output Row

```csv
repo_owner,repo_name,repo_url,commit_sha,commit_datetime,author_name,author_email,commit_message,emojis_detected,readme_additions_snippet,deepseek_affiliation,chatgpt_affiliation,is_pull_request,pr_number,readme_file_path
apache,dubbo,https://github.com/apache/dubbo,abc123...,2024-03-15T10:30:00Z,John Doe,john@example.com,Add support statement,🇺🇦|💙,We stand with Ukraine 🇺🇦💙,supporter,none,True,1234,README.md
```

## 🎯 Expected Results

For 118 repositories, you might find:
- **0-50 commits**: If repos don't have political emojis (normal)
- **50-200 commits**: Good dataset for analysis
- **200+ commits**: Excellent! Many repos show political support

## 🔄 Re-running the Scraper

The scraper doesn't track processed repos, so it will:
- ✅ Process all 118 repos again
- ✅ Overwrite previous results in `results/political_emoji_commits.csv`
- ✅ Create new log file with timestamp

To keep previous results:
```bash
# Backup before re-running
cp results/political_emoji_commits.csv results/backup_$(date +%Y%m%d_%H%M%S).csv
```

## 📞 Need Help?

1. Check `logs/` for detailed error messages
2. Verify setup: `python test_setup.py`
3. Review `IMPLEMENTATION_SUMMARY.md` for technical details
4. Check `README.md` for configuration options

## 🎉 Success Indicators

You'll know it's working when you see:
- ✅ Token rotation happening (different tokens in logs)
- ✅ Progress percentages increasing
- ✅ Discord notifications arriving
- ✅ Log file growing in size
- ✅ No repeated errors in console

---

**Ready to start?** Run: `python commitscrapper.py`

**Want to test first?** Run: `python test_setup.py`
