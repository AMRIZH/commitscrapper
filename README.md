# GitHub Political Emoji Commit Scraper

A multi-threaded Python scraper that extracts GitHub commits containing political emojis from README files. Supports token rotation, rate limit handling, and Discord notifications.

## Features

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

## Setup

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

4. **Prepare input CSV**
   
   Ensure `github_affiliation_combined.csv` has these columns:
   - `repo_owner`: GitHub repository owner
   - `repo_name`: Repository name
   - `repo_url`: Full repository URL
   - `affiliation_deepseek`: Affiliation status (not "none" to be processed)
   - `affiliation_openai`: Affiliation status (not "none" to be processed)

## Usage

Run the scraper:

```bash
python commitscrapper.py
```

The scraper will:
1. Load repositories from CSV where either `affiliation_deepseek` or `affiliation_openai` is NOT "none"
2. Search README files for commits adding political emojis
3. Extract commit details, author info, and diff snippets
4. Save results to `results/political_emoji_commits.csv`
5. Log everything to `logs/scraper_YYYYMMDD_HHMMSS.log`

## Output

Results are saved in `results/political_emoji_commits.csv` with columns:

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

## Configuration

Edit `commitscrapper.py` to adjust:

```python
REQUEST_DELAY = 0.05          # Delay between requests (50ms)
RATE_LIMIT_SLEEP = 3600       # Sleep time when all tokens exhausted (1 hour)
MAX_WORKERS = 20              # Maximum concurrent workers
```

## How It Works

1. **Token Management**: Rotates through available GitHub tokens to maximize API rate limits
2. **GraphQL Queries**: Efficiently fetches commit history for README files
3. **REST API**: Gets detailed diff information for each commit
4. **Emoji Detection**: Searches both Unicode characters and shortcodes (e.g., `:watermelon:`)
5. **Multi-threading**: Processes multiple repositories concurrently
6. **Rate Limit Handling**: Automatically pauses when all tokens are exhausted

## API Strategy

- **GraphQL API**: Used for efficient commit discovery (fewer API calls)
- **REST API**: Used for detailed diff/patch information
- **Token Rotation**: Distributes load across multiple tokens
- **Smart Delays**: 50ms between requests to avoid triggering abuse detection

## Monitoring

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
