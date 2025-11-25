"""
Quick test script for refactored API
Tests all endpoints to verify they work correctly
"""
import requests
import json
import sys
from typing import Dict, Any

BASE_URL = "http://localhost:8001"  # Refactored API port


def test_endpoint(method: str, path: str, expected_status: int = 200, **kwargs) -> Dict[str, Any]:
    """Test an endpoint and return result"""
    url = f"{BASE_URL}{path}"
    try:
        if method.upper() == "GET":
            response = requests.get(url, **kwargs)
        elif method.upper() == "POST":
            response = requests.post(url, json=kwargs.get('json'), headers=kwargs.get('headers', {}))
        elif method.upper() == "PUT":
            response = requests.put(url, json=kwargs.get('json'), headers=kwargs.get('headers', {}))
        elif method.upper() == "DELETE":
            response = requests.delete(url, **kwargs)
        else:
            return {"error": f"Unsupported method: {method}"}
        
        result = {
            "status": "✅ PASS" if response.status_code == expected_status else "❌ FAIL",
            "status_code": response.status_code,
            "expected": expected_status,
            "path": path
        }
        
        try:
            result["data"] = response.json() if response.content else None
        except:
            result["data"] = response.text[:100] if response.text else None
        
        return result
    except requests.exceptions.ConnectionError:
        return {
            "status": "❌ ERROR",
            "error": "Connection refused - is the API running?",
            "path": path
        }
    except Exception as e:
        return {
            "status": "❌ ERROR",
            "error": str(e),
            "path": path
        }


def main():
    print("=" * 60)
    print("Testing Refactored API Service")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}\n")
    
    tests = [
        # Health checks
        ("GET", "/health", 200),
        ("GET", "/", 200),
        
        # Alerts
        ("GET", "/alerts?limit=5", 200),
        ("GET", "/alerts?symbol=BTCUSDT&limit=5", 200),
        ("GET", "/alerts/summary", 200),
        
        # Candles
        ("GET", "/candles/BTCUSDT?timeframe=1h&limit=10", 200),
        
        # Symbols
        ("GET", "/symbols", 200),
        
        # Metadata
        ("GET", "/metadata/market", 200),
        
        # Config
        ("GET", "/strategy-config", 200),
        ("GET", "/ingestion-config", 200),
        
        # Symbol filters
        ("GET", "/symbol-filters", 200),
        ("GET", "/symbol-filters?filter_type=whitelist", 200),
    ]
    
    results = []
    for method, path, expected in tests:
        print(f"Testing {method} {path}...", end=" ")
        result = test_endpoint(method, path, expected)
        results.append(result)
        print(result["status"])
        if "error" in result:
            print(f"  Error: {result['error']}")
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for r in results if r["status"] == "✅ PASS")
    failed = sum(1 for r in results if r["status"] == "❌ FAIL")
    errors = sum(1 for r in results if r["status"] == "❌ ERROR")
    
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"⚠️  Errors: {errors}")
    print(f"Total: {len(results)}")
    
    if failed > 0 or errors > 0:
        print("\nFailed/Error Details:")
        for r in results:
            if r["status"] != "✅ PASS":
                print(f"  {r['path']}: {r.get('error', f"Status {r['status_code']}, expected {r['expected']}")}")
        sys.exit(1)
    else:
        print("\n🎉 All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()

