#!/usr/bin/env python3
"""
GitHub Political Emoji Commit Scraper
Scrapes GitHub commits that add political emojis to README files
Supports multi-threading with token rotation and rate limit handling
"""

import os
import csv
import json
import time
import re
import logging
from datetime import datetime, timedelta

# Increase CSV field size limit for large README content
csv.field_size_limit(1000000)
from typing import List, Dict, Optional, Set, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from dataclasses import dataclass, asdict
import requests
from dotenv import load_dotenv
from pathlib import Path
import traceback

# Load environment variables
load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

POLITICAL_EMOJIS = [
    "🇮🇱","💙","🤍","✡️","🇵🇸","❤️","💚","🖤","🍉",
    "🇺🇦","💙","💛","🌻","🇷🇺",
    "✊","✊🏾","✊🏿","🤎",
    "♻️","🌱","🌍","🌎","🌏","🔥",
    "♀️","🚺","💔","😔","🍚","🐰",
    "🌈","🏳️‍🌈","🏳️‍⚧️",
]

EMOJI_SHORTCODES = {
    "🇮🇱": [":flag_il:", ":israel:"],
    "💙": [":blue_heart:"],
    "🤍": [":white_heart:"],
    "✡️": [":star_of_david:"],
    "🇵🇸": [":flag_ps:", ":palestinian_territories:", ":palestine:"],
    "❤️": [":heart:", ":red_heart:"],
    "💚": [":green_heart:"],
    "🖤": [":black_heart:"],
    "🍉": [":watermelon:"],
    "🇺🇦": [":flag_ua:", ":ukraine:"],
    "💛": [":yellow_heart:"],
    "🌻": [":sunflower:"],
    "🇷🇺": [":flag_ru:", ":ru:", ":russia:"],
    "✊": [":fist:", ":raised_fist:"],
    "✊🏾": [":fist_tone4:", ":raised_fist_tone4:"],
    "✊🏿": [":fist_tone5:", ":raised_fist_tone5:"],
    "🤎": [":brown_heart:"],
    "♻️": [":recycle:"],
    "🌱": [":seedling:"],
    "🌍": [":earth_africa:"],
    "🌎": [":earth_americas:"],
    "🌏": [":earth_asia:"],
    "🔥": [":fire:"],
    "♀️": [":female_sign:"],
    "🚺": [":womens:"],
    "💔": [":broken_heart:"],
    "😔": [":pensive:"],
    "🍚": [":rice:"],
    "🐰": [":rabbit:"],
    "🌈": [":rainbow:"],
    "🏳️‍🌈": [":rainbow_flag:", ":pride_flag:"],
    "🏳️‍⚧️": [":transgender_flag:"],
}

# File paths
INPUT_CSV = "github_affiliation_combined_cleaned.csv"
OUTPUT_CSV = "results/political_emoji_commits.csv"
LOG_DIR = "logs"
LOG_FILE = f"{LOG_DIR}/scraper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# API Configuration
REQUEST_DELAY = 0.05  # 50ms delay between requests
RATE_LIMIT_SLEEP = 3600  # 1 hour sleep when all tokens exhausted
MAX_WORKERS = 20  # Maximum concurrent workers

# Filter Configuration
# Set to True to check only repos with affiliation (deepseek or chatgpt)
# Set to False to check ALL repos regardless of affiliation
FILTER_BY_AFFILIATION = False  # Default: only check repos with affiliation

# README file patterns to check
README_PATTERNS = [
    "README.md", "readme.md", "README.MD", 
    "README.rst", "README.txt", "README",
    "Readme.md", "ReadMe.md"
]

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class CommitResult:
    """Result of a commit analysis"""
    repo_owner: str
    repo_name: str
    repo_url: str
    commit_sha: str
    commit_datetime: str
    author_name: str
    author_email: str
    commit_message: str
    emojis_detected: str
    readme_additions_snippet: str
    deepseek_affiliation: str
    chatgpt_affiliation: str
    is_pull_request: bool
    pr_number: Optional[int]
    readme_file_path: str

# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging():
    """Setup logging configuration"""
    os.makedirs(LOG_DIR, exist_ok=True)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(detailed_formatter)
    
    # Root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

