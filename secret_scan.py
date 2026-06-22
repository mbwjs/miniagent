#!/usr/bin/env python3
"""Pre-commit secret scanner — blocks commits containing API keys, tokens, private keys."""
import sys, json, re, subprocess
from pathlib import Path

# ── Patterns to detect ────────────────────────────
PATTERNS = [
    # AWS keys
    (r'(?:AKIA|ASIA)[A-Z0-9]{16}', 'AWS Access Key'),
    # GitHub tokens
    (r'(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}', 'GitHub Token'),
    (r'github_pat_[A-Za-z0-9_]{22,}', 'GitHub PAT'),
    # Private keys
    (r'-----BEGIN (?:RSA|OPENSSH|EC|DSA|PGP) PRIVATE KEY-----', 'Private Key Block'),
    # Generic API keys/secrets
    (r'(?:api_key|apikey|secret|token|password|passwd)\s*[:=]\s*["\'](?!your_|example_|test_|demo_|xxxx|changeme|placeholder|xxx|TODO)([A-Za-z0-9_\-+=\/]{20,})["\']', 'API Key/Token in code'),
    # JWT tokens
    (r'eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+', 'JWT Token'),
    # OpenAI keys
    (r'sk-(?:proj-)?[A-Za-z0-9\-_]{20,}', 'OpenAI API Key'),
    # Anthropic keys
    (r'sk-ant-[A-Za-z0-9\-_]{20,}', 'Anthropic API Key'),
    # SSH private key references
    (r'-----BEGIN (?:RSA|OPENSSH|EC|DSA) PRIVATE KEY-----', 'SSH Private Key'),
]

# Files/directories to skip entirely
SKIP_PATHS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', '.DS_Store'}
SKIP_FILES = {'package-lock.json', 'yarn.lock', 'poetry.lock', '.gitignore', '.dockerignore'}

def should_skip(path):
    import fnmatch
    parts = path.replace('\\', '/').split('/')
    for part in parts:
        if part in SKIP_PATHS:
            return True
    filename = parts[-1] if parts else ''
    if filename in SKIP_FILES:
        return True
    for skip in SKIP_PATHS:
        if '*' in skip and fnmatch.fnmatch(filename, skip):
            return True
    return False

def scan_files(repo_path, files):
    """Scan specific files (full content) for secrets."""
    findings = []
    for f in files:
        if should_skip(f):
            continue
        filepath = Path(repo_path) / f
        if not filepath.exists():
            continue
        try:
            content = filepath.read_text(encoding='utf-8', errors='ignore')
        except:
            continue
        for lineno, line in enumerate(content.splitlines(), 1):
            for pattern, label in PATTERNS:
                m = re.search(pattern, line, re.IGNORECASE)
                if m:
                    match_val = m.group(0)
                    if len(match_val) > 40:
                        match_val = match_val[:20] + '...' + match_val[-10:]
                    findings.append(f"{label}: {match_val}  in {f}:{lineno}")
                    break
    return findings

if __name__ == '__main__':
    try:
        ctx = json.loads(sys.stdin.read())
    except:
        ctx = {}

    event = ctx.get('event', '')
    tool_input = ctx.get('tool_input', {})
    command = tool_input.get('command', '')
    tool_name = ctx.get('tool_name', '')

    # When to scan:
    is_git_cmd = 'git commit' in command or 'git add' in command
    is_post_write = event == 'PostToolUse' and tool_name in ('write', 'edit')

    if not is_git_cmd and not is_post_write:
        sys.exit(0)

    # Determine repo
    repo_path = '/root/miniagent'
    if 'aipulse' in command or '/root/aipulse' in command:
        repo_path = '/root/aipulse'
    if is_post_write:
        filepath = tool_input.get('path', '')
        if 'aipulse' in filepath:
            repo_path = '/root/aipulse'

    # For PreToolUse (git about to run): scan staged changes
    # For PostToolUse (write/edit just happened): scan the written file
    if is_post_write:
        target = tool_input.get('path', '')
        if target:
            # Make path relative to repo
            try:
                target = str(Path(target).relative_to(repo_path))
            except ValueError:
                pass
            files_to_scan = [target]
        else:
            files_to_scan = []
    else:
        # Staged files
        r = subprocess.run(
            ['git', '-C', repo_path, 'diff', '--cached', '--name-only'],
            capture_output=True, text=True, timeout=5
        )
        files_to_scan = [f.strip() for f in r.stdout.splitlines() if f.strip()]

    findings = scan_files(repo_path, files_to_scan)

    if findings:
        print(f"🚫 SECRET DETECTION: {len(findings)} potential secrets in staged changes:")
        for f in findings:
            print(f"  • {f}")
        print(f"\nCommit blocked. Remove secrets from files before committing.")
        print(f"Repo: {repo_path}")
        sys.exit(2)
    else:
        sys.exit(0)
