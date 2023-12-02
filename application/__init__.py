import os
from flask import Flask
from flask_cors import CORS, cross_origin

#create an instance of a flask app and indicating its location
app_path = os.path.dirname(__file__)
# print("app_path: ", app_path)
app = Flask(__name__, static_folder=app_path+'/static')
CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
app.config['REMOTE_ADDR'] = '0.0.0.0/0'
app.secret_key = os.urandom(24) # generate a secret key for the session


#print("secret  key" , app.secret_key)
#creating a secret key for security
# app.config['SECRET_KEY'] = '5791628bb0b13ce0c676dfde280ba241'
#locating the database in our directory
#db_path = os.path.join(os.path.dirname(__file__), 'Kanban.db')
#URI = 'sqlite:///{}'.format(db_path)
#app.config['SQLALCHEMY_DATABASE_URI'] = URI
#db = SQLAlchemy(app)

from application import routes