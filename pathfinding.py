import math as m # For Algorithm
import heapq # For Algorithm
import time # Displaying time taken to find a path
import ast # Parsing Data
import pandas as pd # Data Organisation
import sqlite3 as sql # Database

from concurrent.futures import ThreadPoolExecutor, wait # Threading

from collections import deque # Troubleshooting

class Node: # Establishes Node Class with Methods
    def __init__(self, node_id, lat, lon):
        self._node_id = node_id
        self._lat = lat
        self._lon = lon 
        self._roadtype = ''
        self._neighbours = [] # Lists Neighbours
        self._roadtype = ''
    
    # ////////////////////////////// #
    def get_pos(self):
        return self._lat, self._lon   
    def get_id(self):
        return self._node_id
    def get_neighbours(self):
        return self._neighbours
    # ////////////////////////////// #
    def update_neighbours(self, neighbours):
        self._neighbours = neighbours
    # ////////////////////////////// #

def haversine(p1, p2): # Accurate Distance Calculations
    lat1, lon1 = p1
    lat2, lon2 = p2

    delta_lon = m.radians(lon2-lon1)
    delta_lat = m.radians(lat2-lat1)

    a = m.sin(delta_lat)**2 + m.cos(m.radians(lat1)) * m.cos(m.radians(lat2)) * m.sin(delta_lon/2)**2

    angle = 2 * m.atan2(m.sqrt(a), m.sqrt(1-a))
    return 6731 * angle #6731 = approx radius of the earth

def algorithm(start, end, edge_speeds, edge_roadtypes=None, max_count=None, priority_factor = 0.8):
      
    count = 0 # For Heuristically Searching
    open_set = []

    heapq.heappush(open_set, (0, 0, count, start))

    # Ordered precedence for driving highways (lower value = higher priority)
    DRIVING_HIGHWAY_PRECEDENCE = {
    'motorway': 0, 'motorway_link': 0,
    'trunk': 0, 'trunk_link': 0,
    'primary': 6, 'primary_link': 6,
    'secondary': 8, 'secondary_link': 8,
    'tertiary': 10, 'tertiary_link': 10,
    'unclassified': 9, 'residential': 10,
    'living_street': 12, 'service': 12, 'road': 9,
    }

    if max_count is None:
        max_count = m.inf

    default_speed_kmph = 40 * 1.60934

    came_from = {}
    g_score = {start: 0.0} # Initialise Start Node, has been "Explored" so set to 0

    # initial heuristic: straight-line distance (km)
    initial_h = haversine(start.get_pos(), end.get_pos())
    f_score = {start: initial_h / default_speed_kmph}

    while open_set:
        if count >= max_count:
            return False # Heuristic Stop Case
        
        _, _, _, current = heapq.heappop(open_set)

        if current == end:
            # Reconstruct path by walking back through visited nodes.
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            return path[::-1]
        
        for neighbour in current.get_neighbours():
            edge = (current.get_id(), neighbour.get_id())
            speed_kmph = edge_speeds.get(edge)

            # geometric distance of this edge (km)
            edge_distance_km = haversine(current.get_pos(), neighbour.get_pos())

            # Protection against missing speed value,
            if not speed_kmph or speed_kmph == 0:
                speed_kmph = 50
            
            # time-based cost (hours) with precedence penalty (older behaviour)
            speed_kmph = edge_speeds.get(edge)
            if not speed_kmph or speed_kmph == 0:
                speed_kmph = 50  # fallback km/h
            base_travel_time = edge_distance_km / speed_kmph  # hours

            precedence = DRIVING_HIGHWAY_PRECEDENCE.get(
                edge_roadtypes.get(edge) if edge_roadtypes else None,
                max(DRIVING_HIGHWAY_PRECEDENCE.values()) + 1
            )

            edge_cost = base_travel_time * (1 + precedence * priority_factor)

            tentative_g = g_score[current] + edge_cost

            if neighbour not in g_score or tentative_g < g_score[neighbour]:
                came_from[neighbour] = current
                g_score[neighbour] = tentative_g

                # heuristic: remaining distance (km) OR remaining time depending on mode
                remaining_distance_km = haversine(neighbour.get_pos(), end.get_pos())

                heuristic = remaining_distance_km / default_speed_kmph
                f_score[neighbour] = tentative_g + heuristic

                count += 1
                # use precedence as second sorting key to prefer higher quality roads on ties
                precedence = DRIVING_HIGHWAY_PRECEDENCE.get(
                    edge_roadtypes.get(edge) if edge_roadtypes else None,
                    max(DRIVING_HIGHWAY_PRECEDENCE.values()) + 1
                )
                heapq.heappush(open_set, (f_score[neighbour], precedence, count, neighbour))
    return False

