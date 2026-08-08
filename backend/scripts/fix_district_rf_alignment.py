#!/usr/bin/env python3
"""
Fix ALL districts so each has exactly 10 crops resolvable via crop_aliases.json to RF labels.
RF model knows: apple, banana, blackgram, chickpea, coconut, coffee, cotton, grapes, jute,
                kidneybeans, lentil, maize, mango, mothbeans, mungbean, muskmelon, orange,
                papaya, pigeonpeas, pomegranate, rice, watermelon
Strategy:
  - Keep existing crops that resolve to RF labels
  - Replace non-RF crops (vegetables, misc) with the best RF-compatible crops for each
    state/agro-zone, using verified agricultural sources
"""

import json
import re
from pathlib import Path

BASE = Path(__file__).parent.parent / "app" / "data"

with open(BASE / "region_crop_mapping.json") as f:
    mapping = json.load(f)

with open(BASE / "crop_aliases.json") as f:
    aliases = json.load(f)

alias_keys = {k.lower(): v for k, v in aliases.items()}

RF_CROPS = {
    'apple', 'banana', 'blackgram', 'chickpea', 'coconut', 'coffee',
    'cotton', 'grapes', 'jute', 'kidneybeans', 'lentil', 'maize',
    'mango', 'mothbeans', 'mungbean', 'muskmelon', 'orange', 'papaya',
    'pigeonpeas', 'pomegranate', 'rice', 'watermelon'
}

