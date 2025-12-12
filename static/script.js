
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
    const resModelVega = document.getElementById('res-model-vega');

    // Inputs
    const strikeTypeSelect = document.getElementById('strike-type');
    const strikeInput = document.getElementById('strike');
    const strikeLabel = document.getElementById('strike-label');
    const strike2Group = document.getElementById('strike-2-group');
    const strike2Input = document.getElementById('strike_2');
    const typeSelect = document.getElementById('type');

    function updateUI() {
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

    strikeTypeSelect.addEventListener('change', updateUI);
    typeSelect.addEventListener('change', updateUI);

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

                // Vega
                resVega.textContent = result.vega ? result.vega.toFixed(4) : '--';

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
                        label: 'Vol Surface',
                        data: curvePoints,
                        showLine: true,
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        borderWidth: 2,
                        pointRadius: 0
                    },
                    {
                        label: 'Quotes',
                        data: knotPoints,
                        backgroundColor: '#8b5cf6',
                        pointRadius: 6,
                        pointHoverRadius: 8
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
                        position: 'bottom',
                        title: { display: true, text: 'Strike', color: '#94a3b8' },
                        grid: { color: '#334155' },
                        ticks: { color: '#94a3b8' }
                    },
                    y: {
                        title: { display: true, text: 'Volatility', color: '#94a3b8' },
                        grid: { color: '#334155' },
                        ticks: {
                            color: '#94a3b8',
                            callback: function (value) { return (value * 100).toFixed(1) + '%'; }
                        }
                    }
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
                        label: 'Payoff at Maturity',
                        data: curvePoints,
                        borderColor: '#10b981', // Emerald 500
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        borderWidth: 2,
                        pointRadius: 0,
                        fill: true
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
                                return `Spot=${context.raw.x.toFixed(4)}, Payoff=${context.raw.y.toFixed(4)}`;
                            }
                        }
                    },
                    legend: {
                        labels: { color: '#94a3b8' }
                    },
                    title: {
                        display: true,
                        text: 'Payoff at Maturity vs Spot',
                        color: '#94a3b8'
                    }
                },
                scales: {
                    x: {
                        type: 'linear',
                        position: 'bottom',
                        title: { display: true, text: 'Spot Price', color: '#94a3b8' },
                        grid: { color: '#334155' },
                        ticks: { color: '#94a3b8' }
                    },
                    y: {
                        title: { display: true, text: 'Payoff', color: '#94a3b8' },
                        grid: { color: '#334155' },
                        ticks: { color: '#94a3b8' }
                    }
                }
            }
        });
    }
});
