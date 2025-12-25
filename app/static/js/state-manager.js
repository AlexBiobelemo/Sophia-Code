/**
 * Client-side state management utilities for preserving user state across page navigations.
 * Provides auto-save, local storage, and state restoration capabilities.
 */

class StateManager {
    constructor() {
        this.autoSaveInterval = null;
        this.lastSaveTime = null;
        this.isDirty = false;
        this.init();
    }

    init() {
        // Detect back/forward navigation and handle accordingly
        this.handleNavigationType();
        
        // Initialize auto-save for textareas and content-editable elements
        this.initAutoSave();
        // Restore state on page load
        this.restorePageState();
        // Set up beforeunload warning for unsaved changes
        this.initBeforeUnloadWarning();
    }

    /**
     * Handle different navigation types
     */
    handleNavigationType() {
        // Check for back/forward navigation
        window.addEventListener('pageshow', (event) => {
            if (event.persisted) {
                // This is a bfcache restoration
                console.log('Page restored from bfcache');
                this.restorePageState();
            }
        });

        // Add back button detection
        let perfEntries = performance.getEntriesByType('navigation');
        if (perfEntries.length > 0) {
            const navEntry = perfEntries[0];
            if (navEntry.type === 'back_forward') {
                console.log('Back/forward navigation detected');
                // Force content check after a delay
                setTimeout(() => {
                    if (document.body && !document.body.textContent.trim()) {
                        console.log('Empty page detected, reloading...');
                        window.location.reload();
                    }
                }, 500);
            }
        }
    }

    /**
     * Initialize auto-save functionality
     */
    initAutoSave() {
        const textareas = document.querySelectorAll('textarea[data-autosave]');
        const contentEditable = document.querySelectorAll('[contenteditable][data-autosave]');

        [...textareas, ...contentEditable].forEach(element => {
            element.addEventListener('input', () => {
                this.markDirty();
                this.scheduleAutoSave(element);
            });

            // Restore saved content
            this.restoreElementState(element);
        });
    }

    /**
     * Schedule auto-save with debouncing
     */
    scheduleAutoSave(element) {
        clearTimeout(this.autoSaveTimeout);
        this.autoSaveTimeout = setTimeout(() => {
            this.autoSaveElement(element);
        }, 2000); // 2 second debounce
    }

