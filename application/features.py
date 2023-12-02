import time
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import json
import base64, json
import requests
import random as rand
import pandas as pd
import string as string
import logging
import os
from dotenv import load_dotenv
load_dotenv()


client_id = os.getenv('SPOTIFY_CLIENT_ID')
client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')


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
 
    redirect_uri = os.getenv('SPOTIFY_REDIRECT_URI')          
    client_creds = f"{client_id}:{client_secret}"
    #print("client_creds:", client_creds)

    client_creds_b64 = base64.b64encode(client_creds.encode("ascii"))
    #print("AUTHORIZATION:", client_creds_b64.decode("ascii"))
    authorization = client_creds_b64.decode('ascii')
              
    headers = {'Authorization': f"Basic {authorization}", 'Content-Type': 'application/x-www-form-urlencoded'}
    body = {'code': code, 'redirect_uri': redirect_uri, 'grant_type': 'authorization_code'}
    #print("code:", code)
    post_response = requests.post(token_url, headers=headers, data=body)
    #print("POST RESPONSE TEXT IS:", post_response.text)
   
    # 200 code indicates access token was properly granted
    if post_response.status_code == 200:
        json = post_response.json()
        return json['access_token'], json['refresh_token'], json['expires_in']
    else:
        logging.error('getToken:' + str(post_response.status_code))
        return None

"""
Requests an access token from the Spotify API with a refresh token. Only called if an access
token and refresh token were previously acquired.
Returns: either [access token, expiration time] or None if request failed
"""
def refreshToken(refresh_token):
	token_url = 'https://accounts.spotify.com/api/token'
	client_creds = f"{client_id}:{client_secret}"
	client_creds_b64 = base64.b64encode(client_creds.encode("ascii"))
	authorization = client_creds_b64.decode('ascii')

	headers = {'Authorization': f"Basic {authorization}", 'Accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded'}
	body = {'refresh_token': refresh_token, 'grant_type': 'refresh_token'}
	post_response = requests.post(token_url, headers=headers, data=body)

	# 200 code indicates access token was properly granted
	if post_response.status_code == 200:
		return post_response.json()['access_token'], post_response.json()['expires_in']
	else:
		logging.error('refreshToken:' + str(post_response.status_code))
		return None


"""
Determines whether new access token has to be requested because time has expired on the 
old token. If the access token has expired, the token refresh function is called. 
Returns: None if error occured or 'Success' string if access token is okay
"""
def checkTokenStatus(session):
	if time.time() > session['token_expiration']:
		payload = refreshToken(session['refresh_token'])

		if payload != None:
			session['token'] = payload[0]
			session['token_expiration'] = time.time() + payload[1]
		else:
			logging.error('checkTokenStatus')
			return None

	return "Success"


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