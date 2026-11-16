"""Schemas for disease, weather, knowledge documents, dashboards and admin."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------- Disease ----------------
class DiseaseInfoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    class_label: str
    crop: str
    disease_name: str
    is_healthy: bool
    pathogen_type: str | None
    description: str
    symptoms: str
    treatment: str
    prevention: str


class TopPrediction(BaseModel):
    label: str
    crop: str | None = None
    disease_name: str | None = None
    confidence: float


class DiseasePredictionOut(BaseModel):
    id: int
    predicted_label: str
    confidence: float
    is_uncertain: bool
    message: str
    top_predictions: list[TopPrediction]
    disease: DiseaseInfoOut | None
    blur_score: float | None
    is_blurry: bool
    model_version: str | None
    inference_ms: int | None
    image_url: str
    created_at: datetime


# ---------------- Weather ----------------
class CurrentWeatherOut(BaseModel):
    location_name: str | None
    latitude: float
    longitude: float
    temperature_c: float
    feels_like_c: float
    humidity_pct: int
    pressure_hpa: int | None
    wind_speed_ms: float
    wind_deg: int | None
    clouds_pct: int | None
    rain_1h_mm: float | None
    description: str
    icon: str | None
    observed_at: datetime
    sunrise: datetime | None
    sunset: datetime | None
    cached: bool


class ForecastPoint(BaseModel):
    time: datetime
    temperature_c: float
    humidity_pct: int
    wind_speed_ms: float
    rain_3h_mm: float
    pop: float  # probability of precipitation 0..1
    description: str
    icon: str | None


class DailySummary(BaseModel):
    date: str
    temp_min_c: float
    temp_max_c: float
    rain_mm: float
    max_pop: float
    avg_humidity_pct: float
    max_wind_ms: float


class Advisory(BaseModel):
    level: str  # info | warning | alert
    category: str  # spraying | irrigation | disease_risk | heat | cold | rain
    title: str
    message: str


class ForecastOut(BaseModel):
    location_name: str | None
    latitude: float
    longitude: float
    points: list[ForecastPoint]
    daily: list[DailySummary]
    advisories: list[Advisory]
    cached: bool


class GeocodeResult(BaseModel):
    name: str
    state: str | None
    country: str
    latitude: float
    longitude: float


# ---------------- Knowledge documents ----------------
class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    original_filename: str
    source_url: str | None
    file_size_bytes: int
    num_pages: int | None
    num_chunks: int | None
    status: str
    error_message: str | None
    created_at: datetime


# ---------------- Dashboards ----------------
class RecentQuestion(BaseModel):
    conversation_id: int
    question: str
    intent: str | None
    created_at: datetime


class RecentPrediction(BaseModel):
    id: int
    label: str
    disease_name: str | None
    confidence: float
    is_uncertain: bool
    created_at: datetime


class FarmerDashboardOut(BaseModel):
    total_queries: int
    total_conversations: int
    total_disease_scans: int
    voice_queries: int
    recent_questions: list[RecentQuestion]
    recent_predictions: list[RecentPrediction]
    has_location: bool


class CountItem(BaseModel):
    label: str
    count: int


class AdminDashboardOut(BaseModel):
    total_farmers: int
    total_admins: int
    active_users_7d: int
    new_users_30d: int
    total_queries: int
    queries_today: int
    total_disease_scans: int
    total_documents: int
    helpful_feedback_pct: float | None


class AdminStatisticsOut(BaseModel):
    language_usage: list[CountItem]
    intent_distribution: list[CountItem]
    disease_distribution: list[CountItem]
    queries_per_day: list[CountItem]
    input_modes: list[CountItem]
    avg_response_ms: float | None
    grounded_answer_pct: float | None


class AdminUserOut(BaseModel):
    id: int
    full_name: str
    phone: str
    email: str | None
    role: str
    language_code: str
    district: str | None
    state: str | None
    is_active: bool
    query_count: int
    created_at: datetime
    last_login_at: datetime | None


class AdminUserList(BaseModel):
    items: list[AdminUserOut]
    total: int
    page: int
    page_size: int


class AdminUserUpdate(BaseModel):
    is_active: bool | None = None
    role: str | None = Field(default=None, pattern="^(farmer|admin)$")


class SystemStatusOut(BaseModel):
    database: str
    vector_store: str
    vector_chunks: int | None
    gemini_configured: bool
    gemini_model: str
    openweather_configured: bool
    disease_model_available: bool
    intent_model_available: bool
    models_loaded: dict[str, bool]
    disk_free_gb: float
    storage_used_mb: float
