"""Test Cosmos Reason2-8B via NVIDIA NIM API and/or vLLM."""

import base64
import json
import os
import sys

import requests

# --- Configuration ---
# Option A: NVIDIA NIM API (hosted)
NIM_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NIM_KEY = os.environ.get("NVIDIA_API_KEY_NEW", "")

# Option B: Vast.ai vLLM (self-hosted)
VLLM_URL = os.environ.get("VLLM_URL", "http://localhost:8000/v1/chat/completions")  # SSH tunnel to Vast.ai


def encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def test_nim_api(image_path: str | None = None):
    """Test Cosmos R2 via NVIDIA NIM API."""
    print("=" * 60)
    print("Testing NVIDIA NIM API (build.nvidia.com)")
    print("=" * 60)

    if not NIM_KEY:
        print("ERROR: NVIDIA_API_KEY_NEW not set")
        return False

    headers = {
        "Authorization": f"Bearer {NIM_KEY}",
        "Content-Type": "application/json",
    }

    # Build message content
    user_content = []

    if image_path:
        ext = image_path.rsplit(".", 1)[-1].lower()
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(ext, "image/jpeg")
        b64 = encode_image(image_path)
        user_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}"},
        })

    user_content.append({
        "type": "text",
        "text": (
            "Describe what you see in this image. "
            "Answer using the following format: "
            "<think>Your reasoning about what you observe.</think> "
            "Then provide your description."
        ),
    })

    payload = {
        "model": "nvidia/cosmos-reason2-8b",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": user_content},
        ],
        "max_tokens": 2048,
        "temperature": 0.6,
        "top_p": 0.95,
    }

    print(f"\nSending request to {NIM_URL}...")
    print(f"Image: {image_path or 'none (text-only)'}")

    try:
        r = requests.post(NIM_URL, headers=headers, json=payload, timeout=120)
        print(f"Status: {r.status_code}")

        if r.status_code == 200:
            data = r.json()
            msg = data["choices"][0]["message"]["content"]
            print(f"\n--- Cosmos R2 Response ---")
            print(msg)
            print(f"\nTokens: {data.get('usage', {})}")
            return True
        else:
            print(f"Error: {r.text[:500]}")
            return False
    except Exception as e:
        print(f"Exception: {e}")
        return False


def test_vllm_api(image_path: str | None = None):
    """Test Cosmos R2 via self-hosted vLLM."""
    print("=" * 60)
    print("Testing vLLM API (self-hosted)")
    print("=" * 60)

    if not VLLM_URL:
        print("VLLM_URL not set, skipping")
        return False

    headers = {"Content-Type": "application/json"}

    user_content = []

    if image_path:
        ext = image_path.rsplit(".", 1)[-1].lower()
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(ext, "image/jpeg")
        b64 = encode_image(image_path)
        user_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}"},
        })

    user_content.append({
        "type": "text",
        "text": (
            "Describe what you see in this image. "
            "Answer using the following format: "
            "<think>Your reasoning about what you observe.</think> "
            "Then provide your description."
        ),
    })

    payload = {
        "model": "nvidia/Cosmos-Reason2-8B",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": user_content},
        ],
        "max_tokens": 2048,
        "temperature": 0.6,
        "top_p": 0.95,
    }

    print(f"\nSending request to {VLLM_URL}...")

    try:
        r = requests.post(VLLM_URL, headers=headers, json=payload, timeout=120)
        print(f"Status: {r.status_code}")

        if r.status_code == 200:
            data = r.json()
            msg = data["choices"][0]["message"]["content"]
            print(f"\n--- Cosmos R2 Response ---")
            print(msg)
            return True
        else:
            print(f"Error: {r.text[:500]}")
            return False
    except Exception as e:
        print(f"Exception: {e}")
        return False


if __name__ == "__main__":
    image = sys.argv[1] if len(sys.argv) > 1 else None

    if not image:
        print("Usage: python cosmos_test.py [image_path]")
        print("Will test with text-only if no image provided.\n")

    # Try NIM API first
    nim_ok = test_nim_api(image)
    print()

    # Try vLLM if configured
    vllm_ok = test_vllm_api(image)

    print("\n" + "=" * 60)
    print(f"NIM API:  {'OK' if nim_ok else 'FAIL'}")
    print(f"vLLM API: {'OK' if vllm_ok else 'N/A' if not VLLM_URL else 'FAIL'}")