# ============================================================================
# TOKEN MANAGER
# ============================================================================

class TokenManager:
    """Manages GitHub token rotation and rate limiting with dynamic token borrowing"""
    
    def __init__(self):
        self.tokens = self._load_tokens()
        self.token_stats = {token: {"remaining": 5000, "reset_time": None, "requests": 0} 
                           for token in self.tokens}
        self.lock = Lock()
        self.current_index = 0
        
        logger.info(f"✓ Loaded {len(self.tokens)} GitHub tokens")
    
    def _load_tokens(self) -> List[str]:
        """Load all GitHub tokens from environment"""
        tokens = []
        for i in range(1, 21):  # Try loading up to 20 tokens
            token = os.getenv(f"GITHUB_TOKEN_{i}")
            if token and token.strip():
                tokens.append(token.strip())
        
        if not tokens:
            raise ValueError("No GitHub tokens found in .env file!")
        
        return tokens
    
    def _is_token_available(self, token: str) -> bool:
        """Check if a token has available rate limit"""
        stats = self.token_stats[token]
        
        # If rate limit is reset or never set, token is available
        if stats["reset_time"] is None or datetime.now() >= stats["reset_time"]:
            return stats["remaining"] > 10
        
        # If reset time hasn't passed, check remaining
        return stats["remaining"] > 10
    
    def get_token(self) -> str:
        """Get next available token with rate limit check and dynamic borrowing"""
        with self.lock:
            # First pass: Try tokens starting from current index (normal rotation)
            for _ in range(len(self.tokens)):
                token = self.tokens[self.current_index]
                
                if self._is_token_available(token):
                    # This token is good to use
                    self.token_stats[token]["requests"] += 1
                    self.current_index = (self.current_index + 1) % len(self.tokens)
                    logger.debug(f"Using token #{self.tokens.index(token) + 1} (remaining: {self.token_stats[token]['remaining']})")
                    return token
                
                # Try next token
                self.current_index = (self.current_index + 1) % len(self.tokens)
            
            # Second pass: Look for ANY available token (borrowing from pool)
            logger.debug("Primary token exhausted, searching for available token to borrow...")
            for idx, token in enumerate(self.tokens):
                if self._is_token_available(token):
                    self.token_stats[token]["requests"] += 1
                    logger.info(f"✓ Borrowed token #{idx + 1} (remaining: {self.token_stats[token]['remaining']})")
                    return token
            
            # All tokens exhausted - return first one anyway (will trigger rate limit handling)
            logger.warning("⚠️ All tokens exhausted, returning token #1 (may trigger rate limit)")
            token = self.tokens[0]
            self.token_stats[token]["requests"] += 1
            return token
    
    def update_rate_limit(self, token: str, remaining: int, reset_timestamp: int):
        """Update rate limit info for a token"""
        with self.lock:
            self.token_stats[token]["remaining"] = remaining
            self.token_stats[token]["reset_time"] = datetime.fromtimestamp(reset_timestamp)
    
    def get_stats(self) -> Dict:
        """Get current token statistics"""
        with self.lock:
            total_requests = sum(stats["requests"] for stats in self.token_stats.values())
            available_tokens = sum(
                1 for token in self.tokens
                if self._is_token_available(token)
            )
            exhausted_tokens = sum(
                1 for token in self.tokens
                if not self._is_token_available(token)
            )
            
            return {
                "total_tokens": len(self.tokens),
                "available_tokens": available_tokens,
                "exhausted_tokens": exhausted_tokens,
                "total_requests": total_requests,
                "tokens": [
                    {
                        "token_id": f"Token #{idx + 1}",
                        "remaining": stats["remaining"],
                        "reset_time": stats["reset_time"].strftime("%H:%M:%S") if stats["reset_time"] else "N/A",
                        "requests": stats["requests"],
                        "available": self._is_token_available(token)
                    }
                    for idx, (token, stats) in enumerate(self.token_stats.items())
                ]
            }
    
    def all_tokens_exhausted(self) -> bool:
        """Check if all tokens are exhausted"""
        with self.lock:
            for stats in self.token_stats.values():
                if stats["remaining"] > 10:
                    if stats["reset_time"] is None or datetime.now() >= stats["reset_time"]:
                        return False
            return True

