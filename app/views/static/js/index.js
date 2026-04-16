const trmFormatter = new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
});

const pctFormatter = new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
});

let cachedRowsPromise = null;
let allRowsCache = [];
let predictionDashboardState = null;
let predictionScopeState = "all_data";

function formatTrm(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
        return "-";
    }
    return `$${trmFormatter.format(Number(value))}`;
}

function formatPct(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
        return "-";
    }
    return `${pctFormatter.format(Number(value))}%`;
}

function monthToDate(period) {
    if (!period || typeof period !== "string") {
        return null;
    }
    return `${period}-01`;
}

function average(values) {
    if (!values.length) return 0;
    return values.reduce((acc, v) => acc + v, 0) / values.length;
}

function percentile(sortedValues, p) {
    if (!sortedValues.length) return 0;
    const k = (sortedValues.length - 1) * (p / 100);
    const low = Math.floor(k);
    const high = Math.min(low + 1, sortedValues.length - 1);
    if (low === high) return sortedValues[low];
    const frac = k - low;
    return sortedValues[low] * (1 - frac) + sortedValues[high] * frac;
}

function movingAverage(values, windowSize = 3) {
    return values.map((_, i) => {
        const start = Math.max(0, i - windowSize + 1);
        const chunk = values.slice(start, i + 1);
        return average(chunk);
    });
}

function indexBase100(values) {
    if (!values.length) return [];
    const base = values[0] || 1;
    return values.map(v => (v / base) * 100);
}

function getChartDomain(values, paddingRatio = 0.08) {
    if (!values.length) {
        return { min: 0, max: 1, range: 1 };
    }

    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = max - min || Math.max(Math.abs(max), 1);
    const pad = span * paddingRatio;

    return {
        min: min - pad,
        max: max + pad,
        range: (max - min) + pad * 2 || 1,
    };
}

