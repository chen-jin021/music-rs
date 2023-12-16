import datetime
from application import app
from flask import Flask, render_template, request, flash, redirect, request, session, make_response, jsonify, abort
from flask_cors import CORS, cross_origin
from application.features import *
from application.model import *
import time
import logging
import urllib.parse
import tidalapi
from typing import Union
from application.tidal_principal import TidalPrincipal
from pathlib import Path
import os
import re

current_script_dir = os.path.abspath(os.path.dirname(__file__))
parent_dir = os.path.dirname(current_script_dir)
data1_dir = os.path.join(parent_dir, 'data1')
csv_file_path = os.path.join(data1_dir, 'allsong_data.csv')
complete_feature_set = os.path.join(data1_dir, 'complete_feature.csv')
# pretrained data
songDF = pd.read_csv(csv_file_path)
complete_feature_set = pd.read_csv(complete_feature_set)
tidal = TidalPrincipal()
# Regular expression pattern for a Spotify playlist URL


@app.route("/")
def home():
   session['previous_url'] = '/'
   #render the home page
   return render_template('index.html')

@app.route('/index')
def index():
	return render_template('index.html')

"""
customization by playlist
"""
@app.route('/playlist')
def playlist():
   session['previous_url'] = '/playlist'
   return render_template('playlist.html')

@app.route('/authorize', methods=['GET'])
def authorize():
   client_id = os.getenv('SPOTIFY_CLIENT_ID')
   client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
   redirect_uri = os.getenv('SPOTIFY_REDIRECT_URI')
   scope = os.getenv('SPOTIFY_SCOPE')
   
	# state key used to protect against cross-site forgery attacks
   state_key = createStateKey(15)
   session['state_key'] = state_key
   # redirect user to Spotify authorization page
   authorize_url = 'https://accounts.spotify.com/en/authorize?'
   parameters = 'response_type=code&client_id=' + client_id + '&redirect_uri=' + redirect_uri + '&scope=' + scope + '&state=' + state_key + '&show_dialog=true'
   response = make_response(redirect(authorize_url + parameters))
   return response

"""
Called after a new user has authorized the application through the Spotift API page.
Stores user information in a session and redirects user back to the page they initally
attempted to visit.
"""
@app.route('/callback', methods=['GET'])
# @cross_origin()
def callback():
   print("session['state_key']", session['state_key'])
   # make sure the response came from Spotify
   if request.args.get('state') != session['state_key']:
      return render_template('index.html', error='State failed.')
   if request.args.get('error'):
      return render_template('index.html', error='Spotify error.')
   else:
      code = request.args.get('code')
      session.pop('state_key', None)

   # get access token to make requests on behalf of the user
   payload = getToken(code)
   if payload != None:
      session['token'] = payload[0]
      session['refresh_token'] = payload[1]
      session['token_expiration'] = time.time() + payload[2]
   else:
      return render_template('index.html', error='Failed to access token.')
   
   current_user = getUserInformation(session)
   session['user_id'] = current_user['id']
   logging.info('new user:' + session['user_id'])
   # print("session['user_id']", session['user_id'])
   return redirect(session['previous_url'])

"""
recommend songs based on spotify playlist URL and cosine similarity to users,
returns the list of spotify tracks with hyperlinks directing them to their user spotify page
"""
@app.route('/recommend', methods=['POST'])
def recommend():
   # print("recommend() CALLED")
   #requesting the URL form the HTML form
   URL = request.form['URL']
   
   df, success = extract(URL)
   if not success:
      print("error in extracting the URL", df)
      return redirect(('/playlist'))
   
   #retrieve the results and get as many recommendations as the user requested
   edm_top40 = recommend_from_playlist(songDF, complete_feature_set, df)
   number_of_recs = int(request.form['number-of-recs'])
   my_songs = []
   for i in range(number_of_recs):
      my_songs.append([str(edm_top40.iloc[i,1]) + ' - '+ '"'+str(edm_top40.iloc[i,4])+'"', "https://open.spotify.com/track/"+ str(edm_top40.iloc[i,-6]).split("/")[-1]])

   # store my_songs in session so it can be accessed by the export feature
   session['my_songs'] = my_songs
   return render_template('results.html',songs=my_songs)

