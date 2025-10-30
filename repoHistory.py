#!/usr/bin/env python3
"""
GitHub Repository History Scraper
Tracks repository metrics (stars, contributors, PRs, commits, issues) over time
Supports daily and weekly tracking with comprehensive reporting
"""

import os
import csv
import time
import logging
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from dataclasses import dataclass, asdict
from dotenv import load_dotenv
import traceback

# Load environment variables
load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

# API Configuration
REQUEST_DELAY = 0.1  # 100ms delay between requests
RATE_LIMIT_SLEEP = 3600  # 1 hour sleep when all tokens exhausted
MAX_WORKERS = 12  # Maximum concurrent workers

# Filter Configuration
# Set to True to only scrape repos with affiliation (deepseek or chatgpt)
# Set to False to scrape ALL repos regardless of affiliation
FILTER_BY_AFFILIATION = False  # Default: scrape all repos (False)

# Scraping Frequency
# Options: "D" (daily) or "W" (weekly)
SCRAPING_FREQUENCY = "W"  # Set to "D" for daily tracking, "W" for weekly tracking

# File paths
INPUT_CSV = r"datasets/affiliated_deepseek_1000_200000_NoReadme.csv"  # Input CSV with repo info
OUTPUT_CSV = r"results/repo_growth_history.csv"  # Output CSV for growth history
REPORT_FILE = f"results/repo_history_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
LOG_DIR = "logs"
LOG_FILE = f"{LOG_DIR}/repo_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Discord Webhook (optional - leave empty to disable)
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")  # Load from .env

# Repository history tracking
WEEKS_TO_TRACK = 200  # Number of weeks to track (1 year = 52)

# Growth Analysis
CALCULATE_GROWTH = True  # Calculate week-by-week growth from historical data
TEMP_SNAPSHOT_CSV = r"results/.temp_repo_snapshots.csv"  # Temporary snapshots storage

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class StarHistoryRecord:
    """Record of repository history for a repository"""
    repo_owner: str
    repo_name: str
    repo_url: str
    snapshot_date: str  # Date of this snapshot
    total_stars: int  # Total stars count at this snapshot
    total_forks: int  # Total forks count at this snapshot
    total_contributors: int  # Total contributors count at this snapshot
    total_prs: int  # Total pull requests count
    total_commits: int  # Total commits count
    total_issues: int  # Total issues count
    deepseek_affiliation: str
    chatgpt_affiliation: str

@dataclass
class GrowthRecord:
    """Week-by-week growth analysis for a repository"""
    repo_owner: str
    repo_name: str
    repo_url: str
    week_start_date: str
    week_end_date: str
    stars_start: int
    stars_end: int
    stars_gained: int
    forks_start: int
    forks_end: int
    forks_gained: int
    contributors_start: int
    contributors_end: int
    contributors_gained: int
    prs_start: int
    prs_end: int
    prs_created: int
    commits_start: int
    commits_end: int
    commits_added: int
    issues_start: int
    issues_end: int
    issues_created: int
    deepseek_affiliation: str
    chatgpt_affiliation: str

# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging():
    """Setup logging configuration"""
    os.makedirs(LOG_DIR, exist_ok=True)
    
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(detailed_formatter)
    
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
    """Manages GitHub token rotation and rate limiting"""
    
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
    
    def get_token(self) -> str:
        """Get next available token with rotation"""
        with self.lock:
            token = self.tokens[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.tokens)
            self.token_stats[token]["requests"] += 1
            return token
    
    def update_rate_limit(self, token: str, remaining: int, reset_timestamp: int):
        """Update rate limit info for a token"""
        with self.lock:
            self.token_stats[token]["remaining"] = remaining
            self.token_stats[token]["reset_time"] = datetime.fromtimestamp(reset_timestamp)
            
            if remaining < 100:
                logger.warning(f"⚠️ Token running low: {remaining} requests remaining")
    
    def get_stats(self) -> Dict:
        """Get current token statistics"""
        with self.lock:
            total_requests = sum(stats["requests"] for stats in self.token_stats.values())
            
            return {
                "total_tokens": len(self.tokens),
                "total_requests": total_requests,
                "tokens": [
                    {
                        "token_id": f"Token #{idx + 1}",
                        "remaining": stats["remaining"],
                        "reset_time": stats["reset_time"].strftime("%H:%M:%S") if stats["reset_time"] else "N/A",
                        "requests": stats["requests"]
                    }
                    for idx, (token, stats) in enumerate(self.token_stats.items())
                ]
            }

# ============================================================================
# GITHUB API CLIENT
# ============================================================================

