# Advanced Configuration Guide

## Tuning Performance

### Adjusting Worker Count

**Default**: 20 workers (matches token count)

```python
MAX_WORKERS = 20
```

**Recommendations**:
- Set to number of tokens available
- Lower if experiencing connection issues: `MAX_WORKERS = 10`
- Higher only if you have more tokens: `MAX_WORKERS = 30`

### Request Delay

**Default**: 50ms (0.05 seconds)

```python
REQUEST_DELAY = 0.05
```

**Tuning guide**:
- **Faster** (risky): `0.01` - May trigger abuse detection
- **Standard**: `0.05` - Recommended balance
- **Conservative**: `0.1` - Safer for accounts with previous issues
- **Very safe**: `0.2` - Use if getting blocked

### Rate Limit Sleep

**Default**: 1 hour (3600 seconds)

```python
RATE_LIMIT_SLEEP = 3600
```

**Options**:
- **Shorter**: `1800` (30 min) - If tokens reset faster
- **Longer**: `7200` (2 hours) - More conservative
- **Minimal**: `900` (15 min) - Risky, may hit secondary limits

## Filtering Repositories

### Affiliation Filter Toggle

**Configuration Variable** (line ~95 in `commitscrapper.py`):

```python
# Set to True to check only repos with affiliation (deepseek or chatgpt)
# Set to False to check ALL repos regardless of affiliation
FILTER_BY_AFFILIATION = True  # Default: only check repos with affiliation
```

**Behavior**:
- `True` (Default): Processes only repositories where **either** DeepSeek or ChatGPT affiliation is not "none" (~118 repos)
- `False`: Processes **all** repositories in the CSV file (~150+ repos)

**When to use each setting**:
- **FILTER_BY_AFFILIATION = True**: 
  - Focus on repos with known AI tool affiliations
  - Faster execution (fewer repos)
  - Original project scope
  
- **FILTER_BY_AFFILIATION = False**: 
  - Comprehensive analysis across all repos
  - Discover emoji usage in non-affiliated projects
  - Broader dataset for research

**Discord notification** will show current filter mode:
```
🔍 Filter: Affiliation filter enabled
```
or
```
🔍 Filter: All repos mode
```

### Custom Filtering Logic

If you need more specific filtering beyond the toggle, modify the `load_repositories()` function:

**Both affiliations required**:
```python
if deepseek_aff != 'none' and chatgpt_aff != 'none':
    repos.append(row)
```

**Only DeepSeek**:
```python
if deepseek_aff != 'none':
    repos.append(row)
```

**Only ChatGPT/OpenAI**:
```python
if chatgpt_aff != 'none':
    repos.append(row)
```

**Specific affiliation values**:
```python
if deepseek_aff in ['supporter', 'contributor']:
    repos.append(row)
```

## Adding More Emojis

### Adding New Emoji

1. Add unicode character to `POLITICAL_EMOJIS`:
```python
POLITICAL_EMOJIS = [
    # ... existing emojis
    "🕊️",  # Peace dove
]
```

2. Add shortcodes to `EMOJI_SHORTCODES`:
```python
EMOJI_SHORTCODES = {
    # ... existing mappings
    "🕊️": [":dove:", ":peace_dove:"],
}
```

### Emoji Categories

**To focus on specific issues**:

```python
# Only Israel/Palestine
POLITICAL_EMOJIS = [
    "🇮🇱","💙","🤍","✡️","🇵🇸","❤️","💚","🖤","🍉"
]

# Only Ukraine/Russia
POLITICAL_EMOJIS = [
    "🇺🇦","💙","💛","🌻","🇷🇺"
]

# Only LGBTQ+
POLITICAL_EMOJIS = [
    "🌈","🏳️‍🌈","🏳️‍⚧️"
]
```

## README File Patterns

### Current Patterns

```python
README_PATTERNS = [
    "README.md", "readme.md", "README.MD", 
    "README.rst", "README.txt", "README",
    "Readme.md", "ReadMe.md"
]
```

### Adding More Patterns

