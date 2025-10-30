import pandas as pd
import sys
import os
from datetime import datetime
from collections import Counter

# ============================
# CONFIGURATION
# ============================
CSV_FILE = r"results/political_emoji_commits.csv"  # CSV file to analyze
REPORT_FILE = r"results/csv_analysis_report.txt"  # Output report file

# ============================


def analyze_csv(csv_file, report_file):
    """
    Analyze CSV file and display key properties
    
    Args:
        csv_file: Path to CSV file
        report_file: Path to save the report
    """
    try:
        print(f"\n{'='*60}")
        print(f"CSV FILE ANALYSIS - Political Emoji Commits")
        print(f"{'='*60}")
        print(f"File: {csv_file}\n")
        
        # Load CSV
        print("📂 Loading CSV file...")
        df = pd.read_csv(csv_file, encoding='utf-8')
        
        print(f"✅ Successfully loaded!\n")
        
        # Prepare report output
        report = []
        report.append("="*80)
        report.append("POLITICAL EMOJI COMMITS - CSV ANALYSIS REPORT")
        report.append("="*80)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Source File: {csv_file}")
        report.append("="*80)
        report.append("")
        
        # 1. Column names
        print(f"{'='*60}")
        print(f"1. COLUMN NAMES ({len(df.columns)} columns)")
        print(f"{'='*60}")
        report.append("1. COLUMN NAMES")
        report.append("-" * 80)
        report.append(f"Total Columns: {len(df.columns)}")
        report.append("")
        for i, col in enumerate(df.columns, 1):
            print(f"   {i:2d}. {col}")
            report.append(f"   {i:2d}. {col}")
        report.append("")
        
        # 2. Total Records
        print(f"\n{'='*60}")
        print(f"2. TOTAL RECORDS")
        print(f"{'='*60}")
        print(f"   Total commit records: {len(df):,}")
        report.append("2. TOTAL RECORDS")
        report.append("-" * 80)
        report.append(f"Total commit records: {len(df):,}")
        report.append("")
        
        # 3. Unique Repositories
        print(f"\n{'='*60}")
        print(f"3. UNIQUE REPOSITORIES")
        print(f"{'='*60}")
        unique_repos = df.groupby(['repo_owner', 'repo_name']).size().reset_index(name='commits')
        unique_repos = unique_repos.sort_values('commits', ascending=False)
        print(f"   Total unique repositories: {len(unique_repos):,}")
        print(f"   Average commits per repo: {len(df) / len(unique_repos):.2f}")
        report.append("3. UNIQUE REPOSITORIES")
        report.append("-" * 80)
        report.append(f"Total unique repositories: {len(unique_repos):,}")
        report.append(f"Average commits per repo: {len(df) / len(unique_repos):.2f}")
        report.append("")
        report.append("Top 10 Repositories by Commit Count:")
        print(f"\n   Top 10 Repositories by Commit Count:")
        for idx, row in unique_repos.head(10).iterrows():
            print(f"      {row['repo_owner']}/{row['repo_name']}: {row['commits']} commits")
            report.append(f"   {row['repo_owner']}/{row['repo_name']}: {row['commits']} commits")
        report.append("")
        
        # 4. Emoji Statistics
        print(f"\n{'='*60}")
        print(f"4. EMOJI STATISTICS")
        print(f"{'='*60}")
        report.append("4. EMOJI STATISTICS")
        report.append("-" * 80)
        
        # Count individual emojis
        all_emojis = []
        for emojis_str in df['emojis_detected']:
            if pd.notna(emojis_str) and emojis_str:
                all_emojis.extend(emojis_str.split('|'))
        
        emoji_counts = Counter(all_emojis)
        total_emojis = sum(emoji_counts.values())
        unique_emojis = len(emoji_counts)
        
        print(f"   Total emoji occurrences: {total_emojis:,}")
        print(f"   Unique emojis found: {unique_emojis}")
        print(f"\n   Top 10 Most Used Emojis:")
        report.append(f"Total emoji occurrences: {total_emojis:,}")
        report.append(f"Unique emojis found: {unique_emojis}")
        report.append("")
        report.append("Top 10 Most Used Emojis:")
        
        for emoji, count in emoji_counts.most_common(10):
            percentage = (count / total_emojis) * 100
            print(f"      {emoji}: {count:,} ({percentage:.2f}%)")
            report.append(f"   {emoji}: {count:,} ({percentage:.2f}%)")
        report.append("")
        
        # 5. Pull Request Statistics
        print(f"\n{'='*60}")
        print(f"5. PULL REQUEST STATISTICS")
        print(f"{'='*60}")
        pr_count = df['is_pull_request'].sum()
        direct_count = len(df) - pr_count
        pr_percentage = (pr_count / len(df)) * 100
        print(f"   From Pull Requests: {pr_count:,} ({pr_percentage:.2f}%)")
        print(f"   Direct Commits: {direct_count:,} ({(100-pr_percentage):.2f}%)")
        report.append("5. PULL REQUEST STATISTICS")
        report.append("-" * 80)
        report.append(f"From Pull Requests: {pr_count:,} ({pr_percentage:.2f}%)")
        report.append(f"Direct Commits: {direct_count:,} ({(100-pr_percentage):.2f}%)")
        report.append("")
        
        # 6. Affiliation Analysis
        print(f"\n{'='*60}")
        print(f"6. AFFILIATION ANALYSIS")
        print(f"{'='*60}")
        report.append("6. AFFILIATION ANALYSIS")
        report.append("-" * 80)
        
        # DeepSeek
        deepseek_dist = df['deepseek_affiliation'].value_counts()
        print(f"\n   DeepSeek Affiliation:")
        report.append("DeepSeek Affiliation:")
        for value, count in deepseek_dist.items():
            percentage = (count / len(df)) * 100
            print(f"      {value}: {count:,} ({percentage:.2f}%)")
            report.append(f"   {value}: {count:,} ({percentage:.2f}%)")
        
        # ChatGPT/OpenAI
        chatgpt_dist = df['chatgpt_affiliation'].value_counts()
        print(f"\n   ChatGPT/OpenAI Affiliation:")
        report.append("")
        report.append("ChatGPT/OpenAI Affiliation:")
        for value, count in chatgpt_dist.items():
            percentage = (count / len(df)) * 100
            print(f"      {value}: {count:,} ({percentage:.2f}%)")
            report.append(f"   {value}: {count:,} ({percentage:.2f}%)")
        report.append("")
        
        # 7. Timeline Analysis
        print(f"\n{'='*60}")
        print(f"7. TIMELINE ANALYSIS")
        print(f"{'='*60}")
        report.append("7. TIMELINE ANALYSIS")
        report.append("-" * 80)
        
        # Convert to datetime
        df['commit_date'] = pd.to_datetime(df['commit_datetime'])
        df['year'] = df['commit_date'].dt.year
        
        earliest = df['commit_date'].min()
        latest = df['commit_date'].max()
        
        print(f"   Earliest commit: {earliest.strftime('%Y-%m-%d')}")
        print(f"   Latest commit: {latest.strftime('%Y-%m-%d')}")
        print(f"   Time span: {(latest - earliest).days} days")
        report.append(f"Earliest commit: {earliest.strftime('%Y-%m-%d')}")
        report.append(f"Latest commit: {latest.strftime('%Y-%m-%d')}")
        report.append(f"Time span: {(latest - earliest).days} days")
        report.append("")
        
        # Commits by year
        year_dist = df['year'].value_counts().sort_index()
        print(f"\n   Commits by Year:")
        report.append("Commits by Year:")
        for year, count in year_dist.items():
            print(f"      {int(year)}: {count:,}")
            report.append(f"   {int(year)}: {count:,}")
        report.append("")
        
        # 8. README File Distribution
        print(f"\n{'='*60}")
        print(f"8. README FILE DISTRIBUTION")
        print(f"{'='*60}")
        readme_dist = df['readme_file_path'].value_counts()
        print(f"   README file variations found:")
        report.append("8. README FILE DISTRIBUTION")
        report.append("-" * 80)
        report.append("README file variations found:")
        for readme, count in readme_dist.items():
            percentage = (count / len(df)) * 100
            print(f"      {readme}: {count:,} ({percentage:.2f}%)")
            report.append(f"   {readme}: {count:,} ({percentage:.2f}%)")
        report.append("")
        
        # 9. Top Authors
        print(f"\n{'='*60}")
        print(f"9. TOP AUTHORS")
        print(f"{'='*60}")
        author_dist = df['author_name'].value_counts().head(10)
        print(f"   Top 10 Authors by Commit Count:")
        report.append("9. TOP AUTHORS")
        report.append("-" * 80)
        report.append("Top 10 Authors by Commit Count:")
        for author, count in author_dist.items():
            print(f"      {author}: {count:,}")
            report.append(f"   {author}: {count:,}")
        report.append("")
        
        print(f"\n{'='*60}")
        print(f"✅ Analysis completed successfully!")
        print(f"{'='*60}\n")
        
        # Save report to file
        report.append("="*80)
        report.append("END OF REPORT")
        report.append("="*80)
        
        os.makedirs(os.path.dirname(report_file) if os.path.dirname(report_file) else 'results', exist_ok=True)
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report))
        
        print(f"📄 Report saved to: {report_file}\n")
        
        return True
        
    except FileNotFoundError:
        print(f"❌ Error: File not found - {csv_file}")
        print(f"   Please check the file path and try again.\n")
        return False
    except Exception as e:
        print(f"❌ Error analyzing CSV: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def main():
    """
    Main function
    """
    # Check if file is provided as command line argument
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    else:
        csv_file = CSV_FILE
    
    # Check if report file is provided
    if len(sys.argv) > 2:
        report_file = sys.argv[2]
    else:
        report_file = REPORT_FILE
    
    analyze_csv(csv_file, report_file)


if __name__ == "__main__":
    main()