# ============================================================================
# DISCORD NOTIFICATIONS
# ============================================================================

class DiscordNotifier:
    """Send notifications to Discord webhook"""
    
    def __init__(self):
        self.webhook_url = os.getenv("discord_webhook_url")
        self.enabled = bool(self.webhook_url)
        
        if self.enabled:
            logger.info("✓ Discord notifications enabled")
        else:
            logger.warning("⚠ Discord webhook not configured - notifications disabled")
    
    def send(self, message: str, title: str = "GitHub Scraper Update"):
        """Send message to Discord"""
        if not self.enabled:
            return
        
        try:
            payload = {
                "embeds": [{
                    "title": title,
                    "description": message,
                    "color": 3447003,  # Blue color
                    "timestamp": datetime.utcnow().isoformat(),
                    "footer": {"text": "GitHub Political Emoji Scraper"}
                }]
            }
            
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            logger.debug("Discord notification sent successfully")
            
        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")

# ============================================================================
# GITHUB API CLIENT
# ============================================================================

class GitHubClient:
    """GitHub API client with GraphQL and REST support"""
    
    def __init__(self, token_manager: TokenManager):
        self.token_manager = token_manager
        self.graphql_url = "https://api.github.com/graphql"
        self.rest_base = "https://api.github.com"
        self.session = requests.Session()
    
    def _make_request(self, method: str, url: str, **kwargs) -> Optional[requests.Response]:
        """Make HTTP request with token rotation and rate limit handling"""
        max_retries = 3
        
        for attempt in range(max_retries):
            token = self.token_manager.get_token()
            headers = kwargs.get('headers', {})
            headers.update({
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "GitHub-Political-Emoji-Scraper"
            })
            kwargs['headers'] = headers
            
            try:
                time.sleep(REQUEST_DELAY)  # Rate limiting delay
                
                response = self.session.request(method, url, timeout=30, **kwargs)
                
                # Update rate limit info
                if 'X-RateLimit-Remaining' in response.headers:
                    remaining = int(response.headers['X-RateLimit-Remaining'])
                    reset = int(response.headers['X-RateLimit-Reset'])
                    self.token_manager.update_rate_limit(token, remaining, reset)
                
                # Handle rate limiting
                if response.status_code == 403 and 'rate limit' in response.text.lower():
                    logger.warning(f"Rate limit hit for token, retrying with next token...")
                    continue
                
                # Handle other errors
                if response.status_code == 404:
                    logger.debug(f"Resource not found: {url}")
                    return None
                
                response.raise_for_status()
                return response
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    return None
                time.sleep(1 * (attempt + 1))  # Exponential backoff
        
        return None
    
    def graphql_query(self, query: str, variables: Dict = None) -> Optional[Dict]:
        """Execute GraphQL query"""
        response = self._make_request(
            "POST",
            self.graphql_url,
            json={"query": query, "variables": variables or {}}
        )
        
        if response:
            data = response.json()
            if 'errors' in data:
                logger.error(f"GraphQL errors: {data['errors']}")
                return None
            return data.get('data')
        
        return None
    
    def get_commit_details(self, owner: str, repo: str, sha: str) -> Optional[Dict]:
        """Get detailed commit information via REST API"""
        url = f"{self.rest_base}/repos/{owner}/{repo}/commits/{sha}"
        response = self._make_request("GET", url)
        
        if response:
            return response.json()
        return None
    
    def get_pull_request(self, owner: str, repo: str, pr_number: int) -> Optional[Dict]:
        """Get pull request details"""
        url = f"{self.rest_base}/repos/{owner}/{repo}/pulls/{pr_number}"
        response = self._make_request("GET", url)
        
        if response:
            return response.json()
        return None
    
    def search_commits(self, owner: str, repo: str, path: str = "README.md") -> Optional[Dict]:
        """Search for commits that modified a specific file using GraphQL"""
        query = """
        query($owner: String!, $repo: String!, $path: String!) {
          repository(owner: $owner, name: $repo) {
            defaultBranchRef {
              target {
                ... on Commit {
                  history(first: 100, path: $path) {
                    pageInfo {
                      hasNextPage
                      endCursor
                    }
                    edges {
                      node {
                        oid
                        committedDate
                        message
                        author {
                          name
                          email
                        }
                        additions
                        deletions
                        associatedPullRequests(first: 1) {
                          nodes {
                            number
                            title
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """
        
        variables = {
            "owner": owner,
            "repo": repo,
            "path": path
        }
        
        return self.graphql_query(query, variables)

