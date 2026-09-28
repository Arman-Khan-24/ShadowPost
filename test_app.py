from pathlib import Path
from fastapi.testclient import TestClient
from app import app, capacity_for_jpeg, PLATFORM_PROFILES

COVER = Path(r"C:\Users\aakaa\Pictures\Wallpaper.Engine.v2.5.28\Wallpaper.Engine.v2.5.28\Wallpaper.Engine.v2.5.28\projects\defaultprojects\arsenal\preview.jpg")
PASSPHRASE = "test API passphrase"

client = TestClient(app)

# 1. Test platform listing endpoint
platforms_resp = client.get("/platforms")
assert platforms_resp.status_code == 200
platforms = platforms_resp.json()
assert any(p["id"] == "instagram" for p in platforms)
assert any(p["id"] == "telegram" for p in platforms)
print(f"platform_list=passed; found={len(platforms)} profiles")

# 2. Test default profile round-trip
capacity = capacity_for_jpeg(COVER)
with COVER.open("rb") as handle:
    encoded = client.post("/encode", files={"cover": ("cover.jpg", handle, "image/jpeg")},
                          data={"message": "hi", "passphrase": PASSPHRASE, "platform": "default"})
assert encoded.status_code == 200, encoded.text
assert encoded.headers.get("X-ShadowPost-Platform") == "default"

decoded = client.post("/decode", files={"stego": ("stego.jpg", encoded.content, "image/jpeg")}, data={"passphrase": PASSPHRASE})
assert decoded.status_code == 200, decoded.text
assert decoded.json()["message"] == "hi"
print("default_round_trip=passed")

# 3. Test Instagram profile round-trip with auto-crop/conditioning
with COVER.open("rb") as handle:
    ig_encoded = client.post("/encode", files={"cover": ("cover.jpg", handle, "image/jpeg")},
                             data={"message": "secret for instagram", "passphrase": PASSPHRASE, "platform": "instagram"})
assert ig_encoded.status_code == 200, ig_encoded.text
assert ig_encoded.headers.get("X-ShadowPost-Platform") == "instagram"
print("instagram_encoded_dimensions:", ig_encoded.headers.get("X-ShadowPost-Dimensions"))

ig_decoded = client.post("/decode", files={"stego": ("stego.jpg", ig_encoded.content, "image/jpeg")}, data={"passphrase": PASSPHRASE})
assert ig_decoded.status_code == 200, ig_decoded.text
assert ig_decoded.json()["message"] == "secret for instagram"
print("instagram_adaptive_round_trip=passed")

# 4. Capacity limit validation
with COVER.open("rb") as handle:
    too_long = client.post("/encode", files={"cover": ("cover.jpg", handle, "image/jpeg")},
                           data={"message": "x" * (capacity["plaintext_bytes"] + 1), "passphrase": PASSPHRASE})
assert too_long.status_code == 400, too_long.text
print("all_tests_passed_successfully=True")
