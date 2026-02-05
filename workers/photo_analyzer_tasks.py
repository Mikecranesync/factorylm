"""
PHOTO ANALYZER - Celery Tasks
==============================
Analyzes synced photos using Gemini Vision.
Indexes industrial equipment, safety hazards, and site conditions.
"""

import os
import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import base64

sys.path.insert(0, '/opt/master_of_puppets')
from celery_app import app
from workers.base_worker import BaseAgent, with_token_tracking, with_celery_tracing
from observability import traced, track_llm_call, track_api_call

# Paths
PHOTOS_DIR = Path("/opt/factorylm-sync/photos")
STATE_DIR = Path("/opt/master_of_puppets/state")
STATE_DIR.mkdir(exist_ok=True)
ANALYZED_STATE = STATE_DIR / "photo_analysis_state.json"
ANALYSIS_OUTPUT = Path("/opt/factorylm-sync/automatons-output/photo-analysis")
ANALYSIS_OUTPUT.mkdir(parents=True, exist_ok=True)

# Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")


class PhotoAnalyzer(BaseAgent):
    """Analyzes industrial photos using Gemini Vision."""
    
    def __init__(self):
        super().__init__("PhotoAnalyzer")
        self._init_state()
    
    def _init_state(self):
        if not ANALYZED_STATE.exists():
            state = {
                "analyzed_photos": {},  # hash -> analysis
                "total_analyzed": 0,
                "last_scan": None,
            }
            self._save_state(state)
    
    def _load_state(self) -> Dict:
        try:
            with open(ANALYZED_STATE, 'r') as f:
                return json.load(f)
        except:
            self._init_state()
            return self._load_state()
    
    def _save_state(self, state: Dict):
        with open(ANALYZED_STATE, 'w') as f:
            json.dump(state, f, indent=2, default=str)
    
    def _get_file_hash(self, filepath: Path) -> str:
        """Get MD5 hash of file for deduplication."""
        with open(filepath, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def _analyze_with_gemini(self, image_path: Path) -> Optional[Dict]:
        """Analyze image using Gemini Vision API."""
        if not GEMINI_API_KEY:
            self.logger.warning("GEMINI_API_KEY not set")
            return None
        
        try:
            import requests
            
            # Read and encode image
            with open(image_path, 'rb') as f:
                image_data = base64.standard_b64encode(f.read()).decode('utf-8')
            
            # Determine mime type
            suffix = image_path.suffix.lower()
            mime_types = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.gif': 'image/gif'}
            mime_type = mime_types.get(suffix, 'image/jpeg')
            
            # Gemini API request
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
            
            payload = {
                "contents": [{
                    "parts": [
                        {
                            "text": """Analyze this industrial/factory photo. Identify:
1. Equipment visible (motors, PLCs, conveyors, panels, etc.)
2. Any safety hazards or concerns
3. Condition assessment (good, worn, damaged, needs attention)
4. Any visible text, labels, or model numbers
5. Location context if apparent

Be concise but thorough. Format as structured data."""
                        },
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": image_data
                            }
                        }
                    ]
                }]
            }
            
            response = requests.post(url, json=payload, timeout=60)
            
            if response.ok:
                data = response.json()
                text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                return {
                    "analysis": text,
                    "model": "gemini-2.0-flash",
                    "timestamp": datetime.now().isoformat(),
                }
            else:
                self.logger.error(f"Gemini API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Photo analysis failed: {e}")
            return None
    
    def analyze_photo(self, photo_path: Path) -> Dict:
        """Analyze a single photo."""
        self.logger.info(f"Analyzing: {photo_path}")
        
        state = self._load_state()
        file_hash = self._get_file_hash(photo_path)
        
        # Check if already analyzed
        if file_hash in state["analyzed_photos"]:
            return state["analyzed_photos"][file_hash]
        
        # Analyze with Gemini
        result = self._analyze_with_gemini(photo_path)
        
        if result:
            result["file"] = str(photo_path)
            result["hash"] = file_hash
            result["source_folder"] = photo_path.parent.name
            
            # Save to state
            state["analyzed_photos"][file_hash] = result
            state["total_analyzed"] += 1
            state["last_scan"] = datetime.now().isoformat()
            self._save_state(state)
            
            # Write analysis to output folder
            output_file = ANALYSIS_OUTPUT / f"{photo_path.stem}_analysis.json"
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
            
            return result
        
        return {"error": "Analysis failed", "file": str(photo_path)}
    
    def scan_new_photos(self) -> Dict:
        """Scan all photo folders for new unanalyzed photos."""
        state = self._load_state()
        analyzed_hashes = set(state["analyzed_photos"].keys())
        
        new_photos = []
        results = []
        
        # Scan all subdirectories (phone1, laptop1, etc.)
        for folder in PHOTOS_DIR.iterdir():
            if folder.is_dir():
                for photo in folder.glob("*"):
                    if photo.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                        file_hash = self._get_file_hash(photo)
                        if file_hash not in analyzed_hashes:
                            new_photos.append(photo)
        
        self.logger.info(f"Found {len(new_photos)} new photos to analyze")
        
        # Analyze each new photo (limit to 10 per cycle to avoid timeouts)
        for photo in new_photos[:10]:
            result = self.analyze_photo(photo)
            results.append(result)
        
        return {
            "scanned": len(new_photos),
            "analyzed": len(results),
            "remaining": max(0, len(new_photos) - 10),
            "results": results,
        }
    
    def get_stats(self) -> Dict:
        """Get analyzer statistics."""
        state = self._load_state()
        return {
            "total_analyzed": state.get("total_analyzed", 0),
            "last_scan": state.get("last_scan"),
            "photos_in_state": len(state.get("analyzed_photos", {})),
        }


analyzer = PhotoAnalyzer()


# ============== CELERY TASKS ==============

@app.task(bind=True, name='photo_analyzer.scan_new')
@with_token_tracking('photo_analyzer')
def scan_new(self) -> Dict:
    """
    Scan for and analyze new photos.
    Called by Celery Beat every 10 minutes.
    """
    analyzer.log_start('scan_new')
    result = analyzer.scan_new_photos()
    analyzer.log_complete('scan_new', result)
    return result


@app.task(bind=True, name='photo_analyzer.analyze_single')
@with_token_tracking('photo_analyzer')
def analyze_single(self, photo_path: str) -> Dict:
    """Analyze a specific photo."""
    analyzer.log_start('analyze_single', photo=photo_path)
    result = analyzer.analyze_photo(Path(photo_path))
    analyzer.log_complete('analyze_single', result)
    return result


@app.task(bind=True, name='photo_analyzer.stats')
@with_celery_tracing("stats")
@traced(name="stats", layer="execution")
def stats(self) -> Dict:
    """Get analyzer statistics."""
    return analyzer.get_stats()


@app.task(bind=True, name='photo_analyzer.health')
@with_celery_tracing("health")
@traced(name="health", layer="execution")
def health(self) -> Dict:
    """Health check."""
    has_key = bool(GEMINI_API_KEY)
    return {
        "status": "ok" if has_key else "no_api_key",
        "gemini_configured": has_key,
        "photos_dir_exists": PHOTOS_DIR.exists(),
    }
