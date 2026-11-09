from flask import Flask, render_template, request, jsonify, make_response
import requests
from mapgen import *
from pathfinding import *

# Create Flask application
app = Flask(__name__)

# Home route
@app.route('/')
def index():
    return render_template('base.html')

@app.route('/api/forward', methods=['POST'])
def address_search():
    query = request.form.get('search', '')
    query = query.replace(' ', '+')
    url = 'https://nominatim.openstreetmap.org/search'
    params = {'q': query + ', UK', 'format': 'json', 'limit': 5}
    headers = {'User-Agent': 'CS-NEA/1.0 ROUTE'}
    response = requests.get(url, params=params, headers=headers, timeout=10)
    try:
        response.raise_for_status()   # raises HTTPError for 4xx/5xx responses
    except requests.exceptions.HTTPError as e:
        print("Request failed:", e)
        print("Status code:", response.status_code)
        print("Body:", response.text)
        # handle or re-raise
    else:
        data = response.json()
        keep_keys = ('name','display_name', 'lat','lon')
        filtered = [{k: item[k] for k in keep_keys if k in item} for item in data]
    return filtered
    
@app.route('/api/basemap', methods=['GET'])
def generate_basemap():
    html = create_uk_basemap()
    return make_response(html, 200, {'Content-Type': 'text/html'})

@app.route('/api/route', methods=['POST'])
def find_route():
    data = request.get_json()
    start = (float(data['start']['lat']), float(data['start']['lon']))
    end = (float(data['end']['lat']), float(data['end']['lon']))
    
    final_route = route(start, end) 
    
    final_map = plot(final_route[0])
    return jsonify({'route': final_map, 'directions': final_route[1]})


if __name__ == '__main__':
    app.run(debug=True)

