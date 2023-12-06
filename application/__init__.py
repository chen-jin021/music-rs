import os
from flask import Flask
from flask_cors import CORS, cross_origin

#create an instance of a flask app and indicating its location
app_path = os.path.dirname(__file__)
# print("app_path: ", app_path)
app = Flask(__name__, static_folder=app_path+'/static')
# CORS(app)
# app.config['CORS_HEADERS'] = 'Content-Type'
app.config['REMOTE_ADDR'] = '0.0.0.0/0'
app.secret_key = os.urandom(24) # generate a secret key for the session

from application import routes