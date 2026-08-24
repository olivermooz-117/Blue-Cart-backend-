from flask import Flask
from flask_cors import CORS

from config import Config
from extensions import bcrypt, db, jwt
from routes.auth import auth_bp