```python
README_PATTERNS = [
    # ... existing patterns
    "README.markdown",
    "README.mdown",
    "readme.rst",
    "docs/README.md",    # Documentation folder
    "profile/README.md", # GitHub profile README
]
```

**Note**: GitHub's GraphQL `path` parameter supports exact matches only, not wildcards.

## Commit History Depth

### Current Limit

```python
# In GraphQL query
history(first: 100, path: $path)
```

Gets first 100 commits for each README file.

### Increasing Depth

**Option 1**: Increase limit (up to 100 per query)
```graphql
history(first: 100, path: $path)  # Already at max
```

**Option 2**: Implement pagination
```python
def search_commits_paginated(owner, repo, path, max_commits=500):
    all_commits = []
    cursor = None
    
    while len(all_commits) < max_commits:
        query = """
        query($owner: String!, $repo: String!, $path: String!, $cursor: String) {
          repository(owner: $owner, name: $repo) {
            defaultBranchRef {
              target {
                ... on Commit {
                  history(first: 100, path: $path, after: $cursor) {
                    pageInfo {
                      hasNextPage
                      endCursor
                    }
                    edges { node { ... } }
                  }
                }
              }
            }
          }
        }
        """
        # Fetch and collect commits
        # Update cursor for next page
        # Break if no more pages
```

## Output Customization

### Adding Fields

**To add new fields to CSV**:

1. Update `CommitResult` dataclass:
```python
@dataclass
class CommitResult:
    # ... existing fields
    repo_stars: int
    repo_created_at: str
    commit_files_changed: int
```

2. Update CSV writer:
```python
writer = csv.DictWriter(f, fieldnames=[
    # ... existing fields
    'repo_stars', 'repo_created_at', 'commit_files_changed'
])
```

### Filtering Results

**Only save commits from pull requests**:
```python
if emojis and is_pr:
    results.append(result)
```

**Only save commits with multiple emojis**:
```python
if len(emojis) >= 2:
    results.append(result)
```

**Only save commits with specific emojis**:
```python
target_emojis = {"🇺🇦", "🇵🇸"}
if emojis & target_emojis:  # Set intersection
    results.append(result)
```

## Logging Configuration

### Log Levels

**More verbose** (DEBUG):
```python
console_handler.setLevel(logging.DEBUG)  # Show everything
```

**Less verbose** (WARNING):
```python
console_handler.setLevel(logging.WARNING)  # Only warnings/errors
```

**Silent console, file only**:
```python
# Remove console handler
logger.addHandler(file_handler)
# Don't add console_handler
```

### Log Formatting

**Add more details**:
```python
detailed_formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - [%(threadName)s] - %(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
```

**Simpler format**:
```python
simple_formatter = logging.Formatter('%(asctime)s - %(message)s')
```

## Discord Notifications

### Customizing Notification Frequency

**Current**: Every 50 repos

```python
if processed_count % 50 == 0:
    notifier.send(...)
```

**More frequent** (every 10):
```python
if processed_count % 10 == 0:
    notifier.send(...)
```

**Less frequent** (every 100):
```python
if processed_count % 100 == 0:
    notifier.send(...)
```

### Custom Notification Messages

```python
def send_custom_alert(self, emoji_count, repo_name):
    self.send(
        f"🎯 Found {emoji_count} emojis in {repo_name}!",
        title="New Discovery"
    )
```

### Disable Notifications

```python
# In .env file, remove or comment out:
# discord_webhook_url=
```

## GraphQL vs REST Balance

### Current Strategy

- **GraphQL**: Get commit list (1 request per repo)
- **REST**: Get each commit's diff (N requests per repo)

### Alternative: More GraphQL

**Pros**: Fewer API calls
**Cons**: Can't get file diffs via GraphQL

```graphql
# Can get more commit metadata in one call
{
  additions
  deletions
  changedFiles
  committedDate
  author { ... }
  associatedPullRequests { ... }
}
```

### Alternative: All REST

**Pros**: Simpler code
**Cons**: More API calls

```python
# List commits
GET /repos/{owner}/{repo}/commits?path=README.md

# For each commit
GET /repos/{owner}/{repo}/commits/{sha}
```

