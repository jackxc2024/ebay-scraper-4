// Main application JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Search form validation
    const searchForm = document.getElementById('searchForm');
    if (searchForm) {
        searchForm.addEventListener('submit', function(e) {
            const searchTerm = document.getElementById('search_term').value.trim();
            
            if (!searchTerm) {
                e.preventDefault();
                showAlert('Please enter a search term', 'danger');
                return false;
            }
            
            if (searchTerm.length < 3) {
                e.preventDefault();
                showAlert('Search term must be at least 3 characters long', 'warning');
                return false;
            }
            
            // Show loading state
            const submitBtn = this.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Starting...';
                submitBtn.disabled = true;
            }
        });
    }

    // Auto-hide alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(alert => {
        setTimeout(() => {
            const alertInstance = new bootstrap.Alert(alert);
            alertInstance.close();
        }, 5000);
    });

    // Job status auto-refresh for running jobs
    const jobStatusElement = document.querySelector('[data-job-status]');
    if (jobStatusElement) {
        const status = jobStatusElement.getAttribute('data-job-status');
        const jobId = jobStatusElement.getAttribute('data-job-id');
        
        if (status === 'running' && jobId) {
            // Poll for updates every 3 seconds
            const pollInterval = setInterval(() => {
                pollJobStatus(jobId, pollInterval);
            }, 3000);
        }
    }

    // Handle external links
    const externalLinks = document.querySelectorAll('a[href^="http"]:not([href*="' + window.location.hostname + '"])');
    externalLinks.forEach(link => {
        link.setAttribute('target', '_blank');
        link.setAttribute('rel', 'noopener noreferrer');
    });

    // Image loading error handling
    const productImages = document.querySelectorAll('img[src*="aliexpress"], img[src*="alicdn"]');
    productImages.forEach(img => {
        img.addEventListener('error', function() {
            this.style.display = 'none';
            const placeholder = document.createElement('div');
            placeholder.className = 'bg-light rounded d-flex align-items-center justify-content-center';
            placeholder.style.height = '80px';
            placeholder.innerHTML = '<i class="fas fa-image text-muted"></i>';
            this.parentNode.insertBefore(placeholder, this);
        });
    });
});

// Function to show alert messages
function showAlert(message, type = 'info') {
    const alertContainer = document.createElement('div');
    alertContainer.className = `alert alert-${type} alert-dismissible fade show`;
    alertContainer.setAttribute('role', 'alert');
    alertContainer.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // Insert at the top of the main content
    const mainContent = document.querySelector('main.container');
    if (mainContent) {
        mainContent.insertBefore(alertContainer, mainContent.firstChild);
    }
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        const alertInstance = new bootstrap.Alert(alertContainer);
        alertInstance.close();
    }, 5000);
}

// Function to poll job status
function pollJobStatus(jobId, intervalId) {
    fetch(`/api/job/${jobId}/status`)
        .then(response => response.json())
        .then(data => {
            if (data.status !== 'running') {
                clearInterval(intervalId);
                // Reload page to show final results
                window.location.reload();
            } else {
                // Update progress indicators
                updateJobProgress(data);
            }
        })
        .catch(error => {
            console.error('Error polling job status:', error);
            clearInterval(intervalId);
        });
}

// Function to update job progress
function updateJobProgress(jobData) {
    // Update progress bar
    const progressBar = document.querySelector('.progress-bar');
    if (progressBar && jobData.total_pages > 0) {
        const percentage = (jobData.current_page / jobData.total_pages) * 100;
        progressBar.style.width = `${percentage}%`;
        progressBar.textContent = `${Math.round(percentage)}%`;
    }
    
    // Update current page indicator
    const pageIndicators = document.querySelectorAll('[data-current-page]');
    pageIndicators.forEach(indicator => {
        indicator.textContent = `${jobData.current_page}/${jobData.total_pages}`;
    });
    
    // Update product count if available
    const productCounters = document.querySelectorAll('[data-product-count]');
    productCounters.forEach(counter => {
        counter.textContent = jobData.product_count || '0';
    });
}

// Function to copy text to clipboard
function copyToClipboard(text) {
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => {
            showAlert('Copied to clipboard!', 'success');
        }).catch(err => {
            console.error('Failed to copy: ', err);
            showAlert('Failed to copy to clipboard', 'danger');
        });
    } else {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.select();
        try {
            document.execCommand('copy');
            showAlert('Copied to clipboard!', 'success');
        } catch (err) {
            showAlert('Failed to copy to clipboard', 'danger');
        }
        document.body.removeChild(textArea);
    }
}

// Function to format numbers
function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
}

// Function to validate URL
function isValidUrl(string) {
    try {
        new URL(string);
        return true;
    } catch (_) {
        return false;
    }
}

// Function to handle smooth scrolling
function smoothScrollTo(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.scrollIntoView({
            behavior: 'smooth',
            block: 'start'
        });
    }
}

// Function to debounce function calls
function debounce(func, wait, immediate) {
    let timeout;
    return function executedFunction() {
        const context = this;
        const args = arguments;
        const later = function() {
            timeout = null;
            if (!immediate) func.apply(context, args);
        };
        const callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow) func.apply(context, args);
    };
}

// Export functions for use in other scripts
window.AppUtils = {
    showAlert,
    copyToClipboard,
    formatNumber,
    isValidUrl,
    smoothScrollTo,
    debounce
};
