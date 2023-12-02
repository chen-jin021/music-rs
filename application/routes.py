import datetime
from application import app
from flask import Flask, render_template, request, flash, redirect, request, session, make_response, jsonify, abort
from application.features import *
from application.model import *
import time
import logging
import auth_startup
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
   
   return redirect(session['previous_url'])

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
Makes a GET request with the proper headers. If the request succeeds, the json parsed
response is returned. If the request fails because the access token has expired, the
check token function is called to update the access token.
Returns: Parsed json response if request succeeds or None if request fails
"""
def makeGetRequest(session, url, params={}):
	headers = {"Authorization": "Bearer {}".format(session['token'])}
	response = requests.get(url, headers=headers, params=params)

	# 200 code indicates request was successful
	if response.status_code == 200:
		return response.json()

	# if a 401 error occurs, update the access token
	elif response.status_code == 401 and checkTokenStatus(session) != None:
		return makeGetRequest(session, url, params)
	else:
		logging.error('makeGetRequest:' + str(response.status_code))
		return None


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
   return render_template('results.html',songs= my_songs)

