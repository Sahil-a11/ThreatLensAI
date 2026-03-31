"""
Inference engine for NLP Threat Severity Prediction.
Wraps preprocessing + model prediction pipeline.
"""

import re
import json
import logging
import numpy as np
import joblib
from pathlib import Path
from scipy.sparse import hstack, csr_matrix

import nltk
from nltk.corpus import stopwords, wordnet
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize

logger = logging.getLogger(__name__)

# Download NLTK data
for pkg in ['punkt', 'punkt_tab', 'stopwords', 'wordnet', 'omw-1.4']:
    nltk.download(pkg, quiet=True)

# Constants
SEVERITY_LABELS = [0, 1, 2, 3, 4]
SEVERITY_NAMES = ['Normal', 'Low', 'Medium', 'High', 'Critical']
SEVERITY_ICONS = {'Normal': '✅', 'Low': '🟡', 'Medium': '🟠', 'High': '🔴', 'Critical': '🚨'}
SEVERITY_COLORS = {
    'Normal': '#2ecc71', 'Low': '#3498db',
    'Medium': '#f39c12', 'High': '#e74c3c', 'Critical': '#8e44ad'
}

STRUCTURAL_FEATURES = [
    'num_urls', 'num_exclamations', 'num_question_marks',
    'has_urgency', 'has_money', 'capital_ratio',
    'special_char_ratio', 'word_count', 'avg_word_length'
]

# NLP setup
lemmatizer = WordNetLemmatizer()
stop_words = set(stopwords.words('english'))
stop_words -= {'not', 'no', 'never', 'against', 'very', 'urgent', 'immediately'}


def deobfuscate(text: str) -> str:
    """Normalize l33t-speak: @ → a, 0 → o, $ → s, etc."""
    for char, repl in {'@': 'a', '0': 'o', '1': 'i', '$': 's', '!': 'i', '3': 'e', '5': 's'}.items():
        text = text.replace(char, repl)
    return text


def extract_structural_features(text: str) -> dict:
    """Extract 9 behavioral/structural metadata features from raw email text."""
    text = str(text)
    word_list = text.split()
    return {
        'num_urls': len(re.findall(r'https?://|www\.', text)),
        'num_exclamations': text.count('!'),
        'num_question_marks': text.count('?'),
        'has_urgency': int(bool(re.search(
            r'urgent|immediately|act now|expire|suspend|verify|account.*lock',
            text, re.IGNORECASE))),
        'has_money': int(bool(re.search(
            r'\$|bitcoin|btc|payment|wire|transfer|lottery|winner',
            text, re.IGNORECASE))),
        'capital_ratio': sum(1 for c in text if c.isupper()) / max(len(text), 1),
        'special_char_ratio': sum(1 for c in text if not c.isalnum() and not c.isspace()) / max(len(text), 1),
        'word_count': len(word_list),
        'avg_word_length': np.mean([len(w) for w in word_list]) if word_list else 0,
    }


def preprocess_text(text: str) -> str:
    """Full NLP preprocessing pipeline.
    Order: HTML → URLs → deobfuscate → lowercase → tokenize → lemmatize"""
    text = str(text)
    if not text.strip():
        return ""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'https?://\S+|www\.\S+', ' ', text)
    text = deobfuscate(text)
    text = re.sub(r'[^a-zA-Z\s]', ' ', text.lower())
    text = re.sub(r'\s+', ' ', text).strip()
    tokens = word_tokenize(text)
    tokens = [lemmatizer.lemmatize(w) for w in tokens if w not in stop_words and len(w) > 1]
    return ' '.join(tokens)