    /**
     * Auto-save element content
     */
    async autoSaveElement(element) {
        const key = this.getElementKey(element);
        const content = this.getElementContent(element);

        if (!content || content.length < 10) return; // Don't save minimal content

        try {
            const response = await fetch('/api/autosave', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    key: key,
                    content: content,
                    element_type: element.tagName.toLowerCase(),
                    timestamp: new Date().toISOString()
                })
            });

            if (response.ok) {
                this.lastSaveTime = new Date();
                this.markClean();
                this.showAutoSaveIndicator('success');
            }
        } catch (error) {
            console.warn('Auto-save failed:', error);
            this.showAutoSaveIndicator('error');
        }
    }

    /**
     * Restore element state from server
     */
    async restoreElementState(element) {
        const key = this.getElementKey(element);

        try {
            const response = await fetch(`/api/autosave?key=${encodeURIComponent(key)}`);
            if (response.ok) {
                const data = await response.json();
                if (data.content && !element.value && !element.textContent) {
                    this.setElementContent(element, data.content);
                }
            }
        } catch (error) {
            console.warn('Failed to restore element state:', error);
        }
    }

    /**
     * Generate unique key for element
     */
    getElementKey(element) {
        const form = element.closest('form');
        const formId = form ? form.id || 'anonymous' : 'no-form';
        const elementId = element.id || element.name || 'unnamed';
        const page = window.location.pathname;

        return `${page}_${formId}_${elementId}`;
    }

    /**
     * Get content from element
     */
    getElementContent(element) {
        if (element.tagName.toLowerCase() === 'textarea' || element.tagName.toLowerCase() === 'input') {
            return element.value;
        }
        return element.textContent || element.innerText || '';
    }

    /**
     * Set content to element
     */
    setElementContent(element, content) {
        if (element.tagName.toLowerCase() === 'textarea' || element.tagName.toLowerCase() === 'input') {
            element.value = content;
        } else {
            element.textContent = content;
        }

        // Trigger change event
        element.dispatchEvent(new Event('input', { bubbles: true }));
    }

    /**
     * Mark form as dirty
     */
    markDirty() {
        this.isDirty = true;
        this.updateDirtyIndicator();
    }

    /**
     * Mark form as clean
     */
    markClean() {
        this.isDirty = false;
        this.updateDirtyIndicator();
    }

    /**
     * Update dirty indicator
     */
    updateDirtyIndicator() {
        const indicator = document.querySelector('.dirty-indicator');
        if (indicator) {
            indicator.style.display = this.isDirty ? 'inline' : 'none';
        }
    }

    /**
     * Show auto-save indicator
     */
    showAutoSaveIndicator(type) {
        const indicator = document.getElementById('autosave-indicator') || this.createAutoSaveIndicator();

        indicator.className = `autosave-indicator alert alert-${type === 'success' ? 'success' : 'warning'} alert-dismissible fade show`;
        indicator.innerHTML = `
            ${type === 'success' ? '✓' : '⚠'} Auto-saved ${this.lastSaveTime ? this.getRelativeTime(this.lastSaveTime) : 'just now'}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        // Auto-hide after 3 seconds
        setTimeout(() => {
            if (indicator.parentNode) {
                indicator.remove();
            }
        }, 3000);
    }

    /**
     * Create auto-save indicator element
     */
    createAutoSaveIndicator() {
        const indicator = document.createElement('div');
        indicator.id = 'autosave-indicator';
        indicator.className = 'autosave-indicator alert alert-success alert-dismissible fade show';
        indicator.style.cssText = `
            position: fixed;
            top: 80px;
            right: 20px;
            z-index: 9999;
            max-width: 300px;
        `;
        document.body.appendChild(indicator);
        return indicator;
    }

    /**
     * Get relative time string
     */
    getRelativeTime(date) {
        const now = new Date();
        const diff = now - date;
        const seconds = Math.floor(diff / 1000);

        if (seconds < 60) return 'just now';
        if (seconds < 3600) return `${Math.floor(seconds / 60)} minute${Math.floor(seconds / 60) !== 1 ? 's' : ''} ago`;
        return `${Math.floor(seconds / 3600)} hour${Math.floor(seconds / 3600) !== 1 ? 's' : ''} ago`;
    }

    /**
     * Initialize beforeunload warning
     */
    initBeforeUnloadWarning() {
        window.addEventListener('beforeunload', (e) => {
            if (this.isDirty) {
                const message = 'You have unsaved changes. Are you sure you want to leave?';
                e.returnValue = message;
                return message;
            }
        });
    }

    /**
     * Save page state to localStorage
     */
    savePageState() {
        const state = {
            scrollPosition: window.pageYOffset || document.documentElement.scrollTop,
            formData: this.getFormData(),
            filters: this.getSearchFilters(),
            timestamp: Date.now()
        };

        try {
            localStorage.setItem(`page_state_${this.getPageKey()}`, JSON.stringify(state));
        } catch (error) {
            console.warn('Failed to save page state:', error);
        }
    }

    /**
     * Restore page state from localStorage
     */
    restorePageState() {
        try {
            // Check if this is a back/forward navigation
            const navigationType = performance.navigation.type;
            const isBackForward = navigationType === 2 || navigationType === 1;
            
            const stored = localStorage.getItem(`page_state_${this.getPageKey()}`);
            if (!stored) return;

            const state = JSON.parse(stored);

            // Only restore if state is less than 24 hours old (increased from 1 hour)
            if (Date.now() - state.timestamp > 86400000) {
                localStorage.removeItem(`page_state_${this.getPageKey()}`);
                return;
            }

            // For back/forward navigation, wait for page to fully load
            if (isBackForward) {
                // Force page reload if content is missing
                setTimeout(() => {
                    if (document.body && !document.body.innerHTML.trim()) {
                        window.location.reload();
                        return;
                    }
                    this.performRestore(state);
                }, 200);
            } else {
                this.performRestore(state);
            }

        } catch (error) {
            console.warn('Failed to restore page state:', error);
        }
    }

    /**
     * Perform the actual state restoration
     */
    performRestore(state) {
        // Restore scroll position after a short delay
        setTimeout(() => {
            if (state.scrollPosition !== undefined) {
                window.scrollTo(0, state.scrollPosition);
            }
        }, 100);

        // Restore form data
        if (state.formData) {
            this.restoreFormData(state.formData);
        }

        // Restore search filters
        if (state.filters) {
            this.restoreSearchFilters(state.filters);
        }
    }

    /**
     * Get unique page key
     */
    getPageKey() {
        return window.location.pathname + window.location.search;
    }

    /**
     * Get form data
     */
    getFormData() {
        const form = document.querySelector('form');
        if (!form) return {};

        const data = {};
        const inputs = form.querySelectorAll('input, textarea, select');

        inputs.forEach(input => {
            if (input.name && input.type !== 'password') {
                if (input.type === 'checkbox' || input.type === 'radio') {
                    if (input.checked) {
                        data[input.name] = input.value;
                    }
                } else {
                    data[input.name] = input.value;
                }
            }
        });

        return data;
    }

    /**
     * Restore form data
     */
    restoreFormData(data) {
        const form = document.querySelector('form');
        if (!form) return;

        Object.entries(data).forEach(([name, value]) => {
            const input = form.querySelector(`[name="${name}"]`);
            if (input) {
                if (input.type === 'checkbox' || input.type === 'radio') {
                    input.checked = input.value === value;
                } else {
                    input.value = value;
                }
                input.dispatchEvent(new Event('change', { bubbles: true }));
            }
        });
    }

    /**
     * Get search filters
     */
    getSearchFilters() {
        const filters = {};

        // Get URL parameters
        const params = new URLSearchParams(window.location.search);
        params.forEach((value, key) => {
            filters[key] = value;
        });

        // Get form inputs
        const searchForm = document.querySelector('#global-search-form, form[action*="search"]');
        if (searchForm) {
            const inputs = searchForm.querySelectorAll('input, select');
            inputs.forEach(input => {
                if (input.name && input.value) {
                    filters[input.name] = input.value;
                }
            });
        }

        return filters;
    }

    /**
     * Restore search filters
     */
    restoreSearchFilters(filters) {
        // Restore URL parameters
        const params = new URLSearchParams();
        Object.entries(filters).forEach(([key, value]) => {
            if (key !== 'q') { // Don't restore main search query
                params.set(key, value);
            }
        });

        // Update URL without page reload
        const newUrl = window.location.pathname + (params.toString() ? '?' + params.toString() : '');
        window.history.replaceState({}, '', newUrl);

        // Restore form inputs
        Object.entries(filters).forEach(([key, value]) => {
            const input = document.querySelector(`[name="${key}"]`);
            if (input) {
                input.value = value;
            }
        });
    }

    /**
     * Preserve navigation state
     */
    preserveNavigation() {
        // Save current page info for breadcrumbs and navigation
        const navState = {
            currentPage: window.location.pathname,
            referrer: document.referrer,
            timestamp: Date.now()
        };

        try {
            sessionStorage.setItem('navigation_state', JSON.stringify(navState));
        } catch (error) {
            console.warn('Failed to preserve navigation state:', error);
        }
    }

    /**
     * Get preserved navigation state
     */
    getNavigationState() {
        try {
            const stored = sessionStorage.getItem('navigation_state');
            return stored ? JSON.parse(stored) : null;
        } catch (error) {
            console.warn('Failed to get navigation state:', error);
            return null;
        }
    }

    /**
     * Clear all saved state for current page
     */
    clearPageState() {
        try {
            localStorage.removeItem(`page_state_${this.getPageKey()}`);
            sessionStorage.removeItem('navigation_state');
        } catch (error) {
            console.warn('Failed to clear page state:', error);
        }
    }

    /**
     * Preserve form state via API
     */
    async apiPreserveFormState(formName, formData) {
        try {
            const response = await fetch('/api/preserve-form-state', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    form_name: formName,
                    form_data: formData
                })
            });
            return response.ok;
        } catch (error) {
            console.warn('Failed to preserve form state via API:', error);
            return false;
        }
    }

    /**
     * Restore form state via API
     */
    async apiRestoreFormState(formName) {
        try {
            const response = await fetch(`/api/restore-form-state/${encodeURIComponent(formName)}`);
            if (response.ok) {
                const data = await response.json();
                return data.form_data || {};
            }
        } catch (error) {
            console.warn('Failed to restore form state via API:', error);
        }
        return {};
    }

    /**
     * Preserve search state via API
     */
    async apiPreserveSearchState(filters) {
        try {
            const response = await fetch('/api/preserve-search-state', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    filters: filters
                })
            });
            return response.ok;
        } catch (error) {
            console.warn('Failed to preserve search state via API:', error);
            return false;
        }
    }

    /**
     * Restore search state via API
     */
    async apiRestoreSearchState() {
        try {
            const response = await fetch('/api/restore-search-state');
            if (response.ok) {
                const data = await response.json();
                return data.filters || {};
            }
        } catch (error) {
            console.warn('Failed to restore search state via API:', error);
        }
        return {};
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.stateManager = new StateManager();

    // Save page state periodically
    setInterval(() => {
        window.stateManager.savePageState();
    }, 30000); // Every 30 seconds

    // Save page state before page unload
    window.addEventListener('beforeunload', () => {
        window.stateManager.savePageState();
    });

    // Preserve navigation state
    window.stateManager.preserveNavigation();
});

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = StateManager;
}