## Error Handling

### Retry Strategy

**Current**: 3 retries with exponential backoff

```python
max_retries = 3
time.sleep(1 * (attempt + 1))
```

**More aggressive**:
```python
max_retries = 5
time.sleep(0.5 * (attempt + 1))
```

**More conservative**:
```python
max_retries = 2
time.sleep(2 * (attempt + 1))
```

### Timeout Configuration

**Current**: 30 seconds

```python
response = self.session.request(..., timeout=30)
```

**Shorter** (for faster failures):
```python
response = self.session.request(..., timeout=10)
```

**Longer** (for slow connections):
```python
response = self.session.request(..., timeout=60)
```

## Token Management

### Token Priority

**Give priority to certain tokens**:

```python
def __init__(self):
    self.tokens = self._load_tokens()
    # Put high-quota tokens first
    self.tokens.sort(key=lambda t: self._get_token_priority(t), reverse=True)
```

### Token Statistics Export

**Save token usage stats**:

```python
def save_token_stats(self):
    stats = self.get_stats()
    with open('logs/token_stats.json', 'w') as f:
        json.dump(stats, f, indent=2, default=str)
```

## Memory Optimization

### For Large-Scale Scraping

**Stream results to disk**:

```python
# Instead of collecting all results
all_results = []  # Don't do this for 10,000+ commits

# Write incrementally
with open(OUTPUT_CSV, 'a', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=[...])
    for result in results:
        writer.writerow(asdict(result))
```

### Batch Processing

**Process CSV in batches**:

```python
def load_repositories_batched(batch_size=100):
    for i in range(0, len(all_repos), batch_size):
        yield all_repos[i:i+batch_size]

# Process each batch
for batch in load_repositories_batched():
    process_batch(batch)
    save_intermediate_results()
```

## Performance Profiling

### Time Tracking

```python
import time

start = time.time()
# ... operation ...
elapsed = time.time() - start

logger.info(f"Operation took {elapsed:.2f} seconds")
```

### Request Counting

```python
class GitHubClient:
    def __init__(self, token_manager):
        # ... existing code ...
        self.request_count = 0
        self.graphql_count = 0
        self.rest_count = 0
    
    def _make_request(self, ...):
        self.request_count += 1
        # ... existing code ...
```

## Environment-Specific Settings

### Development

```python
if os.getenv('ENVIRONMENT') == 'development':
    MAX_WORKERS = 5
    REQUEST_DELAY = 0.1
    # Test with fewer repos
```

### Production

```python
if os.getenv('ENVIRONMENT') == 'production':
    MAX_WORKERS = 20
    REQUEST_DELAY = 0.05
    # Full throttle
```

## Resume Capability (Future Enhancement)

**Save progress**:

```python
def save_checkpoint(processed_repos):
    with open('checkpoint.json', 'w') as f:
        json.dump({
            'processed': processed_repos,
            'timestamp': datetime.now().isoformat()
        }, f)

def load_checkpoint():
    if os.path.exists('checkpoint.json'):
        with open('checkpoint.json') as f:
            return json.load(f)
    return {'processed': []}
```

**Skip processed**:

```python
checkpoint = load_checkpoint()
processed_urls = set(checkpoint['processed'])

for repo in repositories:
    if repo['repo_url'] in processed_urls:
        continue
    # Process repo...
```

---

## Quick Configuration Presets

### Conservative (Safest)
```python
MAX_WORKERS = 10
REQUEST_DELAY = 0.2
RATE_LIMIT_SLEEP = 7200
```

### Balanced (Recommended)
```python
MAX_WORKERS = 20
REQUEST_DELAY = 0.05
RATE_LIMIT_SLEEP = 3600
```

### Aggressive (Fastest)
```python
MAX_WORKERS = 30
REQUEST_DELAY = 0.01
RATE_LIMIT_SLEEP = 1800
```

---

For questions or issues, refer to:
- `README.md` - General usage
- `IMPLEMENTATION_SUMMARY.md` - Technical details
- `QUICKSTART.md` - Getting started guide