# ============================================================================
# EMOJI DETECTION
# ============================================================================

def detect_emojis_in_text(text: str) -> Set[str]:
    """Detect political emojis in text (both unicode and shortcodes)"""
    detected = set()
    
    if not text:
        return detected
    
    # Check for unicode emojis
    for emoji in POLITICAL_EMOJIS:
        if emoji in text:
            detected.add(emoji)
    
    # Check for shortcodes
    for emoji, shortcodes in EMOJI_SHORTCODES.items():
        for shortcode in shortcodes:
            if shortcode in text:
                detected.add(emoji)
    
    return detected

def extract_additions_from_diff(diff_text: str) -> str:
    """Extract added lines from git diff"""
    if not diff_text:
        return ""
    
    additions = []
    for line in diff_text.split('\n'):
        if line.startswith('+') and not line.startswith('+++'):
            additions.append(line[1:].strip())
    
    return '\n'.join(additions)

# ============================================================================
# COMMIT PROCESSING
# ============================================================================

def process_repository(
    repo_data: Dict,
    github_client: GitHubClient,
    notifier: DiscordNotifier
) -> List[CommitResult]:
    """Process a single repository and find emoji commits"""
    
    owner = repo_data['repo_owner']
    name = repo_data['repo_name']
    url = repo_data['repo_url']
    deepseek_aff = repo_data['affiliation_deepseek']
    chatgpt_aff = repo_data['affiliation_openai']
    
    logger.info(f"📂 Processing: {owner}/{name}")
    
    results = []
    
    try:
        # Try different README file variations
        readme_found = False
        for readme_path in README_PATTERNS:
            logger.debug(f"  Checking for {readme_path}...")
            
            # Get commit history for this README file
            commits_data = github_client.search_commits(owner, name, readme_path)
            
            if not commits_data:
                continue
            
            repo_data_gql = commits_data.get('repository')
            if not repo_data_gql:
                continue
            
            default_branch = repo_data_gql.get('defaultBranchRef')
            if not default_branch:
                continue
            
            target = default_branch.get('target')
            if not target:
                continue
            
            history = target.get('history')
            if not history:
                continue
            
            edges = history.get('edges', [])
            if not edges:
                continue
            
            readme_found = True
            logger.info(f"  ✓ Found {len(edges)} commits for {readme_path}")
            
            # Process each commit
            for edge in edges:
                node = edge['node']
                commit_sha = node['oid']
                
                # Get detailed commit info with diff
                commit_details = github_client.get_commit_details(owner, name, commit_sha)
                
                if not commit_details:
                    continue
                
                # Find README file in commit
                readme_file = None
                for file in commit_details.get('files', []):
                    if file['filename'].upper() == readme_path.upper():
                        readme_file = file
                        break
                
                if not readme_file:
                    continue
                
                # Get the patch (diff)
                patch = readme_file.get('patch', '')
                if not patch:
                    continue
                
                # Extract additions
                additions = extract_additions_from_diff(patch)
                
                # Detect emojis in additions
                emojis = detect_emojis_in_text(additions)
                
                if emojis:
                    # Get author info
                    author = node.get('author', {})
                    author_name = author.get('name', 'Unknown')
                    author_email = author.get('email', 'Unknown')
                    
                    # Check if it's from a PR
                    pr_nodes = node.get('associatedPullRequests', {}).get('nodes', [])
                    is_pr = len(pr_nodes) > 0
                    pr_number = pr_nodes[0]['number'] if is_pr else None
                    
                    # Create result
                    result = CommitResult(
                        repo_owner=owner,
                        repo_name=name,
                        repo_url=url,
                        commit_sha=commit_sha,
                        commit_datetime=node['committedDate'],
                        author_name=author_name,
                        author_email=author_email,
                        commit_message=node['message'].split('\n')[0][:200],  # First line, max 200 chars
                        emojis_detected='|'.join(sorted(emojis)),
                        readme_additions_snippet=additions[:500],  # First 500 chars
                        deepseek_affiliation=deepseek_aff,
                        chatgpt_affiliation=chatgpt_aff,
                        is_pull_request=is_pr,
                        pr_number=pr_number,
                        readme_file_path=readme_path
                    )
                    
                    results.append(result)
                    logger.info(f"  🎯 Found emoji commit: {commit_sha[:8]} - {', '.join(emojis)}")
            
            # If we found commits for this README, don't check other variations
            if results:
                break
        
        if not readme_found:
            logger.debug(f"  ⚠ No README file found in {owner}/{name}")
        elif not results:
            logger.debug(f"  ℹ No emoji commits found in {owner}/{name}")
        
        return results
        
    except Exception as e:
        logger.error(f"❌ Error processing {owner}/{name}: {e}")
        logger.debug(traceback.format_exc())
        return []

