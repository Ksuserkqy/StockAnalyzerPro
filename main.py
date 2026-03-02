from dotenv import load_dotenv
import os
import json
from flask import Flask, render_template, request, Response
from flask_cors import CORS


load_dotenv()

app = Flask(__name__, static_folder='static')

if os.getenv('DEBUG', 'False').lower() == 'true':
    app.config['DEBUG'] = True
    host = "0.0.0.0"
    CORS(app, 
        resources={r"/*": {"origins": "*"}}, 
        supports_credentials=True
    )
else:
    host = "127.0.0.1"
    app.config['DEBUG'] = False

from pages.chat import chat_page
app.register_blueprint(chat_page, url_prefix="/chat")

@app.route('/')
def index():
    return {"message": "worked"}

if __name__ == "__main__":
    app.run(debug=app.config['DEBUG'], host=host, port=8000)