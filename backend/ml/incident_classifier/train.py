"""
Phase 9 — Incident Classifier Training Pipeline
==================================================
Trains a RandomForestClassifier for Vanguard incident classification.

Strategy:
    1. class_weight='balanced' (primary imbalance handling)
    2. SMOTE-ENN hybrid (secondary, via imblearn pipeline)
    3. Stratified train/test split
    4. F1-macro quality gate ≥ 0.70

Output:
    - Trained model (.joblib) → uploaded to GCS
    - Label encoder (.joblib) → uploaded alongside model
    - Training report (JSON) → logged and optionally stored

Usage:
    python -m ml.incident_classifier.train [--source-file path] [--upload]
"""

import os
import io
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple

import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, f1_score

logger = logging.getLogger("ml.incident_classifier.train")

# ─────────────────────────────────────────────
# Defaults
# ─────────────────────────────────────────────
MODEL_VERSION_PREFIX = "incident_classifier"
GCS_BUCKET = os.getenv("ML_ARTIFACTS_BUCKET", "quantsight-ml-artifacts")
GCS_MODEL_PATH = "models/incident_classifier"
QUALITY_GATE_F1_MACRO = 0.70
TEST_SIZE = 0.20
RANDOM_STATE = 42


def _try_smote_pipeline(X_train, y_train) -> Tuple:
    """Try SMOTE-ENN, fall back to plain classifier if minority class too small.
    
    Returns:
        (model, used_smote: bool)
    """
    try:
        from imblearn.pipeline import Pipeline as ImbPipeline
        from imblearn.combine import SMOTEENN
        
        # Check minimum samples per class for SMOTE (needs at least k+1=6)
        from collections import Counter
        class_counts = Counter(y_train)
        min_count = min(class_counts.values())
        
        if min_count < 6:
            logger.warning(
                f"Smallest class has {min_count} samples (< 6). "
                f"SMOTE requires k_neighbors+1. Falling back to class_weight only."
            )
            model = RandomForestClassifier(
                n_estimators=100,
                class_weight="balanced",
                max_depth=15,
                min_samples_split=3,
                min_samples_leaf=2,
                random_state=RANDOM_STATE,
                n_jobs=-1,
            )
            model.fit(X_train, y_train)
            return model, False
        
        # Use SMOTE-ENN with conservative k_neighbors
        k = min(5, min_count - 1)
        pipeline = ImbPipeline([
            ("resample", SMOTEENN(
                random_state=RANDOM_STATE,
                smote={"k_neighbors": k},
            )),
            ("clf", RandomForestClassifier(
                n_estimators=100,
                class_weight="balanced",
                max_depth=15,
                min_samples_split=3,
                min_samples_leaf=2,
                random_state=RANDOM_STATE,
                n_jobs=-1,
            )),
        ])
        pipeline.fit(X_train, y_train)
        return pipeline, True
        
    except ImportError:
        logger.warning("imbalanced-learn not available. Using class_weight='balanced' only.")
        model = RandomForestClassifier(
            n_estimators=100,
            class_weight="balanced",
            max_depth=15,
            min_samples_split=3,
            min_samples_leaf=2,
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )
        model.fit(X_train, y_train)
        return model, False


