"""Test setup.

Uses a REAL PostgreSQL test database (TEST_DATABASE_URL), real ChromaDB, real ONNX
Runtime, real FFmpeg and the real weather parsing code. Only components that need
large model downloads or paid APIs are replaced by small test doubles:
  FakeSTT (Whisper), FakeTranslator (NLLB), HashEmbedder (MiniLM), FakeLLM (Gemini), FakeTTS (Edge-TTS).
Those components are tested separately with real models in ml/evaluation.

Create the test database once:
    psql -U postgres -c "CREATE DATABASE krishimitra_test OWNER krishimitra;"
Run:
    cd backend
    pytest -v
"""
import hashlib
import os
import re
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="krishimitra_test_"))


def _test_database_url() -> str:
    """TEST_DATABASE_URL if set, else DATABASE_URL from backend/.env with the database name + '_test'.
    Tests never touch the main database."""
    if os.environ.get("TEST_DATABASE_URL"):
        return os.environ["TEST_DATABASE_URL"]
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("DATABASE_URL="):
                url = line.split("=", 1)[1].strip().strip('"')
                base, _, name = url.rpartition("/")
                return f"{base}/{name.split('?')[0]}_test"
    raise RuntimeError("Set TEST_DATABASE_URL or create backend/.env with DATABASE_URL")


os.environ["DATABASE_URL"] = _test_database_url()
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-long-enough-1234567890")
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["ENVIRONMENT"] = "test"
os.environ["STORAGE_DIR"] = str(TMP / "storage")
os.environ["CHROMA_DIR"] = str(TMP / "chroma")
os.environ["MODELS_DIR"] = str(TMP / "models")
os.environ["MODEL_CACHE_DIR"] = str(TMP / "cache")
os.environ["OPENWEATHER_API_KEY"] = "test-openweather-key"
os.environ["GEMINI_API_KEY"] = ""
os.environ["RERANK_ENABLED"] = "false"
os.environ["PRELOAD_MODELS"] = "false"  # tests use fakes; never load real models even if .env says true
os.environ["QUERY_REFINE_WITH_LLM"] = "false"
os.environ["LLM_TRANSLATE_LANGUAGES"] = "[]"  # NLLB (fake) for every language, except in the tests that check it  # switched on only in the tests that check it

import json  # noqa: E402

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services.rag.retriever import Retriever  # noqa: E402
from app.services.speech.whisper_stt import TranscriptionResult  # noqa: E402
from scripts.seed_data import main as seed  # noqa: E402

settings = get_settings()

TELUGU_Q = "టమాటా ఆకులపై మచ్చలు ఉన్నాయి, ఏమి చేయాలి?"
TELUGU_Q_EN = "There are spots on tomato leaves, what should I do?"


# ----------------------------------------------------------------- test doubles
class FakeSTT:
    is_loaded = True

    def __init__(self):
        self.language, self.prob, self.text = "te", 0.95, TELUGU_Q
        self.calls = []

    def transcribe(self, wav_path, language=None, hint=None):
        self.calls.append(language)
        lang = language or self.language
        return TranscriptionResult(self.text, lang, self.prob if language is None else 1.0, 2.0)


class FakeTranslator:
    """Deterministic: known sentences map to English; otherwise tags the text with the target code."""

    is_loaded = True
    KNOWN = {TELUGU_Q: TELUGU_Q_EN}

    def translate(self, text, src, tgt):
        if src == tgt:
            return text
        if tgt == "eng_Latn":
            return self.KNOWN.get(text, f"[en] {text}")
        return f"<{tgt}> {text}"


class HashEmbedder:
    """Bag-of-words hashing into 256 dimensions. Similar words -> similar vectors; no download."""

    is_loaded = True

    def encode(self, texts):
        out = []
        for t in texts:
            v = np.zeros(256, dtype=np.float32)
            for w in re.findall(r"[a-z]+", t.lower()):
                if len(w) > 2:
                    v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 256] += 1
            n = np.linalg.norm(v)
            out.append((v / n if n else v).tolist())
        return out


class FakeLLM:
    model = "fake-gemini"

    def __init__(self):
        self.reply = "Remove the spotted lower leaves and spray mancozeb as per the label [1]."
        self.prompts = []

    @property
    def is_configured(self):
        return True

    async def generate(self, prompt, system_instruction, retries=3, image=None, json_output=False,
                       max_output_tokens=None):
        self.prompts.append(prompt)
        if isinstance(self.reply, list):  # a list gives one reply per call, the last one repeats
            return self.reply.pop(0) if len(self.reply) > 1 else self.reply[0]
        return self.reply


class FakeTTS:
    def __init__(self, out_dir: Path):
        self.out_dir = out_dir
        out_dir.mkdir(parents=True, exist_ok=True)

    async def synthesize(self, text, voice, gtts_lang=None):
        path = self.out_dir / (hashlib.sha256(f"{voice}|{text}".encode()).hexdigest()[:32] + ".mp3")
        path.write_bytes(b"ID3" + b"\x00" * 64)
        return path


