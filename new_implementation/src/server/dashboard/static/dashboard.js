// Dashboard JavaScript
const API_BASE = '/dashboard/api';

// State
let refreshInterval = null;
let currentPage = 1;
let currentTable = null;
let tableLimit = 100;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    loadInitialData();
    startAutoRefresh();
});

function setupEventListeners() {
    // Auto-refresh toggle
    const autoRefresh = document.getElementById('autoRefresh');
    autoRefresh.addEventListener('change', (e) => {
        if (e.target.checked) {
            startAutoRefresh();
        } else {
            stopAutoRefresh();
        }
    });

    // Manual refresh
    document.getElementById('manualRefresh').addEventListener('click', () => {
        loadInitialData();
        loadLogs();
        if (currentTable) {
            loadTableData(currentTable, currentPage);
        }
    });

    // Log controls
    document.getElementById('refreshLogs').addEventListener('click', loadLogs);
    document.getElementById('logService').addEventListener('change', loadLogs);
    document.getElementById('logLines').addEventListener('change', loadLogs);
    document.getElementById('logFilter').addEventListener('input', filterLogs);
    
    // Database controls
    document.getElementById('tableSelector').addEventListener('change', (e) => {
        currentTable = e.target.value;
        currentPage = 1;
        if (currentTable) {
            loadTableData(currentTable, currentPage);
        } else {
            clearTableData();
        }
    });
    document.getElementById('refreshTable').addEventListener('click', () => {
        if (currentTable) {
            loadTableData(currentTable, currentPage);
        }
    });
    document.getElementById('prevPage').addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            loadTableData(currentTable, currentPage);
        }
    });
    document.getElementById('nextPage').addEventListener('click', () => {
        currentPage++;
        loadTableData(currentTable, currentPage);
    });
}

async function loadInitialData() {
    await Promise.all([
        loadServiceStatus(),
        loadDatabaseStats(),
        loadDatabaseTables()
    ]);
}

// Service Status
async function loadServiceStatus() {
    try {
        const response = await fetch(`${API_BASE}/services/status`);
        const data = await response.json();
        displayServiceStatus(data.services);
    } catch (error) {
        console.error('Failed to load service status:', error);
        document.getElementById('servicesContainer').innerHTML = 
            `<div class="error-message">Failed to load service status: ${error.message}</div>`;
    }
}

function displayServiceStatus(services) {
    const container = document.getElementById('servicesContainer');
    if (!services || services.length === 0) {
        container.innerHTML = '<div class="error-message">No services found</div>';
        return;
    }

    container.innerHTML = services.map(service => {
        const statusClass = service.is_active ? 'active' : 
                           (service.status === 'error' ? 'error' : 'inactive');
        return `
            <div class="service-card ${statusClass}">
                <h3>${service.name}</h3>
                <span class="service-status ${statusClass}">${service.status}</span>
                ${service.active_since ? `<div class="service-info">Active since: ${service.active_since}</div>` : ''}
                ${service.error ? `<div class="service-info error-message">${service.error}</div>` : ''}
                <div class="service-actions">
                    <button onclick="restartService('${service.name}')" ${service.status === 'error' ? 'disabled' : ''}>
                        Restart Service
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

async function restartService(serviceName) {
    if (!confirm(`Are you sure you want to restart ${serviceName}?`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/services/restart`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ service: serviceName })
        });

        const data = await response.json();
        if (response.ok) {
            alert(`Service ${serviceName} restarted successfully`);
            // Reload status after a short delay
            setTimeout(loadServiceStatus, 2000);
        } else {
            alert(`Failed to restart service: ${data.detail || 'Unknown error'}`);
        }
    } catch (error) {
        alert(`Error restarting service: ${error.message}`);
    }
}

// Database Statistics
async function loadDatabaseStats() {
    try {
        const response = await fetch(`${API_BASE}/database/stats`);
        const data = await response.json();
        displayDatabaseStats(data);
    } catch (error) {
        console.error('Failed to load database stats:', error);
        document.getElementById('statsContainer').innerHTML = 
            `<div class="error-message">Failed to load statistics: ${error.message}</div>`;
    }
}

function displayDatabaseStats(stats) {
    const container = document.getElementById('statsContainer');
    container.innerHTML = `
        <div class="stat-card">
            <h3>Total Games</h3>
            <div class="value">${stats.total_games || 0}</div>
        </div>
        <div class="stat-card">
            <h3>Active Games</h3>
            <div class="value">${stats.active_games || 0}</div>
        </div>
        <div class="stat-card">
            <h3>Total Players</h3>
            <div class="value">${stats.total_players || 0}</div>
        </div>
        <div class="stat-card">
            <h3>Total Users</h3>
            <div class="value">${stats.total_users || 0}</div>
        </div>
        <div class="stat-card">
            <h3>Total Orders</h3>
            <div class="value">${stats.total_orders || 0}</div>
        </div>
        <div class="stat-card">
            <h3>Recent Activity (24h)</h3>
            <div class="value">${stats.recent_activity || 0}</div>
        </div>
    `;
}

