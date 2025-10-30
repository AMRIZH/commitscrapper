# GitHub Repository Analytics Suite

A comprehensive Python toolkit for analyzing GitHub repositories, featuring:
1. **Repository History Tracker** (`repoHistory.py`) - Track repository metrics over time
2. **Political Emoji Commit Scraper** (`commitscrapper.py`) - Extract commits with political emojis

---

## 🌟 Repository History Tracker

Track repository metrics (stars, forks, contributors, PRs, commits, issues) at daily or weekly intervals to analyze growth and activity trends.

### Features

✨ **Comprehensive Metrics**: Stars, forks, contributors, PRs, commits, and issues  
📊 **Snapshot Tracking**: Take periodic snapshots to calculate growth over time  
🔄 **Token Rotation**: Automatic rotation across multiple GitHub tokens  
⚡ **Multi-threading**: Process multiple repositories concurrently (12 workers)  
📈 **Detailed Reports**: Auto-generated text reports with Top 5 rankings  
🔔 **Discord Notifications**: Optional webhook notifications  
⏰ **Flexible Scheduling**: Daily ("D") or Weekly ("W") tracking intervals  

### Metrics Tracked

At each snapshot, the following **total counts** are recorded:
- ⭐ **Total Stars** - Current star count
- 🍴 **Total Forks** - Current fork count
- 👥 **Total Contributors** - Total unique contributors
- 📥 **Total Pull Requests** - All PRs (open + closed)
- 💻 **Total Commits** - All commits in repository
- 🐛 **Total Issues** - All issues (excluding PRs)

**Growth Analysis**: By comparing snapshots from different dates, you can calculate:
- Stars gained per period
- New contributors added
- Development velocity (commits/PRs)
- Issue trends

### Quick Start

1. **Configure frequency** (edit `repoHistory.py` line 40):
   ```python
   SCRAPING_FREQUENCY = "W"  # "D" for daily, "W" for weekly
   ```

2. **Prepare input CSV** with columns:
   - `repo_owner`, `repo_name`, `repo_url`
   - `deepseek_affiliation`, `chatgpt_affiliation` (optional)

3. **Run the tracker**:
   ```bash
   python repoHistory.py
   ```

### Output

**CSV File**: `results/repo_history.csv`
```csv
repo_owner,repo_name,repo_url,snapshot_date,total_stars,total_forks,total_contributors,total_prs,total_commits,total_issues,deepseek_affiliation,chatgpt_affiliation
torvalds,linux,https://github.com/torvalds/linux,2025-10-30,150000,45000,25000,5000,1200000,8000,none,none
```

**Report File**: `results/repo_history_report_YYYYMMDD_HHMMSS.txt`
- Summary statistics
- Repository metrics (totals and averages)
- Top 5 Most Starred
- Top 5 Most Active (commits)
- Top 5 Most Collaborative (contributors)
- Top 5 by Pull Requests
- Top 5 by Issues
- Top 5 Most Forked

### Configuration

```python
# repoHistory.py configuration (lines 29-51)

REQUEST_DELAY = 0.1              # 100ms delay between requests
MAX_WORKERS = 12                 # Concurrent workers
FILTER_BY_AFFILIATION = False    # True: affiliated only, False: all repos
SCRAPING_FREQUENCY = "W"         # "D" (daily) or "W" (weekly)

INPUT_CSV = "datasets/affiliated_deepseek_1000_200000.csv"
OUTPUT_CSV = "results/repo_history.csv"
```

### Discord Integration

Add to `.env`:
```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_URL
```

Notifications include: duration, repos processed, total stars/forks/commits, top repos.

---

## 🏴 Political Emoji Commit Scraper

Extract GitHub commits that add political emojis to README files.

### Features

✨ **Multi-threaded Processing**: Up to 20 concurrent workers for fast scraping  
🔄 **Token Rotation**: Automatic rotation across multiple GitHub tokens  
⚡ **Rate Limit Handling**: Smart handling with automatic 1-hour sleep when all tokens exhausted  
📊 **Progress Tracking**: Real-time logging and Discord notifications  
🎯 **Emoji Detection**: Supports both Unicode emojis and shortcodes  
📝 **Pull Request Support**: Detects commits from both direct pushes and pull requests  

