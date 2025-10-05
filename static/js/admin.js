/**
 * Admin Panel JavaScript
 * Enhanced functionality for the Lucky Spin Wheel admin interface
 */

// Global admin utilities
const AdminUtils = {
    
    /**
     * Initialize admin panel functionality
     */
    init() {
        this.setupFormValidation();
        this.setupImagePreviews();
        this.setupColorPickers();
        this.setupTableActions();
        this.setupModalHandlers();
        this.setupFileUploadValidation();
        this.setupTooltips();
        this.setupConfirmDialogs();
    },

    /**
     * Setup form validation for all admin forms
     */
    setupFormValidation() {
        const forms = document.querySelectorAll('form[data-validate="true"]');
        
        forms.forEach(form => {
            form.addEventListener('submit', (e) => {
                if (!this.validateForm(form)) {
                    e.preventDefault();
                    e.stopPropagation();
                }
                form.classList.add('was-validated');
            });
        });

        // Real-time validation for specific fields
        this.setupRealtimeValidation();
    },

    /**
     * Setup real-time validation for form fields
     */
    setupRealtimeValidation() {
        // Prize name validation
        const prizeNameInputs = document.querySelectorAll('input[name="name"]');
        prizeNameInputs.forEach(input => {
            input.addEventListener('input', (e) => {
                const value = e.target.value.trim();
                const feedback = e.target.nextElementSibling;
                
                if (value.length < 2) {
                    e.target.setCustomValidity('Prize name must be at least 2 characters long');
                    this.showFieldError(e.target, 'Prize name is too short');
                } else if (value.length > 50) {
                    e.target.setCustomValidity('Prize name must be less than 50 characters');
                    this.showFieldError(e.target, 'Prize name is too long');
                } else {
                    e.target.setCustomValidity('');
                    this.clearFieldError(e.target);
                }
            });
        });

        // Probability validation
        const probabilityInputs = document.querySelectorAll('input[name="probability"]');
        probabilityInputs.forEach(input => {
            input.addEventListener('input', (e) => {
                const value = parseFloat(e.target.value);
                
                if (isNaN(value) || value < 0) {
                    e.target.setCustomValidity('Probability must be a positive number');
                    this.showFieldError(e.target, 'Enter a valid probability');
                } else if (value > 100) {
                    e.target.setCustomValidity('Probability cannot exceed 100%');
                    this.showFieldError(e.target, 'Maximum probability is 100%');
                } else {
                    e.target.setCustomValidity('');
                    this.clearFieldError(e.target);
                }
            });
        });

        // Voucher count validation
        const voucherCountInputs = document.querySelectorAll('input[name="count"]');
        voucherCountInputs.forEach(input => {
            input.addEventListener('input', (e) => {
                const value = parseInt(e.target.value);
                
                if (isNaN(value) || value < 1) {
                    e.target.setCustomValidity('Count must be at least 1');
                    this.showFieldError(e.target, 'Enter a valid count');
                } else if (value > 1000) {
                    e.target.setCustomValidity('Maximum 1000 vouchers per batch');
                    this.showFieldError(e.target, 'Too many vouchers requested');
                } else {
                    e.target.setCustomValidity('');
                    this.clearFieldError(e.target);
                }
            });
        });
    },

    /**
     * Validate form before submission
     */
    validateForm(form) {
        const requiredFields = form.querySelectorAll('[required]');
        let isValid = true;

        requiredFields.forEach(field => {
            if (!field.value.trim()) {
                this.showFieldError(field, 'This field is required');
                isValid = false;
            }
        });

        return isValid;
    },

    /**
     * Show field error message
     */
    showFieldError(field, message) {
        field.classList.add('is-invalid');
        
        let feedback = field.parentNode.querySelector('.invalid-feedback');
        if (!feedback) {
            feedback = document.createElement('div');
            feedback.className = 'invalid-feedback';
            field.parentNode.appendChild(feedback);
        }
        feedback.textContent = message;
    },

    /**
     * Clear field error message
     */
    clearFieldError(field) {
        field.classList.remove('is-invalid');
        const feedback = field.parentNode.querySelector('.invalid-feedback');
        if (feedback) {
            feedback.remove();
        }
    },

    /**
     * Setup image preview functionality
     */
    setupImagePreviews() {
        const fileInputs = document.querySelectorAll('input[type="file"][accept*="image"]');
        
        fileInputs.forEach(input => {
            input.addEventListener('change', (e) => {
                this.previewImage(e.target);
            });
        });
    },

    /**
     * Preview uploaded image
     */
    previewImage(input) {
        const file = input.files[0];
        if (!file) return;

        // Validate file type
        const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/svg+xml'];
        if (!allowedTypes.includes(file.type)) {
            this.showToast('Please select a valid image file (JPG, PNG, GIF, or SVG)', 'error');
            input.value = '';
            return;
        }

        // Validate file size (16MB max)
        const maxSize = 16 * 1024 * 1024;
        if (file.size > maxSize) {
            this.showToast('File size must be less than 16MB', 'error');
            input.value = '';
            return;
        }

        const reader = new FileReader();
        reader.onload = (e) => {
            this.displayImagePreview(input, e.target.result, file.name);
        };
        reader.readAsDataURL(file);
    },

    /**
     * Display image preview
     */
    displayImagePreview(input, src, filename) {
        const previewId = input.id + '_preview';
        let preview = document.getElementById(previewId);
        
        if (!preview) {
            preview = document.createElement('div');
            preview.id = previewId;
            preview.className = 'image-preview mt-2';
            input.parentNode.appendChild(preview);
        }

        preview.innerHTML = `
            <div class="d-flex align-items-center gap-2 p-2 bg-dark border border-secondary rounded">
                <img src="${src}" alt="Preview" style="width: 50px; height: 50px; object-fit: cover; border-radius: 4px;">
                <div class="flex-grow-1">
                    <small class="text-light d-block">${filename}</small>
                    <small class="text-muted">Ready to upload</small>
                </div>
                <button type="button" class="btn btn-sm btn-outline-danger" onclick="AdminUtils.removeImagePreview('${previewId}', '${input.id}')">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
    },

    /**
     * Remove image preview
     */
    removeImagePreview(previewId, inputId) {
        const preview = document.getElementById(previewId);
        const input = document.getElementById(inputId);
        
        if (preview) preview.remove();
        if (input) input.value = '';
    },

    /**
     * Setup color picker synchronization
     */
    setupColorPickers() {
        const colorPairs = [
            ['wheel_color_1', 'wheel_color_1_text'],
            ['wheel_color_2', 'wheel_color_2_text'],
            ['text_color', 'text_color_text'],
            ['border_color', 'border_color_text'],
            ['container_bg_color', 'container_bg_color_text'],
            ['prize_border_gradient_start', 'prize_border_gradient_start_text'],
            ['prize_border_gradient_end', 'prize_border_gradient_end_text']
        ];

        colorPairs.forEach(([colorId, textId]) => {
            const colorInput = document.getElementById(colorId);
            const textInput = document.getElementById(textId);
            
            if (colorInput && textInput) {
                this.syncColorInputs(colorInput, textInput);
            }
        });
    },

    /**
     * Synchronize color picker and text input
     */
    syncColorInputs(colorInput, textInput) {
        colorInput.addEventListener('input', () => {
            textInput.value = colorInput.value;
            this.triggerPreviewUpdate();
        });

        textInput.addEventListener('input', () => {
            if (textInput.value.match(/^#[0-9A-Fa-f]{6}$/)) {
                colorInput.value = textInput.value;
                this.triggerPreviewUpdate();
            }
        });
    },

    /**
     * Trigger preview update for settings page
     */
    triggerPreviewUpdate() {
        if (typeof updatePreview === 'function') {
            updatePreview();
        }
    },

    /**
     * Setup table action handlers
     */
    setupTableActions() {
        // Delete confirmation handlers
        document.addEventListener('click', (e) => {
            if (e.target.matches('.btn-delete') || e.target.closest('.btn-delete')) {
                e.preventDefault();
                const button = e.target.closest('.btn-delete');
                const itemType = button.dataset.type || 'item';
                const itemName = button.dataset.name || 'this item';
                const action = button.dataset.action || button.href;
                
                this.confirmDelete(itemName, itemType, action);
            }
        });

        // Edit modal handlers
        document.addEventListener('click', (e) => {
            if (e.target.matches('.btn-edit') || e.target.closest('.btn-edit')) {
                const button = e.target.closest('.btn-edit');
                this.handleEditAction(button);
            }
        });
    },

    /**
     * Handle edit action
     */
    handleEditAction(button) {
        const modalId = button.dataset.target || button.getAttribute('data-bs-target');
        if (!modalId) return;

        const modal = document.querySelector(modalId);
        if (!modal) return;

        // Populate modal with current data
        const data = button.dataset;
        Object.keys(data).forEach(key => {
            if (key !== 'target' && key !== 'bsTarget') {
                const input = modal.querySelector(`[name="${key}"]`);
                if (input) {
                    if (input.type === 'checkbox') {
                        input.checked = data[key] === 'true';
                    } else {
                        input.value = data[key];
                    }
                }
            }
        });

        // Update form action if provided
        const form = modal.querySelector('form');
        if (form && button.dataset.action) {
            form.action = button.dataset.action;
        }
    },

    /**
     * Setup modal handlers
     */
    setupModalHandlers() {
        // Clear modals when closed
        document.addEventListener('hidden.bs.modal', (e) => {
            const modal = e.target;
            const form = modal.querySelector('form');
            
            if (form) {
                form.reset();
                form.classList.remove('was-validated');
                
                // Clear any error messages
                const errorMessages = form.querySelectorAll('.invalid-feedback');
                errorMessages.forEach(msg => msg.remove());
                
                // Remove validation classes
                const invalidFields = form.querySelectorAll('.is-invalid');
                invalidFields.forEach(field => field.classList.remove('is-invalid'));
            }

            // Clear image previews
            const previews = modal.querySelectorAll('.image-preview');
            previews.forEach(preview => preview.remove());
        });

        // Handle modal form submissions
        document.addEventListener('submit', (e) => {
            const form = e.target;
            const modal = form.closest('.modal');
            
            if (modal && form.checkValidity()) {
                const submitButton = form.querySelector('button[type="submit"]');
                if (submitButton) {
                    this.setButtonLoading(submitButton, true);
                }
            }
        });
    },

    /**
     * Setup file upload validation
     */
    setupFileUploadValidation() {
        const fileInputs = document.querySelectorAll('input[type="file"]');
        
        fileInputs.forEach(input => {
            input.addEventListener('change', (e) => {
                this.validateFileUpload(e.target);
            });
        });
    },

    /**
     * Validate file upload
     */
    validateFileUpload(input) {
        const files = Array.from(input.files);
        const maxSize = 16 * 1024 * 1024; // 16MB
        const allowedTypes = input.accept ? input.accept.split(',').map(t => t.trim()) : [];

        files.forEach(file => {
            // Check file size
            if (file.size > maxSize) {
                this.showToast(`File "${file.name}" is too large. Maximum size is 16MB.`, 'error');
                input.value = '';
                return;
            }

            // Check file type if restrictions exist
            if (allowedTypes.length > 0) {
                const isValidType = allowedTypes.some(type => {
                    if (type.startsWith('.')) {
                        return file.name.toLowerCase().endsWith(type.toLowerCase());
                    } else {
                        return file.type.match(type.replace('*', '.*'));
                    }
                });

                if (!isValidType) {
                    this.showToast(`File "${file.name}" has an invalid type.`, 'error');
                    input.value = '';
                    return;
                }
            }
        });
    },

    /**
     * Setup tooltips
     */
    setupTooltips() {
        const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
        const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => 
            new bootstrap.Tooltip(tooltipTriggerEl)
        );
    },

    /**
     * Setup confirm dialogs
     */
    setupConfirmDialogs() {
        document.addEventListener('click', (e) => {
            const element = e.target.closest('[data-confirm]');
            if (element) {
                e.preventDefault();
                const message = element.dataset.confirm;
                
                if (confirm(message)) {
                    if (element.tagName === 'A') {
                        window.location.href = element.href;
                    } else if (element.tagName === 'FORM') {
                        element.submit();
                    } else if (element.dataset.action) {
                        this.performAction(element.dataset.action);
                    }
                }
            }
        });
    },

    /**
     * Confirm delete action
     */
    confirmDelete(itemName, itemType, action) {
        const message = `Are you sure you want to delete ${itemType} "${itemName}"? This action cannot be undone.`;
        
        if (confirm(message)) {
            if (action.startsWith('http')) {
                // It's a URL
                window.location.href = action;
            } else {
                // It's a form action
                const form = document.createElement('form');
                form.method = 'POST';
                form.action = action;
                
                // Add page parameter if available in URL
                const urlParams = new URLSearchParams(window.location.search);
                const page = urlParams.get('page');
                if (page) {
                    const pageInput = document.createElement('input');
                    pageInput.type = 'hidden';
                    pageInput.name = 'page';
                    pageInput.value = page;
                    form.appendChild(pageInput);
                }
                
                document.body.appendChild(form);
                form.submit();
            }
        }
    },

    /**
     * Perform custom action
     */
    performAction(action) {
        try {
            // Execute the action string as a function call
            eval(action);
        } catch (error) {
            console.error('Error performing action:', error);
            this.showToast('An error occurred while performing the action', 'error');
        }
    },

    /**
     * Set button loading state
     */
    setButtonLoading(button, isLoading) {
        if (isLoading) {
            button.disabled = true;
            button.dataset.originalText = button.innerHTML;
            button.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Loading...';
        } else {
            button.disabled = false;
            button.innerHTML = button.dataset.originalText || button.innerHTML;
        }
    },

    /**
     * Show toast notification
     */
    showToast(message, type = 'info') {
        // Create toast container if it doesn't exist
        let toastContainer = document.getElementById('toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toast-container';
            toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
            toastContainer.style.zIndex = '9999';
            document.body.appendChild(toastContainer);
        }

        // Create toast element
        const toastId = 'toast-' + Date.now();
        const iconClass = {
            'success': 'fa-check-circle text-success',
            'error': 'fa-exclamation-circle text-danger',
            'warning': 'fa-exclamation-triangle text-warning',
            'info': 'fa-info-circle text-info'
        }[type] || 'fa-info-circle text-info';

        const toastHTML = `
            <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="toast-header bg-dark text-light">
                    <i class="fas ${iconClass} me-2"></i>
                    <strong class="me-auto">Notification</strong>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
                </div>
                <div class="toast-body bg-dark text-light">
                    ${message}
                </div>
            </div>
        `;

        toastContainer.insertAdjacentHTML('beforeend', toastHTML);

        // Show toast
        const toastElement = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastElement, {
            autohide: true,
            delay: 5000
        });
        toast.show();

        // Remove from DOM after hiding
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
    },

    /**
     * Copy text to clipboard
     */
    copyToClipboard(text) {
        if (navigator.clipboard) {
            navigator.clipboard.writeText(text).then(() => {
                this.showToast('Copied to clipboard!', 'success');
            }).catch(() => {
                this.fallbackCopyToClipboard(text);
            });
        } else {
            this.fallbackCopyToClipboard(text);
        }
    },

    /**
     * Fallback copy to clipboard for older browsers
     */
    fallbackCopyToClipboard(text) {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        textArea.style.top = '-999999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        try {
            document.execCommand('copy');
            this.showToast('Copied to clipboard!', 'success');
        } catch (err) {
            this.showToast('Failed to copy to clipboard', 'error');
        }
        
        document.body.removeChild(textArea);
    },

    /**
     * Format file size for display
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },

    /**
     * Debounce function for performance optimization
     */
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    /**
     * Auto-save form data to localStorage
     */
    enableAutoSave(formId) {
        const form = document.getElementById(formId);
        if (!form) return;

        const saveKey = `autosave_${formId}`;
        
        // Load saved data
        const savedData = localStorage.getItem(saveKey);
        if (savedData) {
            try {
                const data = JSON.parse(savedData);
                Object.keys(data).forEach(name => {
                    const field = form.querySelector(`[name="${name}"]`);
                    if (field && field.type !== 'file') {
                        if (field.type === 'checkbox') {
                            field.checked = data[name];
                        } else {
                            field.value = data[name];
                        }
                    }
                });
            } catch (e) {
                console.warn('Failed to load autosave data:', e);
            }
        }

        // Save data on change
        const saveData = this.debounce(() => {
            const formData = new FormData(form);
            const data = {};
            
            formData.forEach((value, key) => {
                const field = form.querySelector(`[name="${key}"]`);
                if (field && field.type !== 'file') {
                    if (field.type === 'checkbox') {
                        data[key] = field.checked;
                    } else {
                        data[key] = value;
                    }
                }
            });
            
            localStorage.setItem(saveKey, JSON.stringify(data));
        }, 1000);

        form.addEventListener('input', saveData);
        form.addEventListener('change', saveData);

        // Clear autosave on successful submission
        form.addEventListener('submit', () => {
            localStorage.removeItem(saveKey);
        });
    }
};

// Statistics and Analytics utilities
const AdminStats = {
    
    /**
     * Initialize statistics functionality
     */
    init() {
        this.updateStatistics();
        this.setupStatisticsRefresh();
    },

    /**
     * Update statistics counters with animation
     */
    updateStatistics() {
        const counters = document.querySelectorAll('[data-counter]');
        
        counters.forEach(counter => {
            const target = parseInt(counter.dataset.counter);
            const duration = 2000; // 2 seconds
            const step = target / (duration / 16); // 60fps
            let current = 0;
            
            const timer = setInterval(() => {
                current += step;
                if (current >= target) {
                    current = target;
                    clearInterval(timer);
                }
                counter.textContent = Math.floor(current);
            }, 16);
        });
    },

    /**
     * Setup automatic statistics refresh
     */
    setupStatisticsRefresh() {
        // Refresh stats every 30 seconds if on dashboard
        if (window.location.pathname.includes('/admin/dashboard')) {
            setInterval(() => {
                this.refreshStats();
            }, 30000);
        }
    },

    /**
     * Refresh statistics via AJAX
     */
    async refreshStats() {
        try {
            const response = await fetch('/admin/api/stats');
            if (response.ok) {
                const stats = await response.json();
                this.updateStatsDisplay(stats);
            }
        } catch (error) {
            console.warn('Failed to refresh statistics:', error);
        }
    },

    /**
     * Update statistics display
     */
    updateStatsDisplay(stats) {
        Object.keys(stats).forEach(key => {
            const element = document.querySelector(`[data-stat="${key}"]`);
            if (element) {
                element.textContent = stats[key];
            }
        });
    }
};

// Initialize admin functionality when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    AdminUtils.init();
    AdminStats.init();
    
    // Enable auto-save for important forms
    AdminUtils.enableAutoSave('addPrizeForm');
    AdminUtils.enableAutoSave('editPrizeForm');
    AdminUtils.enableAutoSave('settingsForm');
});

// Global functions for inline event handlers
window.AdminUtils = AdminUtils;
window.copyToClipboard = (text) => AdminUtils.copyToClipboard(text);
window.editPrize = (id, name, probability, isActive) => {
    const button = document.createElement('button');
    button.dataset.action = `/admin/prizes/edit/${id}`;
    button.dataset.name = name;
    button.dataset.probability = probability;
    button.dataset.isActive = isActive;
    button.dataset.target = '#editPrizeModal';
    AdminUtils.handleEditAction(button);
};
window.deletePrize = (id, name) => {
    AdminUtils.confirmDelete(name, 'prize', `/admin/prizes/delete/${id}`);
};
window.deleteVoucher = (id, code) => {
    AdminUtils.confirmDelete(code, 'voucher', `/admin/vouchers/delete/${id}`);
};
