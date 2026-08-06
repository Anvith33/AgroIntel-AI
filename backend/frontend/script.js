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
    populatePredStateSelect();
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
        // Set empty map so selects get error message
        indianDistrictsMap = {};
        supportedStates = [];
    }
}

// ─── Populate State Selects ──────────────────────────────────────────────────
function populateStateSelects() {
    const stateSelectIds = ["recState", "advState"];
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

function populatePredStateSelect() {
    const sel = document.getElementById("predState");
    if (!sel) return;
    sel.innerHTML = '<option value="">National Average</option>';
    supportedStates.forEach(state => {
        const opt = document.createElement("option");
        opt.value = state;
        opt.textContent = state;
        sel.appendChild(opt);
    });
}

// ─── State → District: THE ONLY DISTRICT LOADING FUNCTION ───────────────────
/**
 * Called by onchange on every state select element.
 * Clears the district select, then populates ONLY districts
 * belonging to the selected state using indianDistrictsMap.
 * Never uses demoData, global arrays, or alphabetical lists.
 */
function onStateChange(stateSelectId, districtSelectId) {
    const stateEl = document.getElementById(stateSelectId);
    const distEl  = document.getElementById(districtSelectId);
    if (!stateEl || !distEl) return;

    const selectedState = stateEl.value;

    // Always clear existing options first
    distEl.innerHTML = '<option value="">Select District</option>';

    if (!selectedState) return;

    // Fetch ONLY from indianDistrictsMap[selectedState]
    const districts = indianDistrictsMap[selectedState];

    if (!districts || districts.length === 0) {
        distEl.innerHTML = '<option value="">No districts found</option>';
        console.warn(`[AgroIntel] No districts found for state: "${selectedState}"`);
        return;
    }

    // Populate with only the selected state's districts
    districts.forEach(district => {
        const opt = document.createElement("option");
        opt.value  = district;
        opt.textContent = district;
        distEl.appendChild(opt);
    });

    // Auto-select first district
    if (districts.length > 0) {
        distEl.value = districts[0];
    }

    // Debug log (required)
    console.log(`====== AgroIntel District Filter ======`);
    console.log(`Selected State       : ${selectedState}`);
    console.log(`Number of Districts  : ${districts.length}`);
    console.log(`First District       : ${districts[0]}`);
    console.log(`Last District        : ${districts[districts.length - 1]}`);
    console.log(`=======================================`);
}

// ─── Default Selections on Load ─────────────────────────────────────────────
function setDefaultSelections() {
    const defaultState = "Maharashtra";
    ["recState", "advState"].forEach(id => {
        const sel = document.getElementById(id);
        if (!sel) return;
        const distId = id === "recState" ? "recDistrict" : "advDistrict";
        if (supportedStates.includes(defaultState)) {
            sel.value = defaultState;
            onStateChange(id, distId);
        } else if (supportedStates.length > 0) {
            sel.value = supportedStates[0];
            onStateChange(id, distId);
        }
    });
}

// ─── Page Navigation ─────────────────────────────────────────────────────────
function showPage(pageId) {
    // Normalize pageId if passed as 'view-xyz' or 'page-xyz'
    const cleanId = pageId.replace(/^(view-|page-)/, "");

    document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
    const target = document.getElementById(`page-${cleanId}`) || document.getElementById(`view-${cleanId}`);
    if (target) {
        target.classList.add("active");
    } else {
        console.warn(`[AgroIntel] Navigation target not found: "page-${cleanId}" or "view-${cleanId}"`);
    }

    // Highlight active nav button
    document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("nav-active"));
    const navMap = { recommendation: "navRecommend", prediction: "navPrediction", advisory: "navAdvisory" };
    if (navMap[cleanId]) document.getElementById(navMap[cleanId])?.classList.add("nav-active");

    window.scrollTo({ top: 0, behavior: "smooth" });
}