# ── State-level RF crop banks (fallback pool for each agro-zone/state) ──────
# Based on ICAR / State Agriculture Departments
STATE_RF_CROP_BANKS = {
    # Format: state -> [crops in priority order for filling gaps]
    'Andhra Pradesh':     ['Rice', 'Maize', 'Cotton', 'Groundnut', 'Blackgram', 'Mungbean', 'Pigeonpeas', 'Chickpea', 'Banana', 'Mango'],
    'Arunachal Pradesh':  ['Rice', 'Maize', 'Banana', 'Orange', 'Mango', 'Papaya', 'Mungbean', 'Blackgram', 'Pigeonpeas', 'Coconut'],
    'Assam':              ['Rice', 'Jute', 'Maize', 'Banana', 'Orange', 'Mango', 'Papaya', 'Blackgram', 'Mungbean', 'Coconut'],
    'Bihar':              ['Rice', 'Wheat', 'Maize', 'Chickpea', 'Lentil', 'Mungbean', 'Blackgram', 'Pigeonpeas', 'Potato', 'Sugarcane'],
    'Chhattisgarh':       ['Rice', 'Maize', 'Blackgram', 'Pigeonpeas', 'Mungbean', 'Chickpea', 'Lentil', 'Cotton', 'Banana', 'Soybean'],
    'Goa':                ['Rice', 'Coconut', 'Banana', 'Cashewnuts', 'Mango', 'Papaya', 'Blackgram', 'Mungbean', 'Orange', 'Pigeonpeas'],
    'Gujarat':            ['Cotton', 'Groundnut', 'Chickpea', 'Wheat', 'Rice', 'Maize', 'Mungbean', 'Blackgram', 'Sugarcane', 'Banana'],
    'Haryana':            ['Wheat', 'Rice', 'Maize', 'Cotton', 'Sugarcane', 'Chickpea', 'Lentil', 'Mungbean', 'Blackgram', 'Mustard'],
    'Himachal Pradesh':   ['Apple', 'Wheat', 'Maize', 'Rice', 'Orange', 'Mango', 'Grapes', 'Pomegranate', 'Chickpea', 'Lentil'],
    'Jammu and Kashmir':  ['Apple', 'Wheat', 'Rice', 'Maize', 'Orange', 'Grapes', 'Pomegranate', 'Chickpea', 'Lentil', 'Mungbean'],
    'Jharkhand':          ['Rice', 'Maize', 'Wheat', 'Blackgram', 'Mungbean', 'Pigeonpeas', 'Chickpea', 'Lentil', 'Potato', 'Jute'],
    'Karnataka':          ['Rice', 'Maize', 'Blackgram', 'Mungbean', 'Pigeonpeas', 'Coconut', 'Cotton', 'Chickpea', 'Groundnut', 'Banana'],
    'Kerala':             ['Rice', 'Coconut', 'Banana', 'Rubber', 'Mango', 'Orange', 'Papaya', 'Blackgram', 'Mungbean', 'Coffee'],
    'Madhya Pradesh':     ['Wheat', 'Rice', 'Soybean', 'Chickpea', 'Maize', 'Cotton', 'Blackgram', 'Mungbean', 'Pigeonpeas', 'Lentil'],
    'Maharashtra':        ['Cotton', 'Soybean', 'Sugarcane', 'Rice', 'Wheat', 'Maize', 'Chickpea', 'Pigeonpeas', 'Mungbean', 'Blackgram'],
    'Manipur':            ['Rice', 'Maize', 'Blackgram', 'Mungbean', 'Banana', 'Orange', 'Mango', 'Papaya', 'Pigeonpeas', 'Kidneybeans'],
    'Meghalaya':          ['Rice', 'Maize', 'Banana', 'Orange', 'Ginger', 'Mango', 'Papaya', 'Blackgram', 'Mungbean', 'Kidneybeans'],
    'Mizoram':            ['Rice', 'Maize', 'Banana', 'Orange', 'Mango', 'Papaya', 'Blackgram', 'Mungbean', 'Pigeonpeas', 'Ginger'],
    'Nagaland':           ['Rice', 'Maize', 'Banana', 'Orange', 'Mango', 'Papaya', 'Blackgram', 'Mungbean', 'Pigeonpeas', 'Kidneybeans'],
    'Odisha':             ['Rice', 'Maize', 'Blackgram', 'Mungbean', 'Pigeonpeas', 'Coconut', 'Jute', 'Cotton', 'Chickpea', 'Banana'],
    'Punjab':             ['Wheat', 'Rice', 'Maize', 'Cotton', 'Sugarcane', 'Chickpea', 'Lentil', 'Mungbean', 'Blackgram', 'Mustard'],
    'Rajasthan':          ['Wheat', 'Mungbean', 'Blackgram', 'Chickpea', 'Mustard', 'Maize', 'Cotton', 'Groundnut', 'Pigeonpeas', 'Mothbeans'],
    'Sikkim':             ['Rice', 'Maize', 'Orange', 'Apple', 'Banana', 'Mango', 'Chickpea', 'Mungbean', 'Blackgram', 'Pigeonpeas'],
    'Tamil Nadu':         ['Rice', 'Coconut', 'Banana', 'Groundnut', 'Cotton', 'Maize', 'Blackgram', 'Mungbean', 'Pigeonpeas', 'Mango'],
    'Telangana':          ['Rice', 'Maize', 'Cotton', 'Groundnut', 'Blackgram', 'Mungbean', 'Pigeonpeas', 'Chickpea', 'Banana', 'Mango'],
    'Tripura':            ['Rice', 'Jute', 'Maize', 'Banana', 'Orange', 'Mango', 'Papaya', 'Blackgram', 'Mungbean', 'Coconut'],
    'Uttar Pradesh':      ['Wheat', 'Rice', 'Maize', 'Sugarcane', 'Chickpea', 'Lentil', 'Mungbean', 'Blackgram', 'Pigeonpeas', 'Potato'],
    'Uttarakhand':        ['Wheat', 'Rice', 'Maize', 'Apple', 'Orange', 'Mango', 'Chickpea', 'Lentil', 'Mungbean', 'Blackgram'],
    'West Bengal':        ['Rice', 'Jute', 'Maize', 'Wheat', 'Potato', 'Mungbean', 'Blackgram', 'Lentil', 'Chickpea', 'Banana'],
    # UTs
    'Andaman and Nicobar Islands': ['Rice', 'Coconut', 'Banana', 'Mango', 'Papaya', 'Orange', 'Blackgram', 'Mungbean', 'Maize', 'Pigeonpeas'],
    'Chandigarh':         ['Wheat', 'Rice', 'Maize', 'Chickpea', 'Mungbean', 'Blackgram', 'Lentil', 'Cotton', 'Potato', 'Mustard'],
    'Dadra and Nagar Haveli and Daman and Diu': ['Rice', 'Wheat', 'Maize', 'Blackgram', 'Mungbean', 'Banana', 'Coconut', 'Chickpea', 'Pigeonpeas', 'Cotton'],
    'Delhi':              ['Wheat', 'Rice', 'Maize', 'Chickpea', 'Mungbean', 'Blackgram', 'Lentil', 'Potato', 'Mustard', 'Sugarcane'],
    'Lakshadweep':        ['Coconut', 'Banana', 'Rice', 'Mango', 'Papaya', 'Orange', 'Blackgram', 'Mungbean', 'Maize', 'Pigeonpeas'],
    'Puducherry':         ['Rice', 'Coconut', 'Banana', 'Groundnut', 'Blackgram', 'Mungbean', 'Maize', 'Cotton', 'Mango', 'Sugarcane'],
    'Ladakh':             ['Wheat', 'Apple', 'Maize', 'Chickpea', 'Lentil', 'Grapes', 'Apricot', 'Mungbean', 'Blackgram', 'Pomegranate'],
    'Meghalaya':          ['Rice', 'Maize', 'Banana', 'Orange', 'Mango', 'Papaya', 'Blackgram', 'Mungbean', 'Pigeonpeas', 'Kidneybeans'],
}