def get_relevant_nodes(conn, start, end, radius):
    cursor = conn.cursor()

    def resolve_node(val):
        finding_query = 'SELECT id FROM nodes ' \
        'ORDER BY ABS(latitude - ?) + ABS(longitude - ?) ' \
        'LIMIT 1;'

        coordinate_query = "SELECT latitude, longitude FROM nodes WHERE id = ?"

        # If coords Provided:
        if isinstance(val, (list, tuple)) and len(val) == 2: # Guard to check if the value provided is a coordinate
            lat, lon = float(val[0]), float(val[1])
            
            cursor.execute(finding_query, (lat, lon))
            node_id = cursor.fetchone()
            if not node_id:
                return None, None
            node_id = node_id[0] # Ensure that the ID is selected, no other values with it

            cursor.execute(coordinate_query, (node_id,))
            coords = cursor.fetchone()
            return node_id, coords
        # If node ID Provided:
        try: 
            node_id = int(val)
            cursor.execute(coordinate_query, (node_id,))
            coords = cursor.fetchone()
            if not coords:
                return None, None
            return node_id, coords
        except Exception:
            return None, None
        
    start_id, startnode = resolve_node(start)
    end_id, endnode = resolve_node(end)

    if not start_id or not end_id or not startnode or not endnode:
        return None, None, []
    
    start_nearby = []
    end_nearby = []

    box_nodes_cache = []
    box_nodes = []

    MOTORWAY = {
        'motorway', 'motorway_link',
        'trunk', 'trunk_link',
        'primary'
    }

    lat1, lon1 = startnode
    lat2, lon2 = endnode
    delta_deg = radius / 111.0 # approximates lat/lon to km
    query = "SELECT id, latitude, longitude FROM nodes WHERE latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?"

    cursor.execute(
        query,
        (lat1 - delta_deg, lat1 + delta_deg, lon1 - delta_deg, lon1 + delta_deg)
    )
    for row in cursor.fetchall():
        start_nearby.append({'id': row[0], 'lat': row[1], 'lon': row[2]})

    cursor.execute(
        query,
        (lat2 - delta_deg, lat2 + delta_deg, lon2 - delta_deg, lon2 + delta_deg)
    )
    for row in cursor.fetchall():
        end_nearby.append({'id': row[0], 'lat': row[1], 'lon': row[2]})

    min_lat, max_lat = min(lat1, lat2), max(lat1, lat2)
    min_lon, max_lon = min(lon1, lon2), max(lon1, lon2)

    cursor.execute(
        query,
        (min_lat, max_lat, min_lon, max_lon)
    )
    for row in cursor.fetchall():
        box_nodes.append({'id': row[0], 'lat': row[1], 'lon': row[2]})

    # read ways and ensure node_refs parsed to lists
    df = pd.read_sql("SELECT node_refs, highway FROM ways", conn)
    df['node_refs'] = df['node_refs'].apply(lambda x: ast.literal_eval(x) if isinstance(x, str) else x)

    for row in box_nodes_cache:
        roadtypes = df[df['node_refs'].apply(lambda x: row[0] in x)]['highway']
        if any(road in MOTORWAY for road in roadtypes):
            box_nodes.append(row)

    all_nodes = start_nearby + end_nearby + box_nodes

    # removes duplicates by node id
    unique_nodes = {node['id']: node for node in all_nodes}
    relevant_nodes = list(unique_nodes.values())

    return start_id, end_id, relevant_nodes

def preload_ways(conn, relevant_nodes):
    df = pd.read_sql("SELECT * FROM ways", conn)
    
    # converts all the strings into lists
    df['node_refs'] = df['node_refs'].apply(lambda x: ast.literal_eval(x) if isinstance(x, str) else x)

    # filter ways for those that contain relevant nodes
    df = df[df['node_refs'].apply(lambda x: any(node in relevant_nodes for node in x))]
    return df

