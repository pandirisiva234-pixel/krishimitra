"""Import every model so Alembic and Base.metadata see all tables."""
from app.models.conversation import ConversationHistory, Feedback, Intent, Query, Response
from app.models.disease import Disease, DiseasePrediction
from app.models.knowledge import Document, WeatherData
from app.models.language import Language
from app.models.user import ROLE_ADMIN, ROLE_FARMER, Admin, User

__all__ = [
    "Admin",
    "ConversationHistory",
    "Disease",
    "DiseasePrediction",
    "Document",
    "Feedback",
    "Intent",
    "Language",
    "Query",
    "Response",
    "ROLE_ADMIN",
    "ROLE_FARMER",
    "User",
    "WeatherData",
]