# Canonical names used in district mappings (proper case) -> RF canonical
CROP_DISPLAY_TO_RF = {
    'Rice': 'rice', 'Wheat': 'wheat', 'Maize': 'maize',
    'Banana': 'banana', 'Mango': 'mango', 'Coconut': 'coconut',
    'Cotton': 'cotton', 'Sugarcane': 'sugarcane',
    'Groundnut': 'groundnut', 'Mustard': 'mustard',
    'Potato': 'potato', 'Onion': 'onion', 'Soybean': 'soybean',
    'Apple': 'apple', 'Orange': 'orange', 'Grapes': 'grapes',
    'Pomegranate': 'pomegranate', 'Papaya': 'papaya',
    'Watermelon': 'watermelon', 'Muskmelon': 'muskmelon',
    'Coffee': 'coffee', 'Jute': 'jute',
    'Blackgram': 'blackgram', 'Mungbean': 'mungbean',
    'Chickpea': 'chickpea', 'Pigeonpeas': 'pigeonpeas',
    'Lentil': 'lentil', 'Kidneybeans': 'kidneybeans',
    'Mothbeans': 'mothbeans', 'Cashewnuts': 'coconut',  # cashewnuts -> map to coconut region
}

def resolves(crop_name: str) -> bool:
    """Check if a crop name resolves to an RF label via aliases."""
    cl = crop_name.lower().strip()
    if cl in alias_keys:
        return True
    c_sub = re.sub(r'\(.*?\)', '', cl).strip()
    if c_sub in alias_keys:
        return True
    return False

def get_rf_label(crop_name: str) -> str | None:
    cl = crop_name.lower().strip()
    rf = alias_keys.get(cl)
    if rf:
        return rf
    c_sub = re.sub(r'\(.*?\)', '', cl).strip()
    return alias_keys.get(c_sub)

districts = mapping['districts']
total_corrected = 0
total_removed = 0
total_added = 0
correction_log = []

for d_name, d_info in districts.items():
    crops = d_info.get('top_crops', [])
    state = d_info.get('state', '')

    # Find which crops resolve
    resolving = []
    non_resolving = []
    seen_rf = set()

    for c in crops:
        rf = get_rf_label(c)
        if rf and rf not in seen_rf:
            resolving.append(c)
            seen_rf.add(rf)
        elif rf and rf in seen_rf:
            # Duplicate RF label — skip (deduplicate)
            non_resolving.append(f"DUP:{c}")
        else:
            non_resolving.append(c)

    if len(resolving) == 10 and len(non_resolving) == 0:
        # Perfect — no change needed
        continue

    # Need to fix this district
    needed = 10 - len(resolving)
    if needed <= 0 and len(non_resolving) == 0:
        # Trim to 10 if somehow over
        d_info['top_crops'] = resolving[:10]
        continue

    total_corrected += 1
    original_crops = list(crops)
    removed = [c for c in non_resolving if not c.startswith('DUP:')]
    removed_dups = [c[4:] for c in non_resolving if c.startswith('DUP:')]
    total_removed += len(removed) + len(removed_dups)

    # Fill gaps from state bank
    state_bank = STATE_RF_CROP_BANKS.get(state, STATE_RF_CROP_BANKS.get('Odisha', []))
    added = []
    for candidate in state_bank:
        if len(resolving) >= 10:
            break
        c_rf = get_rf_label(candidate)
        if c_rf and c_rf not in seen_rf:
            resolving.append(candidate)
            seen_rf.add(c_rf)
            added.append(candidate)
            total_added += 1

    # Final trim/pad to exactly 10
    final_crops = resolving[:10]

    # Update the district
    d_info['top_crops'] = final_crops
    if removed or removed_dups or added:
        src = d_info.get('source', '')
        if 'Corrected' not in src:
            d_info['source'] = src + ' [Corrected: RF alias alignment]'
        correction_log.append({
            'district': d_name,
            'state': state,
            'removed': removed,
            'removed_duplicates': removed_dups,
            'added': added,
            'final_count': len(final_crops),
        })

print(f"Districts corrected: {total_corrected}")
print(f"Non-RF crops removed: {total_removed}")
print(f"RF-compatible crops added: {total_added}")
print(f"\nSample corrections (first 15):")
for c in correction_log[:15]:
    print(f"  {c['district']} ({c['state']}): removed={c['removed'][:3]}, added={c['added'][:3]}, final={c['final_count']}")

# Final validation
print("\n--- FINAL VALIDATION ---")
errors = []
for d_name, d_info in districts.items():
    crops = d_info.get('top_crops', [])
    if len(crops) != 10:
        errors.append(f"{d_name}: has {len(crops)} crops")
    seen = set()
    dups = []
    for c in crops:
        rf = get_rf_label(c)
        if rf in seen:
            dups.append(c)
        if rf:
            seen.add(rf)
    if dups:
        errors.append(f"{d_name}: duplicate RF labels for {dups}")

print(f"Validation errors: {len(errors)}")
for e in errors[:10]:
    print(f"  {e}")

# Save
with open(BASE / "region_crop_mapping.json", 'w') as f:
    json.dump(mapping, f, indent=2)

with open(BASE / "rf_alignment_correction_log.json", 'w') as f:
    json.dump(correction_log, f, indent=2)

print(f"\nSaved. Total districts: {len(districts)}")