# --------------------------------------------------------------------- helpers
def build_tiny_onnx_model(model_path: Path, labels_path: Path) -> list[str]:
    """A 3-class ONNX 'CNN': global average pool -> linear layer. Real ONNX Runtime inference."""
    import onnx
    from onnx import TensorProto, helper

    labels = ["Tomato___Early_blight", "Tomato___healthy", "Potato___Late_blight"]
    # Channel weights: red-ish images -> class 0, green -> class 1, blue -> class 2
    weight = helper.make_tensor("W", TensorProto.FLOAT, [3, 3], [4, 0, 0, 0, 4, 0, 0, 0, 4])
    graph = helper.make_graph(
        [
            helper.make_node("GlobalAveragePool", ["input"], ["pooled"]),
            helper.make_node("Flatten", ["pooled"], ["flat"]),
            helper.make_node("MatMul", ["flat", "W"], ["logits"]),
        ],
        "tiny",
        [helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 3, 224, 224])],
        [helper.make_tensor_value_info("logits", TensorProto.FLOAT, [1, 3])],
        [weight],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    model.ir_version = 8
    onnx.save(model, str(model_path))
    labels_path.write_text(json.dumps({"labels": labels, "input_size": 224, "mean": [0.485, 0.456, 0.406],
                                       "std": [0.229, 0.224, 0.225], "model_name": "tiny-test",
                                       "version": "test-1"}))
    return labels


def make_jpeg(color_rgb=(200, 30, 30), size=(240, 240), noise=True) -> bytes:
    import cv2

    img = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    img[:] = color_rgb[::-1]  # cv2 uses BGR
    if noise:
        rng = np.random.default_rng(0)
        img = np.clip(img.astype(int) + rng.integers(-40, 40, img.shape), 0, 255).astype(np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return buf.tobytes()


# -------------------------------------------------------------------- fixtures
@pytest.fixture(scope="session", autouse=True)
def database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    seed()
    yield
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_tables(database):
    yield
    with engine.begin() as conn:
        conn.execute(text(
            "TRUNCATE feedback, responses, queries, conversation_history, disease_predictions, "
            "documents, weather_data, admins, users RESTART IDENTITY CASCADE"
        ))


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        services = app.state.services
        services.stt = FakeSTT()
        services.translator = FakeTranslator()
        services.embedder = HashEmbedder()
        services.llm = FakeLLM()
        services.tts = FakeTTS(settings.tts_dir)
        services.reranker = None
        services.retriever = Retriever(services.embedder, services.vector_store, None, top_k=10, top_n=3,
                                       max_distance=0.9)
        services.intent.embedder = services.embedder
        settings.MODELS_DIR.mkdir(parents=True, exist_ok=True)
        build_tiny_onnx_model(settings.disease_model_path, settings.disease_labels_path)
        yield c


@pytest.fixture
def services(client):
    return app.state.services


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


def register(client, phone="9876543210", password="Farmer123", **extra) -> dict:
    body = {"full_name": "Ravi Kumar", "phone": phone, "password": password, "preferred_language": "te",
            "district": "Guntur", "state": "Andhra Pradesh", **extra}
    resp = client.post("/api/auth/register", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
def farmer(client):
    data = register(client)
    return {"headers": {"Authorization": f"Bearer {data['access_token']}"}, "user": data["user"]}


@pytest.fixture
def admin(client, db):
    from app.core.security import hash_password
    from app.models import Admin, Language, User

    en = db.query(Language).filter_by(code="en").one()
    user = User(full_name="Admin", phone="9000000001", password_hash=hash_password("Admin12345"),
                role="admin", preferred_language_id=en.id)
    db.add(user)
    db.flush()
    db.add(Admin(user_id=user.id, designation="Tester"))
    db.commit()
    resp = client.post("/api/auth/login", data={"username": "9000000001", "password": "Admin12345"})
    assert resp.status_code == 200, resp.text
    return {"headers": {"Authorization": f"Bearer {resp.json()['access_token']}"}, "id": user.id}


@pytest.fixture
def knowledge(client, admin, services):
    """Index a small tomato-disease text document through the real upload + ingest path."""
    text_doc = (
        "Tomato early blight management.\n\n"
        "Early blight causes brown spots with concentric rings on older tomato leaves. "
        "Remove spotted lower leaves and spray mancozeb or chlorothalonil at label rate every ten days.\n\n"
        "Paddy irrigation.\n\nKeep two to five centimetres of standing water in paddy fields during tillering."
    )
    resp = client.post(
        "/api/knowledge/upload",
        files={"file": ("tomato_guide.txt", text_doc.encode(), "text/plain")},
        data={"title": "Tomato and paddy guide"},
        headers=admin["headers"],
    )
    assert resp.status_code == 202, resp.text
    yield resp.json()
    services.vector_store.delete_document(resp.json()["id"])
