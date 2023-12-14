from typing import Any, Union
import re
import tidalapi
from application.song import Song
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)
oauth_file = Path("application/tidal-oauth.json")

class TidalPrincipal:

    def __init__(self):
        self._active_session = tidalapi.Session()

    def _save_oauth_session(self, oauth_file: Path):
        # create a new session
        if self._active_session.check_login():
            # store current OAuth session
            data = {}
            data["token_type"] = {"data": self._active_session.token_type}
            data["session_id"] = {"data": self._active_session.session_id}
            data["access_token"] = {"data": self._active_session.access_token}
            data["refresh_token"] = {"data": self._active_session.refresh_token}
            
            print("WRITING TO FILE...") #debug line
            with oauth_file.open("w") as outfile:
                json.dump(data, outfile)
            self._oauth_saved = True

    def _load_oauth_session(self, **data):
        assert self._active_session, "No session loaded"
        args = {
        "token_type": data.get("token_type", {}).get("data"),
        "access_token": data.get("access_token", {}).get("data"),
        "refresh_token": data.get("refresh_token", {}).get("data"),
        }

        self._active_session.load_oauth_session(**args)

    def _login_with_url(self):
        login, _ = self._active_session.login_oauth()
        return f"https://{login.verification_uri_complete}"
    

    @staticmethod
    def __normalize(query: str) -> str:
        normalized: str
        normalized = ''.join(filter(lambda character:ord(character) < 0xff, query.lower())) 
        normalized = query.split('-')[0].strip().split('(')[0].strip().split('[')[0].strip()
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized

    def search_track(self, song: Song) -> Union[str, None]:
        query: str = self.__normalize(f"{song.title} {song.artist}")
        res: dict[str, Any] = self._active_session.search(query)
        tidal_id: Union[str, None] = None
        try:
            if res['tracks'] and res['tracks'][0].id is not None:
                tidal_id = res['tracks'][0].id
                print("[INSIDE Tidal_Principal] TIDAL_ID is: ", tidal_id)

        except Exception as e:
            logging.error(f"Error searching for track: {e}")
            pass
        
        return tidal_id

    
    def add_to_playlist(self, playlist_name: str, tidal_track_ids: list[str]):
        # Ensure the session is logged in
        if not self._active_session.check_login():
            raise Exception("Not logged in to Tidal")

        # Create a new playlist
        user = self._active_session.user
        new_playlist = user.create_playlist(playlist_name, "Playlist created from Spotify recommendations")
        print("Tidal_track_id, ", tidal_track_ids)

        # Filter out None values from tidal_track_ids
        valid_track_ids = [tid for tid in tidal_track_ids if tid is not None]

        # Add tracks to the playlist
        new_playlist.add(valid_track_ids)