// Aliases for comprehensive API compatibility
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
    if (!isNaN(n))  payload.n  = n;
    if (!isNaN(p))  payload.p  = p;
    if (!isNaN(k))  payload.k  = k;
    if (!isNaN(ph)) payload.ph = ph;

    try {
        const res = await fetch("/api/predict/crop", {
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
    const recs = (data.recommended_crops || []).slice(0, 3);
    if (recs.length === 0) {
        document.getElementById("recResults").innerHTML = `
            <div class="placeholder-card glass-card">
                <span class="material-symbols-rounded ph-icon-sym">grass</span>
                <h3>No Crops Found</h3>
                <p>No suitable crops found for the selected parameters. Try a different season or region.</p>
            </div>`;
        return;
    }

    const rankColors = ["first-rank", "second-rank", "third-rank"];
    const rankLabels  = ["Best Match", "2nd Choice", "3rd Choice"];

    const html = `
        <div class="rec-header-row">
            <h3>Top Crops for <strong>${data.district || ''}</strong>, ${data.state || ''}</h3>
            <p class="rec-season-tag">Season: ${data.season || ''}</p>
        </div>
        ${recs.map((rec, i) => {
            const reasons = simplifyReasons(rec.reasons || [], rec.crop);
            const score = Math.round(rec.suitability_score ?? 0);
            return `
            <div class="rec-card glass-card ${rankColors[i] || ''}">
                <div class="rec-card-top">
                    <div class="rec-badge-wrap">
                        <span class="rec-rank">#${rec.rank || i+1}</span>
                        <span class="rank-label">${rankLabels[i]}</span>
                    </div>
                    <div class="rec-crop-info">
                        <h3 class="rec-crop-name">${capitalize(rec.crop)}</h3>
                    </div>
                    <div class="rec-score-wrap">
                        <div class="score-circle ${rankColors[i] || ''}">
                            <span class="score-val">${score}</span>
                            <span class="score-pct">%</span>
                        </div>
                        <span class="score-lbl">Suitability</span>
                    </div>
                </div>
                <div class="rec-reasons">
                    <p class="reasons-title">Why this crop?</p>
                    <ul class="reasons-list">
                        ${reasons.map(r => `<li>${r}</li>`).join('')}
                    </ul>
                </div>
            </div>`;
        }).join('')}`;

    document.getElementById("recResults").innerHTML = html;
}

function simplifyReasons(rawReasons, cropName) {
    // Convert technical reasons to plain farmer-friendly language
    const friendly = [];
    const text = rawReasons.join(" ").toLowerCase();

    if (text.includes("season") || text.includes("kharif") || text.includes("rabi") || text.includes("zaid")) {
        friendly.push("Suitable for the selected season");
    }
    if (text.includes("soil") || text.includes("ph") || text.includes("loam") || text.includes("alluvial") || text.includes("black") || text.includes("red")) {
        friendly.push("Suitable soil conditions for this district");
    }
    if (text.includes("district") || text.includes("region") || text.includes("historical") || text.includes("commonly")) {
        friendly.push(`Commonly cultivated in the selected district`);
    }
    if (text.includes("weather") || text.includes("temperature") || text.includes("rainfall") || text.includes("humid")) {
        friendly.push("Current weather conditions are favourable");
    }
    if (text.includes("zone") || text.includes("agro") || text.includes("climate")) {
        friendly.push("Suitable for the agro-climatic zone");
    }

    // If no friendly reasons were inferred, use first 3 raw reasons cleaned up
    if (friendly.length === 0 && rawReasons.length > 0) {
        return rawReasons.slice(0, 4).map(r => r.replace(/\(.*?\)/g, "").trim());
    }

    return friendly.length > 0 ? friendly : [
        "Suitable for current season",
        "Suitable soil conditions",
        "Commonly cultivated in selected district",
        "Weather conditions are favourable"
    ];
}

// ─── Price Prediction ────────────────────────────────────────────────────────
async function submitPricePred(event) {
    event.preventDefault();
    const btn  = document.getElementById("btnPred");
    const spin = document.getElementById("predSpin");
    setLoading(btn, spin, true);

    const crop    = document.getElementById("predCrop").value;
    const state   = document.getElementById("predState").value;
    const horizon = document.getElementById("predHorizon").value;

    let url = `/api/predict/price?crop=${encodeURIComponent(crop)}&horizon_days=${horizon}`;
    if (state) url += `&state=${encodeURIComponent(state)}`;

    try {
        const res = await fetch(url);
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: "Request failed" }));
            throw new Error(err.detail || "Price prediction failed. Please try again.");
        }
        const data = await res.json();
        renderPredResults(data, horizon);
    } catch (err) {
        showToast(err.message, "error");
        document.getElementById("predResults").innerHTML = errorCard(err.message);
    } finally {
        setLoading(btn, spin, false);
    }
}