def build_grids(df, relevant_nodes):
    neighbour_grid = {node_id: set() for node_id in relevant_nodes}
    ROUNDABOUTS = {'roundabout', 'circular'}
    road_types = {}
    for _, row in df.iterrows():
        node_refs = row['node_refs']
        road_type = row.get('highway')
        is_oneway = row.get('oneway', None) == 'yes'
        is_roundabout = row.get('junction', None) in ROUNDABOUTS
        for i in range(len(node_refs) - 1):
            a, b = node_refs[i], node_refs[i+1]
            if a in neighbour_grid and b in neighbour_grid:
                # For one-way or roundabout: only allow a -> b
                if is_oneway or is_roundabout:
                    neighbour_grid[a].add(b)
                # For two-way: allow both directions
                else:
                    neighbour_grid[a].add(b)
                    neighbour_grid[b].add(a)
                
                road_types[(a, b)] = road_type
                if not is_oneway:
                    road_types[(b, a)] = road_type
    # convert sets into a list
    for node in neighbour_grid:
        neighbour_grid[node] = list(neighbour_grid[node])
    
    edge_speeds = {}
    for _, row in df.iterrows():
        node_refs = row['node_refs']
        speed_str = row.get('maxspeed', None)
        if isinstance(speed_str, str) and 'mph' in speed_str:
            speed = float(speed_str.replace(' mph', '').strip())
        else:
            try:
                speed = float(speed_str) * 1.60934
            except (TypeError, ValueError):
                speed = 50 * 1.60934 # default speed if missing
        is_oneway = row.get('oneway', None) == 'yes'
        for i in range(len(node_refs) - 1):
            a, b = node_refs[i], node_refs[i+1]
            if a in relevant_nodes and b in relevant_nodes:
                edge_speeds[(a, b)] = speed
                if not is_oneway:
                    edge_speeds[(b, a)] = speed

    return neighbour_grid, edge_speeds, road_types

def initialise_nodes(conn, first, last, radius):
    nodes_dict = {}
    start_time = time.time()
    first, last, node_data = get_relevant_nodes(conn, first, last, radius)

    relevant_nodes = set([data['id'] for data in node_data])
    ways = preload_ways(conn, relevant_nodes)

    neighbour_grid, speeds, road_types = build_grids(ways, relevant_nodes)

    def create_node(data):
        return data['id'], Node(data['id'], data['lat'], data['lon'])
    
    with ThreadPoolExecutor() as exec:
        results = list(exec.map(create_node, node_data))
        nodes_dict = dict(results)
    
    def assign_neighbours(node_id):
        obj = nodes_dict[node_id]
        obj.update_neighbours([nodes_dict[ref] for ref in neighbour_grid[node_id] if ref in nodes_dict])
    
    with ThreadPoolExecutor() as exec:
        list(exec.map(assign_neighbours, nodes_dict.keys()))
    
    end_time = time.time()

    def bfs(start, end, neighbour_grid):
        visited = set()
        queue = deque([start])
        while queue:
            node = queue.popleft()
            if node == end:
                return True
            visited.add(node)
            for n in neighbour_grid[node]:
                if n not in visited:
                    queue.append(n)
        return False
    
    print("Is path possible?", bfs(first, last, neighbour_grid))

    print(f"Data parsing took {end_time - start_time:.4f} seconds")

    return ways, nodes_dict, first, last, ways, speeds, road_types

