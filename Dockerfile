FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential unzip && \
    rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# NLTK data
RUN python -c "import nltk; nltk.download('punkt', quiet=True); nltk.download('punkt_tab', quiet=True); nltk.download('stopwords', quiet=True); nltk.download('wordnet', quiet=True); nltk.download('omw-1.4', quiet=True)"

# App code
COPY app/ app/

# Reassemble split model archives and extract to models/ at project root
# main.py resolves: Path(__file__).parent.parent / "models" => /app/models/
COPY models.zip.* .
RUN cat models.zip.* > models.zip && \
    unzip -o models.zip -d models/ && \
    rm -f models.zip models.zip.* && \
    echo "=== Models directory ===" && ls -la models/

EXPOSE 10000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
