---
title: ThreatLens AI - Email Threat Intelligence
emoji: 🛡️
colorFrom: indigo
colorTo: purple
sdk: docker
pinned: true
license: mit
app_port: 7860
---

# 🛡️ ThreatLens AI — Email Threat Intelligence Dashboard

**Beyond Binary: NLP-Based Multi-Class Threat Severity Prediction**

An industry-level dashboard for analyzing email threats using a Stacking Ensemble of 5 ML models trained on 50,000+ emails across 5 severity levels.

## Features

- **Real-time Email Scanning** — Paste any email and get instant severity prediction
- **Stacking Ensemble** — Combines XGBoost, Random Forest, Logistic Regression, SVM, and Naive Bayes
- **Risk Indicators** — Identifies urgency language, suspicious URLs, financial references
- **Model Performance Dashboard** — Compare 13 models across accuracy, F1, and MCC
- **Scan Analytics** — Track threats over time with distribution charts

## Architecture

```
Raw Email → Text Preprocessing → TF-IDF (20K) + Structural Features (9)
         → 5 Base Models → Stacking Meta-Learner → Severity Prediction
```

## Severity Levels

| Level | Description | Example |
|-------|------------|---------|
| ✅ Normal | Legitimate email | Team meeting reminder |
| 🟡 Low | Minor suspicious elements | Unsolicited marketing |
| 🟠 Medium | Moderate threat indicators | Credential harvesting attempt |
| 🔴 High | Significant threat | Spear phishing with urgency |
| 🚨 Critical | Severe threat | Ransomware/BEC attack |

## Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: Vanilla HTML/CSS/JS (Glassmorphism design)
- **ML**: scikit-learn, XGBoost
- **Deployment**: Docker on Hugging Face Spaces
