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
    print("access_token is:", post_response.json()['access_token'])
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


def getAllTopTracks(session, limit=10):
	url = 'https://api.spotify.com/v1/me/top/tracks'
	track_ids = []
	time_range = ['short_term', 'medium_term', 'long_term']
	print("reached to this point")
	for time in time_range:
		track_range_ids = []

		params = {'limit': limit, 'time_range': time}
		payload = makeGetRequest(session, url, params)
		print(payload)
		if payload == None:
			return None

		for track in payload['items']:
			track_range_ids.append(track['id'])

		track_ids.append(track_range_ids)

	return track_ids



"""
Makes a GET request with the proper headers. If the request succeeds, the json parsed
response is returned. If the request fails because the access token has expired, the
check token function is called to update the access token.
Returns: Parsed json response if request succeeds or None if request fails
"""
def makeGetRequest(session, url, params={}):
    headers = {"Authorization": "Bearer {}".format(session['token'])}
    response = requests.get(url, headers=headers, params=params)
    # print("GET RESPONSE TEXT IS:", response.text)
    # 200 code indicates request was successful
    if response.status_code == 200:
        return response.json()

    # if a 401 error occurs, update the access token
    elif response.status_code == 401 and checkTokenStatus(session) != None:
        return makeGetRequest(session, url, params)
    else:
        logging.error('makeGetRequest:' + str(response.status_code))
        return None


"""
Makes a PUT request with the proper headers. If the request succeeds or specific errors
occured, the status code is returned. The status code is necessary to identify some errors
that need to be brought to the user's attention (inactive device and forbidden requests due
to Spotify Premium. If the request fails because the access token has expired, the
check token function is called to update the access token.
Returns: Response status code if request succeeds or None if request fails
"""
def makePutRequest(session, url, params={}, data={}):
	headers = {"Authorization": "Bearer {}".format(session['token']), 'Accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded'}
	response = requests.put(url, headers=headers, params=params, data=data)

	# if request succeeds or specific errors occured, status code is returned
	if response.status_code == 204 or response.status_code == 403 or response.status_code == 404 or response.status_code == 500:
		return response.status_code

	# if a 401 error occurs, update the access token
	elif response.status_code == 401 and checkTokenStatus(session) != None:
		return makePutRequest(session, url, data)
	else:
		logging.error('makePutRequest:' + str(response.status_code))
		return None


"""
Makes a POST request with the proper headers. If the request succeeds, the json parsed
response is returned. If the request fails because the access token has expired, the
check token function is called to update the access token. If the requests fails
due to inactive devices or forbidden requests the status code is returned.
Returns: Parsed json response if request succeeds or None/status code if request fails
"""
def makePostRequest(session, url, data):

	headers = {"Authorization": "Bearer {}".format(session['token']), 'Accept': 'application/json', 'Content-Type': 'application/json'}
	response = requests.post(url, headers=headers, data=data)

	# both 201 and 204 indicate success, however only 201 responses have body information
	if response.status_code == 201:
		return response.json()
	if response.status_code == 204:
		return response

	# if a 401 error occurs, update the access token
	elif response.status_code == 401 and checkTokenStatus(session) != None:
		return makePostRequest(session, url, data)
	elif response.status_code == 403 or response.status_code == 404:
		return response.status_code
	else:
		logging.error('makePostRequest:' + str(response.status_code))
		return None

"""
Makes a DELETE request with the proper headers. If the request succeeds, the json parsed
response is returned. If the request fails because the access token has expired, the
check token function is called to update the access token.
Returns: Parsed json response if request succeeds or None if request fails
"""
def makeDeleteRequest(session, url, data):
	headers = {"Authorization": "Bearer {}".format(session['token']), 'Accept': 'application/json', 'Content-Type': 'application/json'}
	response = requests.delete(url, headers=headers, data=data)

	# 200 code indicates request was successful
	if response.status_code == 200:
		return response.json()

	# if a 401 error occurs, update the access token
	elif response.status_code == 401 and checkTokenStatus(session) != None:
		return makeDeleteRequest(session, url, data)
	else:
		logging.error('makeDeleteRequest:' + str(response.status_code))
		return None

"""
PERSONAL USER INFORMATION: Functions that get information specific to the user.
"""

"""
Gets user information such as username, user ID, and user location.
Returns: Json response of user information
"""
def getUserInformation(session):
	url = 'https://api.spotify.com/v1/me'
	payload = makeGetRequest(session, url)

	if payload == None:
		return None

	return payload

