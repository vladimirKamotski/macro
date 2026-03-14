
// Tab Switching
function switchTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));

    document.getElementById(tabId + '-tab').classList.add('active');
    // Find button containing text
    const btns = Array.from(document.querySelectorAll('.tab-btn'));
    const btn = btns.find(b => b.innerText.toLowerCase().includes(tabId.split('-')[0]));
    if (btn) btn.classList.add('active');
}

document.addEventListener('DOMContentLoaded', () => {
    const calculateBtn = document.getElementById('calculate-btn');
    const loading = document.getElementById('loading');
    const results = document.getElementById('results');

    // Result elements
    const resPrice = document.getElementById('res-price');
    const resVol = document.getElementById('res-vol');
    const resAtm = document.getElementById('res-atm');
    const resStrike = document.getElementById('res-strike');
    const resVega = document.getElementById('res-vega');
    const resGamma = document.getElementById('res-gamma');
    const resModelVega = document.getElementById('res-model-vega');

    // Inputs
    const strikeTypeSelect = document.getElementById('strike-type');
    const strikeInput = document.getElementById('strike');
    const strikeLabel = document.getElementById('strike-label');
    const strike2Group = document.getElementById('strike-2-group');
    const strike2Input = document.getElementById('strike_2');
    const typeSelect = document.getElementById('type');

    function updateUI() {
        if (!typeSelect || !strikeTypeSelect || !strikeLabel || !strikeInput || !strike2Group) return;

        const isStrangle = typeSelect.value === 'strangle';
        const isRR = typeSelect.value === 'risk_reversal';
        const isMultiLeg = isStrangle || isRR;
        const isDelta = strikeTypeSelect.value === 'delta';

        if (isDelta) {
            strikeLabel.textContent = isMultiLeg ? 'Delta (e.g. 0.25)' : 'Strike Delta (e.g. 0.25)';
            strikeInput.step = '0.01';
            strike2Group.classList.add('hidden'); // Delta Strangle uses single input
            if (parseFloat(strikeInput.value) > 1) strikeInput.value = '0.25'; // Reset if needed
        } else {
            if (isMultiLeg) {
                strikeLabel.textContent = 'Put Strike (Low)';
            } else {
                strikeLabel.textContent = 'Strike Price';
            }
            strikeInput.step = '0.0001';

            if (isMultiLeg) {
                strike2Group.classList.remove('hidden');
            } else {
                strike2Group.classList.add('hidden');
            }
        }
    }

    if (strikeTypeSelect) strikeTypeSelect.addEventListener('change', updateUI);
    if (typeSelect) typeSelect.addEventListener('change', updateUI);

    // Init
    updateUI();

    calculateBtn.addEventListener('click', async () => {
        // Collect inputs
        const data = {
            spot_ref: document.getElementById('spot_ref').value,
            rd: document.getElementById('rd').value,
            forward: document.getElementById('forward').value,
            T: document.getElementById('T').value,
            atm: document.getElementById('atm').value,
            rr25: document.getElementById('rr25').value,
            st25: document.getElementById('st25').value,
            rr10: document.getElementById('rr10').value,
            st10: document.getElementById('st10').value,
            strike: strikeInput.value,
            strike_2: strike2Input.value,
            strike_type: strikeTypeSelect.value,
            type: document.getElementById('type').value
        };

        // UI State
        calculateBtn.disabled = true;
        loading.classList.remove('hidden');
        results.classList.add('hidden');

        try {
            const response = await fetch('/calculate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (result.success) {
                resPrice.textContent = result.price.toFixed(6);
                resVol.textContent = (result.vol * 100).toFixed(4) + '%';
                resAtm.textContent = result.atm_strike.toFixed(6);

                // Greeks
                resVega.textContent = result.vega ? result.vega.toFixed(4) : '--';
                resGamma.textContent = result.gamma ? result.gamma.toFixed(6) : '--';

                // Model Vega
                if (result.model_vega) {
                    const mv = result.model_vega;
                    let html = '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem;">';
                    for (const [key, val] of Object.entries(mv)) {
                        html += `<div><span style="font-weight:600;">${key}:</span> ${val.toFixed(4)}</div>`;
                    }
                    html += '</div>';
                    resModelVega.innerHTML = html;
                } else {
                    resModelVega.textContent = '--';
                }

                let usedStr = result.strike_used.toFixed(6);
                if (result.strike_2_used) {
                    usedStr += ' / ' + result.strike_2_used.toFixed(6);
                }
                resStrike.textContent = usedStr;

                results.classList.remove('hidden');

                // Render Chart
                if (result.plot_data) {
                    renderChart(result.plot_data);
                }
            } else {
                alert('Error: ' + result.message);
            }

        } catch (error) {
            console.error('Error:', error);
            alert('An unexpected error occurred.');
        } finally {
            calculateBtn.disabled = false;
            loading.classList.add('hidden');
        }
    });

    let volChart = null;
    let payoffChart = null;

    function renderChart(data) {
        renderVolChart(data);
        renderPayoffChart(data);
    }

    function renderVolChart(data) {
        const ctx = document.getElementById('volChart').getContext('2d');

        if (volChart) {
            volChart.destroy();
        }

        // Combine curve data
        const curvePoints = data.curve_x.map((x, i) => ({ x: x, y: data.curve_y[i] }));

        // Combine knot points
        const knotPoints = data.points_x.map((x, i) => ({ x: x, y: data.points_y[i] }));

        volChart = new Chart(ctx, {
            type: 'scatter',
            data: {
                datasets: [
                    {
                        label: 'Volatility Surface',
                        data: curvePoints,
                        showLine: true,
                        borderColor: '#38bdf8', /* matched to --primary */
                        backgroundColor: 'rgba(56, 189, 248, 0.05)',
                        borderWidth: 3,
                        pointRadius: 0,
                        tension: 0.4 /* smooth curve */
                    },
                    {
                        label: 'Market Quotes',
                        data: knotPoints,
                        backgroundColor: '#818cf8', /* matched to --secondary */
                        borderColor: '#ffffff',
                        borderWidth: 2,
                        pointRadius: 6,
                        pointHoverRadius: 9
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: function (context) {
                                if (context.datasetIndex === 1) {
                                    // Knot labels
                                    const index = context.dataIndex;
                                    const label = data.point_labels[index] || '';
                                    return `${label}: K=${context.raw.x.toFixed(4)}, Vol=${(context.raw.y * 100).toFixed(2)}%`;
                                }
                                return `K=${context.raw.x.toFixed(4)}, Vol=${(context.raw.y * 100).toFixed(2)}%`;
                            }
                        }
                    },
                    legend: {
                        labels: { color: '#94a3b8' }
                    }
                },
                scales: {
                    x: {
                        type: 'linear',
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#94a3b8', font: { family: 'Outfit' } },
                        title: { display: true, text: 'Strike Price', color: '#94a3b8' }
                    },
                    y: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: {
                            color: '#94a3b8',
                            font: { family: 'Outfit' },
                            callback: function (value) { return (value * 100).toFixed(1) + '%'; }
                        },
                        title: { display: true, text: 'Volatility', color: '#94a3b8' }
                    }
                },
                plugins: {
                    legend: { labels: { color: '#f8fafc', font: { family: 'Outfit', weight: '600' } } }
                }
            }
        });
    }

    function renderPayoffChart(data) {
        const ctx = document.getElementById('payoffChart').getContext('2d');

        if (payoffChart) {
            payoffChart.destroy();
        }

        if (!data.payoff_y) return;

        // Combine curve data
        // payoff_x is spot_range (which was curve_x in python)
        const curvePoints = data.payoff_x.map((x, i) => ({ x: x, y: data.payoff_y[i] }));

        payoffChart = new Chart(ctx, {
            type: 'line',
            data: {
                datasets: [
                    {
                        label: 'Maturity Payoff',
                        data: curvePoints,
                        borderColor: '#2dd4bf', /* matched to --accent */
                        backgroundColor: 'rgba(45, 212, 191, 0.1)',
                        borderWidth: 3,
                        pointRadius: 0,
                        fill: true,
                        tension: 0.1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        type: 'linear',
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#94a3b8', font: { family: 'Outfit' } },
                        title: { display: true, text: 'Asset Price at Maturity', color: '#94a3b8' }
                    },
                    y: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#94a3b8', font: { family: 'Outfit' } },
                        title: { display: true, text: 'Payoff Value', color: '#94a3b8' }
                    }
                },
                plugins: {
                    legend: { labels: { color: '#f8fafc', font: { family: 'Outfit', weight: '600' } } }
                }
            }
        });
    }

    // Hedge Optimization
    const optimizeBtn = document.getElementById('optimize-btn');
    if (optimizeBtn) {
        optimizeBtn.addEventListener('click', async () => {
            const btn = optimizeBtn;
            const originalText = btn.innerText;
            btn.innerText = 'Optimizing...';
            btn.disabled = true;

            try {
                const data = {
                    // Market
                    spot: document.getElementById('spot_ref').value,
                    rd: document.getElementById('rd').value,
                    forward: document.getElementById('forward').value,
                    T: document.getElementById('T').value,
                    // Surface
                    atm: document.getElementById('atm').value,
                    rr25: document.getElementById('rr25').value,
                    st25: document.getElementById('st25').value,
                    rr10: document.getElementById('rr10').value,
                    st10: document.getElementById('st10').value,
                    // Risk & Spreads
                    risk_profile: {
                        atm: parseFloat(document.getElementById('risk-atm').value) || 0,
                        rr25: parseFloat(document.getElementById('risk-rr25').value) || 0,
                        st25: parseFloat(document.getElementById('risk-st25').value) || 0,
                        rr10: parseFloat(document.getElementById('risk-rr10').value) || 0,
                        st10: parseFloat(document.getElementById('risk-st10').value) || 0
                    },
                    spreads: [
                        parseFloat(document.getElementById('spread-atm').value) || 0,
                        parseFloat(document.getElementById('spread-rr25').value) || 0,
                        parseFloat(document.getElementById('spread-st25').value) || 0,
                        parseFloat(document.getElementById('spread-rr10').value) || 0,
                        parseFloat(document.getElementById('spread-st10').value) || 0
                    ]
                };

                const response = await fetch('/optimize_hedge', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });

                const result = await response.json();

                if (result.success) {
                    displayHedgeResults(result);
                } else {
                    alert('Error: ' + result.message);
                }

            } catch (error) {
                console.error(error);
                alert('An error occurred during optimization.');
            } finally {
                btn.innerText = originalText;
                btn.disabled = false;
            }
        });
    }
});

