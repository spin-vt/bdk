from PIL import Image, ImageFilter
import xml.etree.ElementTree as ET
import zipfile
import os

def load_loss_to_color_mapping(lcf_file_path, floor_loss_rate=None):
    mapping = {}
    filtered_lines = []

    # Read and filter the data
    with open(lcf_file_path, 'r') as file:
        for line in file:
            parts = line.strip().split(':')
            if len(parts) == 2:
                loss, color = parts
                loss = int(loss)

                if floor_loss_rate is None or loss <= floor_loss_rate:
                    r, g, b = map(int, color.split(','))
                    mapping[loss] = (r, g, b)
                    filtered_lines.append(line)

    # Truncate the file by writing the filtered data
    if floor_loss_rate is not None:
        with open(lcf_file_path, 'w') as file:
            file.writelines(filtered_lines)

    return mapping


def filter_image_by_loss(input_image_path, floor_loss_rate, lcf_file_path, output_image_path):
    loss_to_color_mapping = load_loss_to_color_mapping(lcf_file_path, floor_loss_rate)
    with Image.open(input_image_path) as img:
        img = img.convert('RGBA')
        pixels = img.load()

        for i in range(img.width):
            for j in range(img.height):
                r, g, b, a = pixels[i, j]
                # Determine the loss rate based on the color in the loss to color mapping
                loss_rate = next((loss for loss, color in loss_to_color_mapping.items() if color == (r, g, b)), None)
                # If the loss rate is higher than the floor loss rate or not defined, set to transparent
                if loss_rate is None or loss_rate > floor_loss_rate:
                    pixels[i, j] = (255, 255, 255, 0)

        img.save(output_image_path, 'PNG')

def generate_transparent_image(input_image_path, output_image_path):
    with Image.open(input_image_path) as img:
        img = img.convert('RGBA')
        pixels = img.load()

        for i in range(img.width):
            for j in range(img.height):
                if pixels[i, j] != (255, 255, 255, 0):
                    pixels[i, j] = (0, 194, 255, 76)

        img.save(output_image_path, 'PNG')

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