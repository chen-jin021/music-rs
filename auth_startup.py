from flask_spotify_auth import getAuth, refreshAuth, getToken
from dotenv import load_dotenv
load_dotenv()
import os

#Add Client ID
CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
#Add Client Secret Key
CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
#ADD Port
PORT = os.getenv('PORT')
#ADD Callback URL
CALLBACK_URL = os.getenv("SPOTIFY_CALLBACK_URL")
SCOPE = os.getenv('SPOTIFY_SCOPE')

#token_data will hold authentication header with access code, the allowed scopes, and the refresh countdown 
TOKEN_DATA = []


def getUser():
    return getAuth(CLIENT_ID, "{}:{}/callback".format(CALLBACK_URL, PORT), SCOPE)

def getUserToken(code):
    global TOKEN_DATA
    TOKEN_DATA = getToken(code, CLIENT_ID, CLIENT_SECRET, "{}:{}/callback/".format(CALLBACK_URL, PORT))
 
def refreshToken(time):
    time.sleep(time)
    TOKEN_DATA = refreshAuth()

def getAccessToken():
    return TOKEN_DATA
