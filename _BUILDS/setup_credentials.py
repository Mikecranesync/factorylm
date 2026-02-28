#!/usr/bin/env python3
"""Interactive credential setup for FactoryLM desktop apps.

Checks for an existing GitHub token (env, gh CLI, keyring) and
offers to store one if missing.  Non-destructive — never removes
existing credentials.

Usage:
    python _BUILDS/setup_credentials.py
"""

from __future__ import annotations

import os
import sys

# Allow importing token_loader from _BUILDS/shared/
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "shared"))

from token_loader import load_github_token, _try_gh_cli, _try_keyring, save_to_keyring  # noqa: E402


def main() -> None:
    print("=" * 55)
    print("  FactoryLM — GitHub Credential Setup")
    print("=" * 55)
    print()

    # ── Check existing sources ──
    env_token = os.environ.get("GITHUB_TOKEN", "").strip()
    gh_token = _try_gh_cli()
    kr_token = _try_keyring()

    print("Token sources found:")
    print(f"  .env / GITHUB_TOKEN env var : {'YES' if env_token and env_token != 'your_token_here' else 'no'}")
    print(f"  gh CLI (gh auth token)      : {'YES' if gh_token else 'no'}")
    print(f"  Python keyring              : {'YES' if kr_token else 'no'}")
    print()

    best = load_github_token()
    if best:
        masked = best[:8] + "..." + best[-4:] if len(best) > 12 else best[:4] + "..."
        print(f"Active token: {masked}")
        print("You're all set! The scraper will use this token automatically.")
        print()

        # Offer to also store in keyring as backup
        if not kr_token and best != kr_token:
            try:
                import keyring  # noqa: F401
                ans = input("Also save to system keyring as backup? [y/N] ").strip().lower()
                if ans == "y":
                    if save_to_keyring(best):
                        print("Saved to keyring.")
                    else:
                        print("Could not save to keyring.")
            except ImportError:
                print("(keyring package not installed — skipping keyring backup)")
        return

    # ── No token found — guide user ──
    print("No GitHub token found.")
    print()
    print("Option 1 (recommended): Install and authenticate the GitHub CLI")
    print("  > winget install GitHub.cli")
    print("  > gh auth login")
    print("  (This stores the token in Windows Credential Manager)")
    print()
    print("Option 2: Paste a Personal Access Token (PAT)")
    print("  Create one at: https://github.com/settings/tokens")
    print("  Required scopes: repo (read-only is fine)")
    print()

    ans = input("Paste a PAT now, or press Enter to skip: ").strip()
    if not ans:
        print("Skipped. The scraper will run in DEMO_MODE without a token.")
        return

    # Validate the token
    try:
        import httpx
        resp = httpx.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {ans}"},
            timeout=10,
        )
        if resp.status_code == 200:
            login = resp.json().get("login", "unknown")
            print(f"Token valid! Authenticated as: {login}")
        else:
            print(f"Token returned HTTP {resp.status_code} — may not work.")
            confirm = input("Save anyway? [y/N] ").strip().lower()
            if confirm != "y":
                print("Aborted.")
                return
    except Exception as exc:
        print(f"Could not verify token ({exc}). Saving anyway...")

    # Save to keyring if available
    try:
        import keyring  # noqa: F401
        if save_to_keyring(ans):
            print("Token saved to system keyring.")
        else:
            print("Could not save to keyring.")
    except ImportError:
        pass

    # Save to _BUILDS/github-scraper/.env
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "github-scraper", ".env")
    if os.path.isfile(env_path):
        print(f"Note: {env_path} already exists — not overwriting.")
        print(f"  To update it manually, set GITHUB_TOKEN={ans[:8]}...")
    else:
        with open(env_path, "w") as f:
            f.write(f"GITHUB_TOKEN={ans}\n")
            f.write("CACHE_PATH=\n")
            f.write("GITHUB_ORG=Mikecranesync\n")
            f.write("DEMO_MODE=false\n")
        print(f"Written to {env_path}")

    print()
    print("Done. Run the scraper with: python _BUILDS/github-scraper/main.py")


if __name__ == "__main__":
    main()