'''
Exportation Feature with Tidal
'''
@app.route("/playlist/export")
def export():
   # instantiate a Tidal principal
   login_url = tidal._login_with_url()
   # Redirect user to TIDAL authorization page
   return jsonify({'login_url': login_url})

@app.route('/check_tidal_auth')
def check_tidal_auth():
    # Logic to determine if the TIDAL authentication is successful
    if tidal._active_session.check_login():
        return jsonify({'authenticated': True})
    else:
        return jsonify({'authenticated': False})

"""
Optinal saving oauth session into file within the `/tidal_callback` route
If enable the below comments, the oauth session will be saved into `tidal-oauth.json` file under application folder
"""
@app.route('/tidal_callback')
def tidal_callback():
   # oauth_file = Path("application/tidal-oauth.json")
   # tidal._save_oauth_session(oauth_file) 
   return redirect('/tidal_export')

@app.route('/tidal_export')
def tidal_export():
   #retrieve my_songs from session
   my_songs = session.get('my_songs', [])
   parsed_songs = parse_song_info(my_songs)
   # print the dictionary parsed_songs
   tidal_ids = []
   for song in parsed_songs: 
      tidal_ids.append(tidal.search_track(song))
   tidal.add_to_playlist("tidalify Recommendations", tidal_ids)

   return redirect("https://listen.tidal.com/my-collection/playlists")

"""
Called when a user starts to enter an artist or track name within the Create feature.
Acts as an endpoint for autocomplete. Takes the entered text and sends back possible
artist or track names.
"""
@app.route('/autocomplete', methods=['GET'])
def autocomplete():
   search = request.args.get('q')
   results = searchSpotify(session, search)

   return jsonify(matching_results=results)


"""
Page describes the web applications privacy policy as well as information about
the features provided.
"""
@app.route('/information',  methods=['GET'])
def information():
	return render_template('information.html')


"""
Create Feature: Page allows users to enter artists/tracks and creates a playlist based
on these entries.
"""
@app.route('/create',  methods=['GET'])
def create():
	# make sure application is authorized for user 
	if session.get('token') == None or session.get('token_expiration') == None:
		session['previous_url'] = '/create'
		return redirect('/authorize')

	# collect user information
	if session.get('user_id') == None:
		current_user = getUserInformation(session)
		session['user_id'] = current_user['id']

	return render_template('create.html')


"""
Called when a user creates a playlist through the Create feature. All of the user entered
artists/track IDs are gathered from the POST data, as well as any tuneable attributes. Then
create a new playlist, find recommended tracks, and fill the playlist with these tracks.
"""
@app.route('/create/playlist',  methods=['POST'])
def createSelectedPlaylist():
   # collect the IDs of the artists/tracks the user entered
   search = []
   for i in range(0, 5):
      if str(i) in request.form:
         search.append(request.form[str(i)])
      else:
         break
      
   # print("SEARCH", search)
   # store all selected attributes in a dict which can be easily added to GET body
   tuneable_dict = {}
   if 'acoustic_level' in request.form:
      tuneable_dict.update({'acoustic': request.form['slider_acoustic']})

   if 'danceability_level' in request.form:
      tuneable_dict.update({'danceability': request.form['slider_danceability']})

   if 'energy_level' in request.form:
      tuneable_dict.update({'energy': request.form['slider_energy']})

   if 'popularity_level' in request.form:
      tuneable_dict.update({'popularity': request.form['slider_popularity']})

   if 'valence_level' in request.form:
      tuneable_dict.update({'valence': request.form['slider_valence']})

   playlist_id, playlist_uri = createPlaylist(session, request.form['playlist_name'])
   uri_list = getRecommendedTracks(session, search, tuneable_dict)
   addTracksPlaylist(session, playlist_id, uri_list)

   # send back the created playlist URI so the user is redirected to Spotify
   playlist_id = playlist_uri.split(':')[-1]
   # print("Playlist ID is: ", playlist_id)
   web_player_url = f"https://open.spotify.com/playlist/{playlist_id}"
   # print("web_player_url", web_player_url)
   return web_player_url


