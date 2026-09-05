let stackedChartInstance = null;
let statusDonutInstance = null;
let cumulativeCurveInstance = null;
let currentSelectedOrder = null;
let currentOrderAuditData = null;
let currentLanguage = 'en';
let searchDebounceTimer = null;

// Format currency
function formatINR(val) {
    return '₹' + Number(val || 0).toLocaleString('en-IN');
}

// Format date time
function formatDate(isoStr) {
    if (!isoStr) return '-';
    const d = new Date(isoStr);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

// Format failure reason labels
function formatReason(reason) {
    const map = {
        'insufficient_funds': 'Insufficient Funds',
        'card_declined': 'Card Declined',
        'otp_timeout': 'OTP Timeout',
        'network_timeout': 'Network Timeout',
        'bank_server_down': 'Bank Server Down',
        'invalid_cvv': 'Invalid CVV',
        'mandate_expired': 'Mandate Expired',
        'user_input_error': 'User Input Error'
    };
    return map[reason] || reason;
}

// Status Badges (High Contrast Theme)
function getStatusBadge(status) {
    const map = {
        'recovered': '<span class="px-2.5 py-1 rounded-md bg-emerald-100 text-emerald-950 border border-emerald-400 font-extrabold flex items-center gap-1.5 w-fit text-xs shadow-2xs"><span class="w-2 h-2 rounded-full bg-emerald-600"></span>Recovered</span>',
        'retrying': '<span class="px-2.5 py-1 rounded-md bg-amber-100 text-amber-950 border border-amber-400 font-extrabold flex items-center gap-1.5 w-fit text-xs shadow-2xs"><span class="w-2 h-2 rounded-full bg-amber-600"></span>Retrying</span>',
        'stopped': '<span class="px-2.5 py-1 rounded-md bg-rose-100 text-rose-950 border border-rose-400 font-extrabold flex items-center gap-1.5 w-fit text-xs shadow-2xs"><span class="w-2 h-2 rounded-full bg-rose-600"></span>Stopped</span>',
        'abandoned': '<span class="px-2.5 py-1 rounded-md bg-slate-200 text-slate-900 border border-slate-400 font-extrabold flex items-center gap-1.5 w-fit text-xs shadow-2xs"><span class="w-2 h-2 rounded-full bg-slate-600"></span>Abandoned</span>',
        'detected': '<span class="px-2.5 py-1 rounded-md bg-blue-100 text-blue-950 border border-blue-400 font-extrabold w-fit text-xs shadow-2xs">Detected</span>',
        'diagnosed': '<span class="px-2.5 py-1 rounded-md bg-purple-100 text-purple-950 border border-purple-400 font-extrabold w-fit text-xs shadow-2xs">Diagnosed</span>'
    };
    return map[status] || `<span class="px-2.5 py-1 rounded-md bg-slate-100 text-slate-900 border border-slate-300 font-extrabold text-xs">${status}</span>`;
}

// Confidence Badge
function getConfidenceBadge(conf) {
    const val = Number(conf || 0.95);
    let colorClass = 'text-emerald-950 bg-emerald-100 border-emerald-400';
    if (val < 0.85) {
        colorClass = 'text-amber-950 bg-amber-100 border-amber-400';
    } else if (val < 0.93) {
        colorClass = 'text-indigo-950 bg-indigo-100 border-indigo-400';
    }
    return `<span class="px-2.5 py-0.5 rounded font-mono text-xs font-black border ${colorClass}">${(val * 100).toFixed(1)}%</span>`;
}

// Switch Navigation Tabs
function switchTab(tabId) {
    const tabs = ['command', 'analytics', 'compliance', 'audit'];
    tabs.forEach(t => {
        const btn = document.getElementById(`tab-${t}`);
        const content = document.getElementById(`tabContent-${t}`);
        if (!btn || !content) return;
        if (t === tabId) {
            btn.className = 'tab-btn active px-4 py-2.5 border-b-2 border-emerald-600 transition flex items-center gap-2 text-emerald-900 font-extrabold bg-emerald-50';
            content.classList.remove('hidden');
        } else {
            btn.className = 'tab-btn px-4 py-2.5 border-b-2 border-transparent transition flex items-center gap-2 text-slate-700 hover:text-slate-950 font-bold';
            content.classList.add('hidden');
        }
    });

    if (tabId === 'analytics') {
        loadMetrics();
    } else if (tabId === 'audit') {
        loadAuditRawPreview();
    }
}

// Load Metrics and Charts
async function loadMetrics() {
    try {
        const res = await fetch('/api/metrics');
        const data = await res.json();

        // 1. KPI Cards
        const kpiRisk = document.getElementById('kpiRevenueRisk');
        if (kpiRisk) kpiRisk.innerText = formatINR(data.total_revenue_at_risk);
        
        const kpiOrders = document.getElementById('kpiTotalOrders');
        if (kpiOrders) kpiOrders.innerText = data.total_transactions;
        
        const kpiWon = document.getElementById('kpiRecoveredAmount');
        if (kpiWon) kpiWon.innerText = formatINR(data.total_recovered);
        
        const kpiCount = document.getElementById('kpiRecoveredCount');
        if (kpiCount) kpiCount.innerText = data.recovered_count;
        
        const kpiRate = document.getElementById('kpiRecoveryRate');
        if (kpiRate) kpiRate.innerText = data.recovery_rate_pct + '%';
        
        const kpiStop = document.getElementById('kpiStoppedCount');
        if (kpiStop) kpiStop.innerText = data.stopped_count;
        
        const tabBadge = document.getElementById('stoppedBadgeTab');
        if (tabBadge) tabBadge.innerText = data.stopped_count;

        // 2. Financial ROI Metrics
        if (data.financial_roi) {
            const roi = data.financial_roi;
            const kpiRoi = document.getElementById('kpiRoiMultiplier');
            if (kpiRoi) kpiRoi.innerText = roi.roi_multiplier + 'x';
            
            const kpiOut = document.getElementById('kpiOutreachCost');
            if (kpiOut) kpiOut.innerText = formatINR(roi.total_outreach_cost);
            
            const kpiNet = document.getElementById('kpiNetRecovered');
            if (kpiNet) kpiNet.innerText = formatINR(roi.net_recovered);
            
            const kpiCost = document.getElementById('kpiCostPerRecovery');
            if (kpiCost) kpiCost.innerText = '₹' + roi.cost_per_recovery;
        }

        // 3. Guardrail Enforced Rate
        const stoppedPct = data.total_transactions > 0 ? ((data.stopped_count / data.total_transactions) * 100).toFixed(1) : '0.0';
        const guardPct = document.getElementById('guardrailEnforcedPct');
        if (guardPct) guardPct.innerText = stoppedPct + '%';
        
        const guardSub = document.getElementById('kpiStoppedSubtitle');
        if (guardSub) guardSub.innerText = `${stoppedPct}% halted safely`;

        if (data.system_info && data.system_info.razorpay_mode) {
            const modeBadge = document.getElementById('systemModeBadge');
            if (modeBadge) modeBadge.innerText = data.system_info.razorpay_mode;
        }

        // 4. Render Visual Charts
        renderStackedReasonsChart(data.reason_breakdown || []);
        renderStatusDonutChart(data.status_summary || {});
        renderCumulativeCurveChart(data.cumulative_timeline || []);
        renderPaymentMethodBreakdown(data.payment_method_breakdown || []);
        renderExceptionsBreakdown(data.stopped_breakdown || {}, data.stopped_count || 0);

    } catch (err) {
        console.error('Failed to load metrics:', err);
    }
}

// Render Stacked Reasons Chart
function renderStackedReasonsChart(breakdown) {
    const canvas = document.getElementById('stackedReasonsChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    const labels = breakdown.map(b => formatReason(b.reason));
    const recoveredData = breakdown.map(b => b.recovered || 0);
    const retryingData = breakdown.map(b => b.retrying || 0);
    const stoppedData = breakdown.map(b => b.stopped || 0);
    const abandonedData = breakdown.map(b => b.abandoned || 0);

    if (stackedChartInstance) {
        stackedChartInstance.destroy();
    }

    stackedChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Recovered (Won Back)',
                    data: recoveredData,
                    backgroundColor: '#10b981',
                    borderRadius: 4
                },
                {
                    label: 'Retrying (Active Link)',
                    data: retryingData,
                    backgroundColor: '#6366f1',
                    borderRadius: 4
                },
                {
                    label: 'Stopped (Guardrails)',
                    data: stoppedData,
                    backgroundColor: '#f59e0b',
                    borderRadius: 4
                },
                {
                    label: 'Abandoned (Max Cap)',
                    data: abandonedData,
                    backgroundColor: '#f43f5e',
                    borderRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: { color: '#0f172a', font: { size: 11, family: 'Plus Jakarta Sans', weight: 'bold' }, boxWidth: 12 }
                }
            },
            scales: {
                x: {
                    stacked: true,
                    grid: { display: false },
                    ticks: { color: '#1e293b', font: { size: 11, weight: '600' } }
                },
                y: {
                    stacked: true,
                    beginAtZero: true,
                    grid: { color: '#e2e8f0' },
                    ticks: { color: '#1e293b', font: { size: 11, weight: '600' }, precision: 0 }
                }
            }
        }
    });
}

