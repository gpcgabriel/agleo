import networkx as nx
import math
import random
import re

# =========================================
# Utils matemáticos
# =========================================

def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c


# =========================================
# Parser GML (somente coordenadas reais)
# =========================================

def parse_gml_locations(gml_text):
    locations = []
    blocks = re.findall(r'node\s*\[(.*?)\]', gml_text, re.S)

    for b in blocks:
        def extract(field):
            m = re.search(rf'{field}\s+"?([^"\n]+)"?', b)
            return m.group(1) if m else None

        lat = extract("Latitude")
        lon = extract("Longitude")
        label = extract("label")

        if lat and lon and label:
            locations.append({
                "label": label,
                "Latitude": float(lat),
                "Longitude": float(lon)
            })

    return locations


# =========================================
# Perfis reais de links (base estatística)
# =========================================

REAL_LINK_PROFILES = [
    {"LinkSpeed": "10", "LinkLabel": "10Gbps", "LinkSpeedUnits": "G", "LinkSpeedRaw": 10000000000.0},
    {"LinkSpeed": "3", "LinkLabel": "3Gbps", "LinkSpeedUnits": "G", "LinkSpeedRaw": 3000000000.0},
    {"LinkSpeed": "20", "LinkLabel": "20Mbps", "LinkSpeedUnits": "M", "LinkSpeedRaw": 20000000.0},
    {"LinkSpeed": "200", "LinkLabel": "200Mbps", "LinkSpeedUnits": "M", "LinkSpeedRaw": 200000000.0},
    {"LinkSpeed": "1.45", "LinkLabel": "1.45Gbps", "LinkSpeedUnits": "G", "LinkSpeedRaw": 1450000000.0},
    {"LinkSpeed": "3.5", "LinkLabel": "3.5Gbps", "LinkSpeedUnits": "G", "LinkSpeedRaw": 3500000000.0},
    {"LinkSpeed": "20", "LinkLabel": "20Gbps", "LinkSpeedUnits": "G", "LinkSpeedRaw": 20000000000.0},
]

def sample_link_profile():
    return random.choice(REAL_LINK_PROFILES)


# =========================================
# Geração de nós sintéticos
# =========================================

def generate_nodes_from_locations(base_locations, N, noise_km=5, seed=42):
    random.seed(seed)
    nodes = []

    for i in range(N):
        base = random.choice(base_locations)

        noise_lat = random.uniform(-noise_km, noise_km) / 111
        noise_lon = random.uniform(-noise_km, noise_km) / 111

        node = {
            "id": i,
            "label": base["label"],
            "Latitude": base["Latitude"] + noise_lat,
            "Longitude": base["Longitude"] + noise_lon,
            "Country": "Brazil",
            "Internal": random.randint(0, 1)  # sintético
        }

        nodes.append(node)

    return nodes


# =========================================
# Criação da topologia
# =========================================

def build_geo_topology(nodes, k_neighbors=3):
    G = nx.Graph()

    # ---------- NODES ----------
    for n in nodes:
        G.add_node(
            n["id"],
            id=n["id"],
            label=n["label"],
            Country=n["Country"],
            Longitude=n["Longitude"],
            Latitude=n["Latitude"],
            Internal=n["Internal"]
        )

    # ---------- EDGES ----------
    for i in range(len(nodes)):
        ni = nodes[i]
        distances = []

        for j in range(len(nodes)):
            if i == j:
                continue
            nj = nodes[j]
            d = haversine(ni["Latitude"], ni["Longitude"], nj["Latitude"], nj["Longitude"])
            distances.append((d, nj))

        distances.sort(key=lambda x: x[0])

        for d, nj in distances[:k_neighbors]:
            if not G.has_edge(ni["id"], nj["id"]):
                profile = sample_link_profile()

                G.add_edge(
                    ni["id"],
                    nj["id"],
                    source=ni["id"],
                    target=nj["id"],
                    LinkSpeed=profile["LinkSpeed"],
                    LinkLabel=profile["LinkLabel"],
                    LinkSpeedUnits=profile["LinkSpeedUnits"],
                    LinkSpeedRaw=profile["LinkSpeedRaw"]
                )

    return G


# =========================================
# Pipeline completo
# =========================================

def create_topology_from_gml_locations(gml_text, N, k_neighbors=3, noise_km=5):
    base_locations = parse_gml_locations(gml_text)

    synthetic_nodes = generate_nodes_from_locations(
        base_locations=base_locations,
        N=N,
        noise_km=noise_km
    )

    G = build_geo_topology(synthetic_nodes, k_neighbors=k_neighbors)
    return G


# =========================================
# Execução principal
# =========================================

if __name__ == "__main__":
    with open("datasets/rnp.gml", "r", encoding="utf-8") as f:
        gml_text = f.read()

    N = 10  # número de nós

    G = create_topology_from_gml_locations(
        gml_text=gml_text,
        N=N,
        k_neighbors=random.randint(2, 5),
        noise_km=random.randint(50, 200)
    )

    filename = f"topology{N}.gml"
    nx.write_gml(G, filename)

    print(f"Topologia gerada: {filename}")
    print(f"Nodes: {G.number_of_nodes()} | Edges: {G.number_of_edges()}")