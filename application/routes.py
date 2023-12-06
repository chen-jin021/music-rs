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


# pretrained data
songDF = pd.read_csv("./data1/allsong_data.csv")
complete_feature_set = pd.read_csv("./data1/complete_feature.csv")
tidal = TidalPrincipal()

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

@app.route('/authorize')
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
@app.route('/callback')
# @cross_origin()
def callback():
   # print("session['state_key']", session['state_key'])
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
   #using the extract function to get a features dataframe
   df = extract(URL)
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