'''
API for getting the recommendations
'''
@app.route('/api/recommend', methods=['GET'])
def api_recommend():
   playlist_url = request.args.get('playlist_url')
   number_of_recs = request.args.get('number_of_recs', default=10, type=int)  # New line

   if number_of_recs > 40:
      return jsonify({'error': 'Number of recommendations cannot exceed 40'}), 400

   # print("playlist_url", playlist_url)
   if not playlist_url:
      return jsonify({'error': 'Playlist URL is required'}), 400

   df, success = extract(playlist_url)
   if not success:
      return jsonify({'error': df}), 400
   try:
      edm_top40 = recommend_from_playlist(songDF, complete_feature_set, df)
      recommendations = []
      for i in range(number_of_recs):
         track = edm_top40.iloc[i]
         recommendations.append({
               'title': str(track[1]) + ' - ' + '"' + str(track[4]) + '"',
               'spotify_url': "https://open.spotify.com/track/" + str(track[-6]).split("/")[-1]
         })

      return jsonify({'recommendations': recommendations})

   except Exception as e:
      app.logger.error(f'Error in generating recommendations: {e}')
      return jsonify({'error': 'Internal server error'}), 500


'''
create a batch recommendation API where user inputs a json with links of playlist
and we generate the recommendations for them
note: user specified number of recs is applied per operation
'''
@app.route('/api/batch_recommend', methods=['POST'])
def batch_recommend():
    data = request.json
    playlist_urls = data.get('playlist_urls')
    number_of_recs = data.get('number_of_recs', 10)

    if number_of_recs > 40: 
        return jsonify({'error': 'Number of recommendations cannot exceed 40'}), 400

    if not playlist_urls:
        return jsonify({'error': 'Playlist URLs are required'}), 400

    all_recommendations = []

    for playlist_url in playlist_urls:
        seen_tracks = set()

        df, success = extract(playlist_url)
        if not success:
            all_recommendations.append({
                'playlist_url': playlist_url,
                'error': df
            })
            continue

        try:
            edm_top40 = recommend_from_playlist(songDF, complete_feature_set, df)

            recommendations = []
            for i in range(min(number_of_recs, len(edm_top40))):
                track = edm_top40.iloc[i]
                spotify_url = "https://open.spotify.com/track/" + str(track[-6]).split("/")[-1]

                if spotify_url not in seen_tracks:
                    seen_tracks.add(spotify_url)
                    recommendations.append({
                        'title': str(track[1]) + ' - ' + '"' + str(track[4]) + '"',
                        'spotify_url': spotify_url
                    })

            all_recommendations.append({
                'playlist_url': playlist_url,
                'recommendations': recommendations
            })

        except Exception as e:
            app.logger.error(f'Error in generating recommendations for {playlist_url}: {e}')
            all_recommendations.append({
                'playlist_url': playlist_url,
                'error': 'Internal server error'
            })

    return jsonify(all_recommendations)


