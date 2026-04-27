"""Download test data from Yandex Disk."""

import requests
from pathlib import Path

# Yandex Disk public folder URL
YANDEX_DISK_URL = "https://disk.yandex.com/d/aGtcKCVEnii2bw"


def get_yandex_download_link(public_url: str) -> str:
    """
    Get direct download link from Yandex Disk public folder.
    
    Uses Yandex Disk API to get download links.
    """
    # Parse public key from URL
    public_key = public_url.split("/d/")[-1].split("?")[0]
    
    # API endpoint to get download link
    api_url = "https://cloud-api.yandex.net/v1/disk/public/resources"
    
    params = {
        "public_key": f"https://disk.yandex.com/d/{public_key}",
        "limit": 100
    }
    
    headers = {
        "Accept": "application/json"
    }
    
    response = requests.get(api_url, params=params, headers=headers)
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None
    
    data = response.json()
    
    # Extract items
    items = data.get("_embedded", {}).get("items", [])
    
    download_links = []
    for item in items:
        if item.get("type") == "file":
            file_name = item.get("name")
            file_url = item.get("file")  # Direct download link
            
            if file_url:
                download_links.append((file_name, file_url))
    
    return download_links


def download_file(url: str, output_path: Path, chunk_size: int = 8192):
    """Download file from URL."""
    response = requests.get(url, stream=True)
    response.raise_for_status()
    
    total_size = int(response.headers.get('content-length', 0))
    downloaded = 0
    
    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=chunk_size):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    progress = (downloaded / total_size) * 100
                    print(f"\rProgress: {progress:.1f}%", end="")
    
    print(f"\n✓ Downloaded: {output_path.name}")


def download_test_dataset(output_dir: Path = None):
    """
    Download test dataset from Yandex Disk.
    
    Note: Yandex Disk API has limitations for public folders.
    This function attempts to download using available methods.
    """
    if output_dir is None:
        output_dir = Path(__file__).parent.parent / "test_data"
    
    output_dir.mkdir(exist_ok=True)
    
    print("=" * 60)
    print("Unbake Test Data Downloader")
    print("=" * 60)
    print(f"\nTarget directory: {output_dir}")
    print(f"Source: {YANDEX_DISK_URL}")
    
    # Method 1: Try to get download links via API
    print("\nAttempting to fetch file list from Yandex Disk...")
    
    try:
        links = get_yandex_download_link(YANDEX_DISK_URL)
        
        if links:
            print(f"\n✓ Found {len(links)} files")
            
            for file_name, file_url in links:
                output_path = output_dir / file_name
                
                if output_path.exists():
                    print(f"\nSkipping {file_name} (already exists)")
                    continue
                
                print(f"\nDownloading {file_name}...")
                try:
                    download_file(file_url, output_path)
                except Exception as e:
                    print(f"✗ Error downloading {file_name}: {e}")
        else:
            print("\n⚠ Could not retrieve file list automatically.")
            print_manual_instructions(output_dir)
            
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print_manual_instructions(output_dir)


def print_manual_instructions(output_dir: Path):
    """Print manual download instructions."""
    print("\n" + "=" * 60)
    print("MANUAL DOWNLOAD INSTRUCTIONS")
    print("=" * 60)
    print(f"""
1. Open the Yandex Disk link in browser:
   {YANDEX_DISK_URL}

2. Download all files from the folder

3. Move downloaded files to:
   {output_dir}

4. Expected files:
   - Vocal tracks separated with htdemucs v4 (not ft!)
   - Files should be in m4a or mp3 format
   - Artifacts from separation are expected (this is the point!)

5. You'll also need to find ground truth lyrics for each track
   to properly evaluate recognition accuracy.

Alternative: Use your own test data
-------------------------------------
You can use any vocal tracks separated with htdemucs v4:
1. Install demucs: pip install demucs
2. Separate vocals: demucs --two-stems=vocals input.mp3
3. Use the vocals.wav file for testing
""")


def create_sample_test_data(output_dir: Path):
    """Create instructions for creating sample test data."""
    readme_path = output_dir / "README.md"
    
    content = """# Test Data

This directory should contain vocal tracks for testing the recognition system.

## Requirements

1. **Format**: m4a, mp3, or wav
2. **Source**: Demucs v4 (htdemucs, NOT htdemucs_ft)
3. **Content**: Vocal only (separated from backing track)
4. **Expected artifacts**: Yes, separation leaves artifacts on word boundaries

## How to create test data

### Option 1: Use your own music
```bash
# Install demucs
pip install demucs

# Separate vocals
demucs --two-stems=vocals your_song.mp3

# Result will be in: separated/htdemucs/your_song/vocals.wav
```

### Option 2: Download from Yandex Disk
Link: https://disk.yandex.com/d/aGtcKCVEnii2bw

Note: Files in the Yandex Disk are already separated with htdemucs v4.

## Ground Truth

For evaluation, you need ground truth lyrics. Create a file `ground_truth.json`:

```json
{
  "filename_without_extension": {
    "language": "en",
    "text": "actual lyrics here",
    "duration": 180
  }
}
```

## Supported Languages

The system supports: FR, IT, RU, EN, PT, ES, JP, PL
"""
    
    readme_path.write_text(content, encoding='utf-8')
    print(f"\n✓ Created {readme_path}")


def main():
    from config import TEST_DATA_DIR
    
    # Create README
    create_sample_test_data(TEST_DATA_DIR)
    
    # Try to download
    download_test_dataset(TEST_DATA_DIR)


if __name__ == "__main__":
    main()
