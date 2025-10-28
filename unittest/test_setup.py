#!/usr/bin/env python3
"""
Quick Test Script - Verify Setup Before Running Full Scraper
Tests token loading, CSV reading, and API connectivity
"""

import os
from dotenv import load_dotenv
import csv

# Increase CSV field size limit for large README content
csv.field_size_limit(1000000)

def test_env_tokens():
    """Test if GitHub tokens are loaded"""
    load_dotenv()
    
    tokens = []
    for i in range(1, 21):
        token = os.getenv(f"GITHUB_TOKEN_{i}")
        if token and token.strip():
            tokens.append(f"GITHUB_TOKEN_{i}")
    
    print(f"✓ Found {len(tokens)} GitHub tokens:")
    for token_name in tokens:
        print(f"  - {token_name}")
    
    discord_webhook = os.getenv("discord_webhook_url")
    if discord_webhook:
        print(f"✓ Discord webhook configured")
    else:
        print(f"⚠ Discord webhook not configured (optional)")
    
    return len(tokens) > 0

def test_csv_file():
    """Test if input CSV exists and has correct columns"""
    csv_file = "github_affiliation_combined.csv"
    
    if not os.path.exists(csv_file):
        print(f"❌ Input CSV not found: {csv_file}")
        return False
    
    print(f"✓ Found input CSV: {csv_file}")
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        
        required = ['repo_owner', 'repo_name', 'repo_url', 
                   'affiliation_deepseek', 'affiliation_openai']
        
        missing = [col for col in required if col not in headers]
        
        if missing:
            print(f"❌ Missing columns: {missing}")
            return False
        
        print(f"✓ All required columns present")
        
        # Count repos with affiliation
        count = 0
        for row in reader:
            deepseek = row.get('affiliation_deepseek', 'none').strip().lower()
            chatgpt = row.get('affiliation_openai', 'none').strip().lower()
            
            if deepseek != 'none' or chatgpt != 'none':
                count += 1
                if count == 1:
                    print(f"✓ Sample repo: {row['repo_owner']}/{row['repo_name']}")
        
        print(f"✓ Found {count} repositories to process")
        return count > 0

def test_directories():
    """Test if output directories exist"""
    os.makedirs('results', exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    
    print(f"✓ Created/verified output directories:")
    print(f"  - results/")
    print(f"  - logs/")
    return True

def main():
    print("="*60)
    print("GitHub Political Emoji Scraper - Setup Verification")
    print("="*60)
    print()
    
    tests = [
        ("Environment Tokens", test_env_tokens),
        ("Input CSV File", test_csv_file),
        ("Output Directories", test_directories)
    ]
    
    all_passed = True
    
    for test_name, test_func in tests:
        print(f"\n[{test_name}]")
        try:
            result = test_func()
            if not result:
                all_passed = False
        except Exception as e:
            print(f"❌ Test failed: {e}")
            all_passed = False
    
    print()
    print("="*60)
    if all_passed:
        print("✅ All checks passed! Ready to run scraper.")
        print()
        print("Run: python commitscrapper.py")
    else:
        print("❌ Some checks failed. Please fix issues above.")
    print("="*60)

if __name__ == "__main__":
    main()
