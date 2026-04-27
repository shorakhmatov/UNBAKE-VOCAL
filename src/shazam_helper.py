"""
ShazamKit helper for ground truth extraction.

ShazamKit can be used to:
1. Identify the song from a snippet
2. Get original lyrics (via external API)
3. Use as reference for evaluation

Note: This is a conceptual implementation showing how ShazamKit
would be integrated with the iOS app for ground truth retrieval.
"""

import requests
from typing import Optional, Dict, Tuple


class ShazamKitHelper:
    """
    Helper class for ShazamKit integration.
    
    In production iOS app:
    - ShazamKit runs on-device
    - Returns song metadata
    - We use metadata to fetch lyrics from external API
    """
    
    def __init__(self):
        # ShazamKit doesn't require API key for basic usage
        # But for server-side matching, we'd use Shazam API
        self.base_url = "https://api.shazam.com"
        # Note: Requires API key for production use
        self.api_key = None
    
    def identify_song(self, audio_snippet_path: str) -> Optional[Dict]:
        """
        Identify song from audio snippet.
        
        In iOS app:
        ```swift
        let session = SHSession()
        session.delegate = self
        // Send audio buffer to session
        ```
        
        Server-side fallback using Shazam API:
        """
        if not self.api_key:
            print("Warning: Shazam API key not set. Using mock response.")
            return self._mock_identify(audio_snippet_path)
        
        # Actual implementation would POST audio fingerprint
        # to Shazam API and get song metadata
        pass
    
    def _mock_identify(self, audio_path: str) -> Dict:
        """Mock identification for testing."""
        return {
            "track": {
                "title": "Sample Song",
                "artist": "Sample Artist",
                "album": "Sample Album",
                "key": "sample-key-123"
            },
            "confidence": 0.95
        }
    
    def fetch_lyrics(self, song_key: str) -> Optional[str]:
        """
        Fetch lyrics for identified song.
        
        Options:
        1. Genius API (requires key, has rate limits)
        2. LRCLIB (free, open source lyrics)
        3. Musixmatch (requires commercial license)
        
        This is conceptual - actual implementation would
        integrate with lyrics API.
        """
        # Try LRCLIB first (free)
        lyrics = self._fetch_from_lrclib(song_key)
        if lyrics:
            return lyrics
        
        # Fallback to other sources
        return None
    
    def _fetch_from_lrclib(self, song_key: str) -> Optional[str]:
        """Fetch lyrics from LRCLIB.net (open source)."""
        # LRCLIB API: https://lrclib.net/docs
        # Free, no auth required
        
        try:
            # This is a placeholder - actual implementation
            # would search by track/artist name
            url = f"https://lrclib.net/api/get/{song_key}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get("plainLyrics")
        except Exception as e:
            print(f"LRCLIB fetch failed: {e}")
        
        return None
    
    def match_transcription_with_lyrics(
        self, 
        transcribed_text: str, 
        original_lyrics: str
    ) -> Tuple[float, Dict]:
        """
        Match transcribed text with original lyrics.
        
        Used for:
        1. Validation (is this a cover or original?)
        2. Quality scoring (how close to original?)
        3. Alignment (find corresponding timestamps)
        
        Returns:
            (similarity_score, details)
        """
        from difflib import SequenceMatcher
        from evaluator import TextNormalizer
        
        normalizer = TextNormalizer()
        
        # Normalize both texts
        trans_norm = normalizer.normalize(transcribed_text)
        lyrics_norm = normalizer.normalize(original_lyrics)
        
        # Calculate similarity
        similarity = SequenceMatcher(None, trans_norm, lyrics_norm).ratio()
        
        # Determine if it's a cover or original
        is_cover = similarity < 0.8  # Threshold
        
        details = {
            "similarity_score": similarity,
            "is_cover": is_cover,
            "is_instrumental": len(trans_norm) < 10,
            "transcribed_words": len(trans_norm.split()),
            "original_words": len(lyrics_norm.split())
        }
        
        return similarity, details


def create_ground_truth_dataset(
    audio_files: list,
    output_path: str
):
    """
    Create ground truth dataset using ShazamKit + Lyrics API.
    
    Workflow:
    1. For each audio file:
       a. Identify song with ShazamKit
       b. Fetch original lyrics
       c. Store in dataset
    2. Manual verification for covers
    3. Export as JSON
    
    Note: This requires manual verification because:
    - Covers have different lyrics
    - Instrumentals have no lyrics
    - Live versions differ from studio
    """
    import json
    
    shazam = ShazamKitHelper()
    dataset = {}
    
    for audio_path in audio_files:
        print(f"Processing: {audio_path}")
        
        # Identify
        song_info = shazam.identify_song(audio_path)
        
        if song_info:
            # Fetch lyrics
            lyrics = shazam.fetch_lyrics(song_info["track"]["key"])
            
            if lyrics:
                dataset[audio_path] = {
                    "song_info": song_info,
                    "lyrics": lyrics,
                    "verified": False  # Requires manual check
                }
    
    # Save
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)
    
    print(f"Dataset saved to: {output_path}")
    print(f"Total entries: {len(dataset)}")
    print("⚠ Please verify covers and instrumentals manually!")


if __name__ == "__main__":
    # Example usage
    print("ShazamKit Helper - Conceptual Implementation")
    print("=" * 50)
    print("""
This module demonstrates how ShazamKit would be integrated:

iOS App Flow:
1. User records/sends audio
2. ShazamKit identifies song (on-device, free)
3. App fetches original lyrics
4. Lyrics sent to API as ground truth
5. API returns transcription quality metrics

Server-Side Evaluation:
- Use Shazam API for batch identification
- Match with lyrics databases
- Calculate similarity scores
- Flag covers for manual review

Note: Actual ShazamKit integration requires:
- iOS app with ShazamKit framework
- Apple Developer account
- Server-side Shazam API key for batch processing
    """)
