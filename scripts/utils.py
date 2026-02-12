import os
import glob
import random

def get_random_image(root_dir="data/images"):
    """
    Recursively finds all images in root_dir and returns a random file path.
    Supported extensions: jpg, jpeg, png (case insensitive).
    """
    extensions = ["*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"]
    all_images = []
    
    if not os.path.exists(root_dir):
         raise FileNotFoundError(f"Directory not found: {root_dir}")

    for ext in extensions:
        all_images.extend(glob.glob(os.path.join(root_dir, "**", ext), recursive=True))
    
    if not all_images:
        raise FileNotFoundError(f"No images found in {root_dir}")
        
    return random.choice(all_images)
