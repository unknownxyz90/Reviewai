from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from groq import Groq
import json
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

app = FastAPI(title="ReviewAI Backend", version="1.0.0")

# CORS — frontend ko allow karo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production me apna domain daalo
    allow_methods=["*"],
    allow_headers=["*"],
)

# Groq client
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# ─── Request / Response Models ────────────────────────────────
class ReviewRequest(BaseModel):
    business_name: str = Field(..., example="Atha")
    location:      str = Field(..., example="Rajendra Nagar, Indore")
    business_type: str = Field(..., example="Restaurant & Café")
    experience:    str = Field(..., min_length=1, max_length=500)
    rating:        int = Field(..., ge=1, le=5, example=4)
    language:      str = Field(default="english", example="english")  # english | hindi | hinglish
    count:         int = Field(default=30, ge=1, le=30)

    @field_validator("experience")
    @classmethod
    def strip_experience(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Experience note cannot be blank")
        return value

class ReviewResponse(BaseModel):
    reviews: list[str]
    rating:  int
    language: str

# ─── Helpers ──────────────────────────────────────────────────
LANG_MAP = {
    "english":  "English",
    "hindi":    "Hindi",
    "hinglish": "Hinglish (natural mix of Hindi and English like Indians speak)"
}

SENTIMENT_MAP = {
    1: "very negative and disappointed",
    2: "somewhat negative and unimpressed",
    3: "neutral and average",
    4: "positive and happy",
    5: "very positive and highly enthusiastic"
}

def build_prompt(req: ReviewRequest) -> str:
    lang      = LANG_MAP.get(req.language, "English")

    star_guidance = {
        1: "Sound strongly disappointed but mention only details present in the customer's notes. If no problem is described, keep the criticism general.",
        2: "Sound somewhat disappointed but mention only details present in the customer's notes. Do not invent a problem.",
        3: "Sound balanced and honest, using only details from the customer's notes. Do not invent a positive or negative detail.",
        4: "Sound genuinely happy and refer only to positive details present in the customer's notes.",
        5: "Sound very enthusiastic but use only highlights explicitly present in the customer's notes."
    }

    return f"""You are a real Indian customer who just visited "{req.business_name}", a {req.business_type} in {req.location}.

Customer's actual visit notes:
{req.experience}

Write exactly {req.count} different, concise first-person review drafts in {lang} for a {req.rating}-star experience.

Tone guidance for {req.rating} stars:
{star_guidance.get(req.rating, "")}

Rules:
- Keep each review to 1-2 short sentences.
- Use only facts explicitly present in the customer's notes.
- Do not invent dishes, staff names, service events, amenities, prices, or other visit details.
- Vary wording and emphasis without adding unsupported facts.
- Use simple, natural language without corporate clichés, hashtags, or emojis.

Respond ONLY with a valid JSON array of {req.count} strings.
No explanation, no markdown, no backticks, no extra text.
["review1", "review2", "..."]"""

# ─── Routes ───────────────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "ReviewAI backend running 🚀"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/generate-reviews", response_model=ReviewResponse)
async def generate_reviews(req: ReviewRequest):
    if client is None:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is missing. Add it to the .env file before using the API.")

    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that generates realistic customer reviews. Always respond with valid JSON arrays only."
                },
                {
                    "role": "user",
                    "content": build_prompt(req)
                }
            ],
            temperature=0.8,
            max_tokens=4096,
        )

        raw = completion.choices[0].message.content.strip()

        if raw.startswith("```"):
            raw = raw.removeprefix("```json").removesuffix("```").strip()

        reviews = json.loads(raw)

        if (
            not isinstance(reviews, list)
            or len(reviews) != req.count
            or any(not isinstance(item, str) or not item.strip() for item in reviews)
        ):
            raise ValueError("Model returned an invalid review list")

        return ReviewResponse(
            reviews=[item.strip() for item in reviews],
            rating=req.rating,
            language=req.language
        )

    except Exception as e:
        logger.exception("Review generation failed")
        raise HTTPException(
            status_code=502,
            detail="Review generation failed. Please try again.",
        ) from e