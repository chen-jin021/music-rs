import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import json
import base64, json
import requests
import random as rand
import pandas as pd
import string as string
import logging
from dotenv import load_dotenv
load_dotenv()
import os

REFRESH_TOKEN = ''
SPOTIFY_URL_TOKEN = 'https://accounts.spotify.com/api/token/'
HEADER = 'application/x-www-form-urlencoded'



"""
AUTHENTICATION: To make a request to the Spotify API, the application needs an access
token for the user. This token expires every 60 minutes. To acquire a new token, the 
refresh token can be sent to the API, which will return a new access token.
"""

"""
Creates a state key for the authorization request. State keys are used to make sure that
a response comes from the same place where the initial request was sent. This prevents attacks,
such as forgery. 
Returns: A state key (str) with a parameter specified size.
"""
def createStateKey(size):
	#https://stackoverflow.com/questions/2257441/random-string-generation-with-upper-case-letters-and-digits
	return ''.join(rand.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(size))


"""
Requests an access token from the Spotify API. Only called if no refresh token for the
current user exists.
Returns: either [access token, refresh token, expiration time] or None if request failed
"""
def getToken(code):
    token_url = 'https://accounts.spotify.com/api/token'
    client_id = os.getenv('SPOTIFY_CLIENT_ID')
    client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
    redirect_uri = os.getenv('SPOTIFY_REDIRECT_URI')
    scope = os.getenv('SPOTIFY_SCOPE')

    encoded = base64.b64encode("{}:{}".format(client_id, client_secret))
    authorization = (os.getenv('SPOTIFY_AUTHORIZATION')).format(encoded)
    redirect_uri = os.getenv('SPOTIFY_REDIRECT_URI')

    headers = {'Authorization': authorization, 'Accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded'}
    body = {'code': code, 'redirect_uri': redirect_uri, 'grant_type': 'authorization_code'}
    
    post_response = requests.post(token_url, headers=headers, data=body)    
    # 200 code indicates access token was properly granted
    if post_response.status_code == 200:
         json = post_response.json()
         return json['access_token'], json['refresh_token'], json['expires_in']
    else:
         logging.error('getToken:' + str(post_response.status_code))
         return None
    # post = requests.post(token_url, headers=headers, data=body)
    # return handleToken(json.loads(post.text))
 
def handleToken(response):
    auth_head = {"Authorization": "Bearer {}".format(response["access_token"])}
    REFRESH_TOKEN = response["refresh_token"]
    return [response["access_token"], auth_head, response["scope"], response["expires_in"]]

def refreshAuth():
    body = {
        "grant_type" : "refresh_token",
        "refresh_token" : REFRESH_TOKEN
    }

    post_refresh = requests.post(SPOTIFY_URL_TOKEN, data=body, headers=HEADER)
    p_back = json.dumps(post_refresh.text)
    
    return handleToken(p_back)

def extract(URL):
    client_id = os.getenv('SPOTIFY_CLIENT_ID') # api key
    client_secret = os.getenv('SPOTIFY_CLIENT_SECRET') # api secret

    #use the clint secret and id details
    client_credentials_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

    # the URI is split by ':' to get the username and playlist ID
    playlist_id = URL.split("/")[4].split("?")[0]
    playlist_tracks_data = sp.playlist_tracks(playlist_id)

    #lists that will be filled in with features
    playlist_tracks_id = []
    playlist_tracks_titles = []
    playlist_tracks_artists = []
    playlist_tracks_first_artists = []

    #go through the dictionary to extract the data
    for track in playlist_tracks_data['items']:
        playlist_tracks_id.append(track['track']['id'])
        playlist_tracks_titles.append(track['track']['name'])
        # adds a list of all artists involved in the song to the list of artists for the playlist
        artist_list = []
        for artist in track['track']['artists']:
            artist_list.append(artist['name'])
        playlist_tracks_artists.append(artist_list)
        playlist_tracks_first_artists.append(artist_list[0])

    #create a dataframe
    features = sp.audio_features(playlist_tracks_id)
    features_df = pd.DataFrame(data=features, columns=features[0].keys())
    features_df['title'] = playlist_tracks_titles
    features_df['first_artist'] = playlist_tracks_first_artists
    features_df['all_artists'] = playlist_tracks_artists
    features_df = features_df[['id', 'title', 'first_artist', 'all_artists',
                                'danceability', 'energy', 'key', 'loudness',
                                'mode', 'acousticness', 'instrumentalness',
                                'liveness', 'valence', 'tempo',
                                'duration_ms', 'time_signature']]
    
    return features_df