// Render Donut Chart
function renderStatusDonutChart(statusSummary) {
    const canvas = document.getElementById('statusDonutChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    const recCount = statusSummary.recovered ? Number(statusSummary.recovered.count || 0) : 0;
    const retryCount = statusSummary.retrying ? Number(statusSummary.retrying.count || 0) : 0;
    const stopCount = statusSummary.stopped ? Number(statusSummary.stopped.count || 0) : 0;
    const abanCount = statusSummary.abandoned ? Number(statusSummary.abandoned.count || 0) : 0;
    const total = recCount + retryCount + stopCount + abanCount;

    if (statusDonutInstance) {
        statusDonutInstance.destroy();
    }

    const chartData = total > 0 ? [recCount, retryCount, stopCount, abanCount] : [1, 0, 0, 0];
    const chartColors = total > 0 ? ['#10b981', '#6366f1', '#f59e0b', '#f43f5e'] : ['#e2e8f0'];

    statusDonutInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Recovered', 'Retrying', 'Stopped (Rules)', 'Abandoned'],
            datasets: [{
                data: chartData,
                backgroundColor: chartColors,
                borderWidth: 3,
                borderColor: '#ffffff',
                hoverOffset: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '70%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#475569', font: { size: 10, family: 'Plus Jakarta Sans' }, boxWidth: 10 }
                }
            }
        }
    });
}