function displayHedgeResults(result) {
    const summary = document.getElementById('hedge-summary');
    const totalCostEl = document.getElementById('total-cost');

    // Param mapping (Backend uses lowercase/short names)
    const paramMap = {
        'ATM': 'atm',
        '25d RR': 'rr25',
        '25d ST': 'st25',
        '10d RR': 'rr10',
        '10d ST': 'st10'
    };

    const paramOrder = ['atm', 'rr25', 'st25', 'rr10', 'st10'];

    // Update Trades and Costs
    result.trades.forEach(trade => {
        const idSuffix = paramMap[trade.instrument];
        if (!idSuffix) return;

        const tradeEl = document.getElementById('trade-' + idSuffix);
        const costEl = document.getElementById('cost-' + idSuffix);

        if (tradeEl) {
            tradeEl.textContent = trade.size.toFixed(2);
            tradeEl.className = 'res-cell res-trade ' + (trade.size > 0 ? 'text-success' : (trade.size < 0 ? 'text-danger' : ''));
        }
        if (costEl) {
            costEl.textContent = '$' + trade.cost.toFixed(2);
        }
    });

    // Update Residual Risk
    if (result.residual_risk) {
        result.residual_risk.forEach((val, idx) => {
            const param = paramOrder[idx];
            const residEl = document.getElementById('resid-' + param);
            if (residEl) {
                residEl.textContent = val.toExponential(2);
                // Highlight if significant (though solver should make it near 0)
                residEl.style.color = Math.abs(val) > 1e-6 ? 'var(--warning)' : 'var(--text-secondary)';
            }
        });
    }

    summary.style.display = 'block';
    totalCostEl.textContent = '$' + result.total_cost.toFixed(2);
}
