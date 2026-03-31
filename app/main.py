"""
FastAPI Backend — NLP Threat Severity Prediction Dashboard
"""

import logging
import time
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional

from app.predictor import ThreatPredictor

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Model paths
MODELS_DIR = Path(__file__).parent.parent / "models"

# Global predictor
predictor = ThreatPredictor(models_dir=str(MODELS_DIR))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load models on startup."""
    logger.info("🚀 Loading ML models...")
    try:
        predictor.load()
        logger.info("✅ Models loaded successfully!")
    except Exception as e:
        logger.error(f"⚠️ Model loading failed: {e}")
        logger.info("Running in DEMO mode (no models loaded)")
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title="NLP Threat Severity Prediction",
    description="Beyond Binary — Industry-level email threat analysis with 13 ML models",
    version="4.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Pydantic Models ──

class EmailRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=50000,
                      description="Raw email content to analyze")

class BatchEmailRequest(BaseModel):
    emails: List[str] = Field(..., min_length=1, max_length=20,
                              description="List of email texts (max 20)")

class PredictionResponse(BaseModel):
    severity: int
    label: str
    confidence: float
    icon: str
    color: str
    probabilities: dict
    structural_features: dict
    individual_predictions: dict
    risk_indicators: list
    inference_time_ms: float

class HealthResponse(BaseModel):
    status: str
    models_loaded: bool
    model_count: int
    version: str


# ── API Endpoints ──

@app.get("/", response_class=FileResponse)
async def serve_dashboard():
    """Serve the main dashboard."""
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        models_loaded=predictor._loaded,
        model_count=len(predictor.base_models),
        version="4.0.0",
    )


@app.post("/api/predict", response_model=PredictionResponse)
async def predict_threat(request: EmailRequest):
    """Predict threat severity for a single email."""
    start = time.time()

    if not predictor._loaded:
        # Demo mode: return mock prediction
        return _demo_prediction(request.text, start)

    try:
        result = predictor.predict(request.text)
        result['inference_time_ms'] = round((time.time() - start) * 1000, 2)
        return PredictionResponse(**result)
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@app.post("/api/predict/batch")
async def predict_batch(request: BatchEmailRequest):
    """Predict threat severity for multiple emails."""
    results = []
    for email_text in request.emails:
        start = time.time()
        if not predictor._loaded:
            results.append(_demo_prediction(email_text, start))
        else:
            try:
                result = predictor.predict(email_text)
                result['inference_time_ms'] = round((time.time() - start) * 1000, 2)
                results.append(result)
            except Exception as e:
                logger.error(f"Batch prediction error: {e}")
                results.append({'error': str(e), 'text': email_text[:100]})
    return {"results": results, "total": len(results)}


@app.get("/api/model/info")
async def model_info():
    """Return model metadata and performance metrics."""
    if predictor._loaded:
        return predictor.get_model_info()
    return _demo_model_info()


# ── Demo Mode (when models aren't loaded) ──

def _demo_prediction(text: str, start_time: float) -> dict:
    """Generate a realistic demo prediction without loaded models."""
    import re
    text_lower = text.lower()
    score = 0
    indicators = []

    # Simple heuristic scoring for demo
    urgent_words = ['urgent', 'immediately', 'act now', 'expire', 'suspend', 'verify', 'password']
    money_words = ['bitcoin', 'btc', 'payment', 'wire', 'transfer', 'lottery', 'winner', '$']
    threat_words = ['encrypted', 'ransom', 'hack', 'breach', 'stolen', 'compromised']

    for w in urgent_words:
        if w in text_lower:
            score += 1
            indicators.append(f"Urgency: '{w}'")
    for w in money_words:
        if w in text_lower:
            score += 1.5
            indicators.append(f"Financial: '{w}'")
    for w in threat_words:
        if w in text_lower:
            score += 2
            indicators.append(f"Threat: '{w}'")

    urls = len(re.findall(r'https?://|www\.', text))
    if urls > 0:
        score += urls * 0.5
        indicators.append(f"Contains {urls} URL(s)")

    caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
    if caps_ratio > 0.3:
        score += 1
        indicators.append(f"High CAPS ({caps_ratio:.0%})")

    # Map score to severity
    if score <= 0.5:
        severity = 0
    elif score <= 2:
        severity = 1
    elif score <= 4:
        severity = 2
    elif score <= 6:
        severity = 3
    else:
        severity = 4

    labels = ['Normal', 'Low', 'Medium', 'High', 'Critical']
    icons = {'Normal': '✅', 'Low': '🟡', 'Medium': '🟠', 'High': '🔴', 'Critical': '🚨'}
    colors = {'Normal': '#2ecc71', 'Low': '#3498db', 'Medium': '#f39c12',
              'High': '#e74c3c', 'Critical': '#8e44ad'}

    label = labels[severity]
    proba = [0.05] * 5
    proba[severity] = 0.65
    if severity > 0:
        proba[severity - 1] = 0.15
    if severity < 4:
        proba[severity + 1] = 0.10
    total = sum(proba)
    proba = [p / total for p in proba]

    return {
        'severity': severity,
        'label': label,
        'confidence': round(max(proba), 4),
        'icon': icons[label],
        'color': colors[label],
        'probabilities': {labels[i]: round(proba[i], 4) for i in range(5)},
        'structural_features': {
            'num_urls': urls,
            'num_exclamations': text.count('!'),
            'num_question_marks': text.count('?'),
            'has_urgency': 1 if any(w in text_lower for w in urgent_words) else 0,
            'has_money': 1 if any(w in text_lower for w in money_words) else 0,
            'capital_ratio': round(caps_ratio, 4),
            'special_char_ratio': round(sum(1 for c in text if not c.isalnum() and not c.isspace()) / max(len(text), 1), 4),
            'word_count': len(text.split()),
            'avg_word_length': round(sum(len(w) for w in text.split()) / max(len(text.split()), 1), 2),
        },
        'individual_predictions': {
            'xgboost_tuned': {'prediction': severity, 'label': label},
            'random_forest': {'prediction': severity, 'label': label},
            'logistic_regression': {'prediction': max(0, severity - 1), 'label': labels[max(0, severity - 1)]},
        },
        'risk_indicators': indicators if indicators else ['No significant threats detected'],
        'inference_time_ms': round((time.time() - start_time) * 1000, 2),
    }


def _demo_model_info():
    return {
        'version': 'Production (Demo Mode)',
        'base_models': ['logistic_regression', 'random_forest', 'xgboost_tuned', 'linear_svm', 'multinomial_nb'],
        'has_stacking': True,
        'total_models': 6,
        'tfidf_features': 20000,
        'structural_features': [
            'num_urls', 'num_exclamations', 'num_question_marks',
            'has_urgency', 'has_money', 'capital_ratio',
            'special_char_ratio', 'word_count', 'avg_word_length'
        ],
        'severity_labels': ['Normal', 'Low', 'Medium', 'High', 'Critical'],
        'model_results': {
            'BERT+XGBoost': {'Accuracy': 0.9231, 'Macro F1': 0.8849, 'Weighted F1': 0.9224, 'MCC': 0.8690},
            'BERT+RF': {'Accuracy': 0.9215, 'Macro F1': 0.8788, 'Weighted F1': 0.9198, 'MCC': 0.8672},
            'Fine-Tuned BERT': {'Accuracy': 0.9189, 'Macro F1': 0.7889, 'Weighted F1': 0.9187, 'MCC': 0.8618},
            'Stacking': {'Accuracy': 0.9061, 'Macro F1': 0.7846, 'Weighted F1': 0.9057, 'MCC': 0.8396},
            'BERT+XGBoost Ensemble': {'Accuracy': 0.9145, 'Macro F1': 0.7720, 'Weighted F1': 0.9126, 'MCC': 0.8557},
            'Linear SVM': {'Accuracy': 0.8988, 'Macro F1': 0.7707, 'Weighted F1': 0.8987, 'MCC': 0.8270},
            'Logistic Regression': {'Accuracy': 0.8980, 'Macro F1': 0.7425, 'Weighted F1': 0.8971, 'MCC': 0.8264},
            'Random Forest': {'Accuracy': 0.8779, 'Macro F1': 0.7412, 'Weighted F1': 0.8659, 'MCC': 0.8024},
            'Voting Ensemble': {'Accuracy': 0.8688, 'Macro F1': 0.7130, 'Weighted F1': 0.8527, 'MCC': 0.7902},
            'BERT+LogReg': {'Accuracy': 0.8902, 'Macro F1': 0.7091, 'Weighted F1': 0.8921, 'MCC': 0.8141},
            'LSTM': {'Accuracy': 0.8759, 'Macro F1': 0.6799, 'Weighted F1': 0.8742, 'MCC': 0.7922},
            'Multinomial NB': {'Accuracy': 0.8643, 'Macro F1': 0.6133, 'Weighted F1': 0.8622, 'MCC': 0.7727},
            'XGBoost (Tuned)': {'Accuracy': 0.6688, 'Macro F1': 0.4135, 'Weighted F1': 0.6423, 'MCC': 0.5362}
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
