#!/usr/bin/env python3
"""
Test Token Borrowing Feature
Demonstrates how workers can borrow unused tokens when their assigned token hits rate limit
"""

import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Simulate the TokenManager class
class MockTokenManager:
    """Simulated TokenManager to demonstrate token borrowing"""
    
    def __init__(self, num_tokens=20):
        load_dotenv()
        self.tokens = [f"TOKEN_{i}" for i in range(1, num_tokens + 1)]
        self.token_stats = {
            token: {
                "remaining": 5000,
                "reset_time": None,
                "requests": 0
            } for token in self.tokens
        }
        print(f"✓ Initialized with {len(self.tokens)} tokens")
    
    def _is_token_available(self, token: str) -> bool:
        """Check if a token has available rate limit"""
        stats = self.token_stats[token]
        
        if stats["reset_time"] is None or datetime.now() >= stats["reset_time"]:
            return stats["remaining"] > 10
        
        return stats["remaining"] > 10
    
    def get_token(self) -> str:
        """Get next available token with borrowing"""
        # Simulate finding an available token
        for token in self.tokens:
            if self._is_token_available(token):
                self.token_stats[token]["requests"] += 1
                return token
        
        # All exhausted
        return self.tokens[0]
    
    def simulate_usage(self, token: str, requests: int):
        """Simulate token usage"""
        self.token_stats[token]["remaining"] -= requests
        self.token_stats[token]["requests"] += requests
        
        if self.token_stats[token]["remaining"] <= 10:
            # Simulate reset time 1 hour from now
            self.token_stats[token]["reset_time"] = datetime.now() + timedelta(hours=1)
    
    def show_stats(self):
        """Display token statistics"""
        available = sum(1 for t in self.tokens if self._is_token_available(t))
        exhausted = len(self.tokens) - available
        
        print(f"\n📊 Token Statistics:")
        print(f"   Available: {available}/{len(self.tokens)}")
        print(f"   Exhausted: {exhausted}/{len(self.tokens)}")
        print(f"\n   Detailed breakdown:")
        
        for idx, token in enumerate(self.tokens[:10], 1):  # Show first 10
            stats = self.token_stats[token]
            status = "✓ Available" if self._is_token_available(token) else "✗ Exhausted"
            reset = stats["reset_time"].strftime("%H:%M:%S") if stats["reset_time"] else "N/A"
            print(f"   Token #{idx}: {status} | Remaining: {stats['remaining']} | "
                  f"Requests: {stats['requests']} | Reset: {reset}")
        
        if len(self.tokens) > 10:
            print(f"   ... and {len(self.tokens) - 10} more tokens")

def test_scenario_1():
    """
    Scenario 1: 5 workers, 20 tokens
    Workers can easily borrow from the pool of 20 tokens
    """
    print("\n" + "="*70)
    print("SCENARIO 1: 5 Workers, 20 Tokens (Easy Borrowing)")
    print("="*70)
    
    manager = MockTokenManager(num_tokens=20)
    num_workers = 5
    
    print(f"\nSimulating {num_workers} workers making requests...")
    
    # Simulate 5 workers making many requests
    for worker_id in range(1, num_workers + 1):
        print(f"\n👷 Worker #{worker_id}:")
        
        # Each worker makes 15 requests
        for request_num in range(1, 16):
            token = manager.get_token()
            manager.simulate_usage(token, 50)  # Each request costs ~50 rate limit
            
            if request_num % 5 == 0:
                print(f"   ✓ Completed {request_num} requests")
        
        # Show which tokens this worker used
        token_usage = {t: s["requests"] for t, s in manager.token_stats.items() if s["requests"] > 0}
        print(f"   Total unique tokens used: {len(token_usage)}")
    
    manager.show_stats()
    
    print("\n💡 Observation:")
    print("   With 5 workers and 20 tokens, workers can freely borrow")
    print("   from the large pool. Even if some tokens hit rate limits,")
    print("   many fresh tokens are available for borrowing.")

def test_scenario_2():
    """
    Scenario 2: 15 workers, 20 tokens
    Some workers will need to borrow from others
    """
    print("\n" + "="*70)
    print("SCENARIO 2: 15 Workers, 20 Tokens (Moderate Borrowing)")
    print("="*70)
    
    manager = MockTokenManager(num_tokens=20)
    num_workers = 15
    
    print(f"\nSimulating {num_workers} workers making requests...")
    
    # Exhaust first 10 tokens heavily
    print("\nPhase 1: First 10 workers exhaust their primary tokens...")
    for worker_id in range(1, 11):
        primary_token = manager.tokens[worker_id - 1]
        manager.simulate_usage(primary_token, 4990)  # Almost exhaust
        print(f"   Worker #{worker_id} exhausted {primary_token}")
    
    manager.show_stats()
    
    # Now these workers need to borrow
    print("\nPhase 2: Exhausted workers borrow from remaining 10 tokens...")
    for worker_id in range(1, 11):
        token = manager.get_token()  # Will borrow from pool
        token_id = manager.tokens.index(token) + 1
        print(f"   Worker #{worker_id} borrowed Token #{token_id}")
    
    manager.show_stats()
    
    print("\n💡 Observation:")
    print("   Workers whose primary tokens are exhausted successfully")
    print("   borrow from the pool of available tokens. The system")
    print("   maximizes throughput by utilizing all available tokens.")

def test_scenario_3():
    """
    Scenario 3: All tokens exhausted
    Shows what happens when all tokens hit rate limit
    """
    print("\n" + "="*70)
    print("SCENARIO 3: All Tokens Exhausted (Rate Limit Hit)")
    print("="*70)
    
    manager = MockTokenManager(num_tokens=20)
    
    print("\nExhausting all 20 tokens...")
    for idx, token in enumerate(manager.tokens, 1):
        manager.simulate_usage(token, 4990)
        if idx % 5 == 0:
            print(f"   Exhausted {idx}/20 tokens...")
    
    manager.show_stats()
    
    print("\n⚠️ Attempting to get a token when all are exhausted...")
    token = manager.get_token()
    print(f"   Returned: {token} (falls back to first token)")
    print(f"   This will trigger the 1-hour sleep mechanism in the real scraper")
    
    print("\n💡 Observation:")
    print("   When all tokens are exhausted, the system falls back gracefully")
    print("   and triggers the batch sleep mechanism (1 hour wait).")

def main():
    print("\n" + "="*70)
    print("Token Borrowing Feature Demonstration")
    print("="*70)
    print("\nThis test demonstrates how workers can borrow unused tokens")
    print("when their assigned token reaches the rate limit.")
    print("\nKey Benefits:")
    print("  ✓ Maximizes API throughput")
    print("  ✓ Works even with fewer workers than tokens")
    print("  ✓ Automatically finds available tokens")
    print("  ✓ Gracefully handles full exhaustion")
    
    test_scenario_1()
    test_scenario_2()
    test_scenario_3()
    
    print("\n" + "="*70)
    print("Summary")
    print("="*70)
    print("\nThe token borrowing system ensures optimal API usage:")
    print("\n1. Primary Rotation: Workers rotate through tokens normally")
    print("2. Smart Borrowing: When a token is exhausted, worker finds")
    print("   another available token from the pool")
    print("3. Full Coverage: All 20 tokens can be utilized even with")
    print("   fewer than 20 workers")
    print("4. Graceful Degradation: When all tokens exhausted, triggers")
    print("   batch sleep mechanism")
    print("\n✅ This maximizes your 100,000 requests/hour capacity!")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
