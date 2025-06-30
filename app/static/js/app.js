// Print Manager JavaScript

// Status indicator animation
document.addEventListener('DOMContentLoaded', function() {
    // Add pulsing animation to status indicators
    const statusIndicators = document.querySelectorAll('.status-indicator');
    statusIndicators.forEach(indicator => {
        if (indicator.classList.contains('bg-success')) {
            indicator.style.animation = 'pulse 2s infinite';
        }
    });
    
    // Auto-refresh for pending jobs
    if (window.location.pathname.includes('/jobs') || window.location.pathname.includes('/dashboard')) {
        setInterval(function() {
            const pendingBadges = document.querySelectorAll('.badge:contains("Pending")');
            if (pendingBadges.length > 0) {
                // Only refresh if there are pending jobs
                location.reload();
            }
        }, 30000); // Refresh every 30 seconds
    }
    
    // File upload validation
    const fileInput = document.getElementById('file');
    if (fileInput) {
        fileInput.addEventListener('change', function() {
            const file = this.files[0];
            if (file) {
                const maxSize = 16 * 1024 * 1024; // 16MB
                if (file.size > maxSize) {
                    alert('File size exceeds 16MB limit. Please choose a smaller file.');
                    this.value = '';
                    return;
                }
                
                // Show file info
                const fileInfo = document.createElement('div');
                fileInfo.className = 'alert alert-info mt-2';
                fileInfo.innerHTML = `
                    <i class="bi bi-info-circle me-1"></i>
                    Selected: <strong>${file.name}</strong> (${formatFileSize(file.size)})
                `;
                
                // Remove existing file info
                const existingInfo = this.parentNode.querySelector('.alert-info');
                if (existingInfo) {
                    existingInfo.remove();
                }
                
                this.parentNode.appendChild(fileInfo);
            }
        });
    }
    
    // Form validation
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const requiredFields = form.querySelectorAll('[required]');
            let valid = true;
            
            requiredFields.forEach(field => {
                if (!field.value.trim()) {
                    field.classList.add('is-invalid');
                    valid = false;
                } else {
                    field.classList.remove('is-invalid');
                }
            });
            
            if (!valid) {
                e.preventDefault();
                showToast('Please fill in all required fields', 'error');
            }
        });
    });
    
    // Tooltip initialization
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

// Utility functions
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function showToast(message, type = 'info') {
    const toastContainer = document.querySelector('.toast-container') || createToastContainer();
    
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type === 'error' ? 'danger' : type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    toastContainer.appendChild(toast);
    
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    // Remove toast element after it's hidden
    toast.addEventListener('hidden.bs.toast', function() {
        toast.remove();
    });
}

function createToastContainer() {
    const container = document.createElement('div');
    container.className = 'toast-container position-fixed top-0 end-0 p-3';
    container.style.zIndex = '9999';
    document.body.appendChild(container);
    return container;
}

// Chart utilities
function createChart(ctx, type, data, options = {}) {
    return new Chart(ctx, {
        type: type,
        data: data,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            ...options
        }
    });
}

// Real-time updates
function startRealtimeUpdates() {
    // Update user balance and quota in navbar
    setInterval(function() {
        fetch('/api/user_status')
            .then(response => response.json())
            .then(data => {
                const balanceBadge = document.querySelector('.navbar .badge');
                if (balanceBadge && data.balance !== undefined) {
                    balanceBadge.textContent = `$${data.balance.toFixed(2)}`;
                }
            })
            .catch(error => console.log('Status update failed:', error));
    }, 60000); // Update every minute
}

// Print job status polling
function pollJobStatus() {
    const jobRows = document.querySelectorAll('[data-job-id]');
    if (jobRows.length === 0) return;
    
    const jobIds = Array.from(jobRows).map(row => row.dataset.jobId);
    
    fetch('/api/job_status', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({jobs: jobIds})
    })
    .then(response => response.json())
    .then(data => {
        data.forEach(job => {
            const row = document.querySelector(`[data-job-id="${job.id}"]`);
            if (row) {
                updateJobRow(row, job);
            }
        });
    })
    .catch(error => console.log('Job status poll failed:', error));
}

function updateJobRow(row, jobData) {
    const statusBadge = row.querySelector('.badge');
    if (statusBadge) {
        statusBadge.className = `badge bg-${getStatusColor(jobData.status)}`;
        statusBadge.textContent = jobData.status.charAt(0).toUpperCase() + jobData.status.slice(1);
    }
}

function getStatusColor(status) {
    const colors = {
        'pending': 'info',
        'printing': 'warning',
        'completed': 'success',
        'failed': 'danger',
        'cancelled': 'secondary'
    };
    return colors[status] || 'secondary';
}

// CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes pulse {
        0% { transform: scale(1); opacity: 1; }
        50% { transform: scale(1.05); opacity: 0.7; }
        100% { transform: scale(1); opacity: 1; }
    }
    
    .status-indicator {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
    }
    
    .table-hover tbody tr:hover {
        background-color: var(--bs-table-hover-bg);
    }
    
    .card {
        transition: box-shadow 0.15s ease-in-out;
    }
    
    .card:hover {
        box-shadow: 0 0.5rem 1rem rgba(0, 0, 0, 0.15);
    }
    
    .btn {
        transition: all 0.15s ease-in-out;
    }
    
    .progress-bar {
        transition: width 0.6s ease;
    }
    
    .fade-in {
        animation: fadeIn 0.5s ease-in;
    }
    
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
`;
document.head.appendChild(style);