function renderPredResults(data, horizon) {
    const dec       = (data.decision || "HOLD").toUpperCase();
    const trend     = (data.trend || "STABLE").toUpperCase();
    const conf      = data.decision_score?.confidence ?? data.confidence ?? 0;
    const curPrice  = typeof data.current_price === "number" ? data.current_price.toFixed(0) : (data.current_price ?? "—");
    const avgPrice  = typeof data.average_price === "number" ? data.average_price.toFixed(0) : (data.average_price ?? "—");
    const changeP   = data.expected_change_percent ?? 0;
    const decReason = simplifyDecisionReason(data);
    const decClass  = dec === "SELL" ? "dec-sell" : dec === "HOLD" ? "dec-hold" : "dec-neutral";
    const trendDir  = trend.includes("UP") ? "Rising" : trend.includes("DOWN") ? "Falling" : "Stable";
    const changeStr = changeP > 0 ? `+${changeP}%` : `${changeP}%`;

    const html = `
        <div class="pred-summary-row">
            <div class="pred-meta">
                <h3>${capitalize(data.crop || '')} — ${horizon}-Day Forecast${data.state ? ` · ${data.state}` : ''}</h3>
            </div>
            <div class="pred-decision ${decClass}">
                <span class="dec-word">${dec}</span>
            </div>
        </div>

        <div class="pred-metrics">
            <div class="metric-box glass-card">
                <span class="metric-lbl">Current Price</span>
                <span class="metric-val">&#8377;${curPrice}</span>
                <span class="metric-unit">per quintal</span>
            </div>
            <div class="metric-box glass-card accent-box">
                <span class="metric-lbl">Predicted Price (${horizon}d)</span>
                <span class="metric-val">&#8377;${avgPrice}</span>
                <span class="metric-unit">${changeStr} change</span>
            </div>
            <div class="metric-box glass-card">
                <span class="metric-lbl">Trend</span>
                <span class="metric-val">${trendDir}</span>
                <span class="metric-unit">${data.trend_strength || "MEDIUM"} strength</span>
            </div>
            <div class="metric-box glass-card">
                <span class="metric-lbl">Confidence</span>
                <span class="metric-val">${Math.round(conf)}%</span>
                <span class="metric-unit">forecast confidence</span>
            </div>
        </div>

        <div class="pred-reason glass-card">
            <span class="material-symbols-rounded reason-icon">info</span>
            <p>${decReason}</p>
        </div>

        <div class="chart-box glass-card">
            <div class="chart-header">
                <h4>Price Forecast Chart</h4>
                <span class="chart-horizon">${horizon}-day outlook</span>
            </div>
            <canvas id="priceChart" height="240"></canvas>
        </div>`;

    document.getElementById("predResults").innerHTML = html;
    renderPriceChart(data, parseInt(horizon));
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

function renderPriceChart(data, horizon) {
    const ctx = document.getElementById("priceChart");
    if (!ctx) return;
    if (activeChart) { activeChart.destroy(); activeChart = null; }

    // Use the predictions dict from backend directly for accuracy
    // These are the ACTUAL model outputs: no interpolation, no smoothing
    const predsDict = data.predictions || {};
    const curPrice  = typeof data.current_price === "number" ? data.current_price : 0;

    // Build milestone points up to the selected horizon ONLY
    const allMilestones = [
        { day: 0,  label: "Today",   val: curPrice },
        { day: 7,  label: "7 Days",  val: predsDict["7_day"] },
        { day: 15, label: "15 Days", val: predsDict["15_day"] },
        { day: 30, label: "30 Days", val: predsDict["30_day"] },
        { day: 60, label: "60 Days", val: predsDict["60_day"] },
        { day: 90, label: "90 Days", val: predsDict["90_day"] },
    ];

    // Only include milestones up to selected horizon
    const points = allMilestones.filter(m => m.day <= horizon && m.val !== undefined);
    // Ensure the exact horizon is the last point
    const lastPoint = points[points.length - 1];
    if (lastPoint && lastPoint.day !== horizon) {
        const exactVal = predsDict[`${horizon}_day`];
        if (exactVal !== undefined) {
            points.push({ day: horizon, label: `${horizon} Days`, val: exactVal });
        }
    }

    const chartLabels = points.map(p => p.label);
    const chartValues = points.map(p => p.val);

    // Styling: amber for Today, green for all forecasted milestones
    const pointRadius  = points.map((p, i) => (i === 0 || i === points.length - 1) ? 7 : 5);
    const pointBgColor = points.map((p, i) => i === 0 ? "#f59e0b" : "#22c55e");

    activeChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: chartLabels,
            datasets: [
                {
                    label: "Price Forecast (Rs. per quintal)",
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
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: items => items[0].label,
                        label: item => `Price: Rs.${item.parsed.y?.toFixed(0)} per quintal`
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
                        callback: v => `Rs.${Math.round(v)}`
                    },
                    grid: { color: "rgba(255,255,255,0.05)" },
                    title: {
                        display: true,
                        text: "Price (Rs. per quintal)",
                        color: "var(--text-muted)",
                        font: { size: 11 }
                    }
                }
            }
        }
    });
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