"""
Gets the top tracks of a user for all three time intervals. Used to display the top
tracks on the TopTracks feature page.
Returns: A list of tracks IDs for each of the three time intervals
"""
def getAllTopTracks(session, limit=10):
	url = 'https://api.spotify.com/v1/me/top/tracks'
	track_ids = []
	time_range = ['short_term', 'medium_term', 'long_term']

	for time in time_range:
		track_range_ids = []

		params = {'limit': limit, 'time_range': time}
		payload = makeGetRequest(session, url, params)

		if payload == None:
			return None

		for track in payload['items']:
			track_range_ids.append(track['id'])

		track_ids.append(track_range_ids)

	return track_ids


"""
Gets the top tracks for a specific time interval for a user.
Returns: A list of the tracks IDs for the specified time
"""
def getTopTracksID(session, time, limit=25):
	url = 'https://api.spotify.com/v1/me/top/tracks'
	params = {'limit': limit, 'time_range': time}
	payload = makeGetRequest(session, url, params)

	if payload == None:
		return None

	track_ids = []
	for track in payload['items']:
		track_ids.append(track['id'])

	return track_ids


"""
Gets the top tracks for a specific time interval for a user.
Returns: A list of the tracks URIs for the specified time
"""
def getTopTracksURI(session, time, limit=25):
	url = 'https://api.spotify.com/v1/me/top/tracks'
	params = {'limit': limit, 'time_range': time}
	payload = makeGetRequest(session, url, params)

	if payload == None:
		return None

	track_uri = []
	for track in payload['items']:
		track_uri.append(track['uri'])

	return track_uri


"""
Gets the top artists for a specific time interval for a user.
Returns: A list of the artist IDs for the specified time
"""
def getTopArtists(session, time, limit=10):
	url = 'https://api.spotify.com/v1/me/top/artists'
	params = {'limit': limit, 'time_range': time}
	payload = makeGetRequest(session, url, params)

	if payload == None:
		return None

	artist_ids = []
	for artist in payload['items']:
		artist_ids.append(artist['id'])

	return artist_ids


"""
Gets the recommended tracks based on an entered tracks/artists and a set of 
tuneable attributes.
Returns: A list of the tracks URIs
"""
def getRecommendedTracks(session, search, tuneable_dict, limit=25):
	track_ids = ""
	artist_ids = ""
	for item in search:

		# tracks IDs start with a 't:' to identify them
		if item[0:2] == 't:':
			track_ids += item[2:] + ","

		# artist IDs start with an 'a:' to identify them
		if item[0:2] == 'a:':
			artist_ids += item[2:] + ","

	url = 'https://api.spotify.com/v1/recommendations'
	params = {'limit': limit, 'seed_tracks': track_ids[0:-1], 'seed_artists': artist_ids[0:-1]}
	params.update(tuneable_dict)
	payload = makeGetRequest(session, url, params)

	if payload == None:
		return None

	rec_track_uri = []
	
	for track in payload['tracks']:
		rec_track_uri.append(track['uri'])

	return rec_track_uri


"""
Gets all of a user playlists.
Returns: A list of playlists, which are a list of [name, uri]
"""
def getUserPlaylists(session, limit=20):
	url = 'https://api.spotify.com/v1/me/playlists'
	offset = 0
	playlist = []

	# iterate through all playlists of a user (Spotify limits amount returned with one call)
	total = 1
	while total > offset:
		params = {'limit': limit, 'offset': offset}
		payload = makeGetRequest(session, url, params)

		if payload == None:
			return None
		
		for item in payload['items']:
			playlist.append([item['name'], item['uri']])

		total = payload['total']
		offset += limit

	return playlist


"""
PLAYBACK: Functions that alter a user's playback or get information about playback.
"""

"""
Gets all of a user's available devices.
Returns: A list of devices, which are a list of [name, id]
"""
def getUserDevices(session):
	url = 'https://api.spotify.com/v1/me/player/devices'
	payload = makeGetRequest(session, url)

	if payload == None:
		return None

	device_list = []
	for device in payload['devices']:

		# restricted devices cannot be accessed by the application
		if device['is_restricted'] != True:
			device_list.append([device['name'], device['id']])

	return device_list