def train_classifier(
    incidents: list,
    upload: bool = False,
) -> Dict[str, Any]:
    """Train the incident classifier.
    
    Args:
        incidents: List of incident dictionaries (from Firestore or BQ)
        upload: Whether to upload the model to GCS
        
    Returns:
        Training report dictionary
    """
    from ml.incident_classifier.features import (
        extract_features_batch,
        extract_labels,
    )
    
    logger.info(f"Training incident classifier on {len(incidents)} incidents")
    
    # ─── Step 1: Feature extraction ───
    X = extract_features_batch(incidents)
    y, label_encoder = extract_labels(incidents)
    
    feature_names = list(X.columns)
    logger.info(f"Feature matrix: {X.shape[0]} samples × {X.shape[1]} features")
    logger.info(f"Classes: {list(label_encoder.classes_)}")
    
    # ─── Step 2: Train/test split (stratified) ───
    # For very small classes, merge them into test via stratify
    try:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y,
            test_size=TEST_SIZE,
            random_state=RANDOM_STATE,
            stratify=y,
        )
    except ValueError:
        # If stratification fails (class with only 1 sample), use shuffle only
        logger.warning("Stratification failed (class with ≤1 sample). Using random split.")
        X_train, X_test, y_train, y_test = train_test_split(
            X, y,
            test_size=TEST_SIZE,
            random_state=RANDOM_STATE,
        )
    
    logger.info(f"Train: {len(X_train)} samples, Test: {len(X_test)} samples")
    
    # ─── Step 3: Train with SMOTE-ENN or fallback ───
    model, used_smote = _try_smote_pipeline(X_train.values, y_train)
    
    # ─── Step 4: Evaluate ───
    if used_smote:
        y_pred = model.predict(X_test.values)
    else:
        y_pred = model.predict(X_test.values)
    
    f1_macro = f1_score(y_test, y_pred, average="macro", zero_division=0)
    f1_weighted = f1_score(y_test, y_pred, average="weighted", zero_division=0)
    
    # Full classification report
    target_names = label_encoder.inverse_transform(sorted(set(y_test) | set(y_pred)))
    report_str = classification_report(
        y_test, y_pred,
        target_names=target_names,
        zero_division=0,
    )
    report_dict = classification_report(
        y_test, y_pred,
        target_names=target_names,
        zero_division=0,
        output_dict=True,
    )
    
    logger.info(f"\n{'='*60}\nClassification Report:\n{report_str}")
    
    # ─── Step 5: Quality gate ───
    passed_gate = f1_macro >= QUALITY_GATE_F1_MACRO
    
    if passed_gate:
        logger.info(f"✅ QUALITY GATE PASSED: F1-macro={f1_macro:.4f} ≥ {QUALITY_GATE_F1_MACRO}")
    else:
        logger.warning(f"⚠️ QUALITY GATE FAILED: F1-macro={f1_macro:.4f} < {QUALITY_GATE_F1_MACRO}")
    
    # ─── Step 6: Feature importance ───
    if hasattr(model, "feature_importances_"):
        importances = model.feature_importances_
    elif hasattr(model, "named_steps") and hasattr(model.named_steps.get("clf", None), "feature_importances_"):
        importances = model.named_steps["clf"].feature_importances_
    else:
        importances = np.zeros(len(feature_names))
    
    top_features = sorted(
        zip(feature_names, importances),
        key=lambda x: x[1],
        reverse=True,
    )[:15]
    
    logger.info("Top 15 features:")
    for name, imp in top_features:
        logger.info(f"  {name}: {imp:.4f}")
    
    # ─── Step 7: Build report ───
    version = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    
    training_report = {
        "model_version": f"{MODEL_VERSION_PREFIX}_v{version}",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "corpus_size": len(incidents),
        "train_size": len(X_train),
        "test_size": len(X_test),
        "n_features": len(feature_names),
        "n_classes": len(label_encoder.classes_),
        "classes": list(label_encoder.classes_),
        "used_smote": used_smote,
        "f1_macro": round(f1_macro, 4),
        "f1_weighted": round(f1_weighted, 4),
        "quality_gate_passed": passed_gate,
        "quality_gate_threshold": QUALITY_GATE_F1_MACRO,
        "top_features": [{"name": n, "importance": round(i, 4)} for n, i in top_features],
        "per_class_metrics": {
            k: {m: round(v, 4) for m, v in metrics.items()}
            for k, metrics in report_dict.items()
            if isinstance(metrics, dict)
        },
        "feature_names": feature_names,
    }
    
    # ─── Step 8: Save locally ───
    artifacts_dir = os.path.join(os.path.dirname(__file__), "..", "..", "ml_artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)
    
    model_path = os.path.join(artifacts_dir, "incident_classifier.joblib")
    encoder_path = os.path.join(artifacts_dir, "label_encoder.joblib")
    report_path = os.path.join(artifacts_dir, "training_report.json")
    
    joblib.dump(model, model_path)
    joblib.dump(label_encoder, encoder_path)
    
    with open(report_path, "w") as f:
        json.dump(training_report, f, indent=2)
    
    model_size_mb = os.path.getsize(model_path) / (1024 * 1024)
    logger.info(f"Model saved: {model_path} ({model_size_mb:.2f} MB)")
    logger.info(f"Encoder saved: {encoder_path}")
    logger.info(f"Report saved: {report_path}")
    
    # ─── Step 9: Upload to GCS (optional) ───
    if upload and passed_gate:
        try:
            _upload_to_gcs(model_path, encoder_path, report_path, version)
        except Exception as e:
            logger.error(f"GCS upload failed: {e}")
    elif upload and not passed_gate:
        logger.warning("Skipping GCS upload — quality gate not passed")
    
    return training_report


def _upload_to_gcs(
    model_path: str,
    encoder_path: str,
    report_path: str,
    version: str,
):
    """Upload model artifacts to GCS."""
    from google.cloud import storage
    
    client = storage.Client()
    bucket = client.bucket(GCS_BUCKET)
    
    files = {
        f"{GCS_MODEL_PATH}/{version}/model.joblib": model_path,
        f"{GCS_MODEL_PATH}/{version}/label_encoder.joblib": encoder_path,
        f"{GCS_MODEL_PATH}/{version}/training_report.json": report_path,
        # Also upload as "latest" for lazy loading
        f"{GCS_MODEL_PATH}/latest.joblib": model_path,
        f"{GCS_MODEL_PATH}/latest_encoder.joblib": encoder_path,
    }
    
    for gcs_path, local_path in files.items():
        blob = bucket.blob(gcs_path)
        blob.upload_from_filename(local_path)
        logger.info(f"  Uploaded → gs://{GCS_BUCKET}/{gcs_path}")
    
    logger.info(f"✅ All artifacts uploaded to GCS (version={version})")


# ─────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import asyncio
    
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    
    source_file = None
    upload = "--upload" in sys.argv
    
    if "--source-file" in sys.argv:
        idx = sys.argv.index("--source-file")
        source_file = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
    
    # Load incidents
    if source_file:
        import json as _json
        with open(source_file, "r") as f:
            data = _json.load(f)
        incidents = data.get("incidents", data if isinstance(data, list) else [])
    else:
        from vanguard.export.incident_exporter import IncidentExporter
        exporter = IncidentExporter()
        incidents = asyncio.run(exporter.fetch_incidents_from_firestore())
    
    # Train
    report = train_classifier(incidents, upload=upload)
    
    print(f"\n{'='*60}")
    print(f"Model: {report['model_version']}")
    print(f"F1-macro: {report['f1_macro']}")
    print(f"Quality gate: {'PASSED ✅' if report['quality_gate_passed'] else 'FAILED ⚠️'}")
    print(f"{'='*60}")
