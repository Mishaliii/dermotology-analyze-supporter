import requests
import json
import os

url = "http://127.0.0.1:8000/analyze"
image_path = "data/ISD-198/Train/Acne_Vulgaris/046542VB.jpg"

try:
    with open(image_path, "rb") as f:
        files = {"file": (os.path.basename(image_path), f, "image/jpeg")}
        data = {"knn_k": 5, "search_k": 10}
        response = requests.post(url, files=files, data=data)
        
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        with open("api_dump.json", "w", encoding="utf-8") as out:
            json.dump(response.json(), out, indent=2)
        print("Dumped to api_dump.json")
except Exception as e:
    print(f"Request failed: {e}")
