"""
Farmer Advisory API — FastAPI Backend
Production REST API for the farmer advisory agent.

Why FastAPI instead of just Streamlit?
- Streamlit is great for demos, but real apps need APIs
- APIs can be consumed by mobile apps, WhatsApp bots, other services
- FastAPI gives you: auto docs, validation, async, OpenAPI schema
- This is how real production AI services are built

For you to learn and extend:
- Add authentication (API keys)
- Add rate limiting
- Add caching (Redis)
- Add database (PostgreSQL) for storing queries
- Add WebSocket for real-time chat
- Deploy with Docker
"""
import os
import json
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

# ─── Pydantic Models (request/response schemas) ───

class CropInfoResponse(BaseModel):
    """Response model for crop information."""
    crop: str
    name: str
    seasons: Optional[list] = None
    soil: Optional[str] = None
    water_needs: Optional[str] = None
    water_note: Optional[str] = None
    temperature: Optional[str] = None
    varieties: Optional[dict] = None
    sowing: Optional[str] = None
    harvest: Optional[str] = None
    yield_avg: Optional[str] = None
    tips: Optional[List[str]] = None
    common_pests: Optional[str] = None
    msp: Optional[str] = None


class CropSearchResponse(BaseModel):
    """Response for crop search."""
    query: str
    found: bool
    crop: Optional[CropInfoResponse] = None
    message: Optional[str] = None
    available_crops: List[str] = []


class SchemeInfo(BaseModel):
    """Single scheme info."""
    name: str
    benefit: Optional[str] = None
    eligibility: Optional[str] = None
    how_to_apply: Optional[str] = None
    documents: Optional[str] = None
    helpline: Optional[str] = None


class SchemeSearchResponse(BaseModel):
    """Response for scheme search."""
    query: str
    results: List[SchemeInfo] = []


class WeatherResponse(BaseModel):
    """Response for weather query."""
    location: str
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    condition: Optional[str] = None
    wind_speed: Optional[float] = None
    advisory: Optional[str] = None


class HealthResponse(BaseModel):
    """Generic response."""
    status: str
    message: str


class ChatRequest(BaseModel):
    """Chat request."""
    message: str = Field(..., min_length=1, max_length=1000, description="User's farming question")
    language: Optional[str] = Field("en", description="Language code (hi, en, ta, etc.)")


class ChatResponse(BaseModel):
    """Chat response."""
    answer: str
    language: str
    sources: List[str] = []


# ─── Data Loading ───

DATA_DIR = Path(__file__).parent.parent / "data"

def load_json(filename: str) -> dict:
    path = DATA_DIR / filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_crops() -> dict:
    # Try knowledge format first, fallback to original format
    data = load_json("crops_knowledge.json")
    if not data:
        data = load_json("crops.json")
    return data


def load_schemes() -> dict:
    data = load_json("schemes_knowledge.json")
    if not data:
        # Convert list format to dict
        raw = load_json("schemes.json")
        if isinstance(raw, list):
            return {s.get("name", "").lower().replace(" ", "_"): s for s in raw}
        return raw
    return data


# ─── FastAPI App ───

app = FastAPI(
    title="🌾 Farmer Advisory API",
    description="REST API for farming queries — crop info, weather, schemes, market prices. "
                "Built for the Farmer Advisory Agent.",
    version="1.0.0",
    docs_url="/docs",       # Swagger UI
    redoc_url="/redoc",     # ReDoc
)


@app.get("/", response_model=HealthResponse)
def root():
    """Health check endpoint."""
    return HealthResponse(status="ok", message="Farmer Advisory API is running. Visit /docs for API documentation.")


@app.get("/health", response_model=HealthResponse)
def health():
    """Health check for load balancers."""
    return HealthResponse(status="ok", message="healthy")


# ─── Crop Endpoints ───

@app.get("/crops", response_model=List[str], tags=["Crops"])
def list_crops():
    """List all available crops."""
    crops = load_crops()
    return sorted(crops.keys())


@app.get("/crops/{crop_name}", response_model=CropSearchResponse, tags=["Crops"])
def get_crop(crop_name: str):
    """Get detailed information about a specific crop."""
    crops = load_crops()
    key = crop_name.lower().strip()

    if key in crops:
        return CropSearchResponse(
            query=crop_name, found=True,
            crop=CropInfoResponse(crop=key, **crops[key]),
            available_crops=sorted(crops.keys()),
        )

    # Fuzzy match
    for k in crops:
        if key in k or k in key:
            return CropSearchResponse(
                query=crop_name, found=True,
                crop=CropInfoResponse(crop=k, **crops[k]),
                available_crops=sorted(crops.keys()),
            )

    return CropSearchResponse(
        query=crop_name, found=False,
        message=f"No data for '{crop_name}'.",
        available_crops=sorted(crops.keys()),
    )


