"""Download and save the MiniLM model locally for offline use."""
from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"
LOCAL_PATH = "backend/models/all-MiniLM-L6-v2"

model = SentenceTransformer(MODEL_NAME)
model.save(LOCAL_PATH)
print(f"Model saved to {LOCAL_PATH}")
