import imagehash
from database.models import Asset, DiscoveredMedia, Incident

def calculate_match_score(hash1_str: str, hash2_str: str) -> float:
    """
    Calculates a similarity score between 0 and 100 based on Hamming distance
    between two hex perceptual hashes.
    """
    try:
        hash1 = imagehash.hex_to_hash(hash1_str)
        hash2 = imagehash.hex_to_hash(hash2_str)
        
        # Hamming distance: lower is more similar. Maximum distance for 64-bit phash is 64.
        distance = hash1 - hash2
        max_distance = 64
        
        # Calculate percentage similarity
        similarity = max(0.0, ((max_distance - distance) / max_distance) * 100.0)
        return similarity
    except Exception as e:
        print(f"Error calculating match score: {e}")
        return 0.0

def find_matches_for_media(discovered_media: DiscoveredMedia, db_session) -> list:
    """
    Compares a discovered media against all registered assets and creates incidents
    if the match score is above a threshold.
    """
    MATCH_THRESHOLD = 80.0 # 80% similarity threshold for MVP
    
    assets = db_session.query(Asset).all()
    incidents_created = []
    
    for asset in assets:
        score = calculate_match_score(asset.fingerprint_hash, discovered_media.fingerprint_hash)
        
        if score >= MATCH_THRESHOLD:
            # Check if an incident already exists to avoid duplicates
            existing_incident = db_session.query(Incident).filter(
                Incident.asset_id == asset.id,
                Incident.discovered_media_id == discovered_media.id
            ).first()
            
            if not existing_incident:
                incident = Incident(
                    asset_id=asset.id,
                    discovered_media_id=discovered_media.id,
                    match_score=score,
                    status="pending_review"
                )
                db_session.add(incident)
                db_session.commit()
                db_session.refresh(incident)
                incidents_created.append(incident)
                print(f"Match found! Score: {score:.2f}% | Asset: {asset.title} | Discovered: {discovered_media.source_url}")
                
    return incidents_created