class GitHubClient:
    """GitHub API client for fetching repository data"""
    
    def __init__(self, token_manager: TokenManager):
        self.token_manager = token_manager
        self.rest_base = "https://api.github.com"
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=MAX_WORKERS,
            pool_maxsize=MAX_WORKERS * 2,
            max_retries=0
        )
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)
    
    def _make_request(self, url: str, headers: Dict = None) -> Optional[requests.Response]:
        """Make HTTP request with token rotation"""
        max_retries = 3
        retry_delays = [2, 5, 10]
        
        for attempt in range(max_retries):
            token = self.token_manager.get_token()
            request_headers = headers or {}
            request_headers.update({
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.star+json",  # Include star timestamps
                "X-GitHub-Api-Version": "2022-11-28"
            })
            
            try:
                time.sleep(REQUEST_DELAY)
                
                logger.debug(f"🌐 Making request to {url[:80]}... (attempt {attempt + 1}/{max_retries})")
                response = self.session.get(url, headers=request_headers, timeout=30)
                logger.debug(f"✓ Response received: {response.status_code}")
                
                # Update rate limit info
                if 'X-RateLimit-Remaining' in response.headers:
                    remaining = int(response.headers['X-RateLimit-Remaining'])
                    reset = int(response.headers['X-RateLimit-Reset'])
                    self.token_manager.update_rate_limit(token, remaining, reset)
                
                # Handle different status codes
                if response.status_code == 200:
                    return response
                elif response.status_code == 404:
                    logger.warning(f"Repository not found: {url}")
                    return None
                elif response.status_code == 403:
                    logger.warning(f"Rate limit or forbidden: {response.text[:200]}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delays[attempt])
                        continue
                elif response.status_code in [502, 503, 504]:
                    logger.warning(f"Server error {response.status_code}, retrying...")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delays[attempt])
                        continue
                
                response.raise_for_status()
                return response
                
            except requests.exceptions.Timeout:
                logger.warning(f"⏱️ Request timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(retry_delays[attempt])
                    continue
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed: {str(e)[:100]}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delays[attempt])
                    continue
        
        logger.error(f"❌ All {max_retries} retry attempts exhausted for {url}")
        return None
    
    def get_repository_info(self, owner: str, repo: str) -> Optional[Dict]:
        """Get repository information including current star count"""
        url = f"{self.rest_base}/repos/{owner}/{repo}"
        response = self._make_request(url)
        
        if response:
            return response.json()
        return None
    
    def get_stargazers_page(self, owner: str, repo: str, page: int = 1, per_page: int = 100) -> Optional[List[Dict]]:
        """Get a page of stargazers with timestamps"""
        url = f"{self.rest_base}/repos/{owner}/{repo}/stargazers?page={page}&per_page={per_page}"
        response = self._make_request(url)
        
        if response:
            return response.json()
        return None
    
    def get_contributors_count(self, owner: str, repo: str) -> int:
        """Get total number of contributors for a repository"""
        url = f"{self.rest_base}/repos/{owner}/{repo}/contributors?per_page=1"
        response = self._make_request(url)
        
        if response and 'Link' in response.headers:
            # Parse the Link header to get total pages
            links = response.headers['Link']
            if 'last' in links:
                import re
                match = re.search(r'page=(\d+)>; rel="last"', links)
                if match:
                    return int(match.group(1))
        
        # If no pagination, count the response
        if response:
            contributors = response.json()
            return len(contributors) if contributors else 0
        return 0
    
    def get_pulls_count(self, owner: str, repo: str) -> int:
        """Get total number of pull requests (all states)"""
        url = f"{self.rest_base}/repos/{owner}/{repo}/pulls?state=all&per_page=1"
        response = self._make_request(url)
        
        if response and 'Link' in response.headers:
            # Parse the Link header to get total count from last page
            links = response.headers['Link']
            if 'last' in links:
                import re
                match = re.search(r'page=(\d+)>; rel="last"', links)
                if match:
                    return int(match.group(1))
        
        # If no pagination, return 1 if we got a response
        if response:
            pulls = response.json()
            return len(pulls) if pulls else 0
        return 0
    
    def get_commits_count(self, owner: str, repo: str) -> int:
        """Get total number of commits in the repository"""
        url = f"{self.rest_base}/repos/{owner}/{repo}/commits?per_page=1"
        response = self._make_request(url)
        
        if response and 'Link' in response.headers:
            # Parse the Link header to get total count
            links = response.headers['Link']
            if 'last' in links:
                import re
                match = re.search(r'page=(\d+)>; rel="last"', links)
                if match:
                    return int(match.group(1))
        
        # If no pagination, try to get count from first page
        if response:
            commits = response.json()
            return len(commits) if commits else 0
        return 0
    
    def get_issues_count(self, owner: str, repo: str) -> int:
        """Get total number of issues (excluding pull requests)"""
        url = f"{self.rest_base}/repos/{owner}/{repo}/issues?state=all&per_page=100"
        response = self._make_request(url)
        
        if not response:
            return 0
        
        issues = response.json()
        # Filter out pull requests (GitHub API includes PRs in issues endpoint)
        count = sum(1 for issue in issues if 'pull_request' not in issue)
        
        # If there are more pages, we need to paginate
        if 'Link' in response.headers and 'last' in response.headers['Link']:
            import re
            links = response.headers['Link']
            match = re.search(r'page=(\d+)>; rel="last"', links)
            if match:
                total_pages = int(match.group(1))
                # Rough estimate: count from first page * total pages
                # This is an approximation since we're filtering out PRs
                count = count * total_pages
        
        return count

