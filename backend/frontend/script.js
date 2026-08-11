/**
 * AgroIntel AI — Frontend Application Script
 * Single source of truth for all frontend logic.
 * 
 * District filtering uses ONLY indianDistrictsMap built from /indian_districts.json.
 * No global district arrays. No cached demo districts. No fallback alphabetical lists.
 */

// ─── Global State ───────────────────────────────────────────────────────────
let activeChart = null;

/** Single source of truth: { "Karnataka": ["Bagalkot", "Ballari", ...], ... } */
let indianDistrictsMap = {};

/** Supported states list (from indianDistrictsMap keys after loading) */
let supportedStates = [];

// ─── App Initialization ──────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    initApp();
});

async function initApp() {
    await loadIndianDistricts();   // Must load first before populating selects
    populateStateSelects();
    setDefaultSelections();
    checkHealth();
}

// ─── Load indian_districts.json (Single Load, Single Source) ─────────────────
async function loadIndianDistricts() {
    try {
        const res = await fetch("/indian_districts.json");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        // Build map: state_name -> sorted array of district names
        indianDistrictsMap = {};
        if (data && Array.isArray(data.states)) {
            data.states.forEach(stateObj => {
                if (stateObj.state && Array.isArray(stateObj.districts)) {
                    indianDistrictsMap[stateObj.state] = stateObj.districts.slice().sort();
                }
            });
        }

        supportedStates = Object.keys(indianDistrictsMap).sort();
        console.log(`[AgroIntel] Loaded ${supportedStates.length} states, ${Object.values(indianDistrictsMap).reduce((a,b)=>a+b.length,0)} districts.`);

    } catch (err) {
        console.error("[AgroIntel] Failed to load indian_districts.json:", err);
        showToast("Unable to load districts. Please refresh the page.", "error");
        indianDistrictsMap = {};
        supportedStates = [];
    }
}

// ─── Populate State Selects ──────────────────────────────────────────────────
function populateStateSelects() {
    const stateSelectIds = ["recState", "predState", "advState"];
    stateSelectIds.forEach(id => {
        const sel = document.getElementById(id);
        if (!sel) return;
        sel.innerHTML = '<option value="">Select State</option>';

        if (supportedStates.length === 0) {
            sel.innerHTML = '<option value="">Unable to load states</option>';
            return;
        }

        supportedStates.forEach(state => {
            const opt = document.createElement("option");
            opt.value = state;
            opt.textContent = state;
            sel.appendChild(opt);
        });
    });
}

// ─── State → District: THE ONLY DISTRICT LOADING FUNCTION ───────────────────
function onStateChange(stateSelectId, districtSelectId) {
    const stateEl = document.getElementById(stateSelectId);
    const distEl  = document.getElementById(districtSelectId);
    if (!stateEl || !distEl) return;

    const selectedState = stateEl.value;

    distEl.innerHTML = '<option value="">Select District</option>';

    if (!selectedState) return;

    const districts = indianDistrictsMap[selectedState];

    if (!districts || districts.length === 0) {
        distEl.innerHTML = '<option value="">No districts found</option>';
        console.warn(`[AgroIntel] No districts found for state: "${selectedState}"`);
        return;
    }

    districts.forEach(district => {
        const opt = document.createElement("option");
        opt.value  = district;
        opt.textContent = district;
        distEl.appendChild(opt);
    });

    if (districts.length > 0) {
        distEl.value = districts[0];
    }
}

// ─── Default Selections on Load ─────────────────────────────────────────────
function setDefaultSelections() {
    const defaultState = "Maharashtra";
    ["recState", "predState", "advState"].forEach(id => {
        const distId = id === "recState" ? "recDistrict" : id === "predState" ? "predDistrict" : "advDistrict";
        if (supportedStates.includes(defaultState)) {
            const sel = document.getElementById(id);
            if (sel) { sel.value = defaultState; onStateChange(id, distId); }
        } else if (supportedStates.length > 0) {
            const sel = document.getElementById(id);
            if (sel) { sel.value = supportedStates[0]; onStateChange(id, distId); }
        }
    });
}