# ============================================================================
# MAIN PROCESSING
# ============================================================================

def load_repositories() -> List[Dict]:
    """Load repositories from CSV (filtered by affiliation or all repos based on config)"""
    logger.info(f"📖 Loading repositories from {INPUT_CSV}...")
    
    repos = []
    
    try:
        with open(INPUT_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                deepseek_aff = row.get('affiliation_deepseek', 'none').strip().lower()
                chatgpt_aff = row.get('affiliation_openai', 'none').strip().lower()
                
                # Filter based on configuration
                if FILTER_BY_AFFILIATION:
                    # Only process repos where either affiliation is NOT "none"
                    if deepseek_aff != 'none' or chatgpt_aff != 'none':
                        repos.append({
                            'repo_owner': row['repo_owner'],
                            'repo_name': row['repo_name'],
                            'repo_url': row['repo_url'],
                            'affiliation_deepseek': row.get('affiliation_deepseek', 'none'),
                            'affiliation_openai': row.get('affiliation_openai', 'none')
                        })
                else:
                    # Process ALL repos regardless of affiliation
                    repos.append({
                        'repo_owner': row['repo_owner'],
                        'repo_name': row['repo_name'],
                        'repo_url': row['repo_url'],
                        'affiliation_deepseek': row.get('affiliation_deepseek', 'none'),
                        'affiliation_openai': row.get('affiliation_openai', 'none')
                    })
        
        if FILTER_BY_AFFILIATION:
            logger.info(f"✓ Loaded {len(repos)} repositories with affiliation (filtered mode)")
        else:
            logger.info(f"✓ Loaded {len(repos)} repositories (all repos mode)")
        
        return repos
        
    except Exception as e:
        logger.error(f"❌ Failed to load CSV: {e}")
        raise

def save_results(results: List[CommitResult]):
    """Save results to CSV"""
    os.makedirs('results', exist_ok=True)
    
    if not results:
        logger.warning("⚠ No results to save")
        return
    
    logger.info(f"💾 Saving {len(results)} results to {OUTPUT_CSV}...")
    
    try:
        with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'repo_owner', 'repo_name', 'repo_url', 'commit_sha', 'commit_datetime',
                'author_name', 'author_email', 'commit_message', 'emojis_detected',
                'readme_additions_snippet', 'deepseek_affiliation', 'chatgpt_affiliation',
                'is_pull_request', 'pr_number', 'readme_file_path'
            ])
            
            writer.writeheader()
            for result in results:
                writer.writerow(asdict(result))
        
        logger.info(f"✓ Results saved successfully to {OUTPUT_CSV}")
        
    except Exception as e:
        logger.error(f"❌ Failed to save results: {e}")
        raise