# ============================================================================
# REPOSITORY HISTORY PROCESSING
# ============================================================================

def get_star_history_snapshot(
    repo_data: Dict,
    github_client: GitHubClient
) -> Optional[StarHistoryRecord]:
    """Get current repository metrics snapshot"""
    
    owner = repo_data['repo_owner']
    name = repo_data['repo_name']
    url = repo_data['repo_url']
    deepseek_aff = repo_data.get('deepseek_affiliation', 'none')
    chatgpt_aff = repo_data.get('chatgpt_affiliation', 'none')
    
    logger.info(f"⭐ Fetching metrics for: {owner}/{name}")
    
    try:
        # Get repository info
        repo_info = github_client.get_repository_info(owner, name)
        
        if not repo_info:
            logger.warning(f"Could not fetch info for {owner}/{name}")
            return None
        
        # Get total counts from repository info
        total_stars = repo_info.get('stargazers_count', 0)
        total_forks = repo_info.get('forks_count', 0)
        
        snapshot_date = datetime.now().strftime('%Y-%m-%d')
        
        # Get additional metrics - total counts
        logger.debug(f"  Fetching total contributors count...")
        total_contributors = github_client.get_contributors_count(owner, name)
        
        logger.debug(f"  Fetching total PRs count...")
        total_prs = github_client.get_pulls_count(owner, name)
        
        logger.debug(f"  Fetching total commits count...")
        total_commits = github_client.get_commits_count(owner, name)
        
        logger.debug(f"  Fetching total issues count...")
        total_issues = github_client.get_issues_count(owner, name)
        
        record = StarHistoryRecord(
            repo_owner=owner,
            repo_name=name,
            repo_url=url,
            snapshot_date=snapshot_date,
            total_stars=total_stars,
            total_forks=total_forks,
            total_contributors=total_contributors,
            total_prs=total_prs,
            total_commits=total_commits,
            total_issues=total_issues,
            deepseek_affiliation=deepseek_aff,
            chatgpt_affiliation=chatgpt_aff
        )
        
        logger.info(f"✓ {owner}/{name}: {total_stars:,} ⭐ | {total_forks:,} 🍴 | "
                   f"{total_contributors} 👥 | {total_prs} PR | {total_commits} commits | {total_issues} issues")
        return record
        
    except Exception as e:
        logger.error(f"❌ Error processing {owner}/{name}: {str(e)[:150]}")
        logger.debug(traceback.format_exc())
        return None

# ============================================================================
# MAIN PROCESSING
# ============================================================================