def heuristics(conn, nodes_dict, first, last, ways, speeds, road_types, radius=2):

    motorway_nodes = set()
    for _, row in ways.iterrows():
        if row.get('highway', None) in ['trunk_link', 'trunk', 'motorway_link', 'motorway', 'primary']:
            motorway_nodes.update(row['node_refs'])
    
    start_node = nodes_dict.get(first)

    if start_node is None:
        return False
    
    min_dist = m.inf
    nearest_motorway_node_id = None

    for node_id in motorway_nodes:
        if node_id in nodes_dict:
            dist = haversine(start_node.get_pos(), nodes_dict[node_id].get_pos())
            if dist < min_dist:
                min_dist = dist
                nearest_motorway_node_id = node_id
    
    if nearest_motorway_node_id is None:
        route = algorithm(nodes_dict[first], nodes_dict[last], speeds, road_types)
        if not route:
            radius = radius * 1.3
            _, nodes_dict, first, last, ways, speeds, road_types = initialise_nodes(conn, first, last, radius)
            return heuristics(conn, nodes_dict, first, last, ways, speeds, radius)
        else:
            return route
    else: 
        route_to_motorway = algorithm(nodes_dict[first], nodes_dict[nearest_motorway_node_id], speeds, road_types, 50)
        if not route_to_motorway:
            route = algorithm(nodes_dict[first], nodes_dict[last], speeds)
            if not route:
                radius = radius * 1.3
                _, nodes_dict, first, last, ways, speeds, road_types = initialise_nodes(conn, first, last, radius)
                return heuristics(conn, nodes_dict, first, last, ways, speeds, road_types, radius)
            else:
                return route
        else:
            next_start = nodes_dict[route_to_motorway[-1].get_id()]
            route_from_motorway = algorithm(next_start, nodes_dict[last], speeds, road_types)
            if not route_from_motorway:
                radius = radius * 1.3
                _, nodes_dict, first, last, ways, speeds, road_types = initialise_nodes(conn, first, last, radius)
                return heuristics(conn, nodes_dict, first, last, ways, speeds, road_types, radius)
            else:
                return route_to_motorway[:-1] + route_from_motorway


def directions(df, route):
    def bearing(p1, p2):
        p1 = p1.get_pos()
        p2 = p2.get_pos()
        lat1, lon1 = m.radians(p1[0]), m.radians(p1[1])
        lat2, lon2 = m.radians(p2[0]), m.radians(p2[1])
        dlon = lon2 - lon1
        x = m.sin(dlon) * m.cos(lat2)
        y = m.cos(lat1)*m.sin(lat2) - m.sin(lat1) * m.cos(lat2) * m.cos(dlon)
        return (m.degrees(m.atan2(x, y)) + 360) % 360

    def roadname(p1, p2):
        p1 = p1.get_id()
        p2 = p2.get_id()

        # Find road containing p1
        current_roads = df[df['node_refs'].apply(lambda refs: p1 in refs)]
        if current_roads.empty:
            currentroad = None
        else:
            currentroad = current_roads.iloc[0].get('name', current_roads.iloc[0].get('ref', current_roads.iloc[0].get('highway')))
        
        # Find road containing p2
        next_roads = df[df['node_refs'].apply(lambda refs: p2 in refs)]
        if next_roads.empty:
            nextroad = None
        else:
            nextroad = next_roads.iloc[0].get('name', next_roads.iloc[0].get('ref', next_roads.iloc[0].get('highway')))
        
        return [currentroad, nextroad]
        
    directions = ['Start']
    for i in range(1, len(route)-1):
        b1 = bearing(route[i-1], route[i])
        b2 = bearing(route[i], route[i+1])
        roads = roadname(route[i-1], route[i])
        

        diff = (b2 - b1 + 540) % 360 - 180  # normalized -180..180

        if diff > 15:
            if roads[0] == roads[1]:
                pass
            else:
                if roads[1] is None:
                    directions.append("Turn right")
                else:
                    directions.append(f"Turn right onto {roads[1]}")
        elif diff < -15:
            if roads[0] == roads[1]:
                pass
            else: 
                if roads[1] is None:
                    directions.append(f"Turn left")
                else:
                    directions.append(f"Turn left onto {roads[1]}")
        else:
            if roads[0] == roads[1]:
                if directions[-1] == "Continue straight":
                    pass
                else:
                    directions.append("Continue straight")
            else:
                if roads[1] is None:
                    directions.append("Continue straight onto Unknown Road")
                else:
                    directions.append(f"Continue straight onto {roads[1]}")


    directions.append('End')
    return directions

def route(start, end, radius=2, conn=None):
    # create DB connection in the same thread that handles the request
    close_conn = False
    if conn is None:
        conn = sql.connect('Database/MapData.sqlite')
        close_conn = True

    try:
        df, nodes_dict, first, last, ways, speeds, road_types = initialise_nodes(conn, start, end, radius)
        path = heuristics(conn, nodes_dict, first, last, ways, speeds, road_types, radius)
        direction = directions(df, path)
        return path, direction
    finally:
        if close_conn:
            conn.close()