@app.route('/api/playlist/create', methods=['POST'])
def api_create_playlist():
   spotify_token = request.headers.get('Authorization')
   if not spotify_token or not spotify_token.startswith('Bearer '):
      return jsonify({'error': 'Spotify token is required'}), 401
   
   # remove 'Bearer ' prefix from token
   spotify_token = spotify_token.split(' ')[1]

   data = request.json
   playlist_url = data.get('playlist_url')
   number_of_recs = data.get('number_of_recs', 10)

   if not playlist_url:
      return jsonify({'error': 'Playlist URL is required'}), 400

   # generate recs
   df, sucess = extract(playlist_url)
   if not sucess:
      return jsonify({'error': df}), 400 
   
   edm_top40 = recommend_from_playlist(songDF, complete_feature_set, df)
   recommendations = []
   for i in range(number_of_recs):
      track = edm_top40.iloc[i]
      recommendations.append({
            'title': str(track[1]) + ' - ' + '"' + str(track[4]) + '"',
            'spotify_url': "https://open.spotify.com/track/" + str(track[-6]).split("/")[-1]
      })

   try:
      track_ids = [track['spotify_url'].split("/")[-1] for track in recommendations]
      sp = Spotify(auth=spotify_token)
      user_id = sp.current_user()['id']
      playlist_name = "Created by Tidalify MRS API"
      playlist = sp.user_playlist_create(user_id, playlist_name, public=False)

      sp.user_playlist_add_tracks(user_id, playlist['id'], track_ids)

      return jsonify({'message': 'Playlist created successfully', 'playlist_url': playlist['external_urls']['spotify']}), 201

   except Exception as e:
      app.logger.error(f'Error in creating playlist: {e}')
      return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/playlist/create_from_songs', methods=['POST'])
def api_create_from_songs():
   spotify_token = request.headers.get('Authorization')
   if not spotify_token or not spotify_token.startswith('Bearer '):
      return jsonify({'error': 'Spotify token is required'}), 401
   
   # remove 'Bearer ' prefix from token
   spotify_token = spotify_token.split(' ')[1]

   data = request.json
   song_names = data.get('song_names')
   attributes_dict = data.get('attributes', {})

   if not song_names or len(song_names) == 0 or len(song_names) > 5:
       return jsonify({'error': 'Please provide between 1 to 5 song names'}), 400
   
   for key, value in attributes_dict.item():
       if value is not None and (value < 0 or value > 1):
           return jsonify({'error': f'{key} level must be between 0 and 1'}), 400
   
    
   # Find track IDs for the input songs
   seed_tracks = []
   for song_name in song_names:
      search_url = 'https://api.spotify.com/v1/search'
      params = {'q': song_name, 'type': 'track', 'limit': 1}
      headers = {'Authorization': f'Bearer {spotify_token}'}
      response = requests.get(search_url, headers=headers, params=params)
      if response.status_code == 200 and response.json()['tracks']['items']:
         seed_tracks.append(response.json()['tracks']['items'][0]['id'])

   # Check if we have at least one seed track
   if not seed_tracks:
      return jsonify({'error': 'No matching tracks found for the provided song names'}), 400

   # Get recommendations
   track_urls = []
   recommendations_url = 'https://api.spotify.com/v1/recommendations'
   params = {
      'seed_tracks': ','.join(seed_tracks),
      'limit': 25
   }
   params.update(attributes_dict)
   response = requests.get(recommendations_url, headers=headers, params=params)

   if response.status_code == 200:
      recommendations = response.json()['tracks']
      track_urls = [track['external_urls']['spotify'] for track in recommendations]
      # if successfully get recommended songs' urls
      try:
         # create a song list and add rec songs into that list and add this list to user's account
         track_ids = [url.split("/")[-1] for url in track_urls]
         sp = Spotify(auth=spotify_token)
         user_id = sp.current_user()['id']
         playlist_name = "Created by Tidalify MRS API"
         playlist = sp.user_playlist_create(user_id, playlist_name, public=False)
         sp.user_playlist_add_tracks(user_id, playlist['id'], track_ids)
         return jsonify({'message': 'Playlist created successfully', 'playlist_url': playlist['external_urls']['spotify']}), 201
      
      except Exception as e:
         app.logger.error(f'Error in creating playlist: {e}')
         return jsonify({'error': 'Internal server error'}), 500
      
   else:
      return jsonify({'error': 'Failed to get recommendations'}), response.status_code