// ─── Page Navigation ─────────────────────────────────────────────────────────
function showPage(pageId) {
    const cleanId = pageId.replace(/^(view-|page-)/, "");

    document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
    const target = document.getElementById(`page-${cleanId}`) || document.getElementById(`view-${cleanId}`);
    if (target) {
        target.classList.add("active");
    } else {
        console.warn(`[AgroIntel] Navigation target not found: "page-${cleanId}" or "view-${cleanId}"`);
    }

    document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("nav-active"));
    const navMap = { recommendation: "navRecommend", prediction: "navPrediction", advisory: "navAdvisory" };
    if (navMap[cleanId]) document.getElementById(navMap[cleanId])?.classList.add("nav-active");

    window.scrollTo({ top: 0, behavior: "smooth" });
}

const showView   = showPage;
const navigate   = showPage;
const switchPage = showPage;
const openPage   = showPage;

// ─── Theme Toggle ────────────────────────────────────────────────────────────
function toggleTheme() {
    const html = document.documentElement;
    const next = html.getAttribute("data-theme") === "dark" ? "light" : "dark";
    html.setAttribute("data-theme", next);
    document.getElementById("themeIcon").textContent = next === "dark" ? "dark_mode" : "light_mode";
}

// ─── Health Check ────────────────────────────────────────────────────────────
async function checkHealth() {
    const badge = document.getElementById("sysBadge");
    const text  = document.getElementById("sysText");
    try {
        const res = await fetch("/health");
        if (res.ok) {
            const data = await res.json();
            const ok = data.status === "healthy";
            text.textContent = ok ? "System Ready" : "System Degraded";
            badge.classList.toggle("badge-warn", !ok);
        } else {
            text.textContent = "API Unavailable";
            badge.classList.add("badge-warn");
        }
    } catch {
        text.textContent = "Offline";
        badge.classList.add("badge-warn");
    }
}

// ─── Crop Recommendation ─────────────────────────────────────────────────────
async function submitCropRec(event) {
    event.preventDefault();
    const btn   = document.getElementById("btnRec");
    const spin  = document.getElementById("recSpin");
    setLoading(btn, spin, true);

    const payload = {
        state:    document.getElementById("recState").value,
        district: document.getElementById("recDistrict").value,
        season:   document.getElementById("recSeason").value,
    };

    const n  = parseFloat(document.getElementById("recN").value);
    const p  = parseFloat(document.getElementById("recP").value);
    const k  = parseFloat(document.getElementById("recK").value);
    const ph = parseFloat(document.getElementById("recPh").value);
    const prev = document.getElementById("recPrevCrop")?.value?.trim();

    if (!isNaN(n))  payload.n  = n;
    if (!isNaN(p))  payload.p  = p;
    if (!isNaN(k))  payload.k  = k;
    if (!isNaN(ph)) payload.soil_ph = ph;
    if (prev)       payload.previous_crop = prev;

    try {
        const res = await fetch("/api/phase6/recommend", {
            method:  "POST",
            headers: { "Content-Type": "application/json" },
            body:    JSON.stringify(payload),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: "Request failed" }));
            throw new Error(err.detail || "Recommendation failed. Please try again.");
        }
        const data = await res.json();
        renderRecResults(data);
    } catch (err) {
        showToast(err.message, "error");
        document.getElementById("recResults").innerHTML = errorCard(err.message);
    } finally {
        setLoading(btn, spin, false);
    }
}

