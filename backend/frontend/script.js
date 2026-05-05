const API_BASE = '/api';

// ── Crop Recommendation ──────────────────────────────────────────────────────
document.getElementById('cropForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const btn = document.getElementById('cropSubmitBtn');
    const originalHTML = btn.innerHTML;
    btn.innerHTML = '<span class="spinner"></span> Analyzing...';
    btn.disabled = true;

    const payload = { location: document.getElementById('location').value.trim() };

    try {
        const response = await fetch(`${API_BASE}/predict/crop`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error(`Server error: ${response.status}`);
        const data = await response.json();

        // Primary crop
        document.getElementById('cropOutput').textContent = data.recommended_crop;

        // Soil badge — use soil_badge from API if present, else build it
        const soilBadge = data.soil_badge || `🌱 ${data.inferred_soil}`;
        document.getElementById('inferredSoil').textContent = soilBadge;

        // Coastal badge
        const coastalEl = document.getElementById('coastalBadge');
        if (data.is_coastal) {
            coastalEl.classList.remove('hidden');
        } else {
            coastalEl.classList.add('hidden');
        }

        // Data source badge
        const dsBadge = document.getElementById('dataSourceBadge');
        if (data.data_source && data.data_source.startsWith('mandi_data')) {
            dsBadge.textContent = '📊 Mandi Data';
            dsBadge.style.color = '#10b981';
            dsBadge.style.borderColor = 'rgba(16,185,129,0.3)';
            dsBadge.style.background = 'rgba(16,185,129,0.2)';
            dsBadge.classList.remove('hidden');
        } else if (data.data_source === 'soil_weather_model') {
            dsBadge.textContent = '🤖 AI Prediction';
            dsBadge.style.color = '#a855f7';
            dsBadge.style.borderColor = 'rgba(168,85,247,0.3)';
            dsBadge.style.background = 'rgba(168,85,247,0.2)';
            dsBadge.classList.remove('hidden');
        } else {
            dsBadge.classList.add('hidden');
        }

        // Weather summary strip
        const wd = data.weather_data || {};
        document.getElementById('weatherTemp').textContent =
            `🌡️ ${wd.temperature !== undefined ? wd.temperature.toFixed(1) + '°C' : '--'}`;
        document.getElementById('weatherHumidity').textContent =
            `💧 ${wd.humidity !== undefined ? wd.humidity.toFixed(0) + '%' : '--'}`;
        document.getElementById('weatherRain').textContent =
            `🌧️ ${data.effective_rain !== undefined ? data.effective_rain + ' mm' : '--'}`;

        // Reasoning & water source
        document.getElementById('cropReasoning').textContent = data.reasoning;
        document.getElementById('waterSource').textContent = data.water_source;

        // Alternative crops
        const altBox  = document.getElementById('altCropsBox');
        const altList = document.getElementById('altCropsList');
        altList.innerHTML = '';

        if (data.alternative_crops && data.alternative_crops.length > 0) {
            data.alternative_crops.forEach(c => {
                const li = document.createElement('li');
                const isCoastalCrop = data.is_coastal && c.reason.includes('coastal');
                li.innerHTML = `<strong style="color:var(--text-main)">${c.name}</strong>${isCoastalCrop ? ' 🌊' : ''} — <span style="color:var(--text-muted)">${c.reason}</span>`;
                altList.appendChild(li);
            });
            altBox.style.display = 'block';
        } else {
            altBox.style.display = 'none';
        }

        document.getElementById('cropResult').classList.remove('hidden');

    } catch (err) {
        alert(`Error: ${err.message}\nEnsure the FastAPI backend is running.`);
    } finally {
        btn.innerHTML = originalHTML;
        btn.disabled = false;
    }
});

// ── Price Prediction ─────────────────────────────────────────────────────────
document.getElementById('priceForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const btn = document.getElementById('priceSubmitBtn');
    const originalHTML = btn.innerHTML;
    btn.innerHTML = '<span class="spinner"></span> Forecasting...';
    btn.disabled = true;

    const crop    = document.getElementById('cropType').value;
    const state   = document.getElementById('stateType').value;
    const horizon = document.getElementById('horizonType').value;

    try {
        const response = await fetch(
            `${API_BASE}/predict?crop=${encodeURIComponent(crop)}&state=${encodeURIComponent(state)}&horizon_days=${horizon}`
        );

        if (!response.ok) throw new Error(`Server error: ${response.status}`);
        const data = await response.json();

        document.getElementById('currentPrice').textContent =
            `₹${data.current_price.toLocaleString('en-IN')}`;
        document.getElementById('predictedPrice').textContent =
            `₹${data.predicted_price.toLocaleString('en-IN')}`;

        // Recommendation badge
        const recBadge = document.getElementById('recBadge');
        recBadge.textContent = data.recommendation;
        recBadge.className = data.recommendation === 'SELL' ? 'rec-badge sell' : 'rec-badge hold';

        document.getElementById('recReason').textContent = data.recommendation_reason || '';

        // Model label
        const modelEl = document.getElementById('modelLabel');
        if (data.best_model_label) {
            modelEl.textContent = `Model: ${data.best_model_label}`;
        } else {
            modelEl.textContent = '';
        }

        // Black swan warning
        if (data.black_swan_warning) {
            const msg = data.black_swan_warning.message || '';
            document.getElementById('recReason').textContent =
                (data.recommendation_reason || '') + (msg ? `\n⚠️ ${msg}` : '');
        }

        document.getElementById('priceResult').classList.remove('hidden');

    } catch (err) {
        alert(`Error: ${err.message}\nEnsure the FastAPI backend is running.`);
    } finally {
        btn.innerHTML = originalHTML;
        btn.disabled = false;
    }
});