## Political Emojis Tracked

- **Israel/Palestine**: 🇮🇱 💙 🤍 ✡️ 🇵🇸 ❤️ 💚 🖤 🍉
- **Ukraine/Russia**: 🇺🇦 💙 💛 🌻 🇷🇺
- **Social Justice**: ✊ ✊🏾 ✊🏿 🤎
- **Climate**: ♻️ 🌱 🌍 🌎 🌏 🔥
- **Gender/Rights**: ♀️ 🚺 💔 😔 🍚 🐰
- **LGBTQ+**: 🌈 🏳️‍🌈 🏳️‍⚧️

---

## 🛠️ Common Setup (Both Tools)

Both tools share the same setup requirements.

1. **Clone the repository**
   ```bash
   git clone <repo-url>
   cd Commit_extractor
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add your tokens:
   ```env
   # GitHub Personal Access Tokens (minimum 1, maximum 20)
   GITHUB_TOKEN_1=github_pat_xxxxxxxxxxxxx
   GITHUB_TOKEN_2=github_pat_xxxxxxxxxxxxx
   # ... add more tokens for faster scraping
   
   # Optional: Discord webhook for notifications
   discord_webhook_url=https://discord.com/api/webhooks/xxxxx/xxxxx
   ```

---

## 📊 Usage

### Repository History Tracker

Track repository metrics over time:

```bash
# Run with default settings (weekly snapshots, all repos)
python repoHistory.py
```

**Customize by editing `repoHistory.py`:**
```python
SCRAPING_FREQUENCY = "D"         # Daily snapshots
FILTER_BY_AFFILIATION = True     # Only affiliated repos
MAX_WORKERS = 8                  # Reduce concurrent workers
```

**Input CSV Requirements:**
- `repo_owner`, `repo_name`, `repo_url` (required)
- `deepseek_affiliation`, `chatgpt_affiliation` (optional, for filtering)

**Output:**
- `results/repo_history.csv` - Time-series data for trend analysis
- `results/repo_history_report_*.txt` - Comprehensive report with rankings
- `logs/repo_history_*.log` - Execution logs

### Political Emoji Scraper

Find commits that add political emojis to README files:

```bash
python commitscrapper.py
```

**Input CSV Requirements:**
- `repo_owner`, `repo_name`, `repo_url` (required)
- `affiliation_deepseek`, `affiliation_openai` (for filtering)

**The scraper will:**
1. Load repositories from CSV (filtered by affiliation if enabled)
2. Search README files for commits adding political emojis
3. Extract commit details, author info, and diff snippets
4. Save results to `results/political_emoji_commits.csv`
5. Log everything to `logs/scraper_YYYYMMDD_HHMMSS.log`

**Output:**
- `results/political_emoji_commits.csv` - Commit details with emoji info
- `results/report.txt` - Comprehensive scraping report
- `logs/scraper_*.log` - Execution logs

---

## 📋 Output Formats

### Repository History CSV

`results/repo_history.csv` - Time-series repository metrics

**Columns:**
- `repo_owner`, `repo_name`, `repo_url`: Repository identification
- `snapshot_date`: Date snapshot was taken (YYYY-MM-DD)
- `total_stars`: Total stars at snapshot time
- `total_forks`: Total forks at snapshot time
- `total_contributors`: Total unique contributors
- `total_prs`: Total pull requests (all states)
- `total_commits`: Total commits in repository
- `total_issues`: Total issues (excluding PRs)
- `deepseek_affiliation`, `chatgpt_affiliation`: Affiliation data

### Political Emoji Commits CSV

`results/political_emoji_commits.csv` - Commits adding political emojis

**Columns:**

- `repo_owner`, `repo_name`, `repo_url`: Repository information
- `commit_sha`: Commit hash
- `commit_datetime`: When the commit was made
- `author_name`, `author_email`: Commit author
- `commit_message`: Commit message (first line)
- `emojis_detected`: List of emojis found (pipe-separated)
- `readme_additions_snippet`: Snippet of added lines containing emojis
- `deepseek_affiliation`, `chatgpt_affiliation`: Original affiliation data
- `is_pull_request`: Whether commit came from a PR
- `pr_number`: Pull request number (if applicable)
- `readme_file_path`: Which README file was modified

---

## ⚙️ Configuration Details

### Repository History Tracker

Edit `repoHistory.py` configuration (lines 29-51):

```python
REQUEST_DELAY = 0.1              # Delay between API requests
MAX_WORKERS = 12                 # Concurrent worker threads
FILTER_BY_AFFILIATION = False    # Filter by affiliation status
SCRAPING_FREQUENCY = "W"         # "D" (daily) or "W" (weekly)

