# ============================================================
# 📦 EXPORT MODELS FOR DEPLOYMENT — Paste this cell in Colab
# ============================================================
# This does NOT retrain anything. It just packages your
# already-trained models into a single zip file for download.
# Run time: ~30 seconds
# ============================================================

import pickle, joblib, shutil, json
from pathlib import Path
from google.colab import files

CHECKPOINT_DIR = Path('/content/drive/MyDrive/NLP_Checkpoints_V3')
EXPORT_DIR = Path('/content/deployment_export')
EXPORT_DIR.mkdir(exist_ok=True)

print("📦 Exporting trained models for deployment...")
print("   (No retraining — just packaging existing checkpoints)\n")

# ── 1. Load all base models from checkpoints ──
base_model_names = {
    'logistic_regression': 'model_v3_logistic_regression',
    'random_forest': 'model_v3_random_forest',
    'xgboost_tuned': 'model_v3_xgboost_tuned',
    'linear_svm': 'model_v3_linear_svm',
    'multinomial_nb': 'model_v3_multinomial_nb',
}

base_models = {}
for short_name, ckpt_name in base_model_names.items():
    ckpt_path = CHECKPOINT_DIR / f'{ckpt_name}.pkl'
    if ckpt_path.exists():
        with open(ckpt_path, 'rb') as f:
            ckpt = pickle.load(f)
        base_models[short_name] = ckpt['model']
        print(f"  ✅ Loaded: {short_name}")
    else:
        print(f"  ⚠️ NOT FOUND: {ckpt_name}")

# ── 2. Load stacking meta-learner ──
stacking_path = CHECKPOINT_DIR / 'model_v3_stacking.pkl'
if stacking_path.exists():
    with open(stacking_path, 'rb') as f:
        stacking_ckpt = pickle.load(f)
    meta_learner = stacking_ckpt['model']['meta_learner']
    print(f"  ✅ Loaded: stacking meta-learner")
else:
    print("  ⚠️ Stacking checkpoint not found!")
    meta_learner = None

# ── 3. Load TF-IDF and Scaler from feature checkpoint ──
feat_path = CHECKPOINT_DIR / 'feature_matrices_v3.pkl'
if feat_path.exists():
    with open(feat_path, 'rb') as f:
        feat_data = pickle.load(f)
    tfidf = feat_data['tfidf']
    scaler = feat_data['scaler']
    print(f"  ✅ Loaded: tfidf_vectorizer")
    print(f"  ✅ Loaded: structural_scaler")
else:
    # Fallback: check final_models dir
    models_dir = CHECKPOINT_DIR / 'final_models'
    tfidf = joblib.load(models_dir / 'tfidf_vectorizer.pkl')
    scaler = joblib.load(models_dir / 'structural_scaler.pkl')
    print(f"  ✅ Loaded from final_models/")

# ── 4. Load results summary ──
results_path = CHECKPOINT_DIR / 'v3_results_summary.pkl'
results_summary = {}
if results_path.exists():
    with open(results_path, 'rb') as f:
        results_summary = pickle.load(f)
    print(f"  ✅ Loaded: results summary ({len(results_summary)} models)")

# ── 5. Save everything to export directory ──
print("\n💾 Saving export files...")

# Save base models individually (smaller files, easier to debug)
for name, model in base_models.items():
    joblib.dump(model, EXPORT_DIR / f'model_{name}.pkl')
    print(f"  💾 model_{name}.pkl")

# Save meta-learner
if meta_learner:
    joblib.dump(meta_learner, EXPORT_DIR / 'stacking_meta_learner.pkl')
    print(f"  💾 stacking_meta_learner.pkl")

# Save TF-IDF and Scaler
joblib.dump(tfidf, EXPORT_DIR / 'tfidf_vectorizer.pkl')
joblib.dump(scaler, EXPORT_DIR / 'structural_scaler.pkl')
print(f"  💾 tfidf_vectorizer.pkl")
print(f"  💾 structural_scaler.pkl")

# Save results as JSON (for dashboard display)
import numpy as np
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)): return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, np.ndarray): return obj.tolist()
        return super().default(obj)

with open(EXPORT_DIR / 'model_results.json', 'w') as f:
    json.dump(results_summary, f, indent=2, cls=NumpyEncoder)
print(f"  💾 model_results.json")

# Save model config metadata
config = {
    'base_models': list(base_models.keys()),
    'has_stacking': meta_learner is not None,
    'tfidf_max_features': tfidf.max_features,
    'structural_features': [
        'num_urls', 'num_exclamations', 'num_question_marks',
        'has_urgency', 'has_money', 'capital_ratio',
        'special_char_ratio', 'word_count', 'avg_word_length'
    ],
    'severity_labels': ['Normal', 'Low', 'Medium', 'High', 'Critical'],
    'version': 'v4.0',
}
with open(EXPORT_DIR / 'config.json', 'w') as f:
    json.dump(config, f, indent=2)
print(f"  💾 config.json")

# ── 6. Zip everything ──
zip_path = '/content/nlp_deployment_models'
shutil.make_archive(zip_path, 'zip', EXPORT_DIR)
print(f"\n✅ Export complete! Total files: {len(list(EXPORT_DIR.glob('*')))}")
print(f"📦 Zip file: {zip_path}.zip")

# ── 7. Auto-download ──
print("\n⬇️ Downloading zip file to your computer...")
files.download(f'{zip_path}.zip')
print("🎉 Done! Extract the zip and place files in nlp_threat_dashboard/models/")