// Render Cumulative Recovery Timeline Curve
function renderCumulativeCurveChart(timeline) {
    const canvas = document.getElementById('cumulativeCurveChart');
    if (!canvas || !timeline.length) return;
    const ctx = canvas.getContext('2d');

    const labels = timeline.map(t => `#${t.transaction_index}`);
    const recoveredCurve = timeline.map(t => t.cumulative_recovered);
    const riskCurve = timeline.map(t => t.cumulative_risk);

    const maxRecovered = recoveredCurve[recoveredCurve.length - 1] || 0;
    const wonBackLabel = document.getElementById('chartTotalWonBack');
    if (wonBackLabel) wonBackLabel.innerText = formatINR(maxRecovered) + ' won back';

    if (cumulativeCurveInstance) {
        cumulativeCurveInstance.destroy();
    }

    cumulativeCurveInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Cumulative Won Back (₹)',
                    data: recoveredCurve,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.08)',
                    fill: true,
                    tension: 0.35,
                    pointRadius: 2.5,
                    pointBackgroundColor: '#10b981'
                },
                {
                    label: 'Cumulative Revenue at Risk (₹)',
                    data: riskCurve,
                    borderColor: '#cbd5e1',
                    borderDash: [4, 4],
                    fill: false,
                    tension: 0.2,
                    pointRadius: 0
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: { color: '#0f172a', font: { size: 11, family: 'Plus Jakarta Sans', weight: 'bold' }, boxWidth: 12 }
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { color: '#1e293b', font: { size: 11, weight: '600' } }
                },
                y: {
                    grid: { color: '#e2e8f0' },
                    ticks: {
                        color: '#1e293b',
                        font: { size: 11, weight: '600' },
                        callback: v => '₹' + (v >= 1000 ? (v / 1000).toFixed(0) + 'k' : v)
                    }
                }
            }
        }
    });
}

// Render Payment Method Breakdown
function renderPaymentMethodBreakdown(methods) {
    const container = document.getElementById('paymentMethodStatsContainer');
    if (!container) return;

    if (!methods || methods.length === 0) {
        container.innerHTML = '<div class="text-xs text-slate-700 font-bold">No payment method metrics available.</div>';
        return;
    }

    let html = '';
    methods.forEach(m => {
        const rate = m.recovery_rate || 0;
        const color = rate >= 50 ? 'bg-emerald-600' : (rate >= 35 ? 'bg-indigo-600' : 'bg-amber-600');
        html += `
            <div class="p-3.5 rounded-xl bg-slate-50 border border-slate-300 space-y-2">
                <div class="flex items-center justify-between text-xs">
                    <span class="font-black text-slate-950">${m.method}</span>
                    <span class="font-mono text-emerald-800 font-black">${rate}% recovery</span>
                </div>
                <div class="w-full bg-slate-200 h-2.5 rounded-full overflow-hidden border border-slate-300">
                    <div class="${color} h-full rounded-full" style="width: ${rate}%"></div>
                </div>
                <div class="flex justify-between text-xs text-slate-700 font-mono font-bold">
                    <span>${m.recovered_count} won of ${m.total_count} orders</span>
                    <span class="font-black text-slate-950">${formatINR(m.recovered_amount)} won back</span>
                </div>
            </div>
        `;
    });
    container.innerHTML = html;
}

// Render Exceptions Breakdown
function renderExceptionsBreakdown(stoppedSummary, totalStopped) {
    const container = document.getElementById('exceptionsCardsContainer');
    if (!container) return;

    const maxAttemptsCount = stoppedSummary.max_attempts_reached ? stoppedSummary.max_attempts_reached.count : 0;
    const cooldownCount = stoppedSummary.cooldown_active ? stoppedSummary.cooldown_active.count : 0;
    const p2pCount = stoppedSummary.promise_to_pay_active ? stoppedSummary.promise_to_pay_active.count : 0;

    container.innerHTML = `
        <div class="p-4 rounded-xl bg-white border border-slate-300 shadow-sm space-y-2">
            <div class="flex items-center justify-between text-xs">
                <span class="text-amber-900 font-black flex items-center gap-1.5">
                    <i data-lucide="shield-alert" class="w-4 h-4 text-amber-600"></i>
                    Max Attempts Reached
                </span>
                <span class="px-2.5 py-0.5 rounded bg-amber-100 text-amber-950 font-mono font-black border border-amber-300">${maxAttemptsCount}</span>
            </div>
            <p class="text-xs text-slate-700 font-medium">Enforced strictly when attempts exceed 3. Halts further SMS/email communications permanently to protect brand integrity.</p>
            <div class="text-xs text-slate-600 font-mono font-bold">Policy: RZP-COMPLIANCE-301</div>
        </div>

        <div class="p-4 rounded-xl bg-white border border-slate-300 shadow-sm space-y-2">
            <div class="flex items-center justify-between text-xs">
                <span class="text-indigo-900 font-black flex items-center gap-1.5">
                    <i data-lucide="clock" class="w-4 h-4 text-indigo-600"></i>
                    Active 24h Cooldown
                </span>
                <span class="px-2.5 py-0.5 rounded bg-indigo-100 text-indigo-950 font-mono font-black border border-indigo-300">${cooldownCount}</span>
            </div>
            <p class="text-xs text-slate-700 font-medium">Mandates minimum 24-hour spacing between non-transient outreach attempts. Holds retries in queue until expiration.</p>
            <div class="text-xs text-slate-600 font-mono font-bold">Policy: RZP-COMPLIANCE-24H</div>
        </div>

        <div class="p-4 rounded-xl bg-white border border-slate-300 shadow-sm space-y-2">
            <div class="flex items-center justify-between text-xs">
                <span class="text-emerald-900 font-black flex items-center gap-1.5">
                    <i data-lucide="calendar" class="w-4 h-4 text-emerald-700"></i>
                    Promise-to-Pay Safe Pause
                </span>
                <span class="px-2.5 py-0.5 rounded bg-emerald-100 text-emerald-950 font-mono font-black border border-emerald-300">${p2pCount}</span>
            </div>
            <p class="text-xs text-slate-700 font-medium">When customers request delaying payment (e.g. salary cycle), all automated notifications pause until the agreed date.</p>
            <div class="text-xs text-slate-600 font-mono font-bold">Policy: RZP-PROMISE-P2P</div>
        </div>
    `;
    lucide.createIcons();
}

// Search with Debounce
function handleSearch() {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
        loadTransactions();
    }, 250);
}

// Reset Filters
function resetFilters() {
    document.getElementById('searchInput').value = '';
    document.getElementById('statusFilter').value = '';
    document.getElementById('reasonFilter').value = '';
    loadTransactions();
}