INPUT_CSV = "datasets/affiliated_deepseek_1000_200000.csv"
OUTPUT_CSV = "results/repo_history.csv"
```

**SCRAPING_FREQUENCY Options:**
- `"D"` - Daily snapshots (track last 24 hours)
- `"W"` - Weekly snapshots (track last 7 days)

**FILTER_BY_AFFILIATION:**
- `True` - Only process repos with DeepSeek or ChatGPT affiliation
- `False` - Process all repositories in the input CSV

### Political Emoji Scraper

Edit `commitscrapper.py` to adjust:

```python
REQUEST_DELAY = 0.05          # Delay between requests (50ms)
RATE_LIMIT_SLEEP = 3600       # Sleep time when all tokens exhausted (1 hour)
MAX_WORKERS = 20              # Maximum concurrent workers

# Filter Configuration
FILTER_BY_AFFILIATION = True  # True: only repos with affiliation, False: all repos
```

### Filter Configuration

**FILTER_BY_AFFILIATION** - Controls which repositories to process:

- **`True` (Default)**: Processes only repositories where either DeepSeek or ChatGPT affiliation is NOT "none" (~118 repos)
- **`False`**: Processes ALL repositories in the CSV file regardless of affiliation (~150+ repos)

**Usage**:
```python
# Option 1: Only affiliated repos (faster, focused dataset)
FILTER_BY_AFFILIATION = True

