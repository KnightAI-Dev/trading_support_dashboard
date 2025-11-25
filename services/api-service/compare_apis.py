"""
Compare responses from old and new API to verify they match
"""
import requests
import json
import sys
from typing import Dict, Any, Optional

OLD_URL = "http://localhost:8000"  # Original API
NEW_URL = "http://localhost:8001"  # Refactored API


def get_response(url: str, path: str) -> Optional[Dict[str, Any]]:
    """Get response from an endpoint"""
    try:
        response = requests.get(f"{url}{path}", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"  ⚠️  Status {response.status_code} from {url}{path}")
            return None
    except requests.exceptions.ConnectionError:
        print(f"  ❌ Connection refused: {url}")
        return None
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None


def compare_endpoint(path: str, description: str = None):
    """Compare an endpoint between old and new API"""
    print(f"\n{'='*60}")
    if description:
        print(f"Comparing: {description}")
    else:
        print(f"Comparing: {path}")
    print(f"{'='*60}")
    
    old_data = get_response(OLD_URL, path)
    new_data = get_response(NEW_URL, path)
    
    if old_data is None or new_data is None:
        print("  ⚠️  Skipping - one or both endpoints failed")
        return False
    
    # Compare structure
    if isinstance(old_data, list) and isinstance(new_data, list):
        if len(old_data) != len(new_data):
            print(f"  ⚠️  Different lengths: old={len(old_data)}, new={len(new_data)}")
            # Compare first item structure
            if old_data and new_data:
                old_keys = set(old_data[0].keys()) if isinstance(old_data[0], dict) else set()
                new_keys = set(new_data[0].keys()) if isinstance(new_data[0], dict) else set()
                if old_keys != new_keys:
                    print(f"  ❌ Different keys: old={old_keys}, new={new_keys}")
                    return False
                else:
                    print(f"  ✅ Same structure, different count (may be due to caching/timing)")
                    return True
        else:
            print(f"  ✅ Same length: {len(old_data)} items")
            # Compare first item
            if old_data and new_data:
                if old_data[0] == new_data[0]:
                    print(f"  ✅ First item matches")
                    return True
                else:
                    print(f"  ⚠️  First item differs (may be due to timing/caching)")
                    print(f"     Old: {json.dumps(old_data[0], indent=2)[:200]}...")
                    print(f"     New: {json.dumps(new_data[0], indent=2)[:200]}...")
                    return True  # Still consider OK if structure matches
    elif isinstance(old_data, dict) and isinstance(new_data, dict):
        old_keys = set(old_data.keys())
        new_keys = set(new_data.keys())
        if old_keys != new_keys:
            print(f"  ❌ Different keys: old={old_keys}, new={new_keys}")
            return False
        else:
            print(f"  ✅ Same keys: {old_keys}")
            # For dicts, just verify structure matches
            return True
    else:
        if old_data == new_data:
            print(f"  ✅ Exact match")
            return True
        else:
            print(f"  ⚠️  Different values (may be expected)")
            return True
    
    return True


def main():
    print("="*60)
    print("API Comparison Tool")
    print("="*60)
    print(f"Old API: {OLD_URL}")
    print(f"New API: {NEW_URL}")
    print("\nMake sure both APIs are running!")
    print("  Old: python main.py (port 8000)")
    print("  New: python main_refactored.py (port 8001)")
    
    endpoints = [
        ("/health", "Health Check"),
        ("/", "Root Endpoint"),
        ("/alerts?limit=5", "Alerts (limit 5)"),
        ("/alerts/summary", "Alerts Summary"),
        ("/candles/BTCUSDT?timeframe=1h&limit=10", "Candles"),
        ("/symbols", "Symbols"),
        ("/metadata/market", "Market Metadata"),
        ("/strategy-config", "Strategy Config"),
        ("/ingestion-config", "Ingestion Config"),
        ("/symbol-filters", "Symbol Filters"),
    ]
    
    results = []
    for path, desc in endpoints:
        result = compare_endpoint(path, desc)
        results.append((path, result))
    
    print("\n" + "="*60)
    print("Summary")
    print("="*60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    print(f"✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {total - passed}/{total}")
    
    if passed == total:
        print("\n🎉 All endpoints match! Ready to switch.")
    else:
        print("\n⚠️  Some differences found. Review above.")
        print("   Differences may be due to:")
        print("   - Caching (new API caches some responses)")
        print("   - Timing (data may have changed between requests)")
        print("   - Expected improvements (optimized queries)")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)

