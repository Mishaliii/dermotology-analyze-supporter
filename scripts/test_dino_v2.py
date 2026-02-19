from pipeline import analyze_skin_image
import os
import glob
import random

TEST_DIR = "data/ISD-198/Test"

extensions = ("*.jpg", "*.jpeg", "*.png")
test_images = []

for ext in extensions:
    test_images.extend(
        glob.glob(os.path.join(TEST_DIR, "**", ext), recursive=True)
    )

if not test_images:
    print("No test images found")
    exit(1)

IMAGE_PATH = random.choice(test_images)
print(f"Test image: {IMAGE_PATH}")

result = analyze_skin_image(IMAGE_PATH)

print("\n" + "=" * 60)
print("     MULTI-METHOD COMPARISON REPORT")
print("=" * 60)

# Helper to print section
def print_section(title, key):
    print(f"\n{title}")
    print("-" * 60)
    
    # Check if kNN method
    is_knn = "knn" in key
    
    print(f"   {'[Disease]':<40} ")
    
    for d, score in result[key]["top_diseases"]:
        
        # Calibrate Confidence
        if is_knn:
            # kNN Vote Logic:
            # If Score > 10.0, it's a "Champion Match" (1-NN override).
            if score > 10.0:
                confidence = 1.0  # 100%
            else:
                # Standard voting consensus (6.0 is strong agreement)
                confidence = min(1.0, score / 6.0)
        else:
            # Cosine Logic: Already 0-1
            confidence = score
            
        print(f"   * {d:<40}")
    
    if "similar_cases" in result[key] and result[key]["similar_cases"]:
        print("\n   [Supporting Evidence / Similar Cases]")
        for i, case in enumerate(result[key]["similar_cases"], 1):
            print(f"     {i}. {case['disease']:<35} -> {os.path.basename(case['image_path'])} ({case['similarity']:.4f})")
    elif not is_knn:
        print("\n   [No specific similar cases found (Prototype comparison)]")

# Run for all methods
print_section("METHOD 1: CLS Token + kNN (Semantic)", "cls_knn")
print_section("METHOD 2: Mean Pool + Centroid (Prototypical)", "mean_cosine")
print_section("METHOD 3: Mean Pool + kNN (Texture)", "mean_knn")

print("\n" + "=" * 60)