"""
Start a user's playback from the current context and parameter specified device.
Returns: The response of the start request (for 403/404 error processing)
"""
def startPlayback(session, device):
	url = 'https://api.spotify.com/v1/me/player/play'
	params = {'device_id': device}
	payload = makePutRequest(session, url, params)
	return payload


"""
Start a user's playback from the parameter specified context and device.
Returns: The response of the start request (for 403/404 error processing)
"""
def startPlaybackContext(session, playlist, device):
	url = 'https://api.spotify.com/v1/me/player/play'
	params = {'device_id': device}
	data = "{\"context_uri\":\"" + playlist + "\",\"offset\":{\"position\":0},\"position_ms\":0}"
	payload = makePutRequest(session, url, params, data)
	return payload


"""
Pauses a user's playback.
Returns: The response of the start request (for 403/404 error processing)
"""
def pausePlayback(session):
	url = 'https://api.spotify.com/v1/me/player/pause'
	payload = makePutRequest(session, url)
	return payload


"""
Sets the shuffle for a user based on parameter specified shuffle toggle.
Returns: The response of the start request (for 403/404 error processing)
"""
def shuffle(session, device, is_shuffle=True):
	url = 'https://api.spotify.com/v1/me/player/shuffle'
	params = {'state': is_shuffle, 'device_id': device}
	payload = makePutRequest(session, url, params)
	return payload


"""
Skips to the next track in a user's playback from the current context.
Returns: The response of the start request (for 403/404 error processing)
"""
def skipTrack(session):
	url = 'https://api.spotify.com/v1/me/player/next'
	data = {}
	payload = makePostRequest(session, url, data)
	return payload


"""
Gets information about the current playing track. Because start and skip take
time to process on the Spotify end, sometimes the application needs to wait to
grab the information of the correct track.
Returns: A dictionary with the name and img URL of the current playing track
"""
def getTrack(session):
	url = 'https://api.spotify.com/v1/me/player/currently-playing'
	payload = makeGetRequest(session, url)

	if payload == None:
		return None

	# check to make sure the newest track is being grabbed (progress must be under 5000ms)
	if payload['progress_ms'] != None and payload['progress_ms'] > 5000:
		time.sleep(0.2)
		payload = makeGetRequest(session, url)

		if payload == None:
			return None

	name = payload['item']['name']
	img = payload['item']['album']['images'][0]['url']

	return {'name': name, 'img': img}


"""
Gets information about the current playing track. Because resume requires no time
to process on the Spotify end, the application does not have to wait to get information.
Returns: A dictionary with the name and img URL of the current playing track
"""
def getTrackAfterResume(session):
	url = 'https://api.spotify.com/v1/me/player/currently-playing'
	payload = makeGetRequest(session, url)

	if payload == None :
		return None

	name = payload['item']['name']
	img = payload['item']['album']['images'][0]['url']

	return {'name': name, 'img': img}


"""
PLAYLIST: Functions that alter a user's playlists.
"""

"""
Creates a blank playlist with the parameter specified playlist name.
Returns: The ID and URI of the playlist
"""
def createPlaylist(session, playlist_name):
	url = 'https://api.spotify.com/v1/users/' + session['user_id'] + '/playlists'
	data = "{\"name\":\"" + playlist_name + "\",\"description\":\"Recommended by Cloudify\"}"
	payload = makePostRequest(session, url, data)

	if payload == None:
		return None

	return payload['id'], payload['uri']


"""
Adds the parameter specified tracks to a playlist.
Returns: None
"""
def addTracksPlaylist(session, playlist_id, uri_list):
	url = 'https://api.spotify.com/v1/playlists/' + playlist_id + '/tracks'

	uri_str = ""
	for uri in uri_list:
		uri_str += "\"" + uri + "\","

	data = "{\"uris\": [" + uri_str[0:-1] + "]}"
	makePostRequest(session, url, data)

	return


"""
Gets all of the URIs of the tracks in a playlist.
Returns: A list of track URIs in the playlist
"""
def getTracksPlaylist(session, playlist_id, limit=100):
	url = 'https://api.spotify.com/v1/playlists/' + playlist_id + '/tracks'

	offset = 0
	track_uri = []

	# iterate through all tracks in a playlist (Spotify limits number per request)
	total = 1
	while total > offset:
		params = {'limit': limit, 'fields': 'total,items(track(uri))', 'offset': offset}
		payload = makeGetRequest(session, url, params)

		if payload == None:
			return None
		
		for item in payload['items']:
			track_uri.append(item['track']['uri'])

		total = payload['total']
		offset += limit

	return track_uri


