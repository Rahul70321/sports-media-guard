import requests
from bs4 import BeautifulSoup
import os
import tempfile
import time
from urllib.parse import urlparse
from database.models import SessionLocal, DiscoveredMedia
from services.fingerprint_service import generate_fingerprint
from services.matching_engine import find_matches_for_media

def download_image(url: str, save_dir: str) -> str:
    try:
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()
        
        filename = os.path.basename(urlparse(url).path)
        if not filename or '.' not in filename:
            filename = f"img_{int(time.time())}.jpg"
            
        filepath = os.path.join(save_dir, filename)
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return filepath
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        return None

def crawl_images_from_url(url: str):
    print(f"Starting crawl on: {url}")
    db = SessionLocal()
    
    # We will save discovered files to a temp directory inside backend
    temp_dir = os.path.join(os.path.dirname(__file__), '..', 'downloads')
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all image tags
        img_tags = soup.find_all('img')
        print(f"Found {len(img_tags)} images on {url}")
        
        discovered_count = 0
        for img in img_tags:
            img_url = img.get('src')
            if not img_url:
                continue
                
            # Handle relative URLs
            if img_url.startswith('//'):
                img_url = f"https:{img_url}"
            elif img_url.startswith('/'):
                parsed_base = urlparse(url)
                img_url = f"{parsed_base.scheme}://{parsed_base.netloc}{img_url}"
            elif not img_url.startswith('http'):
                continue 
                
            # Download and process
            filepath = download_image(img_url, temp_dir)
            if filepath:
                # Generate fingerprint
                hash_val = generate_fingerprint(filepath, 'image')
                if not hash_val:
                    continue
                    
                # Save to DB
                discovered = DiscoveredMedia(
                    source_url=img_url,
                    platform=urlparse(url).netloc,
                    file_path=filepath,
                    fingerprint_hash=hash_val
                )
                db.add(discovered)
                db.commit()
                db.refresh(discovered)
                
                # Check for matches
                find_matches_for_media(discovered, db)
                discovered_count += 1
                
        return {"status": "success", "images_discovered": discovered_count}
                
    except Exception as e:
        print(f"Crawler error: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
        print("Crawl completed.")