function renderRecResults(data) {
    const loc      = data.location || {};
    const recs     = (data.recommendations || []).slice(0, 5);
    const rejected = (data.rejected_crops  || []).slice(0, 3);
    const dq       = data.data_quality     || {};

    if (recs.length === 0) {
        document.getElementById("recResults").innerHTML = `
            <div class="placeholder-card glass-card">
                <span class="material-symbols-rounded ph-icon-sym">grass</span>
                <h3>No Crops Recommended</h3>
                <p>No suitable candidate crops found for ${loc.district || 'selected district'} in ${data.season || 'selected season'}.</p>
            </div>`;
        return;
    }

    const rankColors = ["first-rank", "second-rank", "third-rank", "", ""];

    const recHtml = recs.map((rec, i) => {
        const info = rec.crop_information || {};

        return `
        <div class="rec-card glass-card ${rankColors[i]||''}" style="margin-bottom:16px;padding:18px">
            <div class="rec-card-top" style="margin-bottom:12px">
                <div class="rec-badge-wrap">
                    <span class="rec-rank">#${rec.rank || i+1}</span>
                </div>
                <div class="rec-crop-info">
                    <h3 class="rec-crop-name" style="margin:0;font-size:1.4rem">${rec.crop}</h3>
                    <div style="font-size:0.8rem;opacity:0.75;margin-top:2px">Recommended for ${data.season || ''} in ${loc.district || ''}</div>
                </div>
                <div class="rec-score-wrap">
                    <div class="score-circle ${rankColors[i]||''}">
                        <span class="score-val">${Math.round(rec.final_score)}</span>
                        <span class="score-pct">/100</span>
                    </div>
                </div>
            </div>

            <!-- About this Crop Section -->
            <div style="background:rgba(0,0,0,0.2);border:1px solid rgba(255,255,255,0.06);border-radius:8px;padding:14px">
                <h4 style="margin:0 0 10px;font-size:0.92rem;color:#e2e8f0;display:flex;align-items:center;gap:6px">
                    <span class="material-symbols-rounded" style="font-size:1.1rem;color:#a3e635">info</span> About ${rec.crop}
                </h4>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;font-size:0.82rem;line-height:1.45">
                    <div><strong style="color:#a3e635">Why grown:</strong> <span style="opacity:0.9">${info.why_grown || 'Cultivated for farm revenue and local food demand.'}</span></div>
                    <div><strong style="color:#38bdf8">Common uses:</strong> <span style="opacity:0.9">${info.common_uses || 'Food grain, pulse, or agricultural produce.'}</span></div>
                    <div><strong style="color:#fbbf24">Season:</strong> <span style="opacity:0.9">${info.season || 'Standard regional season.'}</span></div>
                    <div><strong style="color:#c084fc">Soil & Climate:</strong> <span style="opacity:0.9">${info.soil || 'Well-drained soil.'} ${info.climate || ''}</span></div>
                </div>
            </div>
        </div>`;
    }).join('');


    const rejHtml = rejected.length > 0 ? `
    <div class="glass-card" style="padding:14px;margin-top:12px">
        <h4 style="margin:0 0 8px;font-size:0.88rem;opacity:0.8">❌ Excluded Candidates</h4>
        ${rejected.map(r=>`<div style="font-size:0.78rem;padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.05)">
            <strong>${r.crop}</strong> — ${r.rejection_reason}
            <span style="opacity:0.5;font-size:0.7rem">[${r.rejection_stage}]</span>
        </div>`).join('')}
    </div>` : '';

    const html = `
        <div class="rec-header-row" style="margin-bottom:16px">
            <h3>Top Recommended Crops for <strong>${loc.district || data.district || ''}</strong>, ${loc.state || data.state || ''}</h3>
            <p class="rec-season-tag">Season: ${data.season || ''}</p>
        </div>
        ${recHtml}
        ${rejHtml}`;

    document.getElementById("recResults").innerHTML = html;
}

// ─── Price Prediction ────────────────────────────────────────────────────────
async function submitPricePred(event) {
    event.preventDefault();
    const btn  = document.getElementById("btnPred");
    const spin = document.getElementById("predSpin");
    setLoading(btn, spin, true);

    const crop     = document.getElementById("predCrop").value;
    const state    = document.getElementById("predState").value;
    const district = document.getElementById("predDistrict").value;
    const horizon  = document.getElementById("predHorizon").value;

    try {
        let p6Data = {};
        if (state && district) {
            const p6Res = await fetch("/api/phase6/recommend", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ state, district, season: "Kharif" })
            });
            if (p6Res.ok) {
                p6Data = await p6Res.json();
            }
        }

        let predUrl = `/api/predict?crop=${encodeURIComponent(crop)}&horizon_days=${horizon}`;
        if (state) predUrl += `&state=${encodeURIComponent(state)}`;
        const predRes = await fetch(predUrl);
        const predData = predRes.ok ? await predRes.json() : {};

        renderPredResults(p6Data, predData, crop, horizon, state, district);
    } catch (err) {
        showToast(err.message, "error");
        document.getElementById("predResults").innerHTML = errorCard(err.message);
    } finally {
        setLoading(btn, spin, false);
    }
}

