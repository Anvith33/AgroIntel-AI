"""
rf_candidate_adapter.py — Phase 4 Random Forest Candidate Filter & Feature Adapter

Connects validated candidate crop vectors with the existing 22-class Random Forest model.

CRITICAL RULES:
1. The Random Forest model may ONLY evaluate and rank crops that passed the evidence and agronomic suitability candidate filter.
2. The Random Forest model MUST NOT introduce any crop that was not in the input candidate list.
3. Crops in the candidate set that are not present in the RF 22-class training set (e.g. Wheat, Sugarcane, Mustard, Potato) are preserved using transparent evidence & agronomic suitability scores.
"""

import sys
import os
import json
import pickle
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
MODELS_DIR = BASE_DIR / "models"
RF_PATH = MODELS_DIR / "crop_recommender_rf.pkl"
ENCODER_PATH = MODELS_DIR / "crop_recommender_encoder.pkl"

# Mapping from canonical crop names to RF 22-class label names
CANONICAL_TO_RF_LABEL = {
    "Rice": "rice",
    "Maize": "maize",
    "Chickpea (Gram)": "chickpea",
    "Moong (Green Gram)": "mungbean",
    "Black Gram (Urad)": "blackgram",
    "Pigeonpea (Arhar/Tur)": "pigeonpeas",
    "Lentil (Masoor)": "lentil",
    "Cotton": "cotton",
    "Jute": "jute",
    "Banana": "banana",
    "Coconut": "coconut",
    "Coffee": "coffee",
    "Groundnut": "mothbeans" # Closest legume proxy if needed, or mapped
}

