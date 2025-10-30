# Repository History Scraper - Feature Documentation

## 🎯 Overview

The Repository History Scraper is an advanced GitHub repository metrics tracker that captures snapshots of:
- ⭐ Total star counts
- 🍴 Total fork counts
- 👥 Total contributor counts
- 📥 Total pull request counts
- 💻 Total commit counts
- 🐛 Total issue counts

By taking periodic snapshots (daily or weekly), you can analyze repository growth trends over time.

## ✨ Key Features

### 1. Comprehensive Text Report Generation

Automatically generates detailed reports saved to `results/repo_history_report_YYYYMMDD_HHMMSS.txt`

**Report Sections:**
- Summary statistics (repos scraped, duration, API requests)
- Repository metrics (total counts and averages for all 6 metrics)
- Top 5 most starred repositories
- Top 5 most active repositories (by total commits)
- Top 5 most collaborative (by contributors)
- Top 5 by total pull requests
- Top 5 by total issues
- Top 5 most forked repositories
- Affiliation breakdown (DeepSeek/ChatGPT)
- File locations

### 2. Discord Webhook Integration

Sends automated notifications to Discord when scraping completes.

**Setup:**
```bash
# Add to .env file
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN
```

**Notification includes:**
- Total repositories scraped
- Scraping duration
- Total stars, forks, and commits across all repos
- Average stars per repo
- Links to output files

### 3. Daily/Weekly Scraping Choice

Configure scraping frequency to capture repository snapshots:

```python
# In repoHistory.py (line 40)
SCRAPING_FREQUENCY = "D"   # Daily snapshots
# OR
SCRAPING_FREQUENCY = "W"  # Weekly snapshots
```

**Purpose:**
- Creates time-series data for trend analysis
- Each run appends a new snapshot to the CSV
- Compare snapshots to calculate growth metrics

### 4. Extended Metrics Tracking

#### GitHub API Endpoints Used:

1. **Repository Info**
   - Endpoint: `GET /repos/{owner}/{repo}`
   - Data: `stargazers_count`, `forks_count`, basic repo info

2. **Contributors Count**
   - Endpoint: `GET /repos/{owner}/{repo}/contributors`
   - Data: Total contributors (pagination-aware)

3. **Pull Requests Count**
   - Endpoint: `GET /repos/{owner}/{repo}/pulls?state=all&per_page=1`
   - Data: Total PRs (uses pagination headers for count)

4. **Commits Count**
   - Endpoint: `GET /repos/{owner}/{repo}/commits?per_page=1`
   - Data: Total commits (uses pagination headers for count)

5. **Issues Count**
   - Endpoint: `GET /repos/{owner}/{repo}/issues?state=all&per_page=100`
   - Data: Total issues (excludes PRs, uses pagination for accurate count)

### 5. Top 5 Rankings in Reports

Every report includes Top 5 lists for:
- ⭐ Most Starred Repositories
- 🔥 Most Active Repositories (by total commits)
- 👥 Most Collaborative (by contributors)
- 📥 Most Pull Requests (total count)
- 🐛 Most Issues (total count)
- 🍴 Most Forked Repositories

## 📊 CSV Output Structure

File: `results/repo_history.csv`

| Column | Type | Description |
|--------|------|-------------|
| repo_owner | string | Repository owner username |
| repo_name | string | Repository name |
| repo_url | string | Full GitHub URL |
| snapshot_date | date | Date of snapshot (YYYY-MM-DD) |
| total_stars | int | Total stars at snapshot time |
| total_forks | int | Total forks at snapshot time |
| total_contributors | int | Total unique contributors |
| total_prs | int | Total pull requests (all states) |
| total_commits | int | Total commits in repository |
| total_issues | int | Total issues (excluding PRs) |
| deepseek_affiliation | string | DeepSeek affiliation status |
| chatgpt_affiliation | string | ChatGPT affiliation status |

## ⚙️ Configuration

All configuration variables are at the top of `repoHistory.py`:

