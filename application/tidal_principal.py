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

    def _login(self):
        try:
            # attempt to reload existing session from file
            with open(oauth_file) as f:
                logger.info("Loading OAuth session from %s...", oauth_file)
                data = json.load(f)
                self._load_oauth_session(**data)
        except Exception as e:
            logger.info("Could not load OAuth session from %s: %s", oauth_file, e)

        if not self._active_session.check_login():
            logger.info("Creating new OAuth session...")
            print("WE ARE HERE 1") #debug line
            login_url, future = self._active_session.login_oauth_simple()

            print("WE ARE HERE 2")
            self._save_oauth_session(oauth_file)

        if self._active_session.check_login():
            logger.info("TIDAL Login OK")
        else:
            logger.info("TIDAL Login KO")
            raise ConnectionError("Failed to log in.")
    
    def _login_with_url(self):
        login, _ = self._active_session.login_oauth()
        return f"https://{login.verification_uri_complete}"
    
    
    def run(self):
        # do login
        self._login()

        #album = self._active_session.album(110827651)  # Lets Rock (LOSSLESS, HIRES_LOSSLESS, MQA)
        #print(album.name)
        #print(album.image(640))
        #tracks = album.tracks()

        tracks = self._active_session.user.favorites.tracks()
        for track in tracks:
            print(track.name)
            # for artist in track.artists:
            #    print(' by: ', artist.name)
            try:
                print(track.get_url())
            except:
                continue

    @staticmethod
    def __normalize(query: str) -> str:
        normalized: str
        normalized = ''.join(filter(lambda character:ord(character) < 0xff, query.lower())) 
        normalized = query.split('-')[0].strip().split('(')[0].strip().split('[')[0].strip()
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized

    def search_track(self, song: Song) -> Union[str, None]:
        query: str = self.__normalize(f"{song.title} {song.artist}")
        res: dict[str, Any] = self.session.search(query)
        tidal_id: Union[str, None] = None
        try:
            for t in res['tracks']:
                if t.isrc == song.isrc:
                    tidal_id = t.id
                    break
            if not tidal_id:
                possible_ids = filter(lambda s: song.artist in s.artist.name, res['tracks'])
                tidal_id = list(possible_ids)[0].id
        except Exception:
            pass
        
        return tidal_id
    
    def add_to_playlist(self, playlist_name: str, tids: list[str]):
        playlist = self.session.user.create_playlist(playlist_name, "Songs saved from spotify")
        playlist.add(tids)
        
