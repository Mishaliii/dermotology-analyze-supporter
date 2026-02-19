import os
from pathlib import Path
from PIL import Image, ImageOps
from tqdm import tqdm

# Inputs
DATASET_DIR = Path("data/ISD-198")

# Rules
MIN_W, MIN_H = 64, 64          # skip too-small images
MAX_LONG_SIDE = 1024           # downscale if very large

def process_image(src_path: Path):
    """
    Returns: (ok: bool, reason: str)
    """
    try:
        with Image.open(src_path) as im:
            im = ImageOps.exif_transpose(im)      # fix rotation
            im = im.convert("RGB")                # force RGB

            w, h = im.size
            if w < MIN_W or h < MIN_H:
                return False, f"too_small({w}x{h})"

            # downscale if huge (preserves aspect ratio, just limits max size)
            long_side = max(w, h)
            if long_side > MAX_LONG_SIDE:
                scale = MAX_LONG_SIDE / long_side
                new_w = int(w * scale)
                new_h = int(h * scale)
                im = im.resize((new_w, new_h), Image.BICUBIC)
                
            # overwrite in-place
            im.save(src_path, format="JPEG", quality=92, optimize=True)
        return True, "ok"
    except Exception as e:
        return False, f"error:{type(e).__name__}"

def main():
    if not DATASET_DIR.exists():
        raise SystemExit(f"Missing dataset folder: {DATASET_DIR}")

    print(f"Scanning {DATASET_DIR}...")
    
    extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    images = []
    
    # Recursively find all images
    for root, _, files in os.walk(DATASET_DIR):
        for file in files:
            if Path(file).suffix.lower() in extensions:
                images.append(Path(root) / file)

    print(f"Found {len(images)} images. Starting preprocessing...")
    
    processed = 0
    errors = 0
    skipped = 0

    for img_path in tqdm(images):
        ok, reason = process_image(img_path)
        if ok:
            processed += 1
        else:
            if "too_small" in reason:
                skipped += 1
            else:
                try:
                    # If it's a corrupt file, maybe delete it or just log it? 
                    # For now just logging error.
                    print(f"Failed: {img_path} -> {reason}")
                except:
                    pass
                errors += 1

    print(f"\nProcessing Complete.")
    print(f"Processed: {processed}")
    print(f"Skipped (small): {skipped}")
    print(f"Errors: {errors}")

if __name__ == "__main__":
    main()