function renderPredResults(p6Data, predData, crop, horizon, inputState = "", inputDistrict = "") {
    const market   = p6Data.market || {};
    const forecast = p6Data.price_forecast || {};
    const loc      = p6Data.location || {};

    const stateDisplay = loc.state || inputState || "";
    const districtDisplay = loc.district || inputDistrict || "";

    const curPriceNum = typeof market.current_price === 'number' ? market.current_price : (typeof predData.current_price === 'number' ? predData.current_price : null);
    const predPriceNum = typeof predData.predicted_price === 'number' ? predData.predicted_price : (typeof forecast.predicted_price === 'number' ? forecast.predicted_price : null);

    const isPredAvailable = predData.available !== false && typeof predPriceNum === 'number';
    const isMandiAvailable = market.available !== false && typeof curPriceNum === 'number';

    const curPriceDisplay = isMandiAvailable ? `₹${Math.round(curPriceNum).toLocaleString('en-IN')}` : 'Price Unavailable';
    const predPriceDisplay = isPredAvailable ? `₹${Math.round(predPriceNum).toLocaleString('en-IN')}` : 'Prediction Unavailable';

    const obsDate = market.observation_date || '—';
    const mktName = market.market || '—';
    const modelName = predData.best_model_label || predData.best_model || forecast.model || "ML Model";

    // Strict SELL / HOLD advisory badge
    let advAction = "HOLD";
    let advReason = "Reliable market price or forecast is currently unavailable. Please verify local Mandi rates before making transaction decisions.";

    if (isMandiAvailable && isPredAvailable) {
        const changePct = ((predPriceNum - curPriceNum) / curPriceNum) * 100.0;
        if (changePct <= -3.0) {
            advAction = "SELL";
            advReason = `The forecast indicates a decline from ₹${Math.round(curPriceNum).toLocaleString('en-IN')} to approximately ₹${Math.round(predPriceNum).toLocaleString('en-IN')} over the next ${horizon} days. Selling at the current observed price may reduce exposure to the expected decline.`;
        } else if (changePct >= 3.0) {
            advAction = "HOLD";
            advReason = `Prices are expected to increase from ₹${Math.round(curPriceNum).toLocaleString('en-IN')} to approximately ₹${Math.round(predPriceNum).toLocaleString('en-IN')} over the next ${horizon} days. Holding may provide a better expected selling price.`;
        } else {
            advAction = "HOLD";
            advReason = `The forecast indicates only a small price movement of about ${Math.abs(Math.round(changePct))}%. Holding is recommended as prices are expected to remain steady.`;
        }
    } else if (predData.message || (forecast.crop && forecast.crop.toLowerCase() === crop.toLowerCase() && forecast.message)) {
        advReason = predData.message || forecast.message;
    }

    const advColor = advAction === "SELL" ? "#f97316" : "#22c55e";

    const nlpExplanation = isMandiAvailable && isPredAvailable
        ? `${capitalize(crop)} is currently trading at ₹${Math.round(curPriceNum).toLocaleString('en-IN')} per quintal in the latest available Mandi observation in ${districtDisplay}, ${stateDisplay}. The ${modelName} model forecasts approximately ₹${Math.round(predPriceNum).toLocaleString('en-IN')} per quintal over the selected ${horizon}-day horizon. Based on this trend, the system suggests ${advAction}.`
        : `${capitalize(crop)} market data: ${advReason}`;

    const html = `
        <div class="pred-summary-row" style="margin-bottom:16px">
            <div class="pred-meta">
                <h3 style="margin:0;font-size:1.4rem">${capitalize(crop)} Price Outlook</h3>
                <div style="font-size:0.82rem;opacity:0.75;margin-top:2px">📍 ${districtDisplay}${districtDisplay && stateDisplay ? ', ' : ''}${stateDisplay}</div>
            </div>
            <div class="pred-decision" style="background:${advColor}22;border:1px solid ${advColor};color:${advColor};padding:8px 18px">
                <span class="dec-word" style="font-size:1.1rem;font-weight:800;letter-spacing:1px">${advAction}</span>
            </div>
        </div>

        <!-- LATEST MANDI PRICE & EXPECTED PRICE ROW -->
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:18px">
            <div class="glass-card" style="padding:18px;text-align:center">
                <div style="font-size:0.78rem;opacity:0.75;text-transform:uppercase;letter-spacing:0.5px;font-weight:600">Latest Mandi Price</div>
                <div style="font-size:1.8rem;font-weight:800;color:#34d399;margin:8px 0">${curPriceDisplay} <span style="font-size:0.85rem;font-weight:500;opacity:0.7">${isMandiAvailable ? '/ quintal' : ''}</span></div>
                <div style="font-size:0.75rem;opacity:0.8;margin-top:4px">
                    <div><strong>Observation:</strong> ${obsDate}</div>
                    <div><strong>Market:</strong> ${mktName}</div>
                    <div><strong>Source:</strong> data.gov.in</div>
                </div>
            </div>
            <div class="glass-card" style="padding:18px;text-align:center;display:flex;flex-direction:column;justify-content:center">
                <div style="font-size:0.78rem;opacity:0.75;text-transform:uppercase;letter-spacing:0.5px;font-weight:600">Expected Price in ${horizon} Days</div>
                ${isPredAvailable ? `
                <div style="font-size:1.8rem;font-weight:800;color:#a78bfa;margin:8px 0">${predPriceDisplay} <span style="font-size:0.85rem;font-weight:500;opacity:0.7">/ quintal</span></div>
                <div style="font-size:0.72rem;opacity:0.6">Model: ${modelName}</div>
                ` : `
                <div style="font-size:0.82rem;color:#fbbf24;margin-top:10px;line-height:1.4">${predData.forecast?.reason || predData.message || forecast.message || "Price prediction is currently unavailable for this crop because a validated forecasting model is not available."}</div>
                `}
            </div>
        </div>

        <!-- RESTORED 30-DAY PRICE FORECAST GRAPH -->
        ${isPredAvailable ? `
        <div class="chart-box glass-card" style="margin-bottom:18px;padding:16px">
            <div class="chart-header" style="margin-bottom:12px">
                <h4 style="margin:0;font-size:1rem">30-Day Price Forecast</h4>
                <span class="chart-horizon" style="font-size:0.78rem;opacity:0.75">Expected Trend</span>
            </div>
            <canvas id="priceChart"></canvas>
        </div>` : ''}

        <!-- MARKET DECISION ADVISORY -->
        <div class="glass-card" style="padding:18px;margin-bottom:16px;border-left:4px solid ${advColor}">
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">
                <span style="font-size:0.82rem;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;opacity:0.8">MARKET DECISION</span>
                <span style="background:${advColor}22;color:${advColor};border:1px solid ${advColor};padding:2px 10px;border-radius:4px;font-weight:800;font-size:0.9rem">${advAction}</span>
            </div>
            <div style="font-size:0.9rem;line-height:1.45;opacity:0.92;margin-top:6px">${advReason}</div>
        </div>

        <!-- PRICE OUTLOOK NLP EXPLANATION -->
        <div class="glass-card" style="padding:18px;margin-bottom:16px">
            <h4 style="margin:0 0 8px;font-size:0.95rem;color:#38bdf8">Price Outlook</h4>
            <div style="font-size:0.88rem;line-height:1.5;opacity:0.92">${nlpExplanation}</div>
        </div>`;

    document.getElementById("predResults").innerHTML = html;
    if (isPredAvailable) {
        renderPriceChart(predData, parseInt(horizon), curPriceNum);
    }
}