// Load Transactions Table
async function loadTransactions() {
    const status = document.getElementById('statusFilter')?.value || '';
    const reason = document.getElementById('reasonFilter')?.value || '';
    const search = document.getElementById('searchInput')?.value.trim() || '';

    let url = '/api/transactions?limit=100';
    if (status) url += `&status=${encodeURIComponent(status)}`;
    if (reason) url += `&reason=${encodeURIComponent(reason)}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;

    try {
        const res = await fetch(url);
        const data = await res.json();
        const transactions = data.transactions || [];

        const badge = document.getElementById('tableCountBadge');
        if (badge) badge.innerText = `${transactions.length} records`;

        const tbody = document.getElementById('transactionsTbody');
        if (!transactions.length) {
            tbody.innerHTML = '<tr><td colspan="9" class="text-center py-10 text-slate-400 font-medium">No matching failed payment records found.</td></tr>';
            return;
        }

        let html = '';
        let stoppedRowsHtml = '';

        transactions.forEach(t => {
            const shortId = t.order_id.length > 18 ? t.order_id.substring(0, 16) + '...' : t.order_id;
            const actionText = (t.recovery_action || 'new_payment_link').replace(/_/g, ' ');
            const inlineMsg = t.sms_preview || 'Payment link dispatched to customer.';
            const isRecovered = t.status === 'recovered';
            const isStopped = t.status === 'stopped';

            html += `
            <tr class="hover:bg-emerald-50/50 transition cursor-pointer border-b border-slate-200 group bg-white" onclick="openAuditModal('${t.order_id}')">
                <td class="py-3.5 px-3.5 font-mono text-emerald-800 font-extrabold text-xs tracking-tight">${shortId}</td>
                <td class="py-3.5 px-3.5">
                    <div class="font-extrabold text-slate-950 text-sm" style="color: #020617 !important;">${t.customer_name || 'Customer'}</div>
                    <div class="text-xs text-slate-700 font-mono font-bold mt-0.5" style="color: #334155 !important;">${t.customer_phone || ''}</div>
                </td>
                <td class="py-3.5 px-3.5 text-right font-mono font-black text-slate-950 text-sm" style="color: #020617 !important;">${formatINR(t.amount)}</td>
                <td class="py-3.5 px-3.5">
                    <div class="font-bold text-slate-950 text-xs" style="color: #020617 !important;">${formatReason(t.diagnosed_reason || t.raw_error_code)}</div>
                    <div class="text-xs text-slate-800 font-mono font-bold mt-0.5" style="color: #1e293b !important;">${t.payment_sub_method || t.payment_method || 'card'}</div>
                </td>
                <td class="py-3.5 px-3.5">
                    ${getConfidenceBadge(t.confidence)}
                </td>
                <td class="py-3.5 px-3.5">
                    <div class="text-xs text-slate-950 font-black capitalize" style="color: #020617 !important;">${actionText}</div>
                    <div class="text-xs text-slate-800 mt-1 italic max-w-xs group-hover:text-emerald-950 transition font-medium line-clamp-1" style="color: #1e293b !important;" title="${inlineMsg}">
                        "${inlineMsg}"
                    </div>
                </td>
                <td class="py-3.5 px-3.5">${getStatusBadge(t.status)}</td>
                <td class="py-3.5 px-3.5 text-center font-mono">
                    <span class="px-2 py-0.5 rounded text-xs font-black ${t.attempt_count >= 3 ? 'bg-rose-100 text-rose-950 border border-rose-400' : 'bg-slate-100 text-slate-900 border border-slate-300'}">
                        ${t.attempt_count}/3
                    </span>
                </td>
                <td class="py-3.5 px-3.5 text-right">
                    <div class="flex items-center justify-end gap-1.5">
                        ${!isRecovered && !isStopped ? `
                            <button onclick="event.stopPropagation(); triggerRazorpayCheckout('${t.order_id}')" class="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-black flex items-center gap-1.5 shadow-sm transition active:scale-95" title="Pay with Razorpay (QR / Card / UPI)">
                                <svg class="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24"><path d="M22.43 0l-12.01 14.28h6.29l5.72-14.28zm-10.43 12.38l-4.14 4.93h4.94l3.19-4.93h-3.99zm-4.72 5.62l-4.28 6h5.05l3.24-6h-4.01z"/></svg>
                                <span>Pay</span>
                            </button>
                        ` : (isRecovered ? `
                            <span class="px-2.5 py-1 rounded-md bg-emerald-100 text-emerald-950 text-xs font-black border border-emerald-400">Paid</span>
                        ` : '')}
                        <button onclick="event.stopPropagation(); openAuditModal('${t.order_id}')" class="px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-900 text-xs font-extrabold border border-slate-300 transition shadow-2xs">
                            Audit
                        </button>
                    </div>
                </td>
            </tr>
            `;

            if (isStopped) {
                stoppedRowsHtml += `
                <tr class="hover:bg-slate-50 transition cursor-pointer border-b border-slate-200 bg-white" onclick="openAuditModal('${t.order_id}')">
                    <td class="py-3 px-3.5 font-mono text-amber-800 font-extrabold text-xs">${shortId}</td>
                    <td class="py-3 px-3.5 font-bold text-slate-950 text-xs">${t.customer_name}</td>
                    <td class="py-3 px-3.5 font-mono font-black text-slate-950 text-xs">${formatINR(t.amount)}</td>
                    <td class="py-3 px-3.5">
                        <span class="px-2 py-0.5 rounded bg-amber-100 text-amber-950 border border-amber-400 font-mono text-xs font-extrabold">
                            ${t.stopped_reason || 'cooldown_active'}
                        </span>
                    </td>
                    <td class="py-3 px-3.5 font-mono text-center font-black text-slate-900 text-xs">${t.attempt_count}/3</td>
                    <td class="py-3 px-3.5 text-slate-900 font-semibold text-xs">${t.stopped_reason === 'max_attempts_reached' ? 'Permanently Halted (Max 3 Attempts Enforced)' : 'Blocked (24h Cooldown Active)'}</td>
                    <td class="py-3 px-3.5 text-right">
                        <button onclick="event.stopPropagation(); openAuditModal('${t.order_id}')" class="px-3 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-900 text-xs font-bold border border-slate-300">Audit</button>
                    </td>
                </tr>
                `;
            }
        });

        tbody.innerHTML = html;

        const stoppedTbody = document.getElementById('stoppedTbody');
        if (stoppedTbody) {
            stoppedTbody.innerHTML = stoppedRowsHtml || '<tr><td colspan="7" class="text-center py-8 text-slate-400">No active stopped cases found.</td></tr>';
        }

        lucide.createIcons();

    } catch (err) {
        console.error('Failed to load transactions:', err);
    }
}

// Launch Official Razorpay Checkout Modal
async function triggerRazorpayCheckout(orderId) {
    try {
        const res = await fetch(`/api/pay/${orderId}/create-order`, { method: 'POST' });
        const orderData = await res.json();
        
        if (!orderData.success) {
            alert('Failed to initiate Razorpay checkout: ' + (orderData.error || 'Server error'));
            return;
        }

        const options = {
            key: orderData.key_id,
            amount: orderData.amount,
            currency: orderData.currency,
            name: "Razorpay Revenue Recovery",
            description: `Payment for Order ${orderId}`,
            image: "https://razorpay.com/favicon.ico",
            order_id: orderData.order_id,
            prefill: {
                name: orderData.customer_name,
                email: orderData.customer_email,
                contact: orderData.customer_phone
            },
            theme: {
                color: "#0c66e4"
            },
            handler: async function (response) {
                try {
                    await fetch(`/api/pay/${orderId}/verify-razorpay`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            razorpay_payment_id: response.razorpay_payment_id,
                            razorpay_order_id: response.razorpay_order_id,
                            razorpay_signature: response.razorpay_signature
                        })
                    });
                    alert(`Payment Successful via Razorpay! Reference ID: ${response.razorpay_payment_id}. Order marked RECOVERED.`);
                    await loadDashboard();
                    if (currentSelectedOrder === orderId) {
                        await openAuditModal(orderId);
                    }
                } catch (err) {
                    alert('Payment received! Updating status...');
                    await loadDashboard();
                }
            },
            modal: {
                ondismiss: function () {
                    console.log('Razorpay modal closed');
                }
            }
        };

        const rzp = new Razorpay(options);
        rzp.on('payment.failed', function (response) {
            alert('Payment authorization failed: ' + response.error.description);
        });
        rzp.open();
    } catch (err) {
        alert('Could not open Razorpay Checkout: ' + err.message);
    }
}

// Run 75-Payment Batch Simulation
async function runBatch(count = 75) {
    const btn = document.getElementById('batchRunBtn');
    const banner = document.getElementById('loadingBanner');
    
    btn.disabled = true;
    btn.classList.add('opacity-50', 'cursor-not-allowed');
    banner.classList.remove('hidden');

    try {
        const res = await fetch('/api/batch/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ count: count })
        });
        await res.json();
        await loadDashboard();
    } catch (err) {
        alert('Failed to execute batch run: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.classList.remove('opacity-50', 'cursor-not-allowed');
        banner.classList.add('hidden');
    }
}

// Reset Database
async function resetData() {
    if (!confirm('Reset all failed payments, recovery actions, and audit trails?')) return;
    try {
        await fetch('/api/batch/reset', { method: 'POST' });
        await loadDashboard();
    } catch (err) {
        alert('Reset failed: ' + err.message);
    }
}

// Open Audit Modal
async function openAuditModal(orderId) {
    currentSelectedOrder = orderId;
    document.getElementById('modalOrderId').innerText = orderId;
    document.getElementById('auditModal').classList.remove('hidden');

    try {
        const res = await fetch(`/api/transactions/${orderId}/audit`);
        const data = await res.json();
        currentOrderAuditData = data;
        renderModalContent(data);
    } catch (err) {
        alert('Failed to load audit trail: ' + err.message);
    }
}

function closeAuditModal() {
    document.getElementById('auditModal').classList.add('hidden');
    currentSelectedOrder = null;
    currentOrderAuditData = null;
}

// Language toggle in audit modal
function setAuditLanguage(lang) {
    currentLanguage = lang;
    const enBtn = document.getElementById('langEnBtn');
    const hiBtn = document.getElementById('langHiBtn');
    if (lang === 'en') {
        enBtn.className = 'px-2 py-0.5 rounded-md bg-white text-slate-900 shadow-xs font-bold';
        hiBtn.className = 'px-2 py-0.5 rounded-md text-slate-500 font-bold';
    } else {
        hiBtn.className = 'px-2 py-0.5 rounded-md bg-white text-slate-900 shadow-xs font-bold';
        enBtn.className = 'px-2 py-0.5 rounded-md text-slate-500 font-bold';
    }
    if (currentOrderAuditData) {
        renderModalContent(currentOrderAuditData);
    }
}

// Render Modal Content
function renderModalContent(data) {
    const payment = data.payment || {};
    const audit = data.audit || { steps: [] };
    const isPaid = payment.status === 'recovered';

    // Summary Box
    const summaryBox = document.getElementById('modalSummaryBox');
    summaryBox.innerHTML = `
        <div class="p-3 rounded-lg bg-white border border-slate-300 shadow-2xs">
            <span class="text-slate-600 block text-[11px] uppercase font-bold tracking-wider">Customer</span>
            <span class="font-black text-slate-950 text-sm block mt-0.5">${payment.customer_name || 'Customer'}</span>
            <span class="text-xs text-slate-700 block font-mono font-bold mt-0.5">${payment.customer_phone || ''}</span>
        </div>
        <div class="p-3 rounded-lg bg-white border border-slate-300 shadow-2xs">
            <span class="text-slate-600 block text-[11px] uppercase font-bold tracking-wider">Amount & Rail</span>
            <span class="font-black text-slate-950 font-mono text-base block mt-0.5">${formatINR(payment.amount)}</span>
            <span class="text-xs text-slate-800 font-bold block mt-0.5 uppercase">${payment.payment_sub_method || payment.payment_method || 'card'}</span>
        </div>
        <div class="p-3 rounded-lg bg-white border border-slate-300 shadow-2xs">
            <span class="text-slate-600 block text-[11px] uppercase font-bold tracking-wider">Current Status</span>
            <div class="mt-1">${getStatusBadge(payment.status)}</div>
        </div>
        <div class="p-3 rounded-lg bg-white border border-slate-300 shadow-2xs">
            <span class="text-slate-600 block text-[11px] uppercase font-bold tracking-wider">Recovery Actions</span>
            <div class="flex items-center gap-2 mt-1 flex-wrap">
                ${!isPaid ? `
                    <button onclick="triggerRazorpayCheckout('${payment.order_id}')" class="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-black text-xs flex items-center gap-1.5 shadow-sm transition">
                        <svg class="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24"><path d="M22.43 0l-12.01 14.28h6.29l5.72-14.28zm-10.43 12.38l-4.14 4.93h4.94l3.19-4.93h-3.99zm-4.72 5.62l-4.28 6h5.05l3.24-6h-4.01z"/></svg>
                        <span>Razorpay Modal</span>
                    </button>
                ` : `
                    <span class="px-2.5 py-1 rounded bg-emerald-100 text-emerald-950 text-xs font-black border border-emerald-400">Paid</span>
                `}
                <a href="/pay/${payment.order_id}" target="_blank" class="px-2.5 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-900 font-bold text-xs border border-slate-300 flex items-center gap-1">
                    Checkout Page <i data-lucide="external-link" class="w-3 h-3"></i>
                </a>
            </div>
        </div>
    `;

    // Timeline Steps
    const timeline = document.getElementById('modalTimeline');
    let timelineHtml = '';

    audit.steps.forEach((step, idx) => {
        const stage = step.stage;
        const d = step.data || {};
        let stageTitle = '';
        let badgeColor = 'bg-emerald-600';
        let bodyHtml = '';

        if (stage === 'detected') {
            stageTitle = '1. DETECTOR: Payment Failure Captured';
            badgeColor = 'bg-rose-600';
            bodyHtml = `
                <div class="text-slate-900 space-y-1.5">
                    <div><span class="text-slate-700 font-bold">Raw Gateway Error:</span> <code class="font-mono text-rose-950 bg-rose-100 px-2 py-1 rounded border border-rose-400 font-black text-xs">${d.raw_error_code || 'ERROR'}</code></div>
                    <div class="text-slate-800 font-semibold text-xs">${d.raw_error_desc || 'Declined during gateway authorization.'}</div>
                </div>
            `;
        } else if (stage === 'diagnosed') {
            stageTitle = '2. DIAGNOSER: Root Cause & Confidence';
            badgeColor = 'bg-indigo-600';
            bodyHtml = `
                <div class="text-slate-900 space-y-1">
                    <div class="flex items-center gap-2 flex-wrap">
                        <span class="text-slate-700 font-bold">Classified Reason:</span>
                        <span class="font-black text-slate-950 text-sm">${formatReason(d.reason_category)}</span>
                        ${getConfidenceBadge(d.confidence)}
                        <span class="text-xs text-slate-800 font-mono font-bold bg-slate-100 px-2.5 py-0.5 rounded border border-slate-300">Signal: ${d.diagnostic_signal || 'Deterministic'}</span>
                    </div>
                </div>
            `;
        } else if (stage === 'action_chosen') {
            stageTitle = '3. STRATEGY ENGINE: Action & Channel Selected';
            badgeColor = 'bg-purple-600';
            bodyHtml = `
                <div class="text-slate-900 space-y-1.5">
                    <div class="flex items-center gap-2 flex-wrap text-xs">
                        <span class="text-slate-700 font-bold">Action:</span> <span class="font-black text-purple-950 bg-purple-100 px-2.5 py-0.5 rounded border border-purple-400">${d.action}</span>
                        <span class="text-slate-400">&bull;</span>
                        <span class="text-slate-700 font-bold">Channel:</span> <span class="text-slate-950 font-black">${d.channel}</span>
                        <span class="text-slate-400">&bull;</span>
                        <span class="text-slate-700 font-bold">Delay:</span> <span class="text-slate-950 font-mono font-black">+${d.timing_hours || 0}h</span>
                    </div>
                    <div class="text-slate-900 bg-white p-3 rounded-lg border border-slate-300 text-xs shadow-2xs">
                        <span class="text-purple-950 font-black block mb-1">Strategic Rationale:</span> ${d.reasoning}
                    </div>
                </div>
            `;
        } else if (stage === 'stopped') {
            stageTitle = 'STOPPING RULE ENFORCED: Compliance Protection';
            badgeColor = 'bg-amber-600';
            bodyHtml = `
                <div class="p-3.5 rounded-lg bg-amber-50 border-2 border-amber-400 text-amber-950 space-y-2">
                    <div class="font-black flex items-center gap-2 text-amber-950 text-xs">
                        <i data-lucide="shield-alert" class="w-4 h-4 text-amber-600"></i>
                        <span>Outreach Safely Halted: ${d.reason}</span>
                    </div>
                    <div class="text-slate-900 font-mono text-xs bg-white p-2.5 rounded border border-amber-300 font-semibold">
                        ${d.detail}
                    </div>
                    <div class="flex items-center justify-between text-xs text-amber-950 font-mono pt-1 border-t border-amber-300 font-bold">
                        <span>Policy Code: ${d.policy_code || 'RZP-COMPLIANCE-24H'}</span>
                        <span>Next Allowed: ${d.next_allowed_contact || 'None'}</span>
                    </div>
                </div>
            `;
        } else if (stage === 'executed') {
            stageTitle = '4. EXECUTOR: Payment Link & Outreach Dispatched';
            badgeColor = 'bg-blue-600';
            const customerFirstName = payment.customer_name ? payment.customer_name.split(' ')[0] : 'there';
            const previewMsg = currentLanguage === 'hi' ? 
                `Namaste ${customerFirstName}, aapka ₹${payment.amount} ka order safe hai. Yahan click karke payment complete karein: ${d.payment_link}` :
                (d.message_dispatched || 'Outreach dispatched.');

            bodyHtml = `
                <div class="text-slate-900 space-y-2">
                    <div class="flex items-center justify-between text-xs flex-wrap gap-2">
                        <div><span class="text-slate-700 font-bold">Channel:</span> ${d.channel} &bull; <span class="text-slate-700 font-bold">Mode:</span> <span class="text-blue-900 font-mono font-black">${d.link_mode || 'Razorpay Test API'}</span></div>
                        <div class="flex items-center gap-2">
                            ${!isPaid ? `
                                <button onclick="triggerRazorpayCheckout('${payment.order_id}')" class="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-black flex items-center gap-1.5 shadow-sm transition">
                                    <svg class="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24"><path d="M22.43 0l-12.01 14.28h6.29l5.72-14.28zm-10.43 12.38l-4.14 4.93h4.94l3.19-4.93h-3.99zm-4.72 5.62l-4.28 6h5.05l3.24-6h-4.01z"/></svg>
                                    <span>Pay with Razorpay</span>
                                </button>
                            ` : ''}
                            <a href="/pay/${payment.order_id}" target="_blank" class="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-900 rounded-lg text-xs font-bold border border-slate-300 flex items-center gap-1">
                                Open Checkout Page <i data-lucide="external-link" class="w-3 h-3"></i>
                            </a>
                        </div>
                    </div>
                    <div class="p-3 rounded-lg bg-emerald-50 border border-emerald-400 text-emerald-950">
                        <div class="text-xs uppercase font-black text-emerald-950 mb-1 flex items-center justify-between">
                            <span class="flex items-center gap-1.5"><i data-lucide="message-square" class="w-3.5 h-3.5 text-emerald-700"></i> Personalized Copy (${currentLanguage.toUpperCase()})</span>
                            <span class="text-slate-700 font-mono text-xs font-bold">${previewMsg.length}/160 chars</span>
                        </div>
                        <div class="italic text-xs font-bold text-slate-950">"${previewMsg}"</div>
                    </div>
                </div>
            `;
        } else if (stage === 'tracked') {
            const isRec = d.outcome === 'recovered';
            stageTitle = isRec ? '5. TRACKER: Payment Successfully Recovered!' : '5. TRACKER: Outcome Updated';
            badgeColor = isRec ? 'bg-emerald-600' : 'bg-slate-600';
            bodyHtml = `
                <div class="text-slate-900 space-y-1">
                    <div class="flex items-center gap-2">
                        <span class="text-slate-700 font-bold">Final Outcome:</span>
                        <span class="font-black text-sm ${isRec ? 'text-emerald-800' : 'text-slate-800'}">${d.outcome.toUpperCase()}</span>
                        ${isRec ? `<span class="px-2.5 py-1 rounded bg-emerald-100 text-emerald-950 font-mono font-black border border-emerald-400 text-xs">+₹${d.amount_recovered} won back</span>` : ''}
                    </div>
                    <div class="text-slate-800 text-xs font-semibold mt-1">${d.detail || ''}</div>
                </div>
            `;
        }

        timelineHtml += `
            <div class="relative pl-8">
                <div class="absolute left-1.5 top-2 w-3.5 h-3.5 rounded-full ${badgeColor} border-2 border-white shadow-xs"></div>
                <div class="p-3.5 rounded-xl bg-slate-50 border border-slate-300 space-y-1.5">
                    <div class="flex items-center justify-between">
                        <h4 class="text-xs font-black text-slate-950">${stageTitle}</h4>
                        <span class="text-xs text-slate-700 font-mono font-bold">${formatDate(step.timestamp)}</span>
                    </div>
                    ${bodyHtml}
                </div>
            </div>
        `;
    });

    timeline.innerHTML = timelineHtml;
    lucide.createIcons();
}

// Live Replay Decision
async function replayDecision() {
    if (!currentSelectedOrder) return;
    const btn = document.getElementById('modalReplayBtn');
    btn.disabled = true;
    btn.innerHTML = `<div class="w-3 h-3 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin"></div> Replaying...`;

    try {
        const res = await fetch(`/api/transactions/${currentSelectedOrder}/replay`, { method: 'POST' });
        const data = await res.json();
        currentOrderAuditData = { payment: data.payment, audit: data.audit_trail };
        renderModalContent(currentOrderAuditData);
        await loadDashboard();
    } catch (err) {
        alert('Replay failed: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i data-lucide="repeat" class="w-3.5 h-3.5"></i> <span>Replay</span>`;
        lucide.createIcons();
    }
}

