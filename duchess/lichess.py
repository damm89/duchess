import logging
import requests
import json
import time
from typing import Iterator

logger = logging.getLogger(__name__)

class LichessClient:
    """Handles communication with the Lichess API."""
    
    BASE_URL = "https://lichess.org/api"

    @classmethod
    def fetch_user_games(cls, username: str, max_games: int = 100,
                         perf_type: str = None, color: str = None) -> Iterator[dict]:
        """
        Stream games for a specific user as parsing-friendly ndjson.
        Yields raw parsed JSON dictionaries for each game.
        """
        endpoint = f"{cls.BASE_URL}/games/user/{username}"
        
        params = {
            "max": max_games,
            "pgnInJson": "true", # We want the PGN string, but nicely packaged in JSON
            "clocks": "false",
            "evals": "false",
            "opening": "true",
            "moves": "true"
        }
        
        if perf_type and perf_type.lower() != "any":
            params["perfType"] = perf_type.lower()
            
        if color and color.lower() != "any":
            params["color"] = color.lower()

        headers = {
            "Accept": "application/x-ndjson"
        }

        logger.info(f"Fetching games from Lichess for user {username}...")
        
        try:
            # We use stream=True so we don't load 10,000 games into memory at once
            response = requests.get(endpoint, params=params, headers=headers, stream=True)
            
            if response.status_code == 404:
                raise ValueError(f"User '{username}' not found on Lichess.")
            elif response.status_code == 429:
                # Rate limited. This naive client won't orchestrate massive backoffs, just fail gracefully.
                raise Exception("Lichess API rate limit exceeded. Please try again later.")
                
            response.raise_for_status()

            # Iterate over the ndjson stream line by line
            for line in response.iter_lines():
                if line:
                    try:
                        game_data = json.loads(line)
                        yield game_data
                    except json.JSONDecodeError:
                        logger.warning("Failed to decode Lichess API line as JSON.")
                        continue
                        
        except requests.exceptions.RequestException as e:
            logger.error(f"Lichess API request failed: {e}")
            raise Exception(f"Failed to connect to Lichess API: {e}")
