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

print("\n" + "=" * 45)
print("     VISUAL SIMILARITY REPORT")
print("=" * 45)

print(f"\nDECISION TYPE: {result['decision']['type'].upper()}")
print("Most similar documented conditions:")
for d in result["decision"]["diseases"]:
    print(f"   - {d}")

print("\nVISUALLY SIMILAR CASES:")
for i, case in enumerate(result["similar_cases"], 1):
    print(
        f"   {i}. [{case['similarity']:.4f}] "
        f"{case['disease']} -> {os.path.basename(case['image_path'])}"
    )



print("\n" + "=" * 45)