def load_repositories() -> List[Dict]:
    """Load unique repositories from CSV"""
    logger.info(f"📖 Loading repositories from {INPUT_CSV}...")
    
    repos = []
    seen_repos = set()
    
    try:
        with open(INPUT_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                repo_key = f"{row['repo_owner']}/{row['repo_name']}"
                
                # Skip duplicates
                if repo_key in seen_repos:
                    continue
                seen_repos.add(repo_key)
                
                # Get affiliations
                deepseek_aff = row.get('deepseek_affiliation', 'none').strip().lower()
                chatgpt_aff = row.get('chatgpt_affiliation', 'none').strip().lower()
                
                # Filter based on configuration
                if FILTER_BY_AFFILIATION:
                    if deepseek_aff != 'none' or chatgpt_aff != 'none':
                        repos.append({
                            'repo_owner': row['repo_owner'],
                            'repo_name': row['repo_name'],
                            'repo_url': row['repo_url'],
                            'deepseek_affiliation': deepseek_aff,
                            'chatgpt_affiliation': chatgpt_aff
                        })
                else:
                    repos.append({
                        'repo_owner': row['repo_owner'],
                        'repo_name': row['repo_name'],
                        'repo_url': row['repo_url'],
                        'deepseek_affiliation': deepseek_aff,
                        'chatgpt_affiliation': chatgpt_aff
                    })
        
        filter_mode = "with affiliation only" if FILTER_BY_AFFILIATION else "all repos"
        logger.info(f"✓ Loaded {len(repos)} unique repositories ({filter_mode})")
        
        return repos
        
    except Exception as e:
        logger.error(f"❌ Failed to load CSV: {e}")
        raise

def save_results(results: List[StarHistoryRecord]):
    """Save repository snapshots to temporary CSV for growth calculation"""
    os.makedirs('results', exist_ok=True)
    
    if not results:
        logger.warning("⚠ No results to save")
        return
    
    logger.info(f"💾 Saving {len(results)} snapshots to temporary storage...")
    
    # Check if file exists to determine if we need to write headers
    file_exists = os.path.exists(TEMP_SNAPSHOT_CSV)
    
    try:
        # Always append to temp file (it's cleaned at program start)
        with open(TEMP_SNAPSHOT_CSV, 'a' if file_exists else 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'repo_owner', 'repo_name', 'repo_url', 'snapshot_date',
                'total_stars', 'total_forks', 'total_contributors',
                'total_prs', 'total_commits', 'total_issues',
                'deepseek_affiliation', 'chatgpt_affiliation'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            # Write header only if file doesn't exist yet
            if not file_exists:
                writer.writeheader()
            
            for result in results:
                writer.writerow(asdict(result))
        
        mode = "appended to" if file_exists else "created"
        logger.info(f"✓ Snapshots {mode} temporary storage")
        
    except Exception as e:
        logger.error(f"❌ Failed to save snapshots: {e}")
        raise

def calculate_weekly_growth(csv_path: str = TEMP_SNAPSHOT_CSV) -> List[GrowthRecord]:
    """Calculate week-by-week growth from historical snapshot data"""
    
    if not os.path.exists(csv_path):
        logger.warning(f"⚠️ No historical data found at {csv_path}")
        return []
    
    logger.info("📊 Calculating week-by-week growth from historical data...")
    
    # Load all historical snapshots
    snapshots_by_repo = {}
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                repo_key = f"{row['repo_owner']}/{row['repo_name']}"
                
                if repo_key not in snapshots_by_repo:
                    snapshots_by_repo[repo_key] = []
                
                snapshots_by_repo[repo_key].append({
                    'repo_owner': row['repo_owner'],
                    'repo_name': row['repo_name'],
                    'repo_url': row['repo_url'],
                    'snapshot_date': row['snapshot_date'],
                    'total_stars': int(row['total_stars']),
                    'total_forks': int(row['total_forks']),
                    'total_contributors': int(row['total_contributors']),
                    'total_prs': int(row['total_prs']),
                    'total_commits': int(row['total_commits']),
                    'total_issues': int(row['total_issues']),
                    'deepseek_affiliation': row.get('deepseek_affiliation', 'none'),
                    'chatgpt_affiliation': row.get('chatgpt_affiliation', 'none')
                })
        
        logger.info(f"✓ Loaded snapshots for {len(snapshots_by_repo)} repositories")
        
        # Calculate growth for each repository
        growth_records = []
        
        for repo_key, snapshots in snapshots_by_repo.items():
            # Sort snapshots by date
            snapshots.sort(key=lambda x: x['snapshot_date'])
            
            # Calculate growth between consecutive snapshots
            for i in range(len(snapshots) - 1):
                prev = snapshots[i]
                curr = snapshots[i + 1]
                
                growth = GrowthRecord(
                    repo_owner=curr['repo_owner'],
                    repo_name=curr['repo_name'],
                    repo_url=curr['repo_url'],
                    week_start_date=prev['snapshot_date'],
                    week_end_date=curr['snapshot_date'],
                    stars_start=prev['total_stars'],
                    stars_end=curr['total_stars'],
                    stars_gained=curr['total_stars'] - prev['total_stars'],
                    forks_start=prev['total_forks'],
                    forks_end=curr['total_forks'],
                    forks_gained=curr['total_forks'] - prev['total_forks'],
                    contributors_start=prev['total_contributors'],
                    contributors_end=curr['total_contributors'],
                    contributors_gained=curr['total_contributors'] - prev['total_contributors'],
                    prs_start=prev['total_prs'],
                    prs_end=curr['total_prs'],
                    prs_created=curr['total_prs'] - prev['total_prs'],
                    commits_start=prev['total_commits'],
                    commits_end=curr['total_commits'],
                    commits_added=curr['total_commits'] - prev['total_commits'],
                    issues_start=prev['total_issues'],
                    issues_end=curr['total_issues'],
                    issues_created=curr['total_issues'] - prev['total_issues'],
                    deepseek_affiliation=curr['deepseek_affiliation'],
                    chatgpt_affiliation=curr['chatgpt_affiliation']
                )
                
                growth_records.append(growth)
        
        logger.info(f"✓ Calculated {len(growth_records)} growth periods")
        return growth_records
        
    except Exception as e:
        logger.error(f"❌ Failed to calculate growth: {e}")
        logger.debug(traceback.format_exc())
        return []

def save_growth_analysis(growth_records: List[GrowthRecord]):
    """Save growth analysis to CSV"""
    
    if not growth_records:
        logger.warning("⚠️ No growth data to save")
        return
    
    os.makedirs('results', exist_ok=True)
    logger.info(f"💾 Saving {len(growth_records)} growth records to {OUTPUT_CSV}...")
    
    try:
        with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'repo_owner', 'repo_name', 'repo_url',
                'week_start_date', 'week_end_date',
                'stars_start', 'stars_end', 'stars_gained',
                'forks_start', 'forks_end', 'forks_gained',
                'contributors_start', 'contributors_end', 'contributors_gained',
                'prs_start', 'prs_end', 'prs_created',
                'commits_start', 'commits_end', 'commits_added',
                'issues_start', 'issues_end', 'issues_created',
                'deepseek_affiliation', 'chatgpt_affiliation'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for record in growth_records:
                writer.writerow(asdict(record))
        
        logger.info(f"✓ Growth analysis saved to {OUTPUT_CSV}")
        
    except Exception as e:
        logger.error(f"❌ Failed to save growth analysis: {e}")
        raise

def generate_growth_report(growth_records: List[GrowthRecord]) -> str:
    """Generate week-by-week growth analysis report"""
    
    if not growth_records:
        return ""
    
    report_lines = []
    report_lines.append("\n" + "=" * 80)
    report_lines.append("📈 WEEK-BY-WEEK GROWTH ANALYSIS")
    report_lines.append("=" * 80)
    report_lines.append(f"Total Growth Periods Analyzed: {len(growth_records)}")
    report_lines.append(f"Repositories Tracked: {len(set(f'{r.repo_owner}/{r.repo_name}' for r in growth_records))}")
    report_lines.append("")
    
    # Aggregate growth statistics
    total_stars_gained = sum(r.stars_gained for r in growth_records)
    total_forks_gained = sum(r.forks_gained for r in growth_records)
    total_contributors_gained = sum(r.contributors_gained for r in growth_records)
    total_prs_created = sum(r.prs_created for r in growth_records)
    total_commits_added = sum(r.commits_added for r in growth_records)
    total_issues_created = sum(r.issues_created for r in growth_records)
    
    report_lines.append("📊 AGGREGATE GROWTH ACROSS ALL PERIODS")
    report_lines.append("-" * 80)
    report_lines.append(f"Total Stars Gained: {total_stars_gained:,}")
    report_lines.append(f"Total Forks Gained: {total_forks_gained:,}")
    report_lines.append(f"Total Contributors Gained: {total_contributors_gained:,}")
    report_lines.append(f"Total PRs Created: {total_prs_created:,}")
    report_lines.append(f"Total Commits Added: {total_commits_added:,}")
    report_lines.append(f"Total Issues Created: {total_issues_created:,}")
    report_lines.append("")
    
    # Top growing repositories by stars
    report_lines.append("⭐ TOP 10 FASTEST GROWING (STARS PER PERIOD)")
    report_lines.append("-" * 80)
    top_star_growth = sorted(growth_records, key=lambda r: r.stars_gained, reverse=True)[:10]
    for idx, record in enumerate(top_star_growth, 1):
        report_lines.append(f"{idx}. {record.repo_owner}/{record.repo_name}")
        report_lines.append(f"   Period: {record.week_start_date} → {record.week_end_date}")
        report_lines.append(f"   Stars: {record.stars_start:,} → {record.stars_end:,} (+{record.stars_gained:,})")
        report_lines.append("")
    
    # Top growing by commits
    report_lines.append("💻 TOP 10 MOST ACTIVE DEVELOPMENT (COMMITS PER PERIOD)")
    report_lines.append("-" * 80)
    top_commit_growth = sorted(growth_records, key=lambda r: r.commits_added, reverse=True)[:10]
    for idx, record in enumerate(top_commit_growth, 1):
        report_lines.append(f"{idx}. {record.repo_owner}/{record.repo_name}")
        report_lines.append(f"   Period: {record.week_start_date} → {record.week_end_date}")
        report_lines.append(f"   Commits: {record.commits_start:,} → {record.commits_end:,} (+{record.commits_added:,})")
        report_lines.append("")
    
    # Top growing by PRs
    report_lines.append("📥 TOP 10 MOST PULL REQUESTS (PRS PER PERIOD)")
    report_lines.append("-" * 80)
    top_pr_growth = sorted(growth_records, key=lambda r: r.prs_created, reverse=True)[:10]
    for idx, record in enumerate(top_pr_growth, 1):
        report_lines.append(f"{idx}. {record.repo_owner}/{record.repo_name}")
        report_lines.append(f"   Period: {record.week_start_date} → {record.week_end_date}")
        report_lines.append(f"   PRs: {record.prs_start:,} → {record.prs_end:,} (+{record.prs_created:,})")
        report_lines.append("")
    
    # Top growing by issues
    report_lines.append("🐛 TOP 10 MOST ISSUES CREATED (ISSUES PER PERIOD)")
    report_lines.append("-" * 80)
    top_issue_growth = sorted(growth_records, key=lambda r: r.issues_created, reverse=True)[:10]
    for idx, record in enumerate(top_issue_growth, 1):
        report_lines.append(f"{idx}. {record.repo_owner}/{record.repo_name}")
        report_lines.append(f"   Period: {record.week_start_date} → {record.week_end_date}")
        report_lines.append(f"   Issues: {record.issues_start:,} → {record.issues_end:,} (+{record.issues_created:,})")
        report_lines.append("")
    
    report_lines.append("=" * 80)
    report_lines.append(f"📁 Growth data saved to: {OUTPUT_CSV}")
    report_lines.append("=" * 80)
    
    return "\n".join(report_lines)

def generate_report(results: List[StarHistoryRecord], duration, stats: Dict) -> str:
    """Generate comprehensive text report of scraping results"""
    
    if not results:
        return "No data to report"
    
    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("📊 GITHUB REPOSITORY HISTORY SCRAPING REPORT")
    report_lines.append("=" * 80)
    report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"Scraping Frequency: {SCRAPING_FREQUENCY.upper()}")
    report_lines.append(f"Filter Mode: {'Affiliated Only' if FILTER_BY_AFFILIATION else 'All Repositories'}")
    report_lines.append("")
    
    # Summary Statistics
    report_lines.append("📊 SUMMARY STATISTICS")
    report_lines.append("-" * 80)
    report_lines.append(f"Total Repositories Scraped: {len(results)}")
    report_lines.append(f"Scraping Duration: {duration}")
    report_lines.append(f"Total API Requests: {stats['total_requests']:,}")
    report_lines.append(f"Tokens Used: {stats['total_tokens']}")
    report_lines.append("")
    
    # Repository Metrics
    total_stars = sum(r.total_stars for r in results)
    total_forks = sum(r.total_forks for r in results)
    total_contributors = sum(r.total_contributors for r in results)
    total_prs = sum(r.total_prs for r in results)
    total_commits = sum(r.total_commits for r in results)
    total_issues = sum(r.total_issues for r in results)
    
    avg_stars = total_stars / len(results) if results else 0
    avg_forks = total_forks / len(results) if results else 0
    avg_contributors = total_contributors / len(results) if results else 0
    avg_prs = total_prs / len(results) if results else 0
    avg_commits = total_commits / len(results) if results else 0
    avg_issues = total_issues / len(results) if results else 0
    
    report_lines.append("📈 REPOSITORY METRICS (TOTAL COUNTS)")
    report_lines.append("-" * 80)
    report_lines.append(f"Total Stars Across All Repos: {total_stars:,} (avg: {avg_stars:,.0f})")
    report_lines.append(f"Total Forks Across All Repos: {total_forks:,} (avg: {avg_forks:,.0f})")
    report_lines.append(f"Total Contributors: {total_contributors:,} (avg: {avg_contributors:,.0f})")
    report_lines.append(f"Total Pull Requests: {total_prs:,} (avg: {avg_prs:,.0f})")
    report_lines.append(f"Total Commits: {total_commits:,} (avg: {avg_commits:,.0f})")
    report_lines.append(f"Total Issues: {total_issues:,} (avg: {avg_issues:,.0f})")
    report_lines.append("")
    
    # Top 5 Most Starred Repositories
    report_lines.append("🏆 TOP 5 MOST STARRED REPOSITORIES")
    report_lines.append("-" * 80)
    top_starred = sorted(results, key=lambda r: r.total_stars, reverse=True)[:5]
    for idx, repo in enumerate(top_starred, 1):
        report_lines.append(f"{idx}. {repo.repo_owner}/{repo.repo_name}")
        report_lines.append(f"   Stars: {repo.total_stars:,} | Forks: {repo.total_forks:,} | Contributors: {repo.total_contributors:,}")
        report_lines.append(f"   URL: {repo.repo_url}")
        report_lines.append("")
    
    # Top 5 Most Active Repositories (by total commits)
    report_lines.append("🔥 TOP 5 MOST ACTIVE REPOSITORIES (TOTAL COMMITS)")
    report_lines.append("-" * 80)
    top_active = sorted(results, key=lambda r: r.total_commits, reverse=True)[:5]
    for idx, repo in enumerate(top_active, 1):
        report_lines.append(f"{idx}. {repo.repo_owner}/{repo.repo_name}")
        report_lines.append(f"   Commits: {repo.total_commits:,} | PRs: {repo.total_prs:,} | Issues: {repo.total_issues:,}")
        report_lines.append(f"   URL: {repo.repo_url}")
        report_lines.append("")
    
    # Top 5 Most Collaborative (by contributors)
    report_lines.append("👥 TOP 5 MOST COLLABORATIVE REPOSITORIES")
    report_lines.append("-" * 80)
    top_collab = sorted(results, key=lambda r: r.total_contributors, reverse=True)[:5]
    for idx, repo in enumerate(top_collab, 1):
        report_lines.append(f"{idx}. {repo.repo_owner}/{repo.repo_name}")
        report_lines.append(f"   Contributors: {repo.total_contributors:,} | Stars: {repo.total_stars:,} | Commits: {repo.total_commits:,}")
        report_lines.append(f"   URL: {repo.repo_url}")
        report_lines.append("")
    
    # Top 5 by Pull Requests
    report_lines.append("📥 TOP 5 REPOSITORIES BY TOTAL PULL REQUESTS")
    report_lines.append("-" * 80)
    top_prs_repos = sorted(results, key=lambda r: r.total_prs, reverse=True)[:5]
    for idx, repo in enumerate(top_prs_repos, 1):
        report_lines.append(f"{idx}. {repo.repo_owner}/{repo.repo_name}")
        report_lines.append(f"   PRs: {repo.total_prs:,} | Commits: {repo.total_commits:,} | Stars: {repo.total_stars:,}")
        report_lines.append(f"   URL: {repo.repo_url}")
        report_lines.append("")
    
    # Top 5 by Issues
    report_lines.append("🐛 TOP 5 REPOSITORIES BY TOTAL ISSUES")
    report_lines.append("-" * 80)
    top_issues_repos = sorted(results, key=lambda r: r.total_issues, reverse=True)[:5]
    for idx, repo in enumerate(top_issues_repos, 1):
        report_lines.append(f"{idx}. {repo.repo_owner}/{repo.repo_name}")
        report_lines.append(f"   Issues: {repo.total_issues:,} | Stars: {repo.total_stars:,} | Contributors: {repo.total_contributors:,}")
        report_lines.append(f"   URL: {repo.repo_url}")
        report_lines.append("")
    
    # Top 5 Most Forked
    report_lines.append("🍴 TOP 5 MOST FORKED REPOSITORIES")
    report_lines.append("-" * 80)
    top_forked = sorted(results, key=lambda r: r.total_forks, reverse=True)[:5]
    for idx, repo in enumerate(top_forked, 1):
        report_lines.append(f"{idx}. {repo.repo_owner}/{repo.repo_name}")
        report_lines.append(f"   Forks: {repo.total_forks:,} | Stars: {repo.total_stars:,} | Contributors: {repo.total_contributors:,}")
        report_lines.append(f"   URL: {repo.repo_url}")
        report_lines.append("")
    
    # Affiliation Breakdown
    deepseek_count = sum(1 for r in results if r.deepseek_affiliation.lower() != 'none')
    chatgpt_count = sum(1 for r in results if r.chatgpt_affiliation.lower() != 'none')
    
    report_lines.append("🏢 AFFILIATION BREAKDOWN")
    report_lines.append("-" * 80)
    report_lines.append(f"DeepSeek Affiliated: {deepseek_count} ({deepseek_count/len(results)*100:.1f}%)")
    report_lines.append(f"ChatGPT Affiliated: {chatgpt_count} ({chatgpt_count/len(results)*100:.1f}%)")
    report_lines.append("")
    
    # File Locations
    report_lines.append("📁 OUTPUT FILES")
    report_lines.append("-" * 80)
    report_lines.append(f"Growth CSV: {OUTPUT_CSV}")
    report_lines.append(f"Temp Snapshots: {TEMP_SNAPSHOT_CSV}")
    report_lines.append(f"Log File: {LOG_FILE}")
    report_lines.append(f"Report File: {REPORT_FILE}")
    report_lines.append("")
    
    report_lines.append("=" * 80)
    report_lines.append("✅ END OF REPORT")
    report_lines.append("=" * 80)
    
    return "\n".join(report_lines)

def save_report(report_text: str):
    """Save report to text file"""
    try:
        os.makedirs('results', exist_ok=True)
        with open(REPORT_FILE, 'w', encoding='utf-8') as f:
            f.write(report_text)
        logger.info(f"📄 Report saved to: {REPORT_FILE}")
    except Exception as e:
        logger.error(f"❌ Failed to save report: {e}")

def send_discord_notification(report_summary: str):
    """Send summary report to Discord webhook"""
    if not DISCORD_WEBHOOK_URL:
        logger.debug("Discord webhook not configured, skipping notification")
        return
    
    try:
        # Create a shorter summary for Discord (2000 char limit)
        lines = report_summary.split('\n')
        
        # Extract key statistics
        discord_message = "📊 **GitHub Repository History Scraping Complete!**\n\n"
        
        # Add key metrics (find them in the report)
        for line in lines:
            if "Total Repositories Scraped:" in line or \
               "Scraping Duration:" in line or \
               "Total Stars Across All Repos:" in line or \
               "Average Stars Per Repo:" in line or \
               "New Pull Requests" in line or \
               "New Commits" in line or \
               "New Issues" in line:
                discord_message += f"{line.strip()}\n"
        
        discord_message += f"\n📄 Full report saved to: `{REPORT_FILE}`"
        
        # Send to Discord
        payload = {
            "content": discord_message,
            "username": "Repository History Bot"
        }
        
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        
        if response.status_code == 204:
            logger.info("✓ Discord notification sent successfully")
        else:
            logger.warning(f"⚠ Discord notification failed: {response.status_code}")
            
    except Exception as e:
        logger.warning(f"⚠ Failed to send Discord notification: {str(e)[:100]}")

def main():
    """Main execution function"""
    start_time = datetime.now()
    logger.info("="*80)
    logger.info("📊 GitHub Repository History Scraper Started")
    logger.info("="*80)
    logger.info(f"Scraping Frequency: {SCRAPING_FREQUENCY.upper()}")
    logger.info(f"Filter Mode: {'Affiliated Only' if FILTER_BY_AFFILIATION else 'All Repositories'}")
    
    # Clean up temporary snapshot file from previous runs
    if os.path.exists(TEMP_SNAPSHOT_CSV):
        try:
            os.remove(TEMP_SNAPSHOT_CSV)
            logger.info(f"🗑️  Removed previous temporary snapshot file")
        except Exception as e:
            logger.warning(f"⚠️  Could not remove temp file: {e}")
    
    # Initialize components
    token_manager = TokenManager()
    github_client = GitHubClient(token_manager)
    
    # Load repositories
    repositories = load_repositories()
    
    if not repositories:
        logger.error("❌ No repositories to process!")
        return
    
    filter_status = "with affiliation only" if FILTER_BY_AFFILIATION else "all repos"
    logger.info(f"🎯 Processing {len(repositories)} repositories ({filter_status}) with {MAX_WORKERS} workers")
    
    # Process repositories with threading
    all_results = []
    processed_count = 0
    error_count = 0
    
    logger.info(f"⚡ Starting ThreadPoolExecutor with {min(MAX_WORKERS, len(token_manager.tokens))} workers...")
    
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(token_manager.tokens))) as executor:
        # Submit all tasks
        future_to_repo = {
            executor.submit(get_star_history_snapshot, repo, github_client): repo
            for repo in repositories
        }
        
        # Process completed tasks
        for future in as_completed(future_to_repo):
            repo = future_to_repo[future]
            processed_count += 1
            
            try:
                result = future.result()
                if result:
                    all_results.append(result)
                
                # Log progress every 10 repositories
                if processed_count % 10 == 0:
                    progress = (processed_count / len(repositories)) * 100
                    stats = token_manager.get_stats()
                    
                    logger.info(f"📊 Progress: {processed_count}/{len(repositories)} ({progress:.1f}%) - "
                              f"Found: {len(all_results)} records - "
                              f"Errors: {error_count} - "
                              f"API requests: {stats['total_requests']}")
                
            except Exception as e:
                error_count += 1
                logger.error(f"❌ Error processing {repo['repo_owner']}/{repo['repo_name']}: {str(e)[:150]}")
    
    logger.info(f"✓ ThreadPoolExecutor completed all tasks")
    
    # Save results
    save_results(all_results)
    
    # Final statistics
    end_time = datetime.now()
    duration = end_time - start_time
    stats = token_manager.get_stats()
    
    logger.info("="*80)
    logger.info("✅ Repository History Scraping Completed!")
    logger.info("="*80)
    logger.info(f"⏱️  Duration: {duration}")
    logger.info(f"📊 Repositories processed: {processed_count}")
    logger.info(f"⭐ Star records collected: {len(all_results)}")
    logger.info(f"❌ Errors: {error_count}")
    logger.info(f"🔑 Total API requests: {stats['total_requests']}")
    logger.info(f"💾 Results saved to: {OUTPUT_CSV}")
    logger.info(f"📝 Log file: {LOG_FILE}")
    logger.info("="*80)
    
    # Generate and save report
    logger.info("📄 Generating comprehensive report...")
    report_text = generate_report(all_results, duration, stats)
    save_report(report_text)
    
    # Print summary to console
    if all_results:
        total_stars = sum(r.total_stars for r in all_results)
        total_forks = sum(r.total_forks for r in all_results)
        total_commits = sum(r.total_commits for r in all_results)
        avg_stars = total_stars / len(all_results)
        max_stars_repo = max(all_results, key=lambda r: r.total_stars)
        max_commits_repo = max(all_results, key=lambda r: r.total_commits)
        
        logger.info(f"\n📊 Repository Statistics:")
        logger.info(f"   Total stars across all repos: {total_stars:,}")
        logger.info(f"   Total forks across all repos: {total_forks:,}")
        logger.info(f"   Total commits across all repos: {total_commits:,}")
        logger.info(f"   Average stars per repo: {avg_stars:.0f}")
        logger.info(f"   Most starred repo: {max_stars_repo.repo_owner}/{max_stars_repo.repo_name} ({max_stars_repo.total_stars:,} stars)")
        logger.info(f"   Most active repo: {max_commits_repo.repo_owner}/{max_commits_repo.repo_name} ({max_commits_repo.total_commits:,} commits)")
    
    # Send Discord notification
    logger.info("📤 Sending Discord notification...")
    send_discord_notification(report_text)
    
    # Calculate and save week-by-week growth analysis
    if CALCULATE_GROWTH:
        logger.info("\n📈 Analyzing week-by-week growth trends...")
        growth_records = calculate_weekly_growth()
        
        if growth_records:
            save_growth_analysis(growth_records)
            growth_report = generate_growth_report(growth_records)
            print(growth_report)
            
            # Append growth analysis to main report
            growth_report_file = f"results/growth_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            try:
                with open(growth_report_file, 'w', encoding='utf-8') as f:
                    f.write(growth_report)
                logger.info(f"📄 Growth analysis report saved to: {growth_report_file}")
            except Exception as e:
                logger.error(f"❌ Failed to save growth report: {e}")
        else:
            logger.info("ℹ️ Not enough historical data for growth analysis (need at least 2 snapshots per repo)")
    
    # Clean up temporary snapshot file after processing
    if os.path.exists(TEMP_SNAPSHOT_CSV):
        try:
            os.remove(TEMP_SNAPSHOT_CSV)
            logger.info(f"🗑️  Removed temporary snapshot file")
        except Exception as e:
            logger.warning(f"⚠️  Could not remove temp file: {e}")
    
    logger.info(f"\n✅ All tasks completed! Report saved to: {REPORT_FILE}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("\n⚠️ Scraping interrupted by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        logger.debug(traceback.format_exc())
        raise