function renderPriceChart(data, horizon, curPriceFallback = null) {
    const ctx = document.getElementById("priceChart");
    if (!ctx) return;

    if (activeChart) {
        activeChart.destroy();
        activeChart = null;
    }

    const curPrice = typeof data.current_price === "number" ? data.current_price : (curPriceFallback || 2000.0);
    const predPrice = typeof data.predicted_price === "number" ? data.predicted_price : curPrice;
    const predsList = Array.isArray(data.predictions) ? data.predictions : [];

    let day7Val, day15Val, day30Val;

    if (predsList.length >= 30) {
        day7Val  = Math.round(predsList[6]);
        day15Val = Math.round(predsList[14]);
        day30Val = Math.round(predsList[29]);
    } else {
        day7Val  = Math.round(curPrice + (predPrice - curPrice) * (7.0 / 30.0));
        day15Val = Math.round(curPrice + (predPrice - curPrice) * (15.0 / 30.0));
        day30Val = Math.round(predPrice);
    }

    const points = [
        { label: "Today",   val: Math.round(curPrice) },
        { label: "7 Days",  val: day7Val },
        { label: "15 Days", val: day15Val },
        { label: "30 Days", val: day30Val }
    ];

    const chartLabels = points.map(p => p.label);
    const chartValues = points.map(p => p.val);

    const pointRadius  = [7, 5, 5, 7];
    const pointBgColor = ["#f59e0b", "#38bdf8", "#38bdf8", "#22c55e"];

    activeChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: chartLabels,
            datasets: [{
                label: "Price (₹/quintal)",
                data: chartValues,
                borderColor: "#22c55e",
                backgroundColor: "rgba(34,197,94,0.07)",
                borderWidth: 3,
                fill: true,
                tension: 0.3,
                pointRadius: pointRadius,
                pointHoverRadius: 8,
                pointBackgroundColor: pointBgColor,
                pointBorderColor: "#fff",
                pointBorderWidth: 2,
            }],
        },
        options: {
            animation: false,
            responsive: false,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: items => items[0].label,
                        label: item => `Price: ₹${item.parsed.y?.toFixed(0)} / quintal`
                    },
                    backgroundColor: "rgba(15,25,18,0.92)",
                    titleColor: "#a1a1aa",
                    bodyColor: "#f0fdf4",
                    borderColor: "rgba(34,197,94,0.3)",
                    borderWidth: 1,
                    padding: 12,
                }
            },
            scales: {
                x: {
                    ticks: { color: "var(--text-secondary)", font: { size: 12, weight: "500" } },
                    grid: { color: "rgba(255,255,255,0.04)" }
                },
                y: {
                    ticks: {
                        color: "var(--text-secondary)",
                        font: { size: 12 },
                        callback: v => `₹${Math.round(v)}`
                    },
                    grid: { color: "rgba(255,255,255,0.05)" },
                    title: {
                        display: true,
                        text: "Price (₹/quintal)",
                        color: "var(--text-muted)",
                        font: { size: 11 }
                    }
                }
            }
        }
    });
}

