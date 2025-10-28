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
import threading

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
        self.global_sleep_mode = False  # Flag to stop all workers when exhausted
        self.last_exhaustion_check = datetime.now()
        
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
            # Check if we're in global sleep mode
            if self.global_sleep_mode:
                logger.debug("In global sleep mode, waiting...")
                return self.tokens[0]  # Return any token, request will be blocked
            
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
            
            # All tokens exhausted - enable global sleep mode
            logger.warning("⚠️ All tokens exhausted, enabling global sleep mode")
            self.global_sleep_mode = True
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
            for token in self.tokens:
                if self._is_token_available(token):
                    return False  # At least one token is available
            return True  # All tokens are exhausted
    
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
        
        # Send notification (outside lock to avoid blocking)
        notifier.send(
            f"⏸️ Rate limit reached\n"
            f"All {len(self.tokens)} tokens exhausted\n"
            f"Sleeping for 1 hour...\n"
            f"Progress: {processed_count}/{total_repos}\n"
            f"Available tokens: {stats['available_tokens']}/{stats['total_tokens']}",
            "Rate Limit Hit"
        )
        
        # Sleep (outside lock so other threads can finish their current tasks)
        logger.info(f"😴 Sleeping for {RATE_LIMIT_SLEEP} seconds...")
        time.sleep(RATE_LIMIT_SLEEP)
        
        # Reset global sleep mode and token reset times
        with self.lock:
            logger.info("✓ Sleep period ended, resetting tokens...")
            # Reset all tokens as they should have recovered
            for token in self.tokens:
                self.token_stats[token]["remaining"] = 5000
                self.token_stats[token]["reset_time"] = None
            self.global_sleep_mode = False
            logger.info("✓ All tokens reset, resuming scraping...")
        
        # Send resume notification
        notifier.send(
            f"▶️ Resuming scraping\n"
            f"All tokens reset\n"
            f"Progress: {processed_count}/{total_repos}",
            "Scraping Resumed"
        )

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
        # Configure connection pool to handle concurrent requests
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=MAX_WORKERS,
            pool_maxsize=MAX_WORKERS * 2,
            max_retries=0  # We handle retries manually
        )
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)
    
    def _make_request(self, method: str, url: str, **kwargs) -> Optional[requests.Response]:
        """Make HTTP request with token rotation and rate limit handling"""
        max_retries = 5  # Increased from 3 to 5
        retry_delays = [2, 5, 10, 20, 30]  # Progressive backoff delays in seconds
        
        for attempt in range(max_retries):
            # Check if we're in global sleep mode
            if self.token_manager.global_sleep_mode:
                logger.debug("Global sleep mode active, skipping request")
                return None
            
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
                
                logger.debug(f"🌐 Making {method} request to {url[:80]}... (attempt {attempt + 1}/{max_retries})")
                response = self.session.request(method, url, timeout=30, **kwargs)
                logger.debug(f"✓ Response received: {response.status_code}")
                
                # Update rate limit info
                if 'X-RateLimit-Remaining' in response.headers:
                    remaining = int(response.headers['X-RateLimit-Remaining'])
                    reset = int(response.headers['X-RateLimit-Reset'])
                    self.token_manager.update_rate_limit(token, remaining, reset)
                    
                    # Log warning if token is running low
                    if remaining < 100:
                        logger.warning(f"⚠️ Token running low: {remaining} requests remaining")
                
                # Handle different error codes
                if response.status_code == 403:
                    if 'rate limit' in response.text.lower():
                        logger.warning(f"Rate limit hit for current token (remaining: {remaining if 'remaining' in locals() else 'unknown'})")
                        
                        # Check if all tokens are exhausted (avoid retry spam)
                        if self.token_manager.all_tokens_exhausted():
                            logger.warning("All tokens exhausted, stopping retries")
                            return None
                        
                        # Try next token
                        logger.debug(f"Retrying with next token (attempt {attempt + 1}/{max_retries})...")
                        continue
                    else:
                        logger.warning(f"403 Forbidden (not rate limit): {response.text[:200]}")
                        return None
                
                # Handle server errors (502, 503, 504) with retry
                elif response.status_code in [502, 503, 504]:
                    error_name = {502: "Bad Gateway", 503: "Service Unavailable", 504: "Gateway Timeout"}
                    logger.warning(
                        f"🔄 {response.status_code} {error_name.get(response.status_code)} - "
                        f"Retrying in {retry_delays[attempt]}s (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(retry_delays[attempt])
                    continue
                
                # Handle not found
                elif response.status_code == 404:
                    logger.debug(f"Resource not found: {url}")
                    return None
                
                # Handle other client errors (400, 401, etc.) - don't retry
                elif 400 <= response.status_code < 500:
                    logger.warning(f"Client error {response.status_code}: {response.text[:200]}")
                    return None
                
                # Raise for any other error status
                response.raise_for_status()
                return response
                
            except requests.exceptions.Timeout as e:
                logger.warning(f"⏱️ Request timeout (attempt {attempt + 1}/{max_retries}): {url}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delays[attempt])
                    continue
                else:
                    logger.error(f"❌ Request timed out after {max_retries} attempts")
                    return None
                    
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"🔌 Connection error (attempt {attempt + 1}/{max_retries}): {str(e)[:100]}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delays[attempt])
                    continue
                else:
                    logger.error(f"❌ Connection failed after {max_retries} attempts")
                    return None
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {str(e)[:100]}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delays[attempt])
                    continue
                else:
                    logger.error(f"❌ Request failed after {max_retries} attempts: {e}")
                    return None
        
        logger.error(f"❌ All {max_retries} retry attempts exhausted for {url}")
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
    max_retries = 3  # Retry failed repos
    
    for repo_attempt in range(max_retries):
        try:
            # Try different README file variations
            readme_found = False
            for readme_path in README_PATTERNS:
                logger.debug(f"  Checking for {readme_path}...")
                
                # Get commit history for this README file
                commits_data = github_client.search_commits(owner, name, readme_path)
                
                if not commits_data:
                    logger.debug(f"  No data returned for {readme_path}")
                    continue
                
                repo_data_gql = commits_data.get('repository')
                if not repo_data_gql:
                    logger.debug(f"  No repository data for {readme_path}")
                    continue
                
                default_branch = repo_data_gql.get('defaultBranchRef')
                if not default_branch:
                    logger.debug(f"  No default branch for {readme_path}")
                    continue
                
                target = default_branch.get('target')
                if not target:
                    logger.debug(f"  No target for {readme_path}")
                    continue
                
                history = target.get('history')
                if not history:
                    logger.debug(f"  No history for {readme_path}")
                    continue
                
                edges = history.get('edges', [])
                if not edges:
                    logger.debug(f"  No commits for {readme_path}")
                    continue
                
                readme_found = True
                logger.info(f"  ✓ Found {len(edges)} commits for {readme_path}")
                
                # Process each commit
                for edge in edges:
                    try:
                        node = edge['node']
                        commit_sha = node['oid']
                        
                        # Get detailed commit info with diff
                        commit_details = github_client.get_commit_details(owner, name, commit_sha)
                        
                        if not commit_details:
                            logger.debug(f"  Skipping commit {commit_sha[:8]} (no details)")
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
                    
                    except Exception as commit_error:
                        logger.warning(f"  ⚠️ Error processing commit in {owner}/{name}: {str(commit_error)[:100]}")
                        continue
                
                # If we found commits for this README, don't check other variations
                if results:
                    break
            
            if not readme_found:
                logger.debug(f"  ⚠ No README file found in {owner}/{name}")
            elif not results:
                logger.debug(f"  ℹ No emoji commits found in {owner}/{name}")
            
            # Success - return results
            return results
            
        except Exception as e:
            logger.error(f"❌ Error processing {owner}/{name} (attempt {repo_attempt + 1}/{max_retries}): {str(e)[:150]}")
            logger.debug(traceback.format_exc())
            
            if repo_attempt < max_retries - 1:
                logger.info(f"  🔄 Retrying {owner}/{name} in 3 seconds...")
                time.sleep(3)
            else:
                logger.error(f"❌ Failed to process {owner}/{name} after {max_retries} attempts")
                return []
    
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

def generate_final_report(
    start_time: datetime,
    end_time: datetime,
    total_repos: int,
    processed_count: int,
    results: List[CommitResult],
    error_count: int,
    stats: Dict
) -> str:
    """Generate comprehensive final report"""
    duration = end_time - start_time
    
    # Calculate emoji statistics
    emoji_counts = {}
    for result in results:
        for emoji in result.emojis_detected.split('|'):
            if emoji:
                emoji_counts[emoji] = emoji_counts.get(emoji, 0) + 1
    
    # Sort emojis by frequency
    top_emojis = sorted(emoji_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Calculate affiliation statistics
    deepseek_count = sum(1 for r in results if r.deepseek_affiliation.lower() != 'none')
    chatgpt_count = sum(1 for r in results if r.chatgpt_affiliation.lower() != 'none')
    
    # Build report
    report = f"""
{'='*80}
GitHub Political Emoji Commit Scraper - Final Report
{'='*80}

EXECUTION SUMMARY
-----------------
Start Time:        {start_time.strftime('%Y-%m-%d %H:%M:%S')}
End Time:          {end_time.strftime('%Y-%m-%d %H:%M:%S')}
Duration:          {duration}
Status:            {'✅ Completed Successfully' if processed_count == total_repos else '⚠️ Partial Completion'}

REPOSITORY STATISTICS
----------------------
Total Repositories: {total_repos:,}
Processed:          {processed_count:,} ({processed_count/total_repos*100:.1f}%)
Errors:             {error_count:,}
Success Rate:       {(processed_count - error_count)/processed_count*100:.1f}%

EMOJI COMMIT FINDINGS
---------------------
Total Emoji Commits: {len(results):,}
Unique Repositories: {len(set(f"{r.repo_owner}/{r.repo_name}" for r in results)):,}
From Pull Requests:  {sum(1 for r in results if r.is_pull_request):,} ({sum(1 for r in results if r.is_pull_request)/len(results)*100:.1f}% if results else 0)

Top 10 Most Used Emojis:
"""
    
    for idx, (emoji, count) in enumerate(top_emojis, 1):
        report += f"  {idx:2}. {emoji}  →  {count:,} commits\n"
    
    report += f"""
AFFILIATION ANALYSIS
--------------------
DeepSeek Affiliated:  {deepseek_count:,} commits ({deepseek_count/len(results)*100:.1f}% of emoji commits)
ChatGPT Affiliated:   {chatgpt_count:,} commits ({chatgpt_count/len(results)*100:.1f}% of emoji commits)

API USAGE STATISTICS
--------------------
Total API Requests:   {stats['total_requests']:,}
Tokens Used:          {stats['total_tokens']}
Available Tokens:     {stats['available_tokens']}/{stats['total_tokens']}
Exhausted Tokens:     {stats['exhausted_tokens']}/{stats['total_tokens']}

CONFIGURATION
-------------
Filter Mode:          {'Affiliation filter' if FILTER_BY_AFFILIATION else 'All repos mode'}
Max Workers:          {MAX_WORKERS}
Request Delay:        {REQUEST_DELAY}s
Rate Limit Sleep:     {RATE_LIMIT_SLEEP}s ({RATE_LIMIT_SLEEP/3600:.1f} hour)

OUTPUT FILES
------------
Results CSV:          {OUTPUT_CSV}
Log File:             {LOG_FILE}
Report File:          results/report.txt

{'='*80}
Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*80}
"""
    
    return report

def watchdog_thread(processed_count_ref: Dict, total_repos: int, notifier: DiscordNotifier, stop_event: threading.Event):
    """Watchdog thread to detect if scraping has hung"""
    last_count = 0
    hang_checks = 0
    
    while not stop_event.is_set():
        time.sleep(120)  # Check every 2 minutes
        
        if stop_event.is_set():
            break
        
        current_count = processed_count_ref.get('count', 0)
        
        # Check if progress was made
        if current_count > last_count:
            # Progress detected, reset hang counter
            hang_checks = 0
            last_count = current_count
            logger.debug(f"🔍 Watchdog: Progress detected ({current_count}/{total_repos})")
        else:
            # No progress detected
            hang_checks += 1
            logger.warning(f"⚠️ Watchdog: No progress for {hang_checks * 2} minutes ({current_count}/{total_repos})")
            
            # If no progress for 20 minutes (10 checks), send alert
            if hang_checks >= 10:
                notifier.send(
                    f"🚨 Possible Hang!\n"
                    f"No progress for {hang_checks * 2} minutes\n"
                    f"Stuck at: {current_count}/{total_repos}",
                    "🚨 Hang Alert"
                )
                hang_checks = 0  # Reset to avoid spam

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
    
    # Send start notification with configuration
    filter_mode = "Affiliation filter enabled" if FILTER_BY_AFFILIATION else "All repos mode"
    notifier.send(
        f"🚀 Scraper Started\n"
        f"⚙️ Configuration:\n"
        f"  • Tokens: {len(token_manager.tokens)}\n"
        f"  • Workers: {MAX_WORKERS}\n"
        f"  • Filter: {filter_mode}\n"
        f"  • Request delay: {REQUEST_DELAY}s\n"
        f"  • Rate limit sleep: {RATE_LIMIT_SLEEP}s\n"
        f"🕒 {start_time.strftime('%Y-%m-%d %H:%M:%S')}",
        "🚀 Started"
    )
    
    # Load repositories
    repositories = load_repositories()
    
    if not repositories:
        logger.error("❌ No repositories to process!")
        return
    
    # Log configuration
    filter_status = "with affiliation only" if FILTER_BY_AFFILIATION else "all repos (no filter)"
    logger.info(f"🎯 Processing {len(repositories)} repositories ({filter_status}) with {MAX_WORKERS} workers")
    
    # Start watchdog thread to detect hangs
    processed_count_ref = {'count': 0}
    stop_watchdog = threading.Event()
    watchdog = threading.Thread(
        target=watchdog_thread,
        args=(processed_count_ref, len(repositories), notifier, stop_watchdog),
        daemon=True,
        name="WatchdogThread"
    )
    watchdog.start()
    logger.info("🔍 Watchdog thread started to monitor for hangs")
    
    # Process repositories with threading
    all_results = []
    processed_count = 0
    error_count = 0
    last_error_notification = datetime.now()
    consecutive_errors = 0
    last_progress_log = datetime.now()
    
    logger.info(f"⚡ Starting ThreadPoolExecutor with {min(MAX_WORKERS, len(token_manager.tokens))} workers...")
    
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(token_manager.tokens))) as executor:
        # Submit all tasks
        logger.info(f"📤 Submitting {len(repositories)} repository tasks to executor...")
        future_to_repo = {
            executor.submit(process_repository, repo, github_client, notifier): repo
            for repo in repositories
        }
        logger.info(f"✓ All {len(repositories)} tasks submitted, waiting for completion...")
        
        # Process completed tasks
        for future in as_completed(future_to_repo):
            repo = future_to_repo[future]
            processed_count += 1
            processed_count_ref['count'] = processed_count  # Update watchdog reference
            
            try:
                results = future.result()
                all_results.extend(results)
                
                # Reset consecutive errors on success
                if results or consecutive_errors > 0:
                    consecutive_errors = 0
                
                # Log progress every 10 repositories OR every 30 seconds
                current_time = datetime.now()
                time_since_last_log = (current_time - last_progress_log).total_seconds()
                
                if processed_count % 10 == 0 or time_since_last_log >= 30:
                    progress = (processed_count / len(repositories)) * 100
                    stats = token_manager.get_stats()
                    
                    logger.info(f"📊 Progress: {processed_count}/{len(repositories)} ({progress:.1f}%) - "
                              f"Found: {len(all_results)} commits - "
                              f"Errors: {error_count} - "
                              f"Tokens: {stats['available_tokens']} available, {stats['exhausted_tokens']} exhausted")
                    
                    last_progress_log = current_time
                    
                    # Send progress update to Discord only at 25%, 50%, 75%, 100%
                    # Calculate percentage milestones
                    milestone_25 = int(len(repositories) * 0.25)
                    milestone_50 = int(len(repositories) * 0.50)
                    milestone_75 = int(len(repositories) * 0.75)
                    milestone_100 = len(repositories)
                    
                    if processed_count in [milestone_25, milestone_50, milestone_75, milestone_100]:
                        notifier.send(
                            f"📊 Progress Milestone: {progress:.0f}%\n"
                            f"Processed: {processed_count}/{len(repositories)}\n"
                            f"Emoji commits found: {len(all_results)}\n"
                            f"Errors: {error_count}\n"
                            f"Tokens: {stats['available_tokens']}/{stats['total_tokens']} available\n"
                            f"Total API requests: {stats['total_requests']}",
                            f"Milestone: {progress:.0f}% Complete"
                        )
                
                # Check if global sleep mode is active (one thread will handle the sleep)
                if token_manager.global_sleep_mode:
                    logger.warning("🛑 Global sleep mode detected, initiating sleep period...")
                    token_manager.sleep_and_reset(notifier, processed_count, len(repositories))
                
            except Exception as e:
                error_count += 1
                consecutive_errors += 1
                error_msg = str(e)[:150]
                logger.error(f"❌ Error processing {repo['repo_owner']}/{repo['repo_name']}: {error_msg}")
                logger.debug(traceback.format_exc())
                
                # Send notification if too many consecutive errors
                if consecutive_errors >= 10:
                    current_time = datetime.now()
                    # Only send error notification every 10 minutes (reduced spam)
                    if (current_time - last_error_notification).total_seconds() >= 600:
                        notifier.send(
                            f"⚠️ High Error Rate\n"
                            f"Consecutive errors: {consecutive_errors}\n"
                            f"Total errors: {error_count}\n"
                            f"Progress: {processed_count}/{len(repositories)} ({(processed_count/len(repositories)*100):.0f}%)",
                            "⚠️ Error Alert"
                        )
                        last_error_notification = current_time
                        consecutive_errors = 0  # Reset after notification
    
    logger.info(f"✓ ThreadPoolExecutor completed all tasks")
    
    # Stop watchdog thread
    stop_watchdog.set()
    watchdog.join(timeout=5)
    logger.info("✓ Watchdog thread stopped")
    
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
    
    # Generate comprehensive report
    final_report = generate_final_report(
        start_time, end_time, len(repositories), processed_count,
        all_results, error_count, stats
    )
    
    # Print report to console
    logger.info("\n" + final_report)
    
    # Save report to file
    report_file = "results/report.txt"
    try:
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(final_report)
        logger.info(f"📄 Report saved to: {report_file}")
    except Exception as e:
        logger.error(f"❌ Failed to save report: {e}")
    
    # Send completion notification to Discord (concise version with stats)
    emoji_commits = len(all_results)
    unique_repos = len(set(f"{r.repo_owner}/{r.repo_name}" for r in all_results)) if all_results else 0
    
    # Calculate top 3 emojis
    emoji_counts = {}
    for result in all_results:
        for emoji in result.emojis_detected.split('|'):
            if emoji:
                emoji_counts[emoji] = emoji_counts.get(emoji, 0) + 1
    top_3_emojis = sorted(emoji_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    top_emojis_str = ", ".join([f"{emoji} ({count})" for emoji, count in top_3_emojis]) if top_3_emojis else "None"
    
    # Send completion notification
    notifier.send(
        f"✅ Scraping Completed!\n\n"
        f"⏱️ Duration: {duration}\n"
        f"📊 Repos: {processed_count:,}/{len(repositories):,}\n"
        f"🎯 Emoji Commits: {emoji_commits:,} (from {unique_repos:,} repos)\n"
        f"❌ Errors: {error_count:,}\n"
        f"🔥 Top Emojis: {top_emojis_str}\n"
        f"📄 Full report: results/report.txt",
        "✅ Completed"
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