```python
# API Configuration
REQUEST_DELAY = 0.1           # 100ms delay between requests
RATE_LIMIT_SLEEP = 3600       # 1 hour sleep when exhausted
MAX_WORKERS = 12              # Concurrent worker threads

# Filter Configuration
FILTER_BY_AFFILIATION = False # True = affiliated only, False = all repos

# Scraping Frequency
SCRAPING_FREQUENCY = "W" # "D" (daily) or "W" (weekly)

# File Paths
INPUT_CSV = "datasets/affiliated_deepseek_1000_200000.csv"
OUTPUT_CSV = "results/repo_history.csv"
REPORT_FILE = "results/repo_history_report_YYYYMMDD_HHMMSS.txt"

# Discord Webhook (optional)
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
```

## 🚀 Usage Examples

### Basic Weekly Tracking
```bash
# Default configuration (weekly, all repos)
python repoHistory.py
```

### Daily Tracking
```python
# Edit repoHistory.py line 40
SCRAPING_FREQUENCY = "D"
```
```bash
python repoHistory.py
```

### Filter Affiliated Repos Only
```python
# Edit repoHistory.py line 34
FILTER_BY_AFFILIATION = True
```
```bash
python repoHistory.py
```

### Enable Discord Notifications
```bash
# Add to .env
echo 'DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_URL' >> .env
python repoHistory.py
```

## 📈 Performance

**Console:**
- 100,000 requests/hour capacity
- ~5 API calls per repository
- Can scrape ~20,000 repos/hour
- 113 repos takes 1-2 minutes

**Multi-threading:**
- Default: 12 concurrent workers
- Automatically scales to available tokens
- Efficient token rotation

## 📄 Sample Report Excerpt

```
📊 GITHUB REPOSITORY HISTORY SCRAPING REPORT
================================================================================
Generated: 2025-10-30 14:30:00
Scraping Frequency: WEEKLY
Filter Mode: All Repositories

📊 SUMMARY STATISTICS
--------------------------------------------------------------------------------
Total Repositories Scraped: 113
Scraping Duration: 0:15:30
Total API Requests: 565
Tokens Used: 20

⭐ STAR STATISTICS
--------------------------------------------------------------------------------
Total Stars Across All Repos: 125,432
Average Stars Per Repo: 1,110
Total Contributors: 8,543
Average Contributors Per Repo: 76

📈 WEEKLY ACTIVITY STATISTICS
--------------------------------------------------------------------------------
New Pull Requests (Weekly): 45
New Commits (Weekly): 234
New Issues (Weekly): 67

🏆 TOP 5 MOST STARRED REPOSITORIES
--------------------------------------------------------------------------------
1. hykilpikonna/hyfetch
   Stars: 12,345 | Contributors: 156
   URL: https://github.com/hykilpikonna/hyfetch
...
```

## 🔧 Troubleshooting

**No Discord notifications:**
- Check `.env` file has correct webhook URL
- Verify Discord webhook is active
- Check logs for error messages

**Rate limiting issues:**
- Increase `REQUEST_DELAY` (e.g., 0.2)
- Reduce `MAX_WORKERS` (e.g., 8)
- Verify all 20 tokens are valid

**Missing metrics:**
- Some repos may have disabled features
- Private repos require proper permissions
- Check logs for specific errors

## 📝 Notes

- CSV appends data on each run (allows historical tracking)
- First run sets baseline, subsequent runs show trends
- Reports are timestamped to track different runs
- Discord notifications automatically truncated to 2000 chars
- All errors logged to `logs/repo_history_YYYYMMDD_HHMMSS.log`

## 🎓 Best Practices

1. **Run weekly** for consistent trend tracking
2. **Keep CSV file** to calculate star growth over time
3. **Monitor logs** for any API issues
4. **Backup reports** for long-term analysis
5. **Use Discord** for automated monitoring alerts

## 📚 Related Files

- `repoHistory.py` - Main scraper program
- `results/repo_history.csv` - Historical data
- `results/repo_history_report_*.txt` - Reports
- `logs/repo_history_*.log` - Execution logs
- `.env` - Configuration (tokens, webhooks)

---

**Last Updated:** October 30, 2025  
**Version:** 2.0 (Enhanced with activity metrics)
