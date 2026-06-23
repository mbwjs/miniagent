#!/usr/bin/env python3
"""Check DeepSeek API balance. Exit 0 = ok, 1 = low balance, 2 = error.
Reads ANTHROPIC_API_KEY from env, calls /user/balance endpoint.
Also reads JSON from stdin if called as hook (ignores it).
"""
import os, sys, json, urllib.request, urllib.error

THRESHOLD = 1.00  # CNY — warn below this

def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic")
    
    # Derive balance endpoint from base_url
    if "deepseek.com" in base_url:
        balance_url = "https://api.deepseek.com/user/balance"
    else:
        # Not DeepSeek — skip check
        print("⚠️  Not DeepSeek, balance check skipped")
        sys.exit(0)
    
    try:
        req = urllib.request.Request(balance_url, headers={"Authorization": f"Bearer {api_key}"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"❌ Balance API HTTP {e.code}: {e.reason}")
        sys.exit(2)
    except Exception as e:
        print(f"❌ Balance check failed: {e}")
        sys.exit(2)
    
    if not data.get("is_available"):
        print("🚫 Account unavailable!")
        sys.exit(2)
    
    for info in data.get("balance_infos", []):
        currency = info.get("currency", "?")
        total = float(info.get("total_balance", 0))
        granted = float(info.get("granted_balance", 0))
        topped_up = float(info.get("topped_up_balance", 0))
        
        print(f"💰 DeepSeek 余额: {total:.2f} {currency} (充值: {topped_up:.2f}, 赠送: {granted:.2f})")
        
        if total <= THRESHOLD:
            print(f"⚠️  ⚠️  ⚠️  余额不足 {THRESHOLD:.0f} 元！请尽快充值！⚠️  ⚠️  ⚠️")
            sys.exit(1)  # non-zero but not blocking (hook doesn't block on 1)
        else:
            print(f"✅ 余额充足 (>{THRESHOLD:.0f} {currency})")
    
    sys.exit(0)

if __name__ == "__main__":
    main()