function simplifyDecisionReason(data) {
    const dec     = (data.decision || "HOLD").toUpperCase();
    const trend   = (data.trend || "STABLE").toUpperCase();
    const change  = data.expected_change_percent ?? 0;
    const horizon = data.horizon_days ?? 30;

    if (dec === "SELL") {
        if (trend.includes("DOWN")) {
            return `The market price for ${capitalize(data.crop)} is expected to decline over the next ${horizon} days. Selling now is advised to avoid losses.`;
        }
        return `Based on current market data, selling ${capitalize(data.crop)} now offers a better return than holding.`;
    } else {
        if (change > 0) {
            return `The predicted market price is expected to increase by ${change}% over the next ${horizon} days. Holding your stock may yield better returns.`;
        }
        return `Market conditions suggest holding ${capitalize(data.crop)} stock for a better selling opportunity.`;
    }
}

// ─── Farmer Advisory ─────────────────────────────────────────────────────────
async function submitAdvisory(event) {
    event.preventDefault();
    const btn  = document.getElementById("btnAdv");
    const spin = document.getElementById("advSpin");
    setLoading(btn, spin, true);

    const payload = {
        state:    document.getElementById("advState").value,
        district: document.getElementById("advDistrict").value,
        season:   document.getElementById("advSeason").value,
    };
    const crop = document.getElementById("advCrop").value;
    if (crop) payload.crop = crop;

    try {
        const res = await fetch("/api/advisory", {
            method:  "POST",
            headers: { "Content-Type": "application/json" },
            body:    JSON.stringify(payload),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: "Request failed" }));
            throw new Error(err.detail || "Advisory failed. Please try again.");
        }
        const data = await res.json();
        renderAdvisoryResults(data);
    } catch (err) {
        showToast(err.message, "error");
        document.getElementById("advResults").innerHTML = errorCard(err.message);
    } finally {
        setLoading(btn, spin, false);
    }
}

