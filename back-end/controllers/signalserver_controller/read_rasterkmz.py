import xml.etree.ElementTree as ET
import zipfile
import os

def read_rasterkmz(kmz_filename):
    try: 
        with zipfile.ZipFile(kmz_filename, 'r') as kmz:
            with kmz.open('doc.kml', 'r') as kml_file:
                kml = ET.parse(kml_file)
                root = kml.getroot()
                namespace = {'kml': 'http://www.opengis.net/kml/2.2'}
                north = root.find('.//kml:north', namespace).text
                east = root.find('.//kml:east', namespace).text
                south = root.find('.//kml:south', namespace).text
                west = root.find('.//kml:west', namespace).text
                return {
                    'nbound': north,
                    'sbound': south,
                    'ebound': east,
                    'wbound': west
                }
    except Exception as e:
        return {'error': str(e)}