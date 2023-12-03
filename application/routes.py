import datetime
from application import app
from flask import Flask, render_template, request, flash, redirect, request, session, make_response, jsonify, abort
from application.features import *
from application.model import *
import time
import logging
import urllib.parse

songDF = pd.read_csv("./data1/allsong_data.csv")
complete_feature_set = pd.read_csv("./data1/complete_feature.csv")

@app.route("/")
def home():
   session['previous_url'] = '/'
   #render the home page
   return render_template('home.html')

@app.route('/index')
def index():
	return render_template('index.html')

@app.route("/about")
def about():
   #render the about page
   return render_template('about.html')

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
   print("session['user_id']", session['user_id'])
   return redirect(session['previous_url'])


@app.route('/hello')
def playlist():
   # make sure application is authorized for user 
   if session.get('token') == None or session.get('token_expiration') == None:
      session['previous_url'] = '/create'
      return redirect('/authorize')

   # collect user information
   if session.get('user_id') == None:
      current_user = getUserInformation(session)
      session['user_id'] = current_user['id']
         
   url = 'https://api.spotify.com/v1/me/playlists'
   playlist = makeGetRequest(session, url)
   print(playlist)
   return render_template('recommend.html', playlists=playlist)


@app.route('/recommend', methods=['POST'])
def recommend():
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
   return render_template('results.html',songs=my_songs)


@app.route('/tracks',  methods=['GET'])
def tracks():
	# make sure application is authorized for user 
	if session.get('token') == None or session.get('token_expiration') == None:
		session['previous_url'] = '/tracks'
		return redirect('/authorize')

	# collect user information
	if session.get('user_id') == None:
		current_user = getUserInformation(session)
		session['user_id'] = current_user['id']

	track_ids = getAllTopTracks(session)

	if track_ids == None:
		return render_template('index.html', error='Failed to gather top tracks.')
		
	return render_template('tracks.html', track_ids=track_ids)

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
      
   print("search", search)
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
   return playlist_uri