// Promise-to-Pay Safe Pause
async function triggerPromiseToPay() {
    if (!currentSelectedOrder || !currentOrderAuditData) return;
    const defaultDate = new Date(Date.now() + 3 * 86400000).toISOString().split('T')[0];
    const promised = prompt('Enter customer promised payment date (YYYY-MM-DD):', defaultDate);
    if (!promised) return;

    try {
        const res = await fetch('/api/promise-to-pay', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                order_id: currentSelectedOrder,
                customer_name: currentOrderAuditData.payment.customer_name,
                promised_date: promised,
                notes: 'Customer promised payment after salary credit.'
            })
        });
        await res.json();
        alert(`Promise-to-pay saved until ${promised}. Automated outreach paused safely per compliance rules.`);
        await openAuditModal(currentSelectedOrder);
        await loadDashboard();
    } catch (err) {
        alert('Failed to log promise to pay: ' + err.message);
    }
}

// Simulate Single Webhook Failure
function openSimulateModal() {
    document.getElementById('simulateModal').classList.remove('hidden');
}

function closeSimulateModal() {
    document.getElementById('simulateModal').classList.add('hidden');
}

async function submitSimulateWebhook(e) {
    e.preventDefault();
    const name = document.getElementById('simName').value.trim();
    const amount = parseFloat(document.getElementById('simAmount').value);
    const reason = document.getElementById('simReason').value;
    const method = document.getElementById('simMethod').value;
    const attempts = parseInt(document.getElementById('simAttemptCount').value);

    try {
        const res = await fetch('/api/simulate/webhook', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                customer_name: name,
                amount: amount,
                failure_reason_raw: reason,
                payment_method: method,
                attempt_count: attempts
            })
        });
        const data = await res.json();
        closeSimulateModal();
        await loadDashboard();
        if (data.payment && data.payment.order_id) {
            openAuditModal(data.payment.order_id);
        }
    } catch (err) {
        alert('Simulation failed: ' + err.message);
    }
}