class ThreatPredictor:
    """Production inference engine for email threat severity prediction."""

    def __init__(self, models_dir: str = "models"):
        self.models_dir = Path(models_dir)
        self.base_models = {}
        self.meta_learner = None
        self.tfidf = None
        self.scaler = None
        self.config = {}
        self.model_results = {}
        self._loaded = False

    def load(self):
        """Load all model artifacts from disk."""
        logger.info(f"Loading models from {self.models_dir}...")

        # Load config
        config_path = self.models_dir / 'config.json'
        if config_path.exists():
            with open(config_path) as f:
                self.config = json.load(f)
            logger.info(f"Config loaded: {self.config.get('version', 'unknown')}")

        # Load model results
        results_path = self.models_dir / 'model_results.json'
        if results_path.exists():
            with open(results_path) as f:
                self.model_results = json.load(f)
            logger.info(f"Results loaded: {len(self.model_results)} models")

        # Load TF-IDF vectorizer
        tfidf_path = self.models_dir / 'tfidf_vectorizer.pkl'
        if tfidf_path.exists():
            self.tfidf = joblib.load(tfidf_path)
            logger.info(f"TF-IDF loaded ({self.tfidf.max_features} features)")
        else:
            raise FileNotFoundError(f"TF-IDF vectorizer not found at {tfidf_path}")

        # Load structural scaler
        scaler_path = self.models_dir / 'structural_scaler.pkl'
        if scaler_path.exists():
            self.scaler = joblib.load(scaler_path)
            logger.info("Structural scaler loaded")
        else:
            raise FileNotFoundError(f"Scaler not found at {scaler_path}")

        # Load base models
        base_model_names = self.config.get('base_models', [
            'logistic_regression', 'random_forest', 'xgboost_tuned',
            'linear_svm', 'multinomial_nb'
        ])
        for name in base_model_names:
            model_path = self.models_dir / f'model_{name}.pkl'
            if model_path.exists():
                self.base_models[name] = joblib.load(model_path)
                logger.info(f"Base model loaded: {name}")
            else:
                logger.warning(f"Base model NOT found: {model_path}")

        # Load stacking meta-learner
        meta_path = self.models_dir / 'stacking_meta_learner.pkl'
        if meta_path.exists():
            self.meta_learner = joblib.load(meta_path)
            logger.info("Stacking meta-learner loaded")

        self._loaded = True
        logger.info(f"✅ All models loaded: {len(self.base_models)} base + "
                     f"{'stacking' if self.meta_learner else 'no stacking'}")

    def predict(self, email_text: str) -> dict:
        """Full inference: raw email → severity prediction with confidence."""
        if not self._loaded:
            self.load()

        if not email_text or not email_text.strip():
            return {
                'severity': 0,
                'label': 'Normal',
                'confidence': 1.0,
                'icon': '✅',
                'color': '#2ecc71',
                'probabilities': {name: 0.0 for name in SEVERITY_NAMES},
                'structural_features': {},
                'individual_predictions': {},
                'risk_indicators': [],
            }

        # Step 1: Extract structural features (from raw text)
        struct_feats = extract_structural_features(email_text)

        # Step 2: Preprocess text
        cleaned = preprocess_text(email_text)

        # Step 3: TF-IDF transform
        tfidf_vec = self.tfidf.transform([cleaned])

        # Step 4: Scale structural features
        struct_values = [struct_feats[f] for f in STRUCTURAL_FEATURES]
        struct_vec = csr_matrix(self.scaler.transform([struct_values]))

        # Step 5: Combine features
        combined = hstack([tfidf_vec, struct_vec])
        n_tfidf_cols = tfidf_vec.shape[1]

        # Step 6: Get predictions from each base model
        individual_predictions = {}
        meta_features = []

        for name, model in self.base_models.items():
            try:
                if name == 'multinomial_nb':
                    X = tfidf_vec  # NB needs non-negative (TF-IDF only)
                else:
                    X = combined

                if hasattr(model, 'predict_proba'):
                    proba = model.predict_proba(X)[0]
                    pred = int(np.argmax(proba))
                    meta_features.append(proba)
                else:
                    pred = int(model.predict(X)[0])
                    # Create one-hot for meta-features
                    one_hot = np.zeros(5)
                    one_hot[pred] = 1.0
                    meta_features.append(one_hot)
                    proba = one_hot

                individual_predictions[name] = {
                    'prediction': pred,
                    'label': SEVERITY_NAMES[pred],
                    'probabilities': {SEVERITY_NAMES[i]: float(proba[i]) for i in range(5)}
                }
            except Exception as e:
                logger.error(f"Error in {name}: {e}")
                individual_predictions[name] = {
                    'prediction': 0, 'label': 'Normal',
                    'probabilities': {n: 0.0 for n in SEVERITY_NAMES}
                }

        # Step 7: Stacking ensemble prediction
        if self.meta_learner and meta_features:
            stacked = np.hstack(meta_features).reshape(1, -1)
            if hasattr(self.meta_learner, 'predict_proba'):
                final_proba = self.meta_learner.predict_proba(stacked)[0]
            else:
                final_pred = self.meta_learner.predict(stacked)[0]
                final_proba = np.zeros(5)
                final_proba[final_pred] = 1.0
            severity = int(np.argmax(final_proba))
            confidence = float(np.max(final_proba))
        elif self.base_models:
            # Fallback: use best individual model (XGBoost or RF)
            fallback = self.base_models.get('xgboost_tuned',
                       self.base_models.get('random_forest',
                       list(self.base_models.values())[0]))
            X = combined
            if hasattr(fallback, 'predict_proba'):
                final_proba = fallback.predict_proba(X)[0]
                severity = int(np.argmax(final_proba))
                confidence = float(np.max(final_proba))
            else:
                severity = int(fallback.predict(X)[0])
                confidence = 1.0
                final_proba = np.zeros(5)
                final_proba[severity] = 1.0
        else:
            severity = 0
            confidence = 0.0
            final_proba = np.zeros(5)

        # Step 8: Risk indicators
        risk_indicators = []
        if struct_feats['num_urls'] > 0:
            risk_indicators.append(f"Contains {struct_feats['num_urls']} URL(s)")
        if struct_feats['has_urgency']:
            risk_indicators.append("Urgency language detected")
        if struct_feats['has_money']:
            risk_indicators.append("Financial/payment references")
        if struct_feats['capital_ratio'] > 0.2:
            risk_indicators.append(f"High CAPS usage ({struct_feats['capital_ratio']:.0%})")
        if struct_feats['special_char_ratio'] > 0.15:
            risk_indicators.append("High special character density")
        if struct_feats['num_exclamations'] > 2:
            risk_indicators.append(f"Excessive exclamation marks ({struct_feats['num_exclamations']})")

        # Step 9: Heuristic Threat Override (Hybrid ML + Rules system)
        # Real-world ML models often skew towards the middle. We apply a final deterministic check.
        num_triggers = len(risk_indicators)
        malicious_triggers = len([r for r in risk_indicators if "URL" not in r])
        
        # If it's a massive threat (3+ structural indicators) but the model graded it low
        if malicious_triggers >= 3 and severity < 4:
            severity = min(4, severity + 2) # Boost by 2 levels
            final_proba = np.zeros(5)
            final_proba[severity] = min(0.98, confidence + 0.30)
            confidence = final_proba[severity]
            
        # If the email is perfectly clean (0 malicious triggers) and model graded it Low(1) or Medium(2).
        elif malicious_triggers == 0 and severity in [1, 2]:
            severity = 0
            final_proba = np.zeros(5)
            final_proba[severity] = 0.95
            confidence = 0.95

        # Ensure label is always set based on the final severity
        label = SEVERITY_NAMES[severity]

        return {
            'severity': severity,
            'label': label,
            'confidence': round(confidence, 4),
            'icon': SEVERITY_ICONS.get(label, '❓'),
            'color': SEVERITY_COLORS.get(label, '#95a5a6'),
            'probabilities': {SEVERITY_NAMES[i]: round(float(final_proba[i]), 4) for i in range(5)},
            'structural_features': {k: round(float(v), 4) for k, v in struct_feats.items()},
            'individual_predictions': individual_predictions,
            'risk_indicators': risk_indicators,
        }

    def get_model_info(self) -> dict:
        """Return model metadata for dashboard display."""
        return {
            'version': self.config.get('version', 'v4.0'),
            'base_models': list(self.base_models.keys()),
            'has_stacking': self.meta_learner is not None,
            'total_models': len(self.base_models) + (1 if self.meta_learner else 0),
            'tfidf_features': self.tfidf.max_features if self.tfidf else 0,
            'structural_features': STRUCTURAL_FEATURES,
            'severity_labels': SEVERITY_NAMES,
            'model_results': self.model_results,
        }
