const trmFormatter = new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
});

function formatTrm(value) {
    const numericValue = Number(value);
    if (Number.isNaN(numericValue)) {
        return value;
    }
    return `$${trmFormatter.format(numericValue)}`;
}

function getPrediction() {
    const resultEl = document.getElementById("result");
    if (!resultEl) return;

    fetch("/predict")
        .then(res => res.json())
        .then(data => {
            resultEl.innerText = JSON.stringify(data, null, 2);
        })
        .catch(err => {
            resultEl.innerText = "Error obteniendo predicción: " + err;
        });
}

function loadData() {
    const tableBody = document.getElementById("dataTableBody");
    const dataMeta = document.getElementById("dataMeta");
    if (!tableBody || !dataMeta) return;

    fetch("/data")
        .then(res => res.json())
        .then(payload => {
            const rows = payload.data || [];

            dataMeta.innerText = `Total de registros cargados: ${payload.count}`;

            if (rows.length === 0) {
                tableBody.innerHTML = '<tr><td colspan="2" class="meta">No se encontraron datos.</td></tr>';
                return;
            }

            const preview = rows.slice(-200).reverse();
            tableBody.innerHTML = preview
                .map(row => `<tr><td>${row.date}</td><td>${formatTrm(row.trm)}</td></tr>`)
                .join("");
        })
        .catch(err => {
            document.getElementById("dataMeta").innerText = "Error cargando datos: " + err;
        });
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
            cv_pct: `${(d.cv || 0).toFixed(2)}%`,
        },
        outliers: {
            count: o.count,
            ratio_pct: `${(o.ratio_pct || 0).toFixed(2)}%`,
            lower_bound: formatTrm(o.lower_bound),
            upper_bound: formatTrm(o.upper_bound),
        },
        trend: {
            direction: t.direction,
            absolute_change: formatTrm(t.absolute_change),
            percent_change: `${(t.percent_change || 0).toFixed(2)}%`,
            slope_per_step: Number(t.slope_per_step || 0).toFixed(6),
        },
        volatility: {
            avg_abs_daily_change: formatTrm(v.avg_abs_daily_change),
            max_up_day: formatTrm(v.max_up_day),
            max_down_day: formatTrm(v.max_down_day),
        },
        monthly_summary: (eda.monthly_summary || []).slice(-6),
        yearly_summary: eda.yearly_summary || [],
    };
}

function renderSparkline(values) {
    const container = document.getElementById("edaSparkline");
    if (!container) return;

    if (!values || values.length < 2) {
        container.innerHTML = '<span class="meta">Datos insuficientes para gráfica.</span>';
        return;
    }

    const width = 640;
    const height = 130;
    const pad = 12;
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;

    const points = values.map((v, i) => {
        const x = pad + (i * (width - pad * 2)) / (values.length - 1);
        const y = pad + ((max - v) * (height - pad * 2)) / range;
        return `${x.toFixed(2)},${y.toFixed(2)}`;
    }).join(" ");

    const last = values[values.length - 1];
    const lastX = pad + (width - pad * 2);
    const lastY = pad + ((max - last) * (height - pad * 2)) / range;

    container.innerHTML = `
        <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" class="sparkline-svg" role="img" aria-label="Tendencia mensual TRM">
            <polyline fill="none" stroke="#2563eb" stroke-width="3" points="${points}" />
            <circle cx="${lastX}" cy="${lastY}" r="4" fill="#1d4ed8" />
        </svg>
    `;
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
    if (!stats || !summary) {
        return;
    }

    const descriptive = summary.descriptive || {};
    const trend = summary.trend || {};
    const outliers = summary.outliers || {};

    const latest = summary.latest || {};

    stats.innerHTML = `
        <div class="stat-item">
            <span class="stat-label">Media</span>
            <strong class="stat-value">${descriptive.mean ?? "-"}</strong>
        </div>
        <div class="stat-item">
            <span class="stat-label">Desv. estándar</span>
            <strong class="stat-value">${descriptive.std ?? "-"}</strong>
        </div>
        <div class="stat-item">
            <span class="stat-label">Tendencia</span>
            <strong class="stat-value">${trend.direction ?? "-"}</strong>
        </div>
        <div class="stat-item">
            <span class="stat-label">Outliers</span>
            <strong class="stat-value">${outliers.count ?? "-"}</strong>
        </div>
        <div class="stat-item">
            <span class="stat-label">Último valor</span>
            <strong class="stat-value">${latest.value ?? "-"}</strong>
        </div>
        <div class="stat-item">
            <span class="stat-label">Cambio %</span>
            <strong class="stat-value">${trend.percent_change ?? "-"}</strong>
        </div>
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
    if (trendMeta) {
        trendMeta.innerText = `Dirección: ${trend.direction ?? "-"} · Cambio: ${trend.percent_change ?? "-"}`;
    }
}

function loadEda(scrollToPanel = false) {
    const edaMeta = document.getElementById("edaMeta");
    const edaResult = document.getElementById("edaResult");
    const edaCard = document.getElementById("edaCard");
    if (!edaMeta || !edaResult || !edaCard) return;

    if (edaMeta) {
        edaMeta.innerText = "Cargando EDA...";
    }
    if (edaCard) {
        edaCard.classList.add("loading");
    }

    fetch("/eda")
        .then(res => {
            if (!res.ok) {
                throw new Error(`HTTP ${res.status}`);
            }
            return res.json();
        })
        .then(eda => {
            const meta = eda.meta || {};
            edaMeta.innerText =
                `Rango: ${meta.start_date} a ${meta.end_date} · Registros: ${meta.count}`;

            const summary = summarizeEda(eda);
            renderEdaStats(summary);
            renderLatest(summary);
            renderSummaryTables(summary);

            const chartValues = (summary.monthly_summary || []).map(m => Number(m.avg));
            renderSparkline(chartValues);
            edaResult.innerText = JSON.stringify(summary, null, 2);

            if (scrollToPanel && edaCard) {
                edaCard.scrollIntoView({ behavior: "smooth", block: "start" });
            }
        })
        .catch(err => {
            edaMeta.innerText = "Error cargando EDA: " + err;
            edaResult.innerText =
                "No se pudo actualizar el EDA desde /eda.\n" +
                "Mostrando el resumen inicial cargado en servidor (si está disponible).";
        })
        .finally(() => {
            if (edaCard) {
                edaCard.classList.remove("loading");
            }
        });
}

window.getPrediction = getPrediction;
window.loadData = loadData;
window.loadEda = loadEda;

const currentPage = document.querySelector("main.page-container")?.dataset?.page;

if (currentPage === "data") {
    loadData();
}

if (currentPage === "eda") {
    loadEda();
}