// Load Raw Audit Preview
async function loadAuditRawPreview() {
    const box = document.getElementById('auditJsonSnippet');
    if (!box) return;
    try {
        const res = await fetch('/api/export/audit-json');
        const data = await res.json();
        box.innerText = JSON.stringify(data.slice(-15), null, 2);
    } catch (err) {
        box.innerText = 'Failed to load audit logs preview: ' + err.message;
    }
}

// Quick test payment
async function quickPayTest(orderId) {
    try {
        const res = await fetch(`/api/pay/${orderId}/complete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ method: 'quick_action' })
        });
        const data = await res.json();
        alert(`Test payment successful for order ${orderId}! Status updated to RECOVERED.`);
        await openAuditModal(orderId);
        await loadDashboard();
    } catch (err) {
        alert('Payment failed: ' + err.message);
    }
}

// Razorpay API Keys Configuration Modal
async function openApiKeysModal() {
    const modal = document.getElementById('apiKeysModal');
    const alertBox = document.getElementById('keyStatusAlert');
    alertBox.classList.add('hidden');
    
    try {
        const res = await fetch('/api/settings/razorpay');
        const data = await res.json();
        if (data.has_keys) {
            document.getElementById('razorpayKeyId').placeholder = `Active: ${data.key_id_masked}`;
        }
    } catch (e) {}
    
    modal.classList.remove('hidden');
    lucide.createIcons();
}

function closeApiKeysModal() {
    document.getElementById('apiKeysModal').classList.add('hidden');
}

async function saveApiKeys(event) {
    event.preventDefault();
    const btn = document.getElementById('saveKeysBtn');
    const alertBox = document.getElementById('keyStatusAlert');
    const keyId = document.getElementById('razorpayKeyId').value.trim();
    const keySecret = document.getElementById('razorpayKeySecret').value.trim();
    const webhookSecret = document.getElementById('razorpayWebhookSecret').value.trim();

    btn.disabled = true;
    btn.innerHTML = `<div class="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></div> Testing Keys...`;
    alertBox.className = 'p-2.5 rounded-lg text-xs';

    try {
        const res = await fetch('/api/settings/razorpay', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key_id: keyId, key_secret: keySecret, webhook_secret: webhookSecret })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Failed to authenticate Razorpay keys');

        alertBox.classList.remove('hidden');
        alertBox.classList.add('bg-emerald-50', 'border', 'border-emerald-200', 'text-emerald-800');
        alertBox.innerText = 'Razorpay Test Keys validated successfully! System active in Live Test API mode.';
        
        await loadDashboard();
        setTimeout(() => {
            closeApiKeysModal();
            btn.disabled = false;
            btn.innerHTML = `<i data-lucide="check" class="w-3.5 h-3.5"></i> Save & Test Keys`;
            lucide.createIcons();
        }, 1200);
    } catch (err) {
        alertBox.classList.remove('hidden');
        alertBox.classList.add('bg-rose-50', 'border', 'border-rose-200', 'text-rose-800');
        alertBox.innerText = err.message;
        btn.disabled = false;
        btn.innerHTML = `<i data-lucide="check" class="w-3.5 h-3.5"></i> Save & Test Keys`;
        lucide.createIcons();
    }
}

async function disconnectApiKeys() {
    if (!confirm('Switch back to offline Interactive Sandbox Simulation?')) return;
    try {
        await fetch('/api/settings/razorpay', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key_id: '', key_secret: '' })
        });
        document.getElementById('razorpayKeyId').value = '';
        document.getElementById('razorpayKeySecret').value = '';
        document.getElementById('razorpayKeyId').placeholder = 'rzp_test_xxxxxxxxxxxxxx';
        closeApiKeysModal();
        await loadDashboard();
    } catch (err) {
        alert('Disconnect failed: ' + err.message);
    }
}

// Global dashboard loader
async function loadDashboard() {
    await Promise.all([loadMetrics(), loadTransactions()]);
}

window.addEventListener('DOMContentLoaded', () => {
    loadDashboard();
    setInterval(loadDashboard, 20000);
});
