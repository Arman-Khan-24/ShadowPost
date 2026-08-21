from pathlib import Path
from fastapi.testclient import TestClient
from app import app, capacity_for_jpeg

COVER = Path(r"C:\Users\aakaa\Pictures\Wallpaper.Engine.v2.5.28\Wallpaper.Engine.v2.5.28\Wallpaper.Engine.v2.5.28\projects\defaultprojects\arsenal\preview.jpg")
PASSPHRASE = "test API passphrase"

client = TestClient(app)
capacity = capacity_for_jpeg(COVER)
with COVER.open("rb") as handle:
    encoded = client.post("/encode", files={"cover": ("cover.jpg", handle, "image/jpeg")}, data={"message": "hi", "passphrase": PASSPHRASE})
assert encoded.status_code == 200, encoded.text
decoded = client.post("/decode", files={"stego": ("stego.jpg", encoded.content, "image/jpeg")}, data={"passphrase": PASSPHRASE})
assert decoded.status_code == 200, decoded.text
assert decoded.json()["message"] == "hi"
with COVER.open("rb") as handle:
    too_long = client.post("/encode", files={"cover": ("cover.jpg", handle, "image/jpeg")},
                           data={"message": "x" * (capacity["plaintext_bytes"] + 1), "passphrase": PASSPHRASE})
assert too_long.status_code == 400, too_long.text
assert str(capacity["plaintext_bytes"]) in too_long.json()["detail"]
print(f"round_trip=passed; too_long_400=passed; capacity={capacity}")