function renderBacktestChart(containerId, series) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!series || series.length < 2) {
        container.innerHTML = '<div class="meta">Datos insuficientes para evaluar el backtest.</div>';
        return;
    }

    const width = Math.max(1180, Math.floor((container.clientWidth || 1180) - 2));
    const height = 380;
    const padL = 52;
    const padR = 20;
    const padT = 20;
    const padB = 80;
    const actualValues = series.map(point => Number(point.actual));
    const predictedValues = series.map(point => Number(point.predicted));
    const domain = getChartDomain([...actualValues, ...predictedValues]);
    const usableW = width - padL - padR;
    const usableH = height - padT - padB;

    const xFor = index => padL + (index * usableW) / (series.length - 1);
    const yFor = value => padT + ((domain.max - value) * usableH) / domain.range;

    const actualPoints = series.map((point, index) => ({ x: xFor(index), y: yFor(Number(point.actual)), point, index }));
    const predictedPoints = series.map((point, index) => ({ x: xFor(index), y: yFor(Number(point.predicted)), point, index }));

    const grid = [0, 0.25, 0.5, 0.75, 1].map(ratio => {
        const y = padT + ratio * usableH;
        const value = domain.max - ratio * domain.range;
        return `
            <line x1="${padL}" y1="${y.toFixed(2)}" x2="${width - padR}" y2="${y.toFixed(2)}" stroke="#e5e7eb" stroke-width="1"></line>
            <text x="10" y="${(y + 4).toFixed(2)}" fill="#64748b" font-size="10">${formatTrm(value)}</text>
        `;
    }).join("");

    const actualPolyline = actualPoints.map(point => `${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(" ");
    const predictedPolyline = predictedPoints.map(point => `${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(" ");

    const hoverRects = series.map((point, index) => {
        const currentX = xFor(index);
        const prevX = index > 0 ? xFor(index - 1) : padL;
        const nextX = index < series.length - 1 ? xFor(index + 1) : width - padR;
        const left = index === 0 ? padL : (prevX + currentX) / 2;
        const right = index === series.length - 1 ? (width - padR) : (currentX + nextX) / 2;
        const rectW = Math.max(6, right - left);
        return `
            <rect x="${left.toFixed(2)}" y="${padT}" width="${rectW.toFixed(2)}" height="${usableH.toFixed(2)}" fill="transparent">
                <title>${point.date}\nActual: ${formatTrm(point.actual)}\nPredicho: ${formatTrm(point.predicted)}</title>
            </rect>
        `;
    }).join("");

    container.innerHTML = `
        <svg class="chart-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Backtest Random Forest">
            ${grid}
            <line x1="${padL}" y1="${height - padB}" x2="${width - padR}" y2="${height - padB}" stroke="#64748b" stroke-width="1.2"></line>
            ${hoverRects}
            <polyline points="${actualPolyline}" fill="none" stroke="#0f766e" stroke-width="2.8" stroke-linejoin="round" stroke-linecap="round"></polyline>
            <polyline points="${predictedPolyline}" fill="none" stroke="#b45309" stroke-width="2.4" stroke-dasharray="5 4" stroke-linejoin="round" stroke-linecap="round"></polyline>
            ${actualPoints.map(point => `
                <circle cx="${point.x.toFixed(2)}" cy="${point.y.toFixed(2)}" r="3.8" fill="#0f766e">
                    <title>${point.point.date} | actual: ${formatTrm(point.point.actual)}</title>
                </circle>
            `).join("")}
            ${predictedPoints.map(point => `
                <circle cx="${point.x.toFixed(2)}" cy="${point.y.toFixed(2)}" r="3.8" fill="#b45309">
                    <title>${point.point.date} | predicted: ${formatTrm(point.point.predicted)}</title>
                </circle>
            `).join("")}
            ${series.map((point, index) => {
                const interval = Math.max(1, Math.ceil(series.length / 8));
                if (index % interval !== 0 && index !== series.length - 1) return "";
                const x = xFor(index);
                return `<text x="${x.toFixed(2)}" y="${height - 25}" fill="#64748b" font-size="9" text-anchor="middle">${point.date}</text>`;
            }).join("")}
            <text x="${(width / 2)}" y="${height - 3}" fill="#475569" font-size="11" font-weight="bold">Fecha</text>
            <text x="8" y="${padT + 10}" fill="#475569" font-size="11" font-weight="bold" transform="rotate(-90 8 ${padT + 10})">Valor TRM</text>
        </svg>
    `;
}

function renderForecastComparisonChart(containerId, historySeries, rfProjection, mcProjection) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const history = (historySeries || []).slice(-12);
    if (!history.length) {
        container.innerHTML = '<div class="meta">No hay historial suficiente para comparar.</div>';
        return;
    }

    const width = Math.max(1180, Math.floor((container.clientWidth || 1180) - 2));
    const height = 360;
    const padL = 52;
    const padR = 24;
    const padT = 20;
    const padB = 70;
    const historyValues = history.map(row => Number(row.avg));
    const domain = getChartDomain([...historyValues, Number(rfProjection), Number(mcProjection)]);
    const usableW = width - padL - padR - 72;
    const usableH = height - padT - padB;
    const futureX = padL + usableW + 28;

    const xFor = index => padL + (index * usableW) / (history.length - 1 || 1);
    const yFor = value => padT + ((domain.max - value) * usableH) / domain.range;

    const points = history.map((row, index) => ({ x: xFor(index), y: yFor(Number(row.avg)), row }));
    const historyPolyline = points.map(point => `${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(" ");
    const lastPoint = points[points.length - 1];
    const rfY = yFor(Number(rfProjection));
    const mcY = yFor(Number(mcProjection));

    const grid = [0, 0.25, 0.5, 0.75, 1].map(ratio => {
        const y = padT + ratio * usableH;
        const value = domain.max - ratio * domain.range;
        return `
            <line x1="${padL}" y1="${y.toFixed(2)}" x2="${padL + usableW + 40}" y2="${y.toFixed(2)}" stroke="#e5e7eb" stroke-width="1"></line>
            <text x="10" y="${(y + 4).toFixed(2)}" fill="#64748b" font-size="10">${formatTrm(value)}</text>
        `;
    }).join("");

    const hoverRects = points.map((point, index) => {
        const currentX = point.x;
        const prevX = index > 0 ? points[index - 1].x : padL;
        const nextX = index < points.length - 1 ? points[index + 1].x : (padL + usableW);
        const left = index === 0 ? padL : (prevX + currentX) / 2;
        const right = index === points.length - 1 ? (padL + usableW) : (currentX + nextX) / 2;
        const rectW = Math.max(6, right - left);
        return `
            <rect x="${left.toFixed(2)}" y="${padT}" width="${rectW.toFixed(2)}" height="${usableH.toFixed(2)}" fill="transparent">
                <title>${point.row.period}\nPromedio: ${formatTrm(point.row.avg)}</title>
            </rect>
        `;
    }).join("");

    container.innerHTML = `
        <svg class="chart-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Comparación Random Forest y Monte Carlo">
            ${grid}
            <line x1="${padL}" y1="${height - padB}" x2="${padL + usableW + 40}" y2="${height - padB}" stroke="#64748b" stroke-width="1.2"></line>
            ${hoverRects}
            <polyline points="${historyPolyline}" fill="none" stroke="#2563eb" stroke-width="2.8" stroke-linejoin="round" stroke-linecap="round"></polyline>
            ${points.map(point => `
                <circle cx="${point.x.toFixed(2)}" cy="${point.y.toFixed(2)}" r="3.8" fill="#2563eb">
                    <title>${point.row.period}: ${formatTrm(point.row.avg)}</title>
                </circle>
            `).join("")}
            <line x1="${lastPoint.x.toFixed(2)}" y1="${lastPoint.y.toFixed(2)}" x2="${futureX}" y2="${rfY.toFixed(2)}" stroke="#b45309" stroke-width="1.8" stroke-dasharray="4 4"></line>
            <line x1="${lastPoint.x.toFixed(2)}" y1="${lastPoint.y.toFixed(2)}" x2="${futureX}" y2="${mcY.toFixed(2)}" stroke="#0f766e" stroke-width="1.8" stroke-dasharray="4 4"></line>
            <circle cx="${futureX}" cy="${rfY.toFixed(2)}" r="5.5" fill="#b45309">
                <title>Random Forest próximo mes: ${formatTrm(rfProjection)}</title>
            </circle>
            <circle cx="${futureX}" cy="${mcY.toFixed(2)}" r="5.5" fill="#0f766e">
                <title>Monte Carlo próximo mes: ${formatTrm(mcProjection)}</title>
            </circle>
            <text x="${futureX.toFixed(2)}" y="${height - 12}" fill="#64748b" font-size="10" text-anchor="middle">Próx. mes</text>
            ${points.map((point, index) => {
                if (index % 2 !== 0 && index !== points.length - 1) return "";
                return `<text x="${point.x.toFixed(2)}" y="${height - 20}" fill="#64748b" font-size="9" text-anchor="middle">${point.row.period}</text>`;
            }).join("")}
            <text x="${padL}" y="${padT - 4}" fill="#2563eb" font-size="11">Histórico mensual</text>
            <text x="${padL + 170}" y="${padT - 4}" fill="#b45309" font-size="11">RF</text>
            <text x="${padL + 230}" y="${padT - 4}" fill="#0f766e" font-size="11">Monte Carlo</text>
            <text x="${(width / 2)}" y="${height - 3}" fill="#475569" font-size="11" font-weight="bold">Período (Mes-Año)</text>
            <text x="8" y="${padT + 10}" fill="#475569" font-size="11" font-weight="bold" transform="rotate(-90 8 ${padT + 10})">Valor TRM</text>
        </svg>
    `;
}

function renderMonteCarloHistogram(containerId, scenarios, rfProjection, mcProjection, percentiles) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!scenarios || !scenarios.length) {
        container.innerHTML = '<div class="meta">No hay escenarios de Monte Carlo para mostrar.</div>';
        return;
    }

    const width = Math.max(1180, Math.floor((container.clientWidth || 1180) - 2));
    const height = 380;
    const padL = 52;
    const padR = 22;
    const padT = 20;
    const padB = 80;
    const bins = 20;
    const min = Math.min(...scenarios, Number(rfProjection), Number(mcProjection));
    const max = Math.max(...scenarios, Number(rfProjection), Number(mcProjection));
    const range = max - min || 1;
    const step = range / bins;
    const counts = Array.from({ length: bins }, () => 0);

    scenarios.forEach(value => {
        let idx = Math.floor((value - min) / step);
        if (!Number.isFinite(idx)) idx = 0;
        if (idx >= bins) idx = bins - 1;
        if (idx < 0) idx = 0;
        counts[idx] += 1;
    });

    const maxCount = Math.max(...counts) || 1;
    const usableW = width - padL - padR;
    const usableH = height - padT - padB;
    const barW = usableW / bins * 0.76;
    const xFor = value => padL + ((value - min) / range) * usableW;
    const yFor = count => padT + usableH - (count / maxCount) * usableH;

    const bars = counts.map((count, index) => {
        const x = padL + (index * usableW) / bins + ((usableW / bins) * 0.12);
        const h = (count / maxCount) * usableH;
        const y = padT + usableH - h;
        const bucketStart = min + index * step;
        const bucketEnd = bucketStart + step;
        return `
            <rect x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${barW.toFixed(2)}" height="${h.toFixed(2)}" rx="2" fill="#94a3b8">
                <title>${formatTrm(bucketStart)} - ${formatTrm(bucketEnd)}: ${count} escenarios</title>
            </rect>
        `;
    }).join("");

    const rfX = xFor(Number(rfProjection));
    const mcX = xFor(Number(mcProjection));
    const p05X = percentiles ? xFor(Number(percentiles.p05)) : null;
    const p95X = percentiles ? xFor(Number(percentiles.p95)) : null;

    const grid = [0, 0.25, 0.5, 0.75, 1].map(ratio => {
        const y = padT + ratio * usableH;
        const count = Math.round(maxCount - ratio * maxCount);
        return `
            <line x1="${padL}" y1="${y.toFixed(2)}" x2="${width - padR}" y2="${y.toFixed(2)}" stroke="#e5e7eb" stroke-width="1"></line>
            <text x="10" y="${(y + 4).toFixed(2)}" fill="#64748b" font-size="10">${count}</text>
        `;
    }).join("");

    container.innerHTML = `
        <svg class="chart-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Histograma Monte Carlo">
            ${grid}
            <line x1="${padL}" y1="${height - padB}" x2="${width - padR}" y2="${height - padB}" stroke="#64748b" stroke-width="1.2"></line>
            ${bars}
            <line x1="${rfX.toFixed(2)}" y1="${padT}" x2="${rfX.toFixed(2)}" y2="${height - padB}" stroke="#b45309" stroke-width="2.2"></line>
            <line x1="${mcX.toFixed(2)}" y1="${padT}" x2="${mcX.toFixed(2)}" y2="${height - padB}" stroke="#0f766e" stroke-width="2.2"></line>
            ${p05X !== null ? `<line x1="${p05X.toFixed(2)}" y1="${padT}" x2="${p05X.toFixed(2)}" y2="${height - padB}" stroke="#475569" stroke-width="1.2" stroke-dasharray="4 4"></line>` : ""}
            ${p95X !== null ? `<line x1="${p95X.toFixed(2)}" y1="${padT}" x2="${p95X.toFixed(2)}" y2="${height - padB}" stroke="#475569" stroke-width="1.2" stroke-dasharray="4 4"></line>` : ""}
            <text x="${rfX.toFixed(2)}" y="${padT - 4}" fill="#b45309" font-size="11" text-anchor="middle">RF</text>
            <text x="${mcX.toFixed(2)}" y="${padT - 4}" fill="#0f766e" font-size="11" text-anchor="middle">MC</text>
            ${[0, 0.25, 0.5, 0.75, 1].map(ratio => {
                const value = min + ratio * range;
                const x = xFor(value);
                return `<text x="${x.toFixed(2)}" y="${height - 25}" fill="#64748b" font-size="9" text-anchor="middle">${formatTrm(value)}</text>`;
            }).join("")}
            <text x="${(width / 2)}" y="${height - 3}" fill="#475569" font-size="11" font-weight="bold">Valor TRM (COP)</text>
            <text x="8" y="${padT + 10}" fill="#475569" font-size="11" font-weight="bold" transform="rotate(-90 8 ${padT + 10})">Escenarios</text>
        </svg>
    `;
}

function renderFeatureImportance(containerId, featureImportance) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const entries = Object.entries(featureImportance || {});
    if (!entries.length) {
        container.innerHTML = '<div class="meta">Sin importancias de variables disponibles.</div>';
        return;
    }

    const ordered = [...entries].sort((a, b) => b[1] - a[1]);
    container.innerHTML = ordered.map(([name, value]) => `
        <div class="feature-bar">
            <div class="feature-bar-row">
                <span class="stat-label">${name}</span>
                <div class="feature-bar-track"><div class="feature-bar-fill" style="width: ${(Number(value) * 100).toFixed(2)}%"></div></div>
                <strong class="stat-value">${(Number(value) * 100).toFixed(1)}%</strong>
            </div>
        </div>
    `).join("");
}

function normalizePredictionScopes(data) {
    if (data?.scopes && Object.keys(data.scopes).length) {
        return data.scopes;
    }

    return {
        all_data: {
            scope: {
                key: "all_data",
                label: "Todos los datos",
                records_count: null,
            },
            history: data?.history || { series: [] },
            random_forest: data?.random_forest || {},
            monte_carlo: data?.monte_carlo || {},
            comparison: data?.comparison || {},
            recommendation: data?.recommendation || "Modelos calculados.",
        },
    };
}

function updatePredictionScopeButtons(activeScope) {
    const allBtn = document.getElementById("predictionScopeAllBtn");
    const m36Btn = document.getElementById("predictionScope36mBtn");
    const isAll = activeScope === "all_data";

    if (allBtn) {
        allBtn.classList.toggle("is-active", isAll);
        allBtn.classList.toggle("btn-primary", isAll);
        allBtn.classList.toggle("btn-secondary", !isAll);
        allBtn.setAttribute("aria-selected", isAll ? "true" : "false");
    }

    if (m36Btn) {
        m36Btn.classList.toggle("is-active", !isAll);
        m36Btn.classList.toggle("btn-primary", !isAll);
        m36Btn.classList.toggle("btn-secondary", isAll);
        m36Btn.setAttribute("aria-selected", !isAll ? "true" : "false");
    }
}

function renderPredictionScope(scopeData, mlflow) {
    const rf = scopeData?.random_forest || {};
    const mc = scopeData?.monte_carlo || {};
    const comparison = scopeData?.comparison || {};
    const history = (scopeData?.history && scopeData.history.series) ? scopeData.history.series : [];
    const historySeries = history.slice(-12);
    const rfForecastData = rf?.forecast || {};
    const rfForecast = Number(comparison.rf_forecast ?? rf?.forecast?.next_month_projection ?? 0);
    const mcProjection = Number(comparison.mc_projection ?? mc?.projection_next_month ?? 0);
    const rfNextDayProjection = Number(rfForecastData?.next_day_projection ?? 0);
    const mcNextDayProjection = Number(mc?.projection_next_day ?? 0);
    const rfNextDayDate = rfForecastData?.next_day_date || "-";
    const mcNextDayDate = mc?.next_day_date || rfNextDayDate;
    const todayTrm = Number(mc?.historical?.latest_value ?? historySeries[historySeries.length - 1]?.avg ?? 0);
    const todayDate = scopeData?.scope?.end_date || "-";
    const nextMonthStartDate = rfForecastData?.next_month_start || "";
    let projectedNextMonthLabel = "-";
    if (nextMonthStartDate) {
        const dt = new Date(`${nextMonthStartDate}T00:00:00`);
        if (!Number.isNaN(dt.getTime())) {
            projectedNextMonthLabel = new Intl.DateTimeFormat("es-CO", {
                month: "long",
                year: "numeric",
            }).format(dt);
        } else {
            projectedNextMonthLabel = String(nextMonthStartDate).slice(0, 7);
        }
    }

    const kpis = document.getElementById("predictionKpis");
    const status = document.getElementById("predictionStatus");
    const narrative = document.getElementById("predictionNarrative");
    const rfDetail = document.getElementById("predictionRfDetail");
    const mcDetail = document.getElementById("predictionMonteCarloDetail");

    if (kpis) {
        kpis.innerHTML = `
            <div class="stat-item"><span class="stat-label">TRM hoy (${todayDate})</span><strong class="stat-value">${formatTrm(todayTrm)}</strong></div>
            <div class="stat-item"><span class="stat-label">RF próximo mes (${projectedNextMonthLabel})</span><strong class="stat-value">${formatTrm(rfForecast)}</strong></div>
            <div class="stat-item"><span class="stat-label">MC próximo mes (${projectedNextMonthLabel})</span><strong class="stat-value">${formatTrm(mcProjection)}</strong></div>
            <div class="stat-item"><span class="stat-label">RF día siguiente (${rfNextDayDate})</span><strong class="stat-value">${formatTrm(rfNextDayProjection)}</strong></div>
            <div class="stat-item"><span class="stat-label">MC día siguiente (${mcNextDayDate})</span><strong class="stat-value">${formatTrm(mcNextDayProjection)}</strong></div>
            <div class="stat-item"><span class="stat-label">Gap entre modelos</span><strong class="stat-value">${formatTrm(comparison.gap ?? 0)}</strong></div>
            <div class="stat-item"><span class="stat-label">Alineación</span><strong class="stat-value">${(Number(comparison.alignment_score || 0)).toFixed(1)}%</strong></div>
        `;
    }

    if (status) {
        const scopeLabel = scopeData?.scope?.label || "Todos los datos";
        const scopeRecords = scopeData?.scope?.records_count;
        status.innerText = `✅ Predicción completada · Alcance: ${scopeLabel}${scopeRecords ? ` (${scopeRecords} registros)` : ""} · MLflow: ${mlflow?.experiment_name || '-'} · Escenarios: ${mc.scenario_count || mc.scenarios?.length || 0}`;
    }

    if (rfDetail) {
        const metrics = rf.metrics || {};
        const forecast = rf.forecast || {};
        rfDetail.innerText = `MAE ${formatTrm(metrics.mae)} · RMSE ${formatTrm(metrics.rmse)} · R2 ${(Number(metrics.r2 || 0)).toFixed(4)} · Promedio futuro ${formatTrm(forecast.daily_mean)}`;
    }

    if (mcDetail) {
        const hist = mc.historical || {};
        const pct = mc.percentiles || {};
        mcDetail.innerText = `Media cambios ${formatTrm(hist.mean_change)} · Desv. cambios ${formatTrm(hist.std_change)} · P05 ${formatTrm(pct.p05)} · P95 ${formatTrm(pct.p95)}`;
    }

    if (narrative) {
        narrative.innerText = comparison.message || scopeData?.recommendation || "Modelos calculados.";
    }

    renderBacktestChart("predictionRfChart", rf.test_series || []);
    renderFeatureImportance("predictionFeatureImportance", rf.feature_importance || {});
    renderMonteCarloHistogram("predictionMonteCarloChart", mc.scenarios || [], rfForecast, mcProjection, mc.percentiles || {});
    renderForecastComparisonChart("predictionComparisonChart", historySeries, rfForecast, mcProjection);
}

function setPredictionScope(scopeKey) {
    predictionScopeState = scopeKey;
    updatePredictionScopeButtons(scopeKey);

    if (!predictionDashboardState) return;
    const scopes = normalizePredictionScopes(predictionDashboardState);
    const selectedScope = scopes[scopeKey] || scopes.all_data || Object.values(scopes)[0];
    if (!selectedScope) return;

    renderPredictionScope(selectedScope, predictionDashboardState.mlflow || {});
}

function renderPredictionDashboard(data) {
    predictionDashboardState = data;
    const scopes = normalizePredictionScopes(data);
    const defaultScope = data?.default_scope || "all_data";
    const selectedScope = scopes[predictionScopeState] ? predictionScopeState : defaultScope;
    setPredictionScope(selectedScope);
}

function getPrediction() {
    const status = document.getElementById("predictionStatus");
    if (status) {
        status.innerText = "⏳ Ejecutando Random Forest, Monte Carlo y MLflow...";
    }

    fetch("/predict")
        .then(res => res.json())
        .then(data => {
            renderPredictionDashboard(data);
        })
        .catch(err => {
            if (status) {
                status.innerText = "❌ Error obteniendo predicción: " + err;
            }
        });
}

function fetchAllRows() {
    if (!cachedRowsPromise) {
        cachedRowsPromise = fetch("/data")
            .then(res => {
                if (!res.ok) {
                    throw new Error(`HTTP ${res.status}`);
                }
                return res.json();
            })
            .then(payload => {
                const rows = (payload.data || []).map(row => ({
                    date: row.date,
                    trm: Number(row.trm),
                }));
                rows.sort((a, b) => a.date.localeCompare(b.date));
                allRowsCache = rows;
                return rows;
            });
    }
    return cachedRowsPromise;
}

function filterRows(rows, { startDate, endDate, minTrm, maxTrm }) {
    return rows.filter(row => {
        if (startDate && row.date < startDate) return false;
        if (endDate && row.date > endDate) return false;
        if (minTrm !== null && row.trm < minTrm) return false;
        if (maxTrm !== null && row.trm > maxTrm) return false;
        return true;
    });
}

function renderDataTable(rows, limit) {
    const tableBody = document.getElementById("dataTableBody");
    const dataMeta = document.getElementById("dataMeta");
    if (!tableBody || !dataMeta) return;

    const safeLimit = Number(limit);
    const visibleRows = safeLimit > 0 ? rows.slice(-safeLimit).reverse() : [...rows].reverse();
    dataMeta.innerText = `Registros visibles: ${visibleRows.length} · Registros filtrados: ${rows.length} · Total: ${allRowsCache.length}`;

    if (!visibleRows.length) {
        tableBody.innerHTML = '<tr><td colspan="2" class="meta">No hay datos para los filtros seleccionados.</td></tr>';
        return;
    }

    tableBody.innerHTML = visibleRows
        .map(row => `<tr><td>${row.date}</td><td>${formatTrm(row.trm)}</td></tr>`)
        .join("");
}

function readDataFilters() {
    const startDate = document.getElementById("dataFilterStartDate")?.value || "";
    const endDate = document.getElementById("dataFilterEndDate")?.value || "";
    const minTrmRaw = document.getElementById("dataFilterMinTrm")?.value;
    const maxTrmRaw = document.getElementById("dataFilterMaxTrm")?.value;
    const limit = document.getElementById("dataFilterLimit")?.value || "200";

    return {
        startDate,
        endDate,
        minTrm: minTrmRaw === "" || minTrmRaw === undefined ? null : Number(minTrmRaw),
        maxTrm: maxTrmRaw === "" || maxTrmRaw === undefined ? null : Number(maxTrmRaw),
        limit,
    };
}

function applyDataFilters() {
    const filters = readDataFilters();
    const filtered = filterRows(allRowsCache, filters);
    renderDataTable(filtered, filters.limit);
}

function loadData(forceRefresh = false) {
    const dataMeta = document.getElementById("dataMeta");
    if (dataMeta) {
        dataMeta.innerText = "Cargando datos...";
    }

    if (forceRefresh) {
        cachedRowsPromise = null;
    }

    fetchAllRows()
        .then(() => {
            applyDataFilters();
        })
        .catch(err => {
            if (dataMeta) {
                dataMeta.innerText = "Error cargando datos: " + err;
            }
        });
}

function computeEdaFromRows(rows, monthlyWindow) {
    if (!rows.length) {
        return {
            meta: { count: 0, start_date: "-", end_date: "-" },
            descriptive: {},
            outliers: {},
            trend: {},
            volatility: {},
            latest: {},
            monthly_summary: [],
            yearly_summary: [],
        };
    }

    const values = rows.map(r => r.trm);
    const sorted = [...values].sort((a, b) => a - b);
    const count = values.length;
    const mean = average(values);
    const variance = average(values.map(v => (v - mean) ** 2));
    const std = Math.sqrt(variance);
    const q1 = percentile(sorted, 25);
    const q3 = percentile(sorted, 75);
    const iqr = q3 - q1;
    const lowerBound = q1 - 1.5 * iqr;
    const upperBound = q3 + 1.5 * iqr;
    const outliers = values.filter(v => v < lowerBound || v > upperBound);
    const diff = values.slice(1).map((v, i) => v - values[i]);
    const absChange = values[values.length - 1] - values[0];
    const pctChange = values[0] ? (absChange / values[0]) * 100 : 0;

    let direction = "flat";
    if (absChange > 0) direction = "up";
    if (absChange < 0) direction = "down";

    const monthlyMap = new Map();
    const yearlyMap = new Map();
    rows.forEach(row => {
        const period = row.date.slice(0, 7);
        const year = row.date.slice(0, 4);
        if (!monthlyMap.has(period)) monthlyMap.set(period, []);
        if (!yearlyMap.has(year)) yearlyMap.set(year, []);
        monthlyMap.get(period).push(row.trm);
        yearlyMap.get(year).push(row.trm);
    });

    let monthlySummary = [...monthlyMap.entries()].map(([period, vals]) => ({
        period,
        count: vals.length,
        avg: average(vals),
        min: Math.min(...vals),
        max: Math.max(...vals),
    }));
    monthlySummary.sort((a, b) => a.period.localeCompare(b.period));
    if (monthlyWindow > 0) {
        monthlySummary = monthlySummary.slice(-monthlyWindow);
    }

    const yearlySummary = [...yearlyMap.entries()]
        .map(([year, vals]) => ({
            year: Number(year),
            count: vals.length,
            avg: average(vals),
            min: Math.min(...vals),
            max: Math.max(...vals),
        }))
        .sort((a, b) => a.year - b.year);

    const prev = rows[rows.length - 2] || rows[rows.length - 1];
    const latest = rows[rows.length - 1];

    return {
        meta: {
            count,
            start_date: rows[0].date,
            end_date: latest.date,
        },
        descriptive: {
            mean,
            median: percentile(sorted, 50),
            std,
            cv: mean ? (std / mean) * 100 : 0,
            min: Math.min(...values),
            max: Math.max(...values),
            p10: percentile(sorted, 10),
            q1,
            q3,
            p90: percentile(sorted, 90),
        },
        outliers: {
            count: outliers.length,
            ratio_pct: (outliers.length / count) * 100,
            lower_bound: lowerBound,
            upper_bound: upperBound,
        },
        trend: {
            direction,
            absolute_change: absChange,
            percent_change: pctChange,
            slope_per_step: count > 1 ? absChange / (count - 1) : 0,
        },
        volatility: {
            avg_abs_daily_change: diff.length ? average(diff.map(v => Math.abs(v))) : 0,
            max_up_day: diff.length ? Math.max(...diff) : 0,
            max_down_day: diff.length ? Math.min(...diff) : 0,
        },
        latest: {
            date: latest.date,
            value: latest.trm,
            prev_date: prev.date,
            prev_value: prev.trm,
            delta: latest.trm - prev.trm,
        },
        monthly_summary: monthlySummary,
        yearly_summary: yearlySummary,
    };
}

function summarizeEda(eda) {
    const d = eda.descriptive || {};
    const t = eda.trend || {};
    const o = eda.outliers || {};
    const v = eda.volatility || {};
    const l = eda.latest || {};

    return {
        meta: eda.meta,
        latest: {
            date: l.date,
            value: formatTrm(l.value),
            prev_date: l.prev_date,
            prev_value: formatTrm(l.prev_value),
            delta: formatTrm(l.delta),
        },
        descriptive: {
            mean: formatTrm(d.mean),
            median: formatTrm(d.median),
            std: formatTrm(d.std),
            min: formatTrm(d.min),
            max: formatTrm(d.max),
            q1: formatTrm(d.q1),
            q3: formatTrm(d.q3),
            p10: formatTrm(d.p10),
            p90: formatTrm(d.p90),
            cv_pct: formatPct(d.cv),
        },
        outliers: {
            count: o.count ?? 0,
            ratio_pct: formatPct(o.ratio_pct),
            lower_bound: formatTrm(o.lower_bound),
            upper_bound: formatTrm(o.upper_bound),
        },
        trend: {
            direction: t.direction,
            absolute_change: formatTrm(t.absolute_change),
            percent_change: formatPct(t.percent_change),
            slope_per_step: Number(t.slope_per_step || 0).toFixed(6),
        },
        volatility: {
            avg_abs_daily_change: formatTrm(v.avg_abs_daily_change),
            max_up_day: formatTrm(v.max_up_day),
            max_down_day: formatTrm(v.max_down_day),
        },
        monthly_summary: eda.monthly_summary || [],
        yearly_summary: eda.yearly_summary || [],
    };
}

function renderSparkline(summaryMonthly) {
    const container = document.getElementById("edaSparkline");
    const selectedPoint = document.getElementById("edaSelectedPoint");
    if (!container) return;

    const values = summaryMonthly.map(m => Number(m.avg));
    if (values.length < 2) {
        container.innerHTML = '<span class="meta">Datos insuficientes para gráfica.</span>';
        if (selectedPoint) {
            selectedPoint.innerText = "Selecciona un punto en la gráfica para ver detalle.";
        }
        return;
    }

    const width = Math.max(720, Math.floor((container.clientWidth || 720) - 2));
    const height = Math.max(165, Math.min(220, Math.round(width * 0.2)));
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    const previewLabels = [max, max - 0.5 * range, min].map(v => formatTrm(v));
    const maxLabelChars = Math.max(...previewLabels.map(label => String(label).length));
    const padL = Math.min(96, Math.max(54, maxLabelChars * 7));
    const padR = 16;
    const padT = 18;
    const padB = 18;

    const pointTuples = values.map((v, i) => {
        const x = padL + (i * (width - padL - padR)) / (values.length - 1);
        const y = padT + ((max - v) * (height - padT - padB)) / range;
        return { x, y, v, period: summaryMonthly[i].period };
    });

    const polyline = pointTuples.map(p => `${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(" ");
    const yTicks = [0, 0.5, 1].map(ratio => {
        const value = max - ratio * range;
        const y = padT + ratio * (height - padT - padB);
        return { value, y };
    });
    const xTickLabels = pointTuples.map((p, idx) => ({ ...p, idx }))
        .filter(p => p.idx % 3 === 0 || p.idx === pointTuples.length - 1);

    container.innerHTML = `
        <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" class="sparkline-svg" role="img" aria-label="Tendencia mensual TRM">
            <line x1="${padL}" y1="${height - padB}" x2="${width - padR}" y2="${height - padB}" stroke="#64748b" stroke-width="1.2"></line>
            <line x1="${padL}" y1="${padT}" x2="${padL}" y2="${height - padB}" stroke="#64748b" stroke-width="1.2"></line>
            ${yTicks.map(tick => `
                <line x1="${padL - 4}" y1="${tick.y.toFixed(2)}" x2="${padL}" y2="${tick.y.toFixed(2)}" stroke="#64748b" stroke-width="1"></line>
                <text x="${(padL - 8).toFixed(2)}" y="${(tick.y + 3).toFixed(2)}" fill="#64748b" font-size="9" text-anchor="end">${formatTrm(tick.value)}</text>
            `).join("")}
            <polyline fill="none" stroke="#2563eb" stroke-width="2.8" points="${polyline}" />
            ${pointTuples.map((p, idx) => `
                <circle class="interactive-point" cx="${p.x.toFixed(2)}" cy="${p.y.toFixed(2)}" r="4.2" fill="#1d4ed8" pointer-events="none">
                    <title>${p.period}: ${formatTrm(p.v)}</title>
                </circle>
                <circle class="interactive-hit-point" data-index="${idx}" cx="${p.x.toFixed(2)}" cy="${p.y.toFixed(2)}" r="10" fill="transparent"></circle>
            `).join("")}
            ${xTickLabels.map(p => `
                <line x1="${p.x.toFixed(2)}" y1="${(height - padB).toFixed(2)}" x2="${p.x.toFixed(2)}" y2="${(height - padB + 4).toFixed(2)}" stroke="#64748b" stroke-width="1"></line>
                <text x="${p.x.toFixed(2)}" y="${(height - 4).toFixed(2)}" fill="#64748b" font-size="9" text-anchor="middle">${p.period}</text>
            `).join("")}
        </svg>
    `;

    const circles = container.querySelectorAll(".interactive-hit-point");
    circles.forEach(circle => {
        circle.addEventListener("click", () => {
            const idx = Number(circle.dataset.index);
            const point = pointTuples[idx];
            if (!selectedPoint || !point) return;
            selectedPoint.innerText = `Seleccionado ${point.period}: ${formatTrm(point.v)}`;
        });
    });
}

function renderSparklineInContainer(containerId, selectedPointId, summaryMonthly) {
    const container = document.getElementById(containerId);
    const selectedPoint = document.getElementById(selectedPointId);
    if (!container) return;

    const values = summaryMonthly.map(m => Number(m.avg));
    if (values.length < 2) {
        container.innerHTML = '<span class="meta">Datos insuficientes para gráfica.</span>';
        if (selectedPoint) {
            selectedPoint.innerText = "Selecciona un punto en la gráfica para ver detalle.";
        }
        return;
    }

    const width = Math.max(720, Math.floor((container.clientWidth || 720) - 2));
    const height = Math.max(165, Math.min(220, Math.round(width * 0.2)));
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    const previewLabels = [max, max - 0.5 * range, min].map(v => formatTrm(v));
    const maxLabelChars = Math.max(...previewLabels.map(label => String(label).length));
    const padL = Math.min(96, Math.max(54, maxLabelChars * 7));
    const padR = 16;
    const padT = 18;
    const padB = 18;

    const pointTuples = values.map((v, i) => {
        const x = padL + (i * (width - padL - padR)) / (values.length - 1);
        const y = padT + ((max - v) * (height - padT - padB)) / range;
        return { x, y, v, period: summaryMonthly[i].period };
    });

    const polyline = pointTuples.map(p => `${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(" ");
    const yTicks = [0, 0.5, 1].map(ratio => {
        const value = max - ratio * range;
        const y = padT + ratio * (height - padT - padB);
        return { value, y };
    });
    const xTickLabels = pointTuples.map((p, idx) => ({ ...p, idx }))
        .filter(p => p.idx % 3 === 0 || p.idx === pointTuples.length - 1);

    container.innerHTML = `
        <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" class="sparkline-svg" role="img" aria-label="Tendencia mensual TRM">
            <line x1="${padL}" y1="${height - padB}" x2="${width - padR}" y2="${height - padB}" stroke="#64748b" stroke-width="1.2"></line>
            <line x1="${padL}" y1="${padT}" x2="${padL}" y2="${height - padB}" stroke="#64748b" stroke-width="1.2"></line>
            ${yTicks.map(tick => `
                <line x1="${padL - 4}" y1="${tick.y.toFixed(2)}" x2="${padL}" y2="${tick.y.toFixed(2)}" stroke="#64748b" stroke-width="1"></line>
                <text x="${(padL - 8).toFixed(2)}" y="${(tick.y + 3).toFixed(2)}" fill="#64748b" font-size="9" text-anchor="end">${formatTrm(tick.value)}</text>
            `).join("")}
            <polyline fill="none" stroke="#2563eb" stroke-width="2.8" points="${polyline}" />
            ${pointTuples.map((p, idx) => `
                <circle class="interactive-point" cx="${p.x.toFixed(2)}" cy="${p.y.toFixed(2)}" r="4.2" fill="#1d4ed8" pointer-events="none">
                    <title>${p.period}: ${formatTrm(p.v)}</title>
                </circle>
                <circle class="interactive-hit-point" data-index="${idx}" cx="${p.x.toFixed(2)}" cy="${p.y.toFixed(2)}" r="10" fill="transparent"></circle>
            `).join("")}
            ${xTickLabels.map(p => `
                <line x1="${p.x.toFixed(2)}" y1="${(height - padB).toFixed(2)}" x2="${p.x.toFixed(2)}" y2="${(height - padB + 4).toFixed(2)}" stroke="#64748b" stroke-width="1"></line>
                <text x="${p.x.toFixed(2)}" y="${(height - 4).toFixed(2)}" fill="#64748b" font-size="9" text-anchor="middle">${p.period}</text>
            `).join("")}
        </svg>
    `;

    const circles = container.querySelectorAll(".interactive-hit-point");
    circles.forEach(circle => {
        circle.addEventListener("click", () => {
            const idx = Number(circle.dataset.index);
            const point = pointTuples[idx];
            if (!selectedPoint || !point) return;
            selectedPoint.innerText = `Seleccionado ${point.period}: ${formatTrm(point.v)}`;
        });
    });
}

function renderSummaryTables(summary) {
    const monthlyBody = document.getElementById("monthlySummaryBody");
    const yearlyBody = document.getElementById("yearlySummaryBody");

    if (monthlyBody) {
        const monthly = summary.monthly_summary || [];
        monthlyBody.innerHTML = monthly.length
            ? monthly.map(m => `
                <tr>
                    <td>${m.period}</td>
                    <td>${formatTrm(m.avg)}</td>
                    <td>${formatTrm(m.min)}</td>
                    <td>${formatTrm(m.max)}</td>
                </tr>
            `).join("")
            : '<tr><td colspan="4" class="meta">Sin datos mensuales.</td></tr>';
    }

    if (yearlyBody) {
        const yearly = summary.yearly_summary || [];
        yearlyBody.innerHTML = yearly.length
            ? yearly.map(y => `
                <tr>
                    <td>${y.year}</td>
                    <td>${formatTrm(y.avg)}</td>
                    <td>${formatTrm(y.min)}</td>
                    <td>${formatTrm(y.max)}</td>
                </tr>
            `).join("")
            : '<tr><td colspan="4" class="meta">Sin datos anuales.</td></tr>';
    }
}

function renderEdaStats(summary) {
    const stats = document.getElementById("edaStats");
    if (!stats || !summary) return;

    const descriptive = summary.descriptive || {};
    const trend = summary.trend || {};
    const outliers = summary.outliers || {};
    const latest = summary.latest || {};

    stats.innerHTML = `
        <div class="stat-item"><span class="stat-label">Media</span><strong class="stat-value">${descriptive.mean ?? "-"}</strong></div>
        <div class="stat-item"><span class="stat-label">Desv. estándar</span><strong class="stat-value">${descriptive.std ?? "-"}</strong></div>
        <div class="stat-item"><span class="stat-label">Tendencia</span><strong class="stat-value">${trend.direction ?? "-"}</strong></div>
        <div class="stat-item"><span class="stat-label">Outliers</span><strong class="stat-value">${outliers.count ?? "-"}</strong></div>
        <div class="stat-item"><span class="stat-label">Último valor</span><strong class="stat-value">${latest.value ?? "-"}</strong></div>
        <div class="stat-item"><span class="stat-label">Cambio %</span><strong class="stat-value">${trend.percent_change ?? "-"}</strong></div>
    `;
}

function renderLatest(summary) {
    const latest = summary.latest || {};
    const trend = summary.trend || {};

    const latestDate = document.getElementById("latestDate");
    const latestValue = document.getElementById("latestValue");
    const latestPrevDate = document.getElementById("latestPrevDate");
    const latestDelta = document.getElementById("latestDelta");
    const trendMeta = document.getElementById("edaTrendMeta");

    if (latestDate) latestDate.innerText = latest.date ?? "-";
    if (latestValue) latestValue.innerText = latest.value ?? "-";
    if (latestPrevDate) latestPrevDate.innerText = latest.prev_date ?? "-";
    if (latestDelta) latestDelta.innerText = latest.delta ?? "-";
    if (trendMeta) trendMeta.innerText = `Dirección: ${trend.direction ?? "-"} · Cambio: ${trend.percent_change ?? "-"}`;
}

function renderEda36m(eda36m) {
    const summary = summarizeEda(eda36m);
    const meta = document.getElementById("edaMeta36m");
    const stats = document.getElementById("edaStats36m");
    const latestDate = document.getElementById("latestDate36m");
    const latestValue = document.getElementById("latestValue36m");
    const latestPrevDate = document.getElementById("latestPrevDate36m");
    const latestDelta = document.getElementById("latestDelta36m");
    const trendMeta = document.getElementById("edaTrendMeta36m");
    const monthlyBody = document.getElementById("monthlySummaryBody36m");
    const yearlyBody = document.getElementById("yearlySummaryBody36m");
    const result = document.getElementById("edaResult36m");

    if (meta) {
        meta.innerText = `Rango: ${summary.meta?.start_date ?? "-"} a ${summary.meta?.end_date ?? "-"} · Registros: ${summary.meta?.count ?? 0}`;
    }

    if (stats) {
        const d = summary.descriptive || {};
        const t = summary.trend || {};
        const o = summary.outliers || {};
        stats.innerHTML = `
            <div class="stat-item"><span class="stat-label">Media</span><strong class="stat-value">${d.mean ?? "-"}</strong></div>
            <div class="stat-item"><span class="stat-label">Desv. estándar</span><strong class="stat-value">${d.std ?? "-"}</strong></div>
            <div class="stat-item"><span class="stat-label">Tendencia</span><strong class="stat-value">${t.direction ?? "-"}</strong></div>
            <div class="stat-item"><span class="stat-label">Outliers</span><strong class="stat-value">${o.count ?? 0}</strong></div>
        `;
    }

    if (latestDate) latestDate.innerText = summary.latest?.date ?? "-";
    if (latestValue) latestValue.innerText = summary.latest?.value ?? "-";
    if (latestPrevDate) latestPrevDate.innerText = summary.latest?.prev_date ?? "-";
    if (latestDelta) latestDelta.innerText = summary.latest?.delta ?? "-";
    if (trendMeta) {
        trendMeta.innerText = `Dirección: ${summary.trend?.direction ?? "-"} · Cambio: ${summary.trend?.percent_change ?? "-"}`;
    }

    if (monthlyBody) {
        const monthly = summary.monthly_summary || [];
        monthlyBody.innerHTML = monthly.length
            ? monthly.map(m => `
                <tr>
                    <td>${m.period}</td>
                    <td>${formatTrm(m.avg)}</td>
                    <td>${formatTrm(m.min)}</td>
                    <td>${formatTrm(m.max)}</td>
                </tr>
            `).join("")
            : '<tr><td colspan="4" class="meta">Sin datos mensuales.</td></tr>';
    }

    if (yearlyBody) {
        const yearly = summary.yearly_summary || [];
        yearlyBody.innerHTML = yearly.length
            ? yearly.map(y => `
                <tr>
                    <td>${y.year}</td>
                    <td>${formatTrm(y.avg)}</td>
                    <td>${formatTrm(y.min)}</td>
                    <td>${formatTrm(y.max)}</td>
                </tr>
            `).join("")
            : '<tr><td colspan="4" class="meta">Sin datos anuales.</td></tr>';
    }

    renderSparklineInContainer("edaSparkline36m", "edaSelectedPoint36m", summary.monthly_summary || []);

    if (result) {
        result.innerText = JSON.stringify(summary, null, 2);
    }
}

function readEdaFilters() {
    const startDate = document.getElementById("edaFilterStartDate")?.value || "";
    const endDate = document.getElementById("edaFilterEndDate")?.value || "";
    const monthlyWindow = Number(document.getElementById("edaMonthlyWindow")?.value || "6");
    return { startDate, endDate, monthlyWindow };
}

function subtractMonthsFromIsoDate(isoDate, months) {
    const [year, month, day] = isoDate.split("-").map(Number);
    const totalMonths = (year * 12 + (month - 1)) - months;
    const targetYear = Math.floor(totalMonths / 12);
    const targetMonth = (totalMonths % 12) + 1;
    const lastDay = new Date(targetYear, targetMonth, 0).getDate();
    const safeDay = Math.min(day, lastDay);
    return `${targetYear.toString().padStart(4, "0")}-${targetMonth.toString().padStart(2, "0")}-${safeDay.toString().padStart(2, "0")}`;
}

function rowsLastNMonths(rows, months) {
    if (!rows.length || months <= 0) return [...rows];
    const latestDate = rows[rows.length - 1].date;
    const cutoff = subtractMonthsFromIsoDate(latestDate, months);
    return rows.filter(row => row.date >= cutoff);
}

function applyEdaFilters(scrollToPanel = false) {
    const edaMeta = document.getElementById("edaMeta");
    const edaResult = document.getElementById("edaResult");
    const edaCard = document.getElementById("edaCard");
    if (!edaMeta || !edaResult || !edaCard) return;

    const filters = readEdaFilters();
    const filtered = filterRows(allRowsCache, {
        startDate: filters.startDate,
        endDate: filters.endDate,
        minTrm: null,
        maxTrm: null,
    });

    const eda = computeEdaFromRows(filtered, filters.monthlyWindow);
    const summary = summarizeEda(eda);

    edaMeta.innerText = `Rango: ${eda.meta.start_date} a ${eda.meta.end_date} · Registros: ${eda.meta.count} · Total fuente: ${allRowsCache.length}`;
    renderEdaStats(summary);
    renderLatest(summary);
    renderSummaryTables(summary);
    renderSparkline(summary.monthly_summary || []);
    edaResult.innerText = JSON.stringify(summary, null, 2);

    if (scrollToPanel) {
        edaCard.scrollIntoView({ behavior: "smooth", block: "start" });
    }
}

function loadEda(scrollToPanel = false, forceRefresh = false) {
    const edaMeta = document.getElementById("edaMeta");
    const edaCard = document.getElementById("edaCard");
    if (edaMeta) edaMeta.innerText = "Cargando EDA...";
    if (edaCard) edaCard.classList.add("loading");

    if (forceRefresh) {
        cachedRowsPromise = null;
    }

    fetchAllRows()
        .then(() => {
            applyEdaFilters(scrollToPanel);
            const last36Rows = rowsLastNMonths(allRowsCache, 36);
            const eda36m = computeEdaFromRows(last36Rows, 36);
            renderEda36m(eda36m);
        })
        .catch(err => {
            if (edaMeta) {
                edaMeta.innerText = "Error cargando EDA: " + err;
            }
        })
        .finally(() => {
            if (edaCard) edaCard.classList.remove("loading");
        });
}

function buildVisualState(series) {
    const normalized = (series || []).map(row => ({
        period: row.period,
        date: monthToDate(row.period),
        avg: Number(row.avg),
        changeAbs: row.change_abs === null || row.change_abs === undefined ? null : Number(row.change_abs),
        changePct: row.change_pct === null || row.change_pct === undefined ? null : Number(row.change_pct),
    }));
    const avgSeries = normalized.map(r => r.avg);
    const movingAvgSeries = movingAverage(avgSeries, 3);
    const indexSeries = indexBase100(avgSeries);

    return normalized.map((row, idx) => ({
        ...row,
        movingAvg: movingAvgSeries[idx],
        indexBase: indexSeries[idx],
    }));
}

function readVisualFilters() {
    return {
        metric: document.getElementById("visualMetricSelect")?.value || "avg",
        startDate: document.getElementById("visualFilterStartDate")?.value || "",
        endDate: document.getElementById("visualFilterEndDate")?.value || "",
        quickWindow: Number(document.getElementById("visualQuickWindow")?.value || "36"),
    };
}

function applyQuickWindow(series, months) {
    const startInput = document.getElementById("visualFilterStartDate");
    const endInput = document.getElementById("visualFilterEndDate");
    if (!series.length) {
        if (startInput) startInput.value = "";
        if (endInput) endInput.value = "";
        return;
    }

    if (!months || months <= 0) {
        if (startInput) startInput.value = "";
        if (endInput) endInput.value = "";
        return;
    }

    const start = series[Math.max(0, series.length - months)].date;
    const end = series[series.length - 1].date;
    if (startInput) startInput.value = start;
    if (endInput) endInput.value = end;
}

function renderVisualTable(series) {
    const body = document.getElementById("visualSeriesBody");
    if (!body) return;

    body.innerHTML = series.length
        ? series.map(row => `
            <tr>
                <td>${row.period}</td>
                <td>${formatTrm(row.avg)}</td>
                <td>${row.changeAbs === null ? "-" : formatTrm(row.changeAbs)}</td>
                <td>${row.changePct === null ? "-" : formatPct(row.changePct)}</td>
            </tr>
        `).join("")
        : '<tr><td colspan="4" class="meta">No hay datos para el rango seleccionado.</td></tr>';
}

function renderVisualStats(series) {
    const countEl = document.getElementById("visualCountMonths");
    const startEl = document.getElementById("visualStartPeriod");
    const endEl = document.getElementById("visualEndPeriod");
    const latestEl = document.getElementById("visualLatestAvg");

    if (!series.length) {
        if (countEl) countEl.innerText = "0";
        if (startEl) startEl.innerText = "-";
        if (endEl) endEl.innerText = "-";
        if (latestEl) latestEl.innerText = "-";
        return;
    }

    const latest = series[series.length - 1];
    if (countEl) countEl.innerText = String(series.length);
    if (startEl) startEl.innerText = series[0].period;
    if (endEl) endEl.innerText = latest.period;
    if (latestEl) latestEl.innerText = formatTrm(latest.avg);
}

function renderVisualChart(series, metric) {
    const chartContainer = document.getElementById("visualChartContainer");
    const selectionMeta = document.getElementById("visualSelectionMeta");
    const detail = document.getElementById("visualPointDetail");
    if (!chartContainer || !selectionMeta || !detail) return;

    if (series.length < 2) {
        chartContainer.innerHTML = '<div class="meta">Datos insuficientes para graficar.</div>';
        detail.innerHTML = "";
        return;
    }

    const metricMap = {
        avg: { label: "Promedio mensual", format: formatTrm },
        movingAvg: { label: "Media móvil 3M", format: formatTrm },
        changeAbs: { label: "Cambio absoluto mensual", format: formatTrm },
        changePct: { label: "Cambio porcentual mensual", format: formatPct },
        indexBase: { label: "Índice base 100", format: v => Number(v).toFixed(2) },
    };
    const cfg = metricMap[metric] || metricMap.avg;

    const points = series.map(row => {
        let value = row[metric];
        if (value === null || value === undefined) {
            value = 0;
        }
        return { period: row.period, value, row };
    });

    const width = Math.max(980, Math.floor((chartContainer.clientWidth || 980) - 2));
    const height = 320;
    const padL = 52;
    const padR = 20;
    const padT = 18;
    const padB = 44;
    const min = Math.min(...points.map(p => p.value));
    const max = Math.max(...points.map(p => p.value));
    const range = max - min || 1;
    const usableW = width - padL - padR;
    const usableH = height - padT - padB;

    const coords = points.map((point, idx) => {
        const x = padL + (idx * usableW) / (points.length - 1);
        const y = padT + ((max - point.value) * usableH) / range;
        return { ...point, x, y, idx };
    });
    const yTicks = [0, 0.25, 0.5, 0.75, 1].map(ratio => {
        const value = max - ratio * range;
        const y = padT + ratio * usableH;
        return { value, y };
    });

    const polyline = coords.map(c => `${c.x.toFixed(2)},${c.y.toFixed(2)}`).join(" ");

    chartContainer.innerHTML = `
        <svg class="chart-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="${cfg.label}">
            <line x1="${padL}" y1="${height - padB}" x2="${width - padR}" y2="${height - padB}" stroke="#64748b" stroke-width="1.2"></line>
            <line x1="${padL}" y1="${padT}" x2="${padL}" y2="${height - padB}" stroke="#64748b" stroke-width="1.2"></line>
            ${yTicks.map(tick => `
                <line x1="${(padL - 5).toFixed(2)}" y1="${tick.y.toFixed(2)}" x2="${padL}" y2="${tick.y.toFixed(2)}" stroke="#64748b" stroke-width="1"></line>
                <text x="${(padL - 8).toFixed(2)}" y="${(tick.y + 3).toFixed(2)}" fill="#64748b" font-size="10" text-anchor="end">${cfg.format(tick.value)}</text>
            `).join("")}
            <polyline points="${polyline}" fill="none" stroke="#0f766e" stroke-width="2.8" stroke-linejoin="round" stroke-linecap="round"></polyline>
            ${coords.map(c => `
                <circle class="interactive-point" cx="${c.x.toFixed(2)}" cy="${c.y.toFixed(2)}" r="4.4" fill="#115e59" pointer-events="none">
                    <title>${c.period}: ${cfg.format(c.value)}</title>
                </circle>
                <circle class="interactive-hit-point" data-index="${c.idx}" cx="${c.x.toFixed(2)}" cy="${c.y.toFixed(2)}" r="11" fill="transparent"></circle>
            `).join("")}
            ${coords.map((c, i) => {
                if (i % 6 !== 0 && i !== coords.length - 1) return "";
                return `<text x="${(c.x - 18).toFixed(2)}" y="${height - 12}" fill="#64748b" font-size="10">${c.period}</text>`;
            }).join("")}
        </svg>
    `;

    detail.innerHTML = "";
    selectionMeta.innerText = `Serie: ${cfg.label}. Haz clic en un punto para detalle.`;

    chartContainer.querySelectorAll(".interactive-hit-point").forEach(pointEl => {
        pointEl.addEventListener("click", () => {
            const idx = Number(pointEl.dataset.index);
            const selected = coords[idx];
            if (!selected) return;

            selectionMeta.innerText = `Seleccionado ${selected.period}: ${cfg.format(selected.value)}`;
            detail.innerHTML = `
                <div class="stat-item"><span class="stat-label">Periodo</span><strong class="stat-value">${selected.row.period}</strong></div>
                <div class="stat-item"><span class="stat-label">Promedio</span><strong class="stat-value">${formatTrm(selected.row.avg)}</strong></div>
                <div class="stat-item"><span class="stat-label">Cambio abs.</span><strong class="stat-value">${selected.row.changeAbs === null ? "-" : formatTrm(selected.row.changeAbs)}</strong></div>
                <div class="stat-item"><span class="stat-label">Cambio %</span><strong class="stat-value">${selected.row.changePct === null ? "-" : formatPct(selected.row.changePct)}</strong></div>
            `;
        });
    });
}

function renderVisualTrendVsMa(series) {
    const container = document.getElementById("visualTrendVsMaChart");
    if (!container) return;

    if (series.length < 2) {
        container.innerHTML = '<div class="meta">Datos insuficientes para comparar tendencia y media móvil.</div>';
        return;
    }

    const width = 980;
    const height = 280;
    const padL = 48;
    const padR = 20;
    const padT = 18;
    const padB = 42;
    const avgValues = series.map(row => Number(row.avg));
    const maValues = series.map(row => Number(row.movingAvg));
    const merged = [...avgValues, ...maValues];
    const min = Math.min(...merged);
    const max = Math.max(...merged);
    const range = max - min || 1;
    const usableW = width - padL - padR;
    const usableH = height - padT - padB;

    const xFor = i => padL + (i * usableW) / (series.length - 1 || 1);
    const yFor = v => padT + ((max - v) * usableH) / range;

    const avgPts = avgValues.map((v, i) => `${xFor(i).toFixed(2)},${yFor(v).toFixed(2)}`).join(" ");
    const maPts = maValues.map((v, i) => `${xFor(i).toFixed(2)},${yFor(v).toFixed(2)}`).join(" ");
    const yTicks = [0, 0.25, 0.5, 0.75, 1].map(ratio => {
        const y = padT + ratio * usableH;
        const value = max - ratio * range;
        return { y, value };
    });

    container.innerHTML = `
        <svg class="chart-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Tendencia vs media móvil 3M">
            ${yTicks.map(t => `
                <line x1="${padL}" y1="${t.y.toFixed(2)}" x2="${width - padR}" y2="${t.y.toFixed(2)}" stroke="#e5e7eb" stroke-width="1"></line>
                <text x="${(padL - 8).toFixed(2)}" y="${(t.y + 3).toFixed(2)}" fill="#64748b" font-size="10" text-anchor="end">${formatTrm(t.value)}</text>
            `).join("")}
            <line x1="${padL}" y1="${padT}" x2="${padL}" y2="${height - padB}" stroke="#64748b" stroke-width="1.2"></line>
            <line x1="${padL}" y1="${height - padB}" x2="${width - padR}" y2="${height - padB}" stroke="#64748b" stroke-width="1.2"></line>
            <polyline points="${avgPts}" fill="none" stroke="#0f766e" stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round"></polyline>
            <polyline points="${maPts}" fill="none" stroke="#b45309" stroke-width="2.2" stroke-dasharray="5 4" stroke-linejoin="round" stroke-linecap="round"></polyline>
            ${series.map((row, i) => {
                if (i % 6 !== 0 && i !== series.length - 1) return "";
                return `<text x="${xFor(i).toFixed(2)}" y="${height - 10}" fill="#64748b" font-size="10" text-anchor="middle">${row.period}</text>`;
            }).join("")}
            <text x="${padL}" y="${padT - 4}" fill="#0f766e" font-size="11">● Promedio</text>
            <text x="${padL + 120}" y="${padT - 4}" fill="#b45309" font-size="11">● Media móvil 3M</text>
        </svg>
    `;
}

function renderVisualVolatility(series) {
    const container = document.getElementById("visualVolatilityChart");
    if (!container) return;

    const rows = series.filter(row => row.changeAbs !== null && row.changeAbs !== undefined);
    if (!rows.length) {
        container.innerHTML = '<div class="meta">Sin datos de variación para calcular volatilidad.</div>';
        return;
    }

    const width = 980;
    const height = 280;
    const padL = 48;
    const padR = 20;
    const padT = 18;
    const padB = 40;
    const usableW = width - padL - padR;
    const usableH = height - padT - padB;
    const values = rows.map(row => Math.abs(Number(row.changeAbs)));
    const maxVal = Math.max(...values) || 1;
    const barW = Math.max(4, (usableW / values.length) * 0.72);
    const yTicks = [0, 0.25, 0.5, 0.75, 1].map(ratio => {
        const y = padT + ratio * usableH;
        const value = maxVal - ratio * maxVal;
        return { y, value };
    });

    container.innerHTML = `
        <svg class="chart-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Volatilidad mensual absoluta">
            ${yTicks.map(t => `
                <line x1="${padL}" y1="${t.y.toFixed(2)}" x2="${width - padR}" y2="${t.y.toFixed(2)}" stroke="#e5e7eb" stroke-width="1"></line>
                <text x="${(padL - 8).toFixed(2)}" y="${(t.y + 3).toFixed(2)}" fill="#64748b" font-size="10" text-anchor="end">${formatTrm(t.value)}</text>
            `).join("")}
            <line x1="${padL}" y1="${padT}" x2="${padL}" y2="${height - padB}" stroke="#64748b" stroke-width="1.2"></line>
            <line x1="${padL}" y1="${height - padB}" x2="${width - padR}" y2="${height - padB}" stroke="#64748b" stroke-width="1.2"></line>
            ${values.map((value, i) => {
                const slotW = usableW / values.length;
                const x = padL + i * slotW + (slotW - barW) / 2;
                const h = (value / maxVal) * usableH;
                const y = padT + usableH - h;
                return `<rect x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${barW.toFixed(2)}" height="${h.toFixed(2)}" rx="2" fill="#2563eb"><title>${rows[i].period}: ${formatTrm(value)}</title></rect>`;
            }).join("")}
            ${rows.map((row, i) => {
                if (i % 6 !== 0 && i !== rows.length - 1) return "";
                const x = padL + (i * usableW) / rows.length + (usableW / rows.length) / 2;
                return `<text x="${x.toFixed(2)}" y="${height - 10}" fill="#64748b" font-size="10" text-anchor="middle">${row.period}</text>`;
            }).join("")}
        </svg>
    `;
}

function renderVisualDistribution(series) {
    const container = document.getElementById("visualDistributionChart");
    if (!container) return;

    const values = series.map(row => Number(row.avg));
    if (values.length < 2) {
        container.innerHTML = '<div class="meta">Datos insuficientes para distribución.</div>';
        return;
    }

    const bins = 10;
    const width = 980;
    const height = 280;
    const padL = 48;
    const padR = 20;
    const padT = 18;
    const padB = 40;
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    const step = range / bins;
    const counts = Array.from({ length: bins }, () => 0);
    values.forEach(v => {
        let idx = Math.floor((v - min) / step);
        if (!Number.isFinite(idx)) idx = 0;
        if (idx >= bins) idx = bins - 1;
        if (idx < 0) idx = 0;
        counts[idx] += 1;
    });

    const usableW = width - padL - padR;
    const usableH = height - padT - padB;
    const maxCount = Math.max(...counts) || 1;
    const barW = Math.max(6, (usableW / bins) * 0.78);
    const yTicks = [0, 0.25, 0.5, 0.75, 1].map(ratio => {
        const y = padT + ratio * usableH;
        const value = Math.round(maxCount - ratio * maxCount);
        return { y, value };
    });

    container.innerHTML = `
        <svg class="chart-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Distribución de promedios">
            ${yTicks.map(t => `
                <line x1="${padL}" y1="${t.y.toFixed(2)}" x2="${width - padR}" y2="${t.y.toFixed(2)}" stroke="#e5e7eb" stroke-width="1"></line>
                <text x="${(padL - 8).toFixed(2)}" y="${(t.y + 3).toFixed(2)}" fill="#64748b" font-size="10" text-anchor="end">${t.value}</text>
            `).join("")}
            <line x1="${padL}" y1="${padT}" x2="${padL}" y2="${height - padB}" stroke="#64748b" stroke-width="1.2"></line>
            <line x1="${padL}" y1="${height - padB}" x2="${width - padR}" y2="${height - padB}" stroke="#64748b" stroke-width="1.2"></line>
            ${counts.map((count, i) => {
                const slotW = usableW / bins;
                const x = padL + i * slotW + (slotW - barW) / 2;
                const h = (count / maxCount) * usableH;
                const y = padT + usableH - h;
                const startBucket = min + i * step;
                const endBucket = startBucket + step;
                return `<rect x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${barW.toFixed(2)}" height="${h.toFixed(2)}" rx="2" fill="#7c3aed"><title>${formatTrm(startBucket)} - ${formatTrm(endBucket)}: ${count}</title></rect>`;
            }).join("")}
            <text x="${padL}" y="${height - 10}" fill="#64748b" font-size="10">${formatTrm(min)}</text>
            <text x="${width - padR - 70}" y="${height - 10}" fill="#64748b" font-size="10">${formatTrm(max)}</text>
        </svg>
    `;
}

function renderVisualSeasonality(series) {
    const container = document.getElementById("visualSeasonalityChart");
    if (!container) return;

    if (!series.length) {
        container.innerHTML = '<div class="meta">Sin datos para estacionalidad.</div>';
        return;
    }

    const monthNames = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
    const buckets = Array.from({ length: 12 }, () => []);
    series.forEach(row => {
        const month = Number(String(row.period).slice(5, 7));
        if (month >= 1 && month <= 12) {
            buckets[month - 1].push(Number(row.avg));
        }
    });

    const monthAvg = buckets.map(vals => vals.length ? average(vals) : 0);
    if (!monthAvg.some(v => v > 0)) {
        container.innerHTML = '<div class="meta">Sin datos válidos para estacionalidad.</div>';
        return;
    }

    const width = 980;
    const height = 280;
    const padL = 48;
    const padR = 20;
    const padT = 18;
    const padB = 40;
    const usableW = width - padL - padR;
    const usableH = height - padT - padB;
    const min = Math.min(...monthAvg);
    const max = Math.max(...monthAvg);
    const range = max - min || 1;
    const barW = Math.max(8, (usableW / 12) * 0.72);
    const yTicks = [0, 0.25, 0.5, 0.75, 1].map(ratio => {
        const y = padT + ratio * usableH;
        const value = max - ratio * range;
        return { y, value };
    });

    container.innerHTML = `
        <svg class="chart-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Estacionalidad mensual">
            ${yTicks.map(t => `
                <line x1="${padL}" y1="${t.y.toFixed(2)}" x2="${width - padR}" y2="${t.y.toFixed(2)}" stroke="#e5e7eb" stroke-width="1"></line>
                <text x="${(padL - 8).toFixed(2)}" y="${(t.y + 3).toFixed(2)}" fill="#64748b" font-size="10" text-anchor="end">${formatTrm(t.value)}</text>
            `).join("")}
            <line x1="${padL}" y1="${padT}" x2="${padL}" y2="${height - padB}" stroke="#64748b" stroke-width="1.2"></line>
            <line x1="${padL}" y1="${height - padB}" x2="${width - padR}" y2="${height - padB}" stroke="#64748b" stroke-width="1.2"></line>
            ${monthAvg.map((value, i) => {
                const slotW = usableW / 12;
                const x = padL + i * slotW + (slotW - barW) / 2;
                const h = ((value - min) / range) * usableH;
                const y = padT + usableH - h;
                return `<rect x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${barW.toFixed(2)}" height="${h.toFixed(2)}" rx="2" fill="#0ea5e9"><title>${monthNames[i]}: ${formatTrm(value)}</title></rect>`;
            }).join("")}
            ${monthNames.map((name, i) => {
                const x = padL + (i + 0.5) * (usableW / 12);
                return `<text x="${x.toFixed(2)}" y="${height - 10}" fill="#64748b" font-size="10" text-anchor="middle">${name}</text>`;
            }).join("")}
        </svg>
    `;
}

function renderVisualExtraCharts(series) {
    renderVisualTrendVsMa(series);
    renderVisualVolatility(series);
    renderVisualDistribution(series);
    renderVisualSeasonality(series);
}

let visualSeriesState = [];

function applyVisualFilters() {
    const filters = readVisualFilters();
    let series = [...visualSeriesState];

    if (filters.startDate) {
        series = series.filter(row => row.date >= filters.startDate);
    }
    if (filters.endDate) {
        series = series.filter(row => row.date <= filters.endDate);
    }

    renderVisualStats(series);
    renderVisualTable(series);
    renderVisualChart(series, filters.metric);
    renderVisualExtraCharts(series);
}

function resetVisualFilters() {
    const metricSelect = document.getElementById("visualMetricSelect");
    const quickWindow = document.getElementById("visualQuickWindow");
    if (metricSelect) metricSelect.value = "avg";
    if (quickWindow) quickWindow.value = "36";
    applyQuickWindow(visualSeriesState, 36);
    applyVisualFilters();
}

function initDataPage() {
    const applyBtn = document.getElementById("applyDataFiltersBtn");
    const resetBtn = document.getElementById("resetDataFiltersBtn");
    const limit = document.getElementById("dataFilterLimit");

    if (applyBtn) applyBtn.addEventListener("click", applyDataFilters);
    if (resetBtn) {
        resetBtn.addEventListener("click", () => {
            ["dataFilterStartDate", "dataFilterEndDate", "dataFilterMinTrm", "dataFilterMaxTrm"].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.value = "";
            });
            if (limit) limit.value = "200";
            applyDataFilters();
        });
    }
    if (limit) limit.addEventListener("change", applyDataFilters);

    loadData();
}

function initEdaPage() {
    const allBtn = document.getElementById("showEdaAllBtn");
    const m36Btn = document.getElementById("showEda36mBtn");
    const allPanel = document.getElementById("edaViewAll");
    const m36Panel = document.getElementById("edaView36m");
    const applyBtn = document.getElementById("applyEdaFiltersBtn");
    const resetBtn = document.getElementById("resetEdaFiltersBtn");

    const setEdaView = (view) => {
        const isAll = view === "all";

        if (allPanel) allPanel.classList.toggle("is-hidden", !isAll);
        if (m36Panel) m36Panel.classList.toggle("is-hidden", isAll);

        if (allBtn) {
            allBtn.classList.toggle("is-active", isAll);
            allBtn.setAttribute("aria-selected", isAll ? "true" : "false");
        }
        if (m36Btn) {
            m36Btn.classList.toggle("is-active", !isAll);
            m36Btn.setAttribute("aria-selected", !isAll ? "true" : "false");
        }
    };

    if (allBtn) allBtn.addEventListener("click", () => setEdaView("all"));
    if (m36Btn) m36Btn.addEventListener("click", () => setEdaView("36m"));
    setEdaView("all");

    if (applyBtn) applyBtn.addEventListener("click", () => applyEdaFilters(false));
    if (resetBtn) {
        resetBtn.addEventListener("click", () => {
            ["edaFilterStartDate", "edaFilterEndDate"].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.value = "";
            });
            const monthly = document.getElementById("edaMonthlyWindow");
            if (monthly) monthly.value = "6";
            applyEdaFilters(false);
        });
    }

    loadEda();
}

function initVisualizationsPage() {
    visualSeriesState = buildVisualState(window.initialVisualSeries || []);
    applyQuickWindow(visualSeriesState, 36);

    const applyBtn = document.getElementById("applyVisualFiltersBtn");
    const resetBtn = document.getElementById("resetVisualFiltersBtn");
    const quickWindow = document.getElementById("visualQuickWindow");
    const metricSelect = document.getElementById("visualMetricSelect");
    const startInput = document.getElementById("visualFilterStartDate");
    const endInput = document.getElementById("visualFilterEndDate");

    if (applyBtn) applyBtn.addEventListener("click", applyVisualFilters);
    if (resetBtn) resetBtn.addEventListener("click", resetVisualFilters);
    if (metricSelect) metricSelect.addEventListener("change", applyVisualFilters);
    if (startInput) startInput.addEventListener("change", applyVisualFilters);
    if (endInput) endInput.addEventListener("change", applyVisualFilters);
    if (quickWindow) {
        quickWindow.addEventListener("change", () => {
            applyQuickWindow(visualSeriesState, Number(quickWindow.value));
            applyVisualFilters();
        });
    }

    applyVisualFilters();
}

function initPredictionPage() {
    const allBtn = document.getElementById("predictionScopeAllBtn");
    const m36Btn = document.getElementById("predictionScope36mBtn");

    if (allBtn) allBtn.addEventListener("click", () => setPredictionScope("all_data"));
    if (m36Btn) m36Btn.addEventListener("click", () => setPredictionScope("last_36_months"));

    updatePredictionScopeButtons("all_data");
}

window.getPrediction = getPrediction;
window.loadData = loadData;
window.loadEda = loadEda;

const currentPage = document.querySelector("main.page-container")?.dataset?.page;
if (currentPage === "data") initDataPage();
if (currentPage === "eda") initEdaPage();
if (currentPage === "visualizations") initVisualizationsPage();
if (currentPage === "prediction") initPredictionPage();
