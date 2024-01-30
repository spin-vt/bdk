from PIL import Image, ImageFilter
import numpy as np
import math

def smooth_edges(input_image_path, output_image_path, smoothing_iterations=1):
    with Image.open(input_image_path) as img:
        img = img.convert('RGBA')
        # Convert to numpy array for morphological operations
        img_array = np.array(img)
        alpha_channel = img_array[:, :, 3]

        # Perform morphological operations
        for _ in range(smoothing_iterations):
            # Erode
            eroded = np.copy(alpha_channel)
            eroded[1:-1, 1:-1] = np.minimum.reduce([
                alpha_channel[:-2, 1:-1], alpha_channel[2:, 1:-1],
                alpha_channel[1:-1, :-2], alpha_channel[1:-1, 2:],
                alpha_channel[:-2, :-2], alpha_channel[:-2, 2:],
                alpha_channel[2:, :-2], alpha_channel[2:, 2:],
                alpha_channel[1:-1, 1:-1]
            ])

            # Dilate
            dilated = np.copy(eroded)
            dilated[1:-1, 1:-1] = np.maximum.reduce([
                eroded[:-2, 1:-1], eroded[2:, 1:-1],
                eroded[1:-1, :-2], eroded[1:-1, 2:],
                eroded[:-2, :-2], eroded[:-2, 2:],
                eroded[2:, :-2], eroded[2:, 2:],
                eroded[1:-1, 1:-1]
            ])

            alpha_channel = dilated

        # Apply the smoothed alpha channel back to the image
        img_array[:, :, 3] = alpha_channel
        smoothed_img = Image.fromarray(img_array)
        smoothed_img.save(output_image_path, 'PNG')

def compute_bounds(latitude, longitude, range_km):
    # Calculate Upper Left and Lower Right coords
    ul_lat = latitude + (range_km / 111)
    ul_lon = longitude - (range_km / (111 * math.cos(math.radians(latitude))))
    lr_lat = latitude - (range_km / 111)
    lr_lon = longitude + (range_km / (111 * math.cos(math.radians(latitude))))
    
    return ul_lon, ul_lat, lr_lon, lr_lat