// Logs Viewer
async function loadLogs() {
    const service = document.getElementById('logService').value;
    const lines = parseInt(document.getElementById('logLines').value);
    const container = document.getElementById('logsOutput');

    try {
        const response = await fetch(`${API_BASE}/logs/${service}?lines=${lines}`);
        const data = await response.json();
        displayLogs(data.logs || []);
        
        // Auto-scroll if enabled
        if (document.getElementById('autoScrollLogs').checked) {
            container.scrollTop = container.scrollHeight;
        }
    } catch (error) {
        console.error('Failed to load logs:', error);
        container.innerHTML = `<div class="error-message">Failed to load logs: ${error.message}</div>`;
    }
}

function displayLogs(logs) {
    const container = document.getElementById('logsOutput');
    const filter = document.getElementById('logFilter').value.toLowerCase();
    
    container.innerHTML = logs.map(line => {
        const shouldShow = !filter || line.toLowerCase().includes(filter);
        const errorMatch = line.toLowerCase().includes('error') || line.toLowerCase().includes('exception');
        const warningMatch = line.toLowerCase().includes('warning');
        const logClass = errorMatch ? 'error' : (warningMatch ? 'warning' : '');
        
        return `<div class="log-line ${logClass} ${shouldShow ? '' : 'hidden'}">${escapeHtml(line)}</div>`;
    }).join('');
}

function filterLogs() {
    const filter = document.getElementById('logFilter').value.toLowerCase();
    const logLines = document.querySelectorAll('.log-line');
    logLines.forEach(line => {
        const text = line.textContent.toLowerCase();
        line.classList.toggle('hidden', filter && !text.includes(filter));
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Database Viewer
async function loadDatabaseTables() {
    try {
        const response = await fetch(`${API_BASE}/database/tables`);
        const data = await response.json();
        populateTableSelector(data.tables || []);
    } catch (error) {
        console.error('Failed to load database tables:', error);
    }
}

function populateTableSelector(tables) {
    const selector = document.getElementById('tableSelector');
    selector.innerHTML = '<option value="">Select a table...</option>';
    tables.forEach(table => {
        const option = document.createElement('option');
        option.value = table;
        option.textContent = table;
        selector.appendChild(option);
    });
}

async function loadTableData(tableName, page) {
    const offset = (page - 1) * tableLimit;
    const container = document.getElementById('tableContainer');
    const infoDiv = document.getElementById('tableInfo');
    
    container.innerHTML = '<div class="loading">Loading table data...</div>';

    try {
        const response = await fetch(`${API_BASE}/database/table/${tableName}?limit=${tableLimit}&offset=${offset}`);
        const data = await response.json();
        displayTableData(data);
        
        // Update pagination
        const totalPages = Math.ceil(data.total_rows / tableLimit);
        document.getElementById('totalRows').textContent = data.total_rows;
        document.getElementById('currentPage').textContent = page;
        document.getElementById('prevPage').disabled = page <= 1;
        document.getElementById('nextPage').disabled = page >= totalPages || data.total_rows === 0;
        infoDiv.style.display = 'block';
    } catch (error) {
        console.error('Failed to load table data:', error);
        container.innerHTML = `<div class="error-message">Failed to load table data: ${error.message}</div>`;
    }
}

function displayTableData(data) {
    const container = document.getElementById('tableContainer');
    
    if (!data.rows || data.rows.length === 0) {
        container.innerHTML = '<div class="placeholder">No data found in this table</div>';
        return;
    }

    const columns = data.columns || [];
    const columnNames = columns.map(col => col.name);

    let html = '<table><thead><tr>';
    columnNames.forEach(col => {
        html += `<th>${escapeHtml(col)}</th>`;
    });
    html += '</tr></thead><tbody>';

    data.rows.forEach(row => {
        html += '<tr>';
        columnNames.forEach(col => {
            const value = row[col];
            html += `<td>${value !== null && value !== undefined ? escapeHtml(String(value)) : '<em>null</em>'}</td>`;
        });
        html += '</tr>';
    });

    html += '</tbody></table>';
    container.innerHTML = html;
}

function clearTableData() {
    document.getElementById('tableContainer').innerHTML = '<p class="placeholder">Select a table to view data</p>';
    document.getElementById('tableInfo').style.display = 'none';
}

// Auto-refresh
function startAutoRefresh() {
    stopAutoRefresh();
    refreshInterval = setInterval(() => {
        loadServiceStatus();
        loadDatabaseStats();
        // Don't auto-refresh logs and table by default to avoid too much data
    }, 5000);
}

function stopAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
        refreshInterval = null;
    }
}

// Expose restartService to global scope for onclick handlers
window.restartService = restartService;

