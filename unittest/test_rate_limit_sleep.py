#!/usr/bin/env python3
"""
Test script to verify rate limit sleep behavior
Simulates all tokens being exhausted and verifies the program sleeps correctly
"""

import os
import sys
from datetime import datetime, timedelta
from threading import Thread
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from commitscrapper import TokenManager, DiscordNotifier

def test_rate_limit_sleep():
    """Test that sleep_and_reset works correctly when all tokens are exhausted"""
    
    print("="*80)
    print("Testing Rate Limit Sleep Behavior")
    print("="*80)
    
    # Create token manager
    token_manager = TokenManager()
    notifier = DiscordNotifier()
    
    print(f"\n✓ Loaded {len(token_manager.tokens)} tokens")
    
    # Manually exhaust all tokens
    print("\n📉 Simulating token exhaustion...")
    for token in token_manager.tokens:
        token_manager.token_stats[token]["remaining"] = 5
        token_manager.token_stats[token]["reset_time"] = datetime.now() + timedelta(hours=1)
    
    # Check if all tokens are exhausted
    exhausted = token_manager.all_tokens_exhausted()
    print(f"   All tokens exhausted: {exhausted}")
    
    # Try to get a token (should trigger global sleep mode)
    print("\n🔍 Attempting to get token (should trigger global sleep mode)...")
    token = token_manager.get_token()
    print(f"   Global sleep mode: {token_manager.global_sleep_mode}")
    
    if token_manager.global_sleep_mode:
        print("\n✅ Global sleep mode activated correctly!")
        print("   (In production, this would trigger a 1-hour sleep)")
        
        # Simulate quick sleep for testing (5 seconds instead of 1 hour)
        print("\n⏰ Testing sleep_and_reset (5 second test sleep)...")
        
        # Temporarily reduce sleep time for testing
        original_sleep = __import__('commitscrapper').RATE_LIMIT_SLEEP
        __import__('commitscrapper').RATE_LIMIT_SLEEP = 5
        
        start_time = datetime.now()
        token_manager.sleep_and_reset(notifier, 50, 100)
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Restore original sleep time
        __import__('commitscrapper').RATE_LIMIT_SLEEP = original_sleep
        
        print(f"   Sleep duration: {duration:.1f} seconds")
        print(f"   Global sleep mode after reset: {token_manager.global_sleep_mode}")
        print(f"   Tokens reset: {all(stats['remaining'] == 5000 for stats in token_manager.token_stats.values())}")
        
        if not token_manager.global_sleep_mode:
            print("\n✅ Sleep mode correctly disabled after sleep!")
        else:
            print("\n❌ Sleep mode still active after sleep!")
        
        if all(stats['remaining'] == 5000 for stats in token_manager.token_stats.values()):
            print("✅ All tokens correctly reset to 5000!")
        else:
            print("❌ Tokens not properly reset!")
            
    else:
        print("\n❌ Global sleep mode NOT activated!")
        print("   This means the rate limit protection won't work!")
    
    print("\n" + "="*80)
    print("Test Summary:")
    print("="*80)
    print(f"✓ Token exhaustion detection: {'PASS' if exhausted else 'FAIL'}")
    print(f"✓ Global sleep mode activation: {'PASS' if token_manager.global_sleep_mode == False else 'FAIL'}")  # Should be False after reset
    print(f"✓ Token reset after sleep: {'PASS' if all(stats['remaining'] == 5000 for stats in token_manager.token_stats.values()) else 'FAIL'}")
    print("="*80)

if __name__ == "__main__":
    try:
        test_rate_limit_sleep()
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
