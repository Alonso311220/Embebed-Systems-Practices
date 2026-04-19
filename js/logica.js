$(document).ready(function() {
    // 1. Configuración inicial de la Gráfica
    const ctx = document.getElementById('myChart').getContext('2d');
    let myChart = new Chart(ctx, {
        type: 'line',
        data: { labels: [], datasets: [{
            label: 'Temperatura °C',
            data: [],
            borderColor: '#00e5ff',
            backgroundColor: 'rgba(0, 229, 255, 0.1)',
            borderWidth: 2,
            fill: true,
            tension: 0.3
        }]},
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { grid: { color: '#30363d' }, ticks: { color: '#8b949e' } },
                y: { grid: { color: '#30363d' },
                     beginAtZero: false, 
                     ticks: { color: '#8b949e', stepSize: 1 },
                     suggestedMin: 10,
                     suggestedMax: 20
                    }
            }
        }
    });

    // 2. Función para cargar datos desde el servidor
    function loadData() {
        $.getJSON('/temp.log', function(response) {
            if (response.length === 0) return;

            let labels = [];
            let temps = [];
            let tableHtml = '';
            let sum = 0;

            response.forEach((item, index) => {
                // Convertir timestamp a hora legible
                let date = new Date(item.timestamp * 1000);
                let timeStr = date.toLocaleTimeString();
                
                labels.push(timeStr);
                temps.push(item.temp);
                sum += item.temp;

                // Llenar tabla
                tableHtml += `
                    <tr>
                        <td>${index + 1}</td>
                        <td>${timeStr}</td>
                        <td class="temp ${item.temp > 15 ? 'hot' : 'norm'}">${item.temp}</td>
                        <td><span class="badge ${item.temp > 15 ? 'warn' : 'norm'}">OK</span></td>
                    </tr>`;
            });

            // Actualizar Gráfica
            myChart.data.labels = labels;
            myChart.data.datasets[0].data = temps;
            myChart.update();

            // Actualizar Tabla
            $('#tbody').html(tableHtml);
            $('#rowCount').text(response.length);

            // Calcular Estadísticas
            const min = Math.min(...temps);
            const max = Math.max(...temps);
            const avg = (sum / temps.length).toFixed(2);

            $('#sTot').text(temps.length);
            $('#sMin').text(min + '°');
            $('#sMax').text(max + '°');
            $('#sAvg').text(avg + '°');
        });
    }

    // Ejecutar carga inicial
    loadData();

    // Opcional: Recarga automática cada 5 segundos
    setInterval(loadData, 5000);
});
