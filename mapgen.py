import folium

def create_uk_basemap(zoom_start: int = 6, tiles: str = "OpenStreetMap"):
    # centre roughly over Great Britain
    uk_center = (54.0, -2.0)
    m = folium.Map(location=uk_center, zoom_start=zoom_start, tiles=tiles)
    folium.TileLayer(tiles=tiles).add_to(m)
    folium.LayerControl().add_to(m)
    return m.get_root().render()


def plot(route):
    coordinates = [(node.get_pos()[0], node.get_pos()[1]) for node in route]

    m = folium.Map(location=coordinates[0], zoom_start=14, tiles='OpenStreetMap')
    
    
    folium.PolyLine(
        coordinates,
        color = "blue",
        weight = 5,
        opacity = 0.8
    ).add_to(m)

    folium.Marker(coordinates[0], popup="Start", icon=folium.Icon(color="green")).add_to(m)
    folium.Marker(coordinates[-1], popup="End", icon=folium.Icon(color="red")).add_to(m)

    return m.get_root().render()