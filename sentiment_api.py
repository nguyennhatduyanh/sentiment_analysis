from flask import Flask, request, Response, jsonify, make_response
from textblob import TextBlob
from functools import wraps
import logging
import json
import re
from collections import OrderedDict


app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

# Expected headers values
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['USE_ETAGS'] = True
EXPECTED_ACCEPT_HEADER = "application/vnd.premier.v1.hal+json"
EXPECTED_CONTENT_TYPE = "application/json"
SUPPORTED_ENCODINGS = ['identity', 'gzip', 'deflate']

# Decorators

def require_accept_header(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.headers.get('Accept') != EXPECTED_ACCEPT_HEADER:
            logging.debug("Invalid Accept header")
            return jsonify(error="Invalid Accept header"), 406
        return f(*args, **kwargs)
    return decorated

def valid_accept_encoding(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        encodings = request.headers.get('Accept-Encoding', '').split(',')
        encodings = [encoding.strip() for encoding in encodings]

        unsupported_encodings = set(encodings) - set(SUPPORTED_ENCODINGS)
        if 'compress' in unsupported_encodings or 'x-compress' in unsupported_encodings:
            logging.debug("Invalid Accept-Encoding header")
            return jsonify(error="Invalid Accept-Encoding header"), 406

        return f(*args, **kwargs)
    return decorated_function

def require_valid_content_type(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        content_type = request.headers.get('Content-Type')
        if content_type != EXPECTED_CONTENT_TYPE:
            logging.debug("Invalid Content-Type header")
            return jsonify(error="Invalid Content-Type header"), 415
        return f(*args, **kwargs)
    return decorated

@app.after_request
def set_response_headers(response):
    # Set Cache-Control header
    response.headers["Cache-Control"] = "no-cache"
    return response

# Predefined password for demonstration
PASSWORD_FOR_TEXT = "my_secure_password"

def has_meaning(s):
    # Define a regex pattern for Roman characters (letters, numbers, spaces, and common punctuation)
    pattern = re.compile(r'^(?=.*[A-Za-z])[A-Za-z\s.,;:!?"\'()-]*$')
    return bool(pattern.match(s))

def analyze_sentiment_textblob(text, threshold):
    blob = TextBlob(text)
    sentiment = None
    polarity = round(blob.sentiment.polarity,3)
    subjectivity = round(blob.sentiment.subjectivity, 3)
    
    if polarity > threshold:
        sentiment = "Positive"
    elif polarity < threshold:
        sentiment = "Negative"
    else:
        sentiment = "Neutral"
    
    return sentiment, "{:.3f}".format(polarity), "{:.3f}".format(subjectivity)

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify(error="Method Not Allowed"), 405

@app.route('/analyze-sentiment', methods=['POST'])
@require_accept_header
@valid_accept_encoding
@require_valid_content_type
def analyze_sentiment_endpoint():
    password = request.args.get('password')
    include_text = password == PASSWORD_FOR_TEXT
    threshold_str = request.args.get('threshold')

    default_threshold = 0.0
    threshold = default_threshold

    if threshold_str:
        try:
            threshold = float(threshold_str)
        except ValueError:
            return jsonify(error="Invalid threshold value"), 400

    data = request.json
    results = {}

    if not data:
        return jsonify(error="No text given"), 400
    
    for id, text in data.items():
        if not has_meaning(text):
            return jsonify(error=f"Invalid characters in value for key '{id}'"), 400

        sentiment, polarity, subjectivity = analyze_sentiment_textblob(text, threshold)
        results[id] = OrderedDict([
            ('sentiment', sentiment),
            ('polarity', polarity),
            ('subjectivity', subjectivity)
        ])

        if include_text:
            results[id]['text'] = text

    return Response(json.dumps(results, indent=4), mimetype='application/json', status=201)



if __name__ == '__main__':
    app.run(debug=True)