function renderAdvisoryResults(data) {
    const priceData = data.price_prediction || {};
    const dec       = (priceData.decision || "HOLD").toUpperCase();
    const conf      = priceData.confidence ?? 0;
    const avgPrice  = priceData.predicted_30d_avg ?? "—";
    const curPrice  = priceData.current_price ?? "—";
    const recs      = data.crop_recommendations?.slice(0, 3) || [];
    const decClass  = dec === "SELL" ? "dec-sell" : "dec-hold";

    const html = `
        <div class="adv-summary glass-card">
            <p class="adv-summary-text">${data.combined_summary || "Advisory generated."}</p>
        </div>

        ${recs.length > 0 ? `
        <div class="adv-section">
            <h4>🌱 Recommended Crops</h4>
            ${recs.map((r, i) => `
                <div class="adv-crop-row glass-card">
                    <span class="adv-rank">#${i+1}</span>
                    <span class="adv-crop-name">${capitalize(r.crop)}</span>
                    <span class="adv-score">${Math.round(r.suitability_score ?? 0)}% match</span>
                </div>`).join('')}
        </div>` : ''}

        <div class="adv-market glass-card">
            <h4>📈 Market Analysis — ${capitalize(data.target_price_crop || '')}</h4>
            <div class="adv-market-grid">
                <div class="adv-metric">
                    <span class="adv-m-lbl">Current Price</span>
                    <span class="adv-m-val">₹${curPrice}</span>
                </div>
                <div class="adv-metric">
                    <span class="adv-m-lbl">30-Day Predicted</span>
                    <span class="adv-m-val">₹${avgPrice}</span>
                </div>
                <div class="adv-metric">
                    <span class="adv-m-lbl">Recommendation</span>
                    <span class="adv-m-val ${decClass}">${dec}</span>
                </div>
                <div class="adv-metric">
                    <span class="adv-m-lbl">Confidence</span>
                    <span class="adv-m-val">${Math.round(conf)}%</span>
                </div>
            </div>
        </div>

        ${(data.consolidated_reasons || []).length > 0 ? `
        <div class="adv-reasons glass-card">
            <h4>💬 Key Reasons</h4>
            <ul class="reasons-list">
                ${data.consolidated_reasons.slice(0, 5).map(r => `<li>${r}</li>`).join('')}
            </ul>
        </div>` : ''}`;

    document.getElementById("advResults").innerHTML = html;
}

// ─── UI Helpers ──────────────────────────────────────────────────────────────
function setLoading(btn, spin, on) {
    if (!btn) return;
    btn.disabled = on;
    btn.style.opacity = on ? "0.7" : "1";
    if (spin) spin.classList.toggle("hidden", !on);
}

function showToast(message, type = "info") {
    const box   = document.getElementById("toastBox");
    if (!box) return;
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    const icons = { success: "check_circle", error: "error", info: "info" };
    toast.innerHTML = `<span class="material-symbols-rounded toast-icon">${icons[type] || "info"}</span><span>${message}</span>`;
    box.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add("show"));
    setTimeout(() => {
        toast.classList.remove("show");
        setTimeout(() => toast.remove(), 350);
    }, 4500);
}

function capitalize(str) {
    return str ? str.charAt(0).toUpperCase() + str.slice(1).toLowerCase() : "";
}

function errorCard(msg) {
    return `<div class="placeholder-card glass-card error-card">
        <div class="ph-icon">⚠️</div>
        <h3>Something went wrong</h3>
        <p>${msg}</p>
    </div>`;
}