"""
Gets the name of possible artists and tracks based on the user entered text.
Returns: List of dicts of possible artists/tracks, dicts include label (name)
and value (URI)
"""
def searchSpotify(session, search, limit=4):
	url = 'https://api.spotify.com/v1/search'
	params = {'limit': limit, 'q': search + "*", 'type': 'artist,track'}
	payload = makeGetRequest(session, url, params)

	if payload == None:
		return None

	# response includes both artist and track names
	results = []
	for item in payload['artists']['items']:

		# append 'a:' to artist URIs so artists and tracks can be distinguished 
		results.append([item['name'], 'a:' + item['id'], item['popularity']])

	for item in payload['tracks']['items']:

		# track names will include both the name of the track and all artists
		full_name = item['name'] + " - "
		for artist in item['artists']:
			full_name += artist['name'] + ", "

		# append 't:' to track URIs so tracks and artists can be distinguished 
		results.append([full_name[0:-2], 't:' + item['id'], item['popularity']])


	# sort them by popularity (highest first)
	results.sort(key=lambda x: int(x[2]), reverse=True)

	results_json = []
	for item in results:
		results_json.append({'label': item[0], 'value': item[1]})

	return results_json


"""
DATABASE: These functions are called by the database update function. The access token is
passed from the database function, so requests do not use the above specified request functions.
"""

"""
Adds the parameter specified tracks to a playlist.
Returns: None if failed, or 'success' if success
"""
def dbAddTracksPlaylist(access_token, playlist_id, uri_list):
	url = 'https://api.spotify.com/v1/playlists/' + playlist_id + '/tracks'

	headers = {"Authorization": "Bearer {}".format(access_token), 'Accept': 'application/json', 'Content-Type': 'application/json'}
	uri_str = ""
	for uri in uri_list:
		uri_str += "\"" + uri + "\","

	data = "{\"uris\": [" + uri_str[0:-1] + "]}"

	payload = requests.post(url, headers=headers, data=data)

	if payload.status_code == 201:
		return "success"
	else:
		return None


"""
Gets all of the URIs of the tracks in a playlist.
Returns: A list of track URIs in the playlist
"""
def dbGetTracksPlaylist(access_token, playlist_id, limit=100):
	url = 'https://api.spotify.com/v1/playlists/' + playlist_id + '/tracks'

	headers = {"Authorization": "Bearer {}".format(access_token)}
	offset = 0
	track_uri = []

	# iterate through all tracks in a playlist (Spotify limits number per request)
	total = 1
	while total > offset:
		params = {'limit': limit, 'fields': 'total,items(track(uri))', 'offset': offset}
		payload = requests.get(url, headers=headers, params=params)

		if payload.status_code == 200:
			payload = payload.json()
		else:
			return None
		
		for item in payload['items']:
			track_uri.append(item['track']['uri'])

		total = payload['total']
		offset += limit

	return track_uri


"""
Clears the playlist so new music can be filled in.
Returns: None if failed, or 'success' if success
"""
def dbClearPlaylist(access_token, playlist_id):
	url = 'https://api.spotify.com/v1/playlists/' + playlist_id + '/tracks'
	uri_list = dbGetTracksPlaylist(access_token, playlist_id)

	uri_str = ""
	for uri in uri_list:
		uri_str += "{\"uri\":\"" + uri + "\"},"

	data = "{\"tracks\": [" + uri_str[0:-1] + "]}"
	headers = {"Authorization": "Bearer {}".format(access_token), 'Accept': 'application/json', 'Content-Type': 'application/json'}
	payload = requests.delete(url, headers=headers, data=data)

	if payload.status_code == 200:
		return "success"
	else:
		return None


"""
Gets the top tracks for a specific time interval for a user.
Returns: A list of the tracks URIs for the specified time
"""
def dbGetTopTracksURI(access_token, time, limit=25):
	url = 'https://api.spotify.com/v1/me/top/tracks'
	params = {'limit': limit, 'time_range': time}
	headers = {"Authorization": "Bearer {}".format(access_token)}
	payload = requests.get(url, headers=headers, params=params)

	if payload.status_code == 200:
		payload = payload.json()
	else:
		return None

	track_uri = []
	for track in payload['items']:
		track_uri.append(track['uri'])

	return track_uri