# Option 2: All repos (comprehensive analysis)
FILTER_BY_AFFILIATION = False
```

The current filter mode will be shown in Discord notifications and console logs when scraping starts.

See [Advanced Configuration](docs/ADVANCED_CONFIG.md) for more tuning options.

---

## 🔍 How the Tools Work

### Repository History Tracker

1. **Snapshot Collection**: Takes periodic snapshots of repository metrics
2. **GitHub API**: Uses REST API to fetch repository information
3. **Metrics Aggregation**: Collects stars, forks, contributors, PRs, commits, issues
4. **Time-Series Data**: Appends to CSV for historical tracking
5. **Trend Analysis**: Compare snapshots to calculate growth over time

**API Endpoints Used:**
- `GET /repos/{owner}/{repo}` - Stars, forks, basic info
- `GET /repos/{owner}/{repo}/contributors` - Contributors count
- `GET /repos/{owner}/{repo}/pulls?state=all` - Total PRs
- `GET /repos/{owner}/{repo}/commits` - Total commits
- `GET /repos/{owner}/{repo}/issues?state=all` - Total issues

### Political Emoji Scraper

1. **Token Management**: Rotates through available GitHub tokens to maximize API rate limits
2. **GraphQL Queries**: Efficiently fetches commit history for README files
3. **REST API**: Gets detailed diff information for each commit
4. **Emoji Detection**: Searches both Unicode characters and shortcodes (e.g., `:watermelon:`)
5. **Multi-threading**: Processes multiple repositories concurrently
6. **Rate Limit Handling**: Automatically pauses when all tokens are exhausted

---

## 📊 Performance & Monitoring

### Repository History Tracker

**Performance:**
- ~5 API calls per repository
- Can track ~20,000 repos/hour with 20 tokens
- Typical run: 100 repos in 1-2 minutes

**Monitoring:**
- Console logs with real-time progress
- Detailed log files in `logs/` directory
- Optional Discord notifications for completion
- Comprehensive reports with Top 5 rankings

### Political Emoji Scraper

**Performance:**
- GraphQL for efficient commit discovery
- REST API for detailed diff information
- 50ms delay between requests
- Token rotation distributes load

**Monitoring:**
- Console logs with real-time updates
- Detailed log files in `logs/` directory
- Discord notifications (optional):
  - Scraping start/completion
  - Progress updates (every 50 repos)
  - Rate limit warnings

---

## 🔧 Troubleshooting

### Repository History Tracker

**No Discord notifications:**
- Verify `DISCORD_WEBHOOK_URL` in `.env`
- Check webhook is active in Discord
- Review logs for connection errors

**Incomplete metrics:**
- Some repos may have disabled features
- Private repos need proper permissions
- Check logs for specific API errors

**Rate limiting:**
- Increase `REQUEST_DELAY` to 0.2 or higher
- Reduce `MAX_WORKERS` to 8 or less
- Verify all 20 tokens are valid

### Political Emoji Scraper

**No results found:**
- Check if repositories have README files
- Verify emojis were actually added (not removed)
- Review log files for errors

**Rate limit errors:**
- Add more GitHub tokens to `.env`
- Increase `REQUEST_DELAY`
- Wait for rate limits to reset

**Connection errors:**
- Check internet connection
- Verify GitHub tokens are valid
- Ensure repositories are accessible

---

## 📚 Documentation

Detailed documentation available in the `docs/` folder:

- **[Quick Start Guide](docs/QUICKSTART.md)** - Step-by-step instructions
- **[Repository History Features](docs/REPO_HISTORY_FEATURES.md)** - Comprehensive feature docs
- **[Implementation Summary](docs/IMPLEMENTATION_SUMMARY.md)** - Technical architecture
- **[Advanced Configuration](docs/ADVANCED_CONFIG.md)** - Performance tuning
- **[Token Borrowing](docs/TOKEN_BORROWING.md)** - Dynamic token management
- **[Project Complete](docs/PROJECT_COMPLETE.md)** - Full project summary

---

## 📄 License

MIT License

## 🤝 Contributing

Contributions welcome! Please open an issue or submit a pull request.

## 📊 Performance & Monitoring

### Repository History Tracker

**Performance:**
- ~5 API calls per repository
- Can track ~20,000 repos/hour with 20 tokens
- Typical run: 100 repos in 1-2 minutes

**Monitoring:**
- Console logs with real-time progress
- Detailed log files in `logs/` directory
- Optional Discord notifications for completion
- Comprehensive reports with Top 5 rankings

### Political Emoji Scraper

**Performance:**

- **Console Logs**: Real-time progress updates
- **Log Files**: Detailed logs in `logs/` directory
- **Discord Notifications**: Optional webhook notifications for:
  - Scraping start
  - Progress updates (every 50 repos)
  - Rate limit warnings
  - Completion summary

## Troubleshooting

**No results found?**
- Check if repositories have README files
- Verify emojis were actually added (not removed)
- Check log files for errors

**Rate limit errors?**
- Add more GitHub tokens to `.env`
- Increase `REQUEST_DELAY`
- Wait for rate limits to reset

**Connection errors?**
- Check internet connection
- Verify GitHub tokens are valid
- Check if repositories are accessible

## Documentation

For detailed information, see the `docs/` folder:

- **[Quick Start Guide](docs/QUICKSTART.md)** - Step-by-step usage instructions
- **[Implementation Summary](docs/IMPLEMENTATION_SUMMARY.md)** - Technical architecture and design
- **[Advanced Configuration](docs/ADVANCED_CONFIG.md)** - Performance tuning and customization
- **[Token Borrowing](docs/TOKEN_BORROWING.md)** - Dynamic token management feature
- **[Project Complete](docs/PROJECT_COMPLETE.md)** - Comprehensive project summary

## License

MIT License

## Contributing

Contributions welcome! Please open an issue or submit a pull request.