# ─── Scheme Endpoints ───

@app.get("/schemes", response_model=List[str], tags=["Schemes"])
def list_schemes():
    """List all available government schemes."""
    schemes = load_schemes()
    if isinstance(schemes, dict):
        return sorted(schemes.keys())
    elif isinstance(schemes, list):
        return sorted(set(s.get("name", "unknown") for s in schemes if isinstance(s, dict)))
    return []


@app.get("/schemes/search", response_model=SchemeSearchResponse, tags=["Schemes"])
def search_schemes(q: str = Query(..., min_length=1, description="Search query")):
    """Search for government schemes matching a query."""
    schemes = load_schemes()
    q_lower = q.lower()
    results = []

    items = schemes.items() if isinstance(schemes, dict) else [(s.get("name", "").lower().replace(" ", "_"), s) for s in schemes]

    for key, data in items:
        if not isinstance(data, dict):
            continue
        searchable = " ".join([
            key, data.get("name", ""), data.get("benefit", ""), data.get("description", ""),
            data.get("eligibility", ""), data.get("eligibility_text", ""),
            " ".join(data.get("keywords", [])),
        ]).lower()
        if q_lower in searchable:
            results.append(SchemeInfo(
                name=data.get("name", key),
                benefit=data.get("benefit") or data.get("description"),
                eligibility=data.get("eligibility") or data.get("eligibility_text"),
                how_to_apply=data.get("how_to_apply"),
                documents=data.get("documents") or str(data.get("documents_needed", "")),
                helpline=data.get("helpline"),
            ))

    return SchemeSearchResponse(query=q, results=results[:5])


@app.get("/schemes/{scheme_key}", response_model=SchemeInfo, tags=["Schemes"])
def get_scheme(scheme_key: str):
    """Get detailed info about a specific scheme."""
    schemes = load_schemes()
    key = scheme_key.lower().strip()

    if key in schemes:
        data = schemes[key]
        if isinstance(data, dict):
            return SchemeInfo(
                name=data.get("name", key),
                benefit=data.get("benefit") or data.get("description"),
                eligibility=data.get("eligibility") or data.get("eligibility_text"),
                how_to_apply=data.get("how_to_apply"),
                documents=data.get("documents") or str(data.get("documents_needed", "")),
                helpline=data.get("helpline"),
            )

    # Fuzzy match
    for k, v in schemes.items():
        if key in k or k in key:
            if isinstance(v, dict):
                return SchemeInfo(
                    name=v.get("name", k),
                    benefit=v.get("benefit") or v.get("description"),
                    eligibility=v.get("eligibility") or v.get("eligibility_text"),
                    how_to_apply=v.get("how_to_apply"),
                    documents=v.get("documents") or str(v.get("documents_needed", "")),
                    helpline=v.get("helpline"),
                )

    raise HTTPException(status_code=404, detail=f"Scheme '{scheme_key}' not found.")


# ─── Weather Endpoint ───

@app.get("/weather/{location}", response_model=WeatherResponse, tags=["Weather"])
def get_weather(location: str):
    """Get current weather for a location."""
    import requests
    try:
        resp = requests.get(
            f"https://wttr.in/{location}?format=j1",
            timeout=10,
            headers={"User-Agent": "FarmerAPI/1.0"},
        )
        if resp.status_code == 200:
            data = resp.json()
            current = data.get("current_condition", [{}])[0]
            temp = float(current.get("temp_C", 25))

            # Generate advisory
            advisory = None
            if temp > 40:
                advisory = "Extreme heat! Increase irrigation. Avoid midday fieldwork."
            elif temp < 5:
                advisory = "Frost risk! Protect sensitive crops."
            elif int(current.get("chanceofrain", 0)) > 70:
                advisory = "Heavy rain expected. Delay fertilizer application."

            return WeatherResponse(
                location=location,
                temperature=temp,
                humidity=float(current.get("humidity", 50)),
                condition=current.get("weatherDesc", [{}])[0].get("value", "Unknown"),
                wind_speed=float(current.get("windspeedKmph", 0)),
                advisory=advisory,
            )
    except Exception:
        pass

    return WeatherResponse(location=location, advisory=f"Could not fetch weather for {location}")


# ─── Chat Endpoint (optional, uses LLM) ───

@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
def chat(req: ChatRequest):
    """
    Chat endpoint — ask any farming question.
    Requires GROQ_API_KEY or OPENAI_API_KEY environment variable.
    """
    api_key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Chat endpoint requires GROQ_API_KEY or OPENAI_API_KEY")

    # Import the agent
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from agent.core import FarmerAgent

    agent = FarmerAgent(api_key=api_key, provider="groq")
    answer = agent.process_query(req.message)

    return ChatResponse(answer=answer, language=req.language or "en")


# ─── Run ───

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
