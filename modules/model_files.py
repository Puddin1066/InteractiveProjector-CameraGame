"""Fetches pre-trained model files on first use."""
import os
import urllib.request


def download_if_missing(path: str, url: str) -> None:
    if os.path.exists(path):
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    print(f"Downloading {os.path.basename(path)}...")
    partial_path = f"{path}.part"
    urllib.request.urlretrieve(url, partial_path)
    os.replace(partial_path, path)