def main():
    """Main execution function"""
    start_time = datetime.now()
    logger.info("="*80)
    logger.info("🚀 GitHub Political Emoji Commit Scraper Started")
    logger.info("="*80)
    
    # Initialize components
    token_manager = TokenManager()
    github_client = GitHubClient(token_manager)
    notifier = DiscordNotifier()
    
    # Send start notification
    filter_mode = "Affiliation filter enabled" if FILTER_BY_AFFILIATION else "All repos mode"
    notifier.send(
        f"🚀 Scraping started\n"
        f"📊 Tokens: {len(token_manager.tokens)}\n"
        f"⚙️ Max workers: {MAX_WORKERS}\n"
        f"� Filter: {filter_mode}\n"
        f"�🕒 Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}",
        "Scraper Started"
    )
    
    # Load repositories
    repositories = load_repositories()
    
    if not repositories:
        logger.error("❌ No repositories to process!")
        return
    
    # Log configuration
    filter_status = "with affiliation only" if FILTER_BY_AFFILIATION else "all repos (no filter)"
    logger.info(f"🎯 Processing {len(repositories)} repositories ({filter_status}) with {MAX_WORKERS} workers")
    
    # Process repositories with threading
    all_results = []
    processed_count = 0
    error_count = 0
    
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(token_manager.tokens))) as executor:
        # Submit all tasks
        future_to_repo = {
            executor.submit(process_repository, repo, github_client, notifier): repo
            for repo in repositories
        }
        
        # Process completed tasks
        for future in as_completed(future_to_repo):
            repo = future_to_repo[future]
            processed_count += 1
            
            try:
                results = future.result()
                all_results.extend(results)
                
                # Log progress every 10 repositories
                if processed_count % 10 == 0:
                    progress = (processed_count / len(repositories)) * 100
                    stats = token_manager.get_stats()
                    
                    logger.info(f"📊 Progress: {processed_count}/{len(repositories)} ({progress:.1f}%) - "
                              f"Found: {len(all_results)} commits - "
                              f"Tokens: {stats['available_tokens']} available, {stats['exhausted_tokens']} exhausted")
                    
                    # Send progress update to Discord
                    if processed_count % 50 == 0:
                        notifier.send(
                            f"📊 Progress Update\n"
                            f"Processed: {processed_count}/{len(repositories)} ({progress:.1f}%)\n"
                            f"Emoji commits found: {len(all_results)}\n"
                            f"Tokens: {stats['available_tokens']} available, {stats['exhausted_tokens']} exhausted\n"
                            f"Total API requests: {stats['total_requests']}",
                            "Progress Update"
                        )
                
                # Check if all tokens are exhausted
                if token_manager.all_tokens_exhausted():
                    logger.warning("⚠️ All tokens exhausted! Waiting 1 hour...")
                    notifier.send(
                        f"⏸️ Rate limit reached\n"
                        f"All {stats['total_tokens']} tokens exhausted\n"
                        f"Sleeping for 1 hour...\n"
                        f"Progress: {processed_count}/{len(repositories)}",
                        "Rate Limit Hit"
                    )
                    time.sleep(RATE_LIMIT_SLEEP)
                
            except Exception as e:
                error_count += 1
                logger.error(f"❌ Error processing {repo['repo_owner']}/{repo['repo_name']}: {e}")
    
    # Save results
    save_results(all_results)
    
    # Final statistics
    end_time = datetime.now()
    duration = end_time - start_time
    stats = token_manager.get_stats()
    
    logger.info("="*80)
    logger.info("✅ Scraping Completed!")
    logger.info("="*80)
    logger.info(f"⏱️  Duration: {duration}")
    logger.info(f"📊 Repositories processed: {processed_count}")
    logger.info(f"🎯 Emoji commits found: {len(all_results)}")
    logger.info(f"❌ Errors: {error_count}")
    logger.info(f"🔑 Total API requests: {stats['total_requests']}")
    logger.info(f"💾 Results saved to: {OUTPUT_CSV}")
    logger.info(f"📝 Log file: {LOG_FILE}")
    logger.info("="*80)
    
    # Send completion notification
    notifier.send(
        f"✅ Scraping completed!\n\n"
        f"⏱️ Duration: {duration}\n"
        f"📊 Repositories: {processed_count}\n"
        f"🎯 Emoji commits found: {len(all_results)}\n"
        f"❌ Errors: {error_count}\n"
        f"🔑 API requests: {stats['total_requests']}\n"
        f"💾 Output: {OUTPUT_CSV}",
        "Scraper Completed"
    )

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("\n⚠️ Scraping interrupted by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        logger.debug(traceback.format_exc())
        raise
