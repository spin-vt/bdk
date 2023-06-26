from sklearn.cluster import DBSCAN
import numpy as np
import pandas as pd
import json

def get_bounding_boxes(filename, zoom_level):
    epsilon = 0.5 / zoom_level
    df = pd.read_csv(filename)
    coords = df[['latitude', 'longitude']].values
    clustering = DBSCAN(eps=epsilon, min_samples=2).fit(coords)

    cluster_labels = clustering.labels_
    unique_labels = set(cluster_labels)

    clusters = [coords[cluster_labels == i] for i in unique_labels if i != -1]

    bounding_boxes = []
    for cluster in clusters:
        lat_min, lon_min = np.min(cluster, axis=0)
        lat_max, lon_max = np.max(cluster, axis=0)

        bounding_boxes.append({
            'latitude': {
                'min': lat_min,
                'max': lat_max
            },
            'longitude': {
                'min': lon_min,
                'max': lon_max
            }
        })

    with open('clusterCoordinate.json', 'w') as json_file:
        json.dump(bounding_boxes, json_file)
    
    return bounding_boxes