class RFCandidateAdapter:
    def __init__(self):
        self.rf_model = None
        self.encoder = None
        self.rf_classes = []
        self._load_models()

    def _load_models(self):
        if RF_PATH.exists() and ENCODER_PATH.exists():
            try:
                with open(RF_PATH, "rb") as f:
                    self.rf_model = pickle.load(f)
                with open(ENCODER_PATH, "rb") as f:
                    self.encoder = pickle.load(f)
                self.rf_classes = list(self.encoder.classes_)
                print(f"[RFCandidateAdapter] Loaded RF model ({len(self.rf_classes)} crop classes).")
            except Exception as e:
                print(f"[RFCandidateAdapter] Warning: Error loading RF model: {e}")
        else:
            print("[RFCandidateAdapter] Model files not found. Adapter running in agronomic evidence mode.")

    def rank_candidates(self, district_id, season, candidate_list, soil_features=None, weather_features=None, previous_crop=None):
        """
        Ranks candidate crops for a given district & season.
        ONLY crops present in candidate_list can be returned.
        RF model cannot introduce outside crops.
        """
        if not candidate_list:
            return []

        # Default environmental features for RF feature vector [N, P, K, temp, humidity, ph, rainfall]
        s_feat = soil_features or {"N": 60, "P": 40, "K": 40, "ph": 6.5}
        w_feat = weather_features or {"temperature": 25.0, "humidity": 70.0, "rainfall": 1000.0}

        feature_vector = np.array([[
            float(s_feat.get("N", 60)),
            float(s_feat.get("P", 40)),
            float(s_feat.get("K", 40)),
            float(w_feat.get("temperature", 25.0)),
            float(w_feat.get("humidity", 70.0)),
            float(s_feat.get("ph", 6.5)),
            float(w_feat.get("rainfall", 1000.0))
        ]])

        rf_prob_map = {}
        if self.rf_model and self.encoder:
            try:
                probs = self.rf_model.predict_proba(feature_vector)[0]
                for idx, cls_name in enumerate(self.rf_classes):
                    rf_prob_map[cls_name.lower()] = float(probs[idx])
            except Exception as e:
                print(f"[RFCandidateAdapter] RF prediction warning: {e}")

        ranked_results = []
        valid_candidate_names = set(c["crop"] for c in candidate_list)

        for candidate in candidate_list:
            c_name = candidate["crop"]

            # Map candidate to RF label
            rf_label = CANONICAL_TO_RF_LABEL.get(c_name, c_name.lower())
            
            rf_score = 0.0
            is_rf_compatible = False

            if rf_label.lower() in rf_prob_map:
                rf_score = rf_prob_map[rf_label.lower()]
                is_rf_compatible = True

            # Calculate Evidence & Agronomic Composite Score
            hist_score = candidate.get("historical_consistency_score", 0.5)
            soil_score = candidate.get("soil_suitability_score", 0.8)
            weather_score = candidate.get("weather_suitability_score", 0.8)
            water_score = candidate.get("water_suitability_score", 0.8)
            rotation_score = candidate.get("rotation_compatibility_score", 0.75)
            duration_score = candidate.get("duration_compatibility_score", 0.8)

            agronomic_score = (soil_score * 0.25) + (weather_score * 0.25) + (water_score * 0.20) + (rotation_score * 0.15) + (duration_score * 0.15)
            
            if is_rf_compatible:
                final_score = round((hist_score * 0.35) + (agronomic_score * 0.35) + (rf_score * 0.30), 4)
                compatibility_status = "RF_COMPATIBLE"
            else:
                final_score = round((hist_score * 0.50) + (agronomic_score * 0.50), 4)
                compatibility_status = "RF_INCOMPATIBLE_EVIDENCE_PRESERVED"

            ranked_results.append({
                "crop": c_name,
                "district_id": district_id,
                "season": season,
                "evidence_status": candidate.get("historical_evidence_status", "HISTORICAL"),
                "historical_evidence_score": hist_score,
                "current_evidence_status": candidate.get("current_evidence_status", "INSUFFICIENT"),
                "soil_suitability_status": candidate.get("soil_suitability_status", "SUITABLE"),
                "weather_suitability_status": candidate.get("weather_suitability_status", "SUITABLE"),
                "water_suitability_status": candidate.get("water_suitability_status", "SUITABLE"),
                "duration_compatibility_status": candidate.get("duration_compatibility_status", "SUITABLE"),
                "rotation_compatibility_score": rotation_score,
                "agronomic_composite_score": round(agronomic_score, 4),
                "rf_score": round(rf_score, 4) if is_rf_compatible else None,
                "rf_compatibility_status": compatibility_status,
                "final_candidate_confidence": final_score
            })

        # STRICT RULE: Sort ONLY the input candidates. Cannot add external crops!
        ranked_results.sort(key=lambda x: x["final_candidate_confidence"], reverse=True)
        return ranked_results

if __name__ == "__main__":
    adapter = RFCandidateAdapter()
    test_candidates = [
        {"crop": "Rice", "historical_consistency_score": 0.90, "soil_suitability_score": 0.9, "weather_suitability_score": 0.85, "water_suitability_score": 0.9, "rotation_compatibility_score": 0.75, "duration_compatibility_score": 0.85, "historical_evidence_status": "HISTORICAL", "current_evidence_status": "INSUFFICIENT"},
        {"crop": "Wheat", "historical_consistency_score": 0.85, "soil_suitability_score": 0.85, "weather_suitability_score": 0.8, "water_suitability_score": 0.8, "rotation_compatibility_score": 0.80, "duration_compatibility_score": 0.85, "historical_evidence_status": "HISTORICAL", "current_evidence_status": "INSUFFICIENT"},
        {"crop": "Moong (Green Gram)", "historical_consistency_score": 0.75, "soil_suitability_score": 0.8, "weather_suitability_score": 0.8, "water_suitability_score": 0.85, "rotation_compatibility_score": 0.95, "duration_compatibility_score": 0.90, "historical_evidence_status": "HISTORICAL", "current_evidence_status": "INSUFFICIENT"}
    ]
    ranked = adapter.rank_candidates("Karnataka::Udupi", "Kharif", test_candidates)
    print("\nTest Candidate Adapter Ranking:")
    for r in ranked:
        print(f"  {r['crop']:<22} | Final Conf: {r['final_candidate_confidence']} | RF Compatible: {r['rf_compatibility_status']} | RF Score: {r['rf_score']}")
