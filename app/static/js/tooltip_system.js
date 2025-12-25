/**
 * Tooltip System for MiniMax API Fix
 * Provides hover-based tooltips that auto-disappear when not hovering
 */

class TooltipSystem {
    constructor() {
        this.tooltips = new Map();
        this.hoverTimers = new Map();
        this.autoHideTimers = new Map();
        this.longPressTimers = new Map();
        this.init();
    }

    init() {
        // Create global tooltip container
        this.container = document.createElement('div');
        this.container.id = 'minimax-tooltip-container';
        this.container.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            z-index: 10000;
            pointer-events: none;
        `;
        document.body.appendChild(this.container);
    }

    createTooltip(id, options) {
        const {
            title = '',
            content = '',
            type = 'info',
            position = { x: 0, y: 0 },
            autoHideDelay = 3000,
            persistent = false,
            element = null
        } = options;

        // Remove existing tooltip with same id
        this.removeTooltip(id);

        // Create tooltip element
        const tooltip = document.createElement('div');
        tooltip.className = `minimax-tooltip minimax-tooltip-${type}`;
        tooltip.id = `tooltip-${id}`;
        tooltip.style.cssText = `
            position: absolute;
            background: #2563eb;
            color: white;
            padding: 12px 16px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            max-width: 300px;
            font-size: 14px;
            line-height: 1.4;
            opacity: 0;
            transform: translateY(-5px);
            transition: opacity 0.2s ease, transform 0.2s ease;
            z-index: 10001;
            pointer-events: auto;
        `;

        // Tooltip content structure
        const titleEl = document.createElement('div');
        titleEl.className = 'tooltip-title';
        titleEl.style.cssText = `
            font-weight: bold;
            margin-bottom: 6px;
            font-size: 15px;
        `;
        titleEl.textContent = title;

        const contentEl = document.createElement('div');
        contentEl.className = 'tooltip-content';
        contentEl.style.cssText = `
            font-size: 13px;
            opacity: 0.9;
        `;
        contentEl.textContent = content;

        tooltip.appendChild(titleEl);
        tooltip.appendChild(contentEl);

        // Add arrow
        const arrow = document.createElement('div');
        arrow.className = 'tooltip-arrow';
        arrow.style.cssText = `
            position: absolute;
            width: 0;
            height: 0;
            border-left: 8px solid transparent;
            border-right: 8px solid transparent;
            border-top: 8px solid #2563eb;
            bottom: -8px;
            left: 20px;
        `;
        tooltip.appendChild(arrow);

        // Store tooltip data
        this.tooltips.set(id, {
            element: tooltip,
            position,
            autoHideDelay,
            persistent,
            elementRef: element,
            isVisible: false
        });

        this.container.appendChild(tooltip);
        return tooltip;
    }

    showTooltip(id) {
        const tooltipData = this.tooltips.get(id);
        if (!tooltipData) return;

        const { element, position } = tooltipData;

        // Position tooltip
        element.style.left = `${position.x}px`;
        element.style.top = `${position.y}px`;

        // Show tooltip
        element.style.opacity = '1';
        element.style.transform = 'translateY(0)';
        tooltipData.isVisible = true;

        // Start auto-hide timer if not persistent
        if (!tooltipData.persistent) {
            this.startAutoHideTimer(id);
        }

        console.log(`🔍 Tooltip '${id}' shown and being hovered`);
    }

    hideTooltip(id) {
        const tooltipData = this.tooltips.get(id);
        if (!tooltipData) return;

        const { element } = tooltipData;

        // Hide tooltip
        element.style.opacity = '0';
        element.style.transform = 'translateY(-5px)';
        tooltipData.isVisible = false;

        // Clear auto-hide timer
        this.clearAutoHideTimer(id);

        console.log(`🔍 Tooltip '${id}' hidden (not being hovered)`);
    }

    removeTooltip(id) {
        const tooltipData = this.tooltips.get(id);
        if (tooltipData) {
            // Remove from DOM
            if (tooltipData.element && tooltipData.element.parentNode) {
                tooltipData.element.parentNode.removeChild(tooltipData.element);
            }
            // Clear timers
            this.clearAutoHideTimer(id);
            // Remove from maps
            this.tooltips.delete(id);
        }
    }

    // New method to disable all tooltips when user turns them off
    async disableAllTooltips() {
        console.log('🔍 Disabling all tooltips');

        // Clear all hover timers
        for (const [id, timer] of this.hoverTimers) {
            clearTimeout(timer);
        }
        this.hoverTimers.clear();

        // Clear all auto-hide timers
        for (const [id, timer] of this.autoHideTimers) {
            clearTimeout(timer);
        }
        this.autoHideTimers.clear();

        // Clear all long press timers
        for (const [id, timer] of this.longPressTimers) {
            clearTimeout(timer);
        }
        this.longPressTimers.clear();

        // Remove all tooltips from DOM
        for (const [id] of this.tooltips) {
            this.removeTooltip(id);
        }

        console.log('🔍 All tooltips disabled and cleaned up');
    }

    // New method to reinitialize tooltips when preferences change
    async reinitializeTooltips() {
        console.log('🔍 Reinitializing tooltips based on current preferences');

        // First check if tooltips are enabled
        const tooltipsEnabled = await this.isTooltipsEnabled();

        if (!tooltipsEnabled) {
            // If disabled, clean up everything
            await this.disableAllTooltips();
            return;
        }

        // If enabled, reinitialize the delayed tooltips
        await initializeDelayedTooltips();
    }

    startAutoHideTimer(id) {
        this.clearAutoHideTimer(id);

        const tooltipData = this.tooltips.get(id);
        if (!tooltipData || tooltipData.persistent) return;

        const timer = setTimeout(() => {
            // Only hide if not currently being hovered
            if (!this.isHovered(id)) {
                this.hideTooltip(id);
            }
        }, tooltipData.autoHideDelay);

        this.autoHideTimers.set(id, timer);
    }

    clearAutoHideTimer(id) {
        const timer = this.autoHideTimers.get(id);
        if (timer) {
            clearTimeout(timer);
            this.autoHideTimers.delete(id);
        }
    }

    isHovered(id) {
        const timer = this.hoverTimers.get(id);
        return timer !== undefined;
    }

    async startHover(id, customDelay = null) {
        // First check if tooltips are enabled globally
        const tooltipsEnabled = await this.isTooltipsEnabled();
        if (!tooltipsEnabled) {
            console.log('🔍 Tooltips are disabled by user preferences');
            return; // Exit early if tooltips are disabled
        }

        // Clear any existing hover timer
        this.stopHover(id);

        try {
            // Get user preferences if available
            const userDelay = await this.getUserTooltipDelay();
            const delay = customDelay || userDelay || 3000; // Default to 3 seconds

            // Start hover timer with configured delay
            const timer = setTimeout(() => {
                this.showTooltip(id);
            }, delay);

            this.hoverTimers.set(id, timer);

            console.log(`🔍 Tooltip '${id}' will appear in ${delay / 1000} seconds`);
        } catch (e) {
            console.warn('Error starting hover for tooltip:', id, e);
            // Fallback to default behavior
            const timer = setTimeout(() => {
                this.showTooltip(id);
            }, 3000);
            this.hoverTimers.set(id, timer);
        }
    }

    async getUserTooltipDelay() {
        // Try to get user preferences from server first, then localStorage as fallback
        try {
            // First try to get from server
            const serverPrefs = await this.getUserPreferencesFromServer();
            if (serverPrefs && serverPrefs.tooltip_delay !== undefined) {
                return serverPrefs.tooltip_delay * 1000; // Convert to milliseconds
            }

            // Fallback to localStorage
            const userPrefs = localStorage.getItem('user_preferences');
            if (userPrefs) {
                const prefs = JSON.parse(userPrefs);
                return (prefs.tooltip_delay || 3) * 1000; // Convert to milliseconds
            }
        } catch (e) {
            console.warn('Could not load user tooltip preferences:', e);
        }
        return 3000; // Default 3 seconds
    }

    async isTooltipsEnabled() {
        try {
            // First try to get from server
            const serverPrefs = await this.getUserPreferencesFromServer();
            if (serverPrefs && serverPrefs.enable_tooltips !== undefined) {
                return serverPrefs.enable_tooltips;
            }

            // Fallback to localStorage
            const userPrefs = localStorage.getItem('user_preferences');
            if (userPrefs) {
                const prefs = JSON.parse(userPrefs);
                return prefs.enable_tooltips !== false; // Default to true
            }
        } catch (e) {
            console.warn('Could not load user tooltip preferences:', e);
        }
        return true; // Default to enabled
    }

    async getUserPreferencesFromServer() {
        try {
            const response = await fetch('/api/user-preferences', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin'
            });

            if (response.ok) {
                const data = await response.json();
                if (data.success && data.preferences) {
                    // Cache preferences in localStorage for offline use
                    localStorage.setItem('user_preferences', JSON.stringify(data.preferences));
                    console.log('🔍 Loaded user preferences from server:', data.preferences);
                    return data.preferences;
                }
            } else {
                console.warn('Failed to fetch user preferences from server:', response.status);
            }
        } catch (e) {
            console.warn('Could not fetch user preferences from server:', e);
        }
        return null;
    }

    async loadUserPreferences() {
        try {
            const prefs = await this.getUserPreferencesFromServer();
            if (prefs) {
                // Store in localStorage for offline access
                localStorage.setItem('user_preferences', JSON.stringify(prefs));
                console.log('🔍 Loaded user tooltip preferences:', prefs);
                return prefs;
            }
        } catch (e) {
            console.warn('Could not load user preferences:', e);
        }
        return null;
    }

    // New method for long press detection
    startLongPress(id) {
        // Clear any existing long press timer
        this.stopLongPress(id);

        // Start long press timer - 2 seconds
        const timer = setTimeout(() => {
            this.showTooltip(id);
        }, 2000); // 2 seconds for long press

        this.longPressTimers.set(id, timer);
    }

    stopLongPress(id) {
        const timer = this.longPressTimers.get(id);
        if (timer) {
            clearTimeout(timer);
            this.longPressTimers.delete(id);
        }
    }

    stopHover(id) {
        const timer = this.hoverTimers.get(id);
        if (timer) {
            clearTimeout(timer);
            this.hoverTimers.delete(id);
        }

        // Hide tooltip when hover stops (with small delay)
        setTimeout(() => {
            if (!this.isHovered(id)) {
                this.hideTooltip(id);
            }
        }, 100);
    }

    // Convenience methods for different tooltip types
    async showError(id, title, content, position = { x: 100, y: 100 }, autoHideDelay = 5000) {
        // Check if tooltips are enabled
        const tooltipsEnabled = await this.isTooltipsEnabled();
        if (!tooltipsEnabled) {
            console.log('🔍 Tooltips are disabled, not showing error tooltip');
            return;
        }

        const tooltip = this.createTooltip(id, {
            title,
            content,
            type: 'error',
            position,
            autoHideDelay
        });
        // Start the hover timer with user preferences
        await this.startHover(id);
        return tooltip;
    }

    async showSuccess(id, title, content, position = { x: 100, y: 100 }, autoHideDelay = 3000) {
        // Check if tooltips are enabled
        const tooltipsEnabled = await this.isTooltipsEnabled();
        if (!tooltipsEnabled) {
            console.log('🔍 Tooltips are disabled, not showing success tooltip');
            return;
        }

        const tooltip = this.createTooltip(id, {
            title,
            content,
            type: 'success',
            position,
            autoHideDelay
        });
        // Start the hover timer with user preferences
        await this.startHover(id);
        return tooltip;
    }

    async showWarning(id, title, content, position = { x: 100, y: 100 }, autoHideDelay = 4000) {
        // Check if tooltips are enabled
        const tooltipsEnabled = await this.isTooltipsEnabled();
        if (!tooltipsEnabled) {
            console.log('🔍 Tooltips are disabled, not showing warning tooltip');
            return;
        }

        const tooltip = this.createTooltip(id, {
            title,
            content,
            type: 'warning',
            position,
            autoHideDelay
        });
        // Start the hover timer with user preferences
        await this.startHover(id);
        return tooltip;
    }

    async showInfo(id, title, content, position = { x: 100, y: 100 }, autoHideDelay = 3000) {
        // Check if tooltips are enabled
        const tooltipsEnabled = await this.isTooltipsEnabled();
        if (!tooltipsEnabled) {
            console.log('🔍 Tooltips are disabled, not showing info tooltip');
            return;
        }

        const tooltip = this.createTooltip(id, {
            title,
            content,
            type: 'info',
            position,
            autoHideDelay
        });
        // Start the hover timer with user preferences
        await this.startHover(id);
        return tooltip;
    }

    async showDebug(id, title, content, position = { x: 50, y: 50 }, autoHideDelay = 6000) {
        // Check if tooltips are enabled
        const tooltipsEnabled = await this.isTooltipsEnabled();
        if (!tooltipsEnabled) {
            console.log('🔍 Tooltips are disabled, not showing debug tooltip');
            return;
        }

        const tooltip = this.createTooltip(id, {
            title,
            content,
            type: 'debug',
            position,
            autoHideDelay,
            persistent: true
        });
        // Start the hover timer with user preferences
        await this.startHover(id);
        return tooltip;
    }
}

// Initialize tooltip system
const tooltipSystem = new TooltipSystem();

// Enhanced integration with existing HTML elements
async function initializeDelayedTooltips() {
    // First check if tooltips are enabled for the user
    const tooltipsEnabled = await tooltipSystem.isTooltipsEnabled();
    if (!tooltipsEnabled) {
        console.log('🔍 Tooltips are disabled by user preferences, skipping initialization');
        return;
    }

    // Find all elements with tooltip-related attributes
    const tooltipElements = document.querySelectorAll('[data-bs-toggle="tooltip"], [data-tooltip], [title]');

    // Load user preferences first
    await tooltipSystem.loadUserPreferences();

    tooltipElements.forEach(element => {
        // Skip if already processed
        if (element.hasAttribute('data-tooltip-processed')) return;

        // Get tooltip content
        let tooltipTitle = element.getAttribute('title') || '';
        let tooltipContent = element.getAttribute('data-tooltip') || '';

        // If using Bootstrap tooltip format, extract content
        if (element.hasAttribute('data-bs-toggle') && element.getAttribute('data-bs-toggle') === 'tooltip') {
            tooltipTitle = element.getAttribute('title') || 'Tooltip';
            tooltipContent = element.getAttribute('title') || '';
        }

        // Skip if no tooltip content
        if (!tooltipTitle && !tooltipContent) return;

        // Generate unique ID for this tooltip
        const tooltipId = `delayed_tooltip_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

        // Store original title to prevent browser tooltip
        const originalTitle = element.getAttribute('title');
        if (originalTitle) {
            element.setAttribute('data-original-title', originalTitle);
            element.removeAttribute('title');
        }

        // Mark as processed
        element.setAttribute('data-tooltip-processed', 'true');
        element.setAttribute('data-tooltip-id', tooltipId);

        // Add hover event listeners with user-configured delay
        element.addEventListener('mouseenter', async function (e) {
            // Double-check if tooltips are still enabled
            const tooltipsEnabled = await tooltipSystem.isTooltipsEnabled();
            if (!tooltipsEnabled) {
                return; // Exit early if tooltips are disabled
            }

            // Calculate tooltip position
            const rect = element.getBoundingClientRect();
            const position = {
                x: rect.left + (rect.width / 2),
                y: rect.top - 10
            };

            // Create tooltip
            tooltipSystem.createTooltip(tooltipId, {
                title: tooltipTitle || 'Tooltip',
                content: tooltipContent || tooltipTitle || '',
                type: 'info',
                position: position,
                autoHideDelay: 3000
            });

            // Start hover timer with user preferences
            await tooltipSystem.startHover(tooltipId);
        });

        element.addEventListener('mouseleave', function (e) {
            // Stop hover timer and hide tooltip
            tooltipSystem.stopHover(tooltipId);
        });

        // Also handle touch events for mobile
        element.addEventListener('touchstart', function (e) {
            e.preventDefault();
            const rect = element.getBoundingClientRect();
            const position = {
                x: rect.left + (rect.width / 2),
                y: rect.top - 10
            };

            tooltipSystem.createTooltip(tooltipId, {
                title: tooltipTitle || 'Tooltip',
                content: tooltipContent || tooltipTitle || '',
                type: 'info',
                position: position,
                autoHideDelay: 3000
            });

            // Show immediately on touch
            tooltipSystem.showTooltip(tooltipId);
        });

        element.addEventListener('touchend', function (e) {
            setTimeout(() => {
                tooltipSystem.hideTooltip(tooltipId);
            }, 2000); // Hide after 2 seconds on touch
        });
    });

    console.log(`🔍 Initialized delayed tooltips for ${tooltipElements.length} elements`);
}

// Auto-initialize when DOM is ready
async function initializeTooltipSystem() {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeDelayedTooltips);
    } else {
        await initializeDelayedTooltips();
    }
}

// Initialize the tooltip system
initializeTooltipSystem();

// Also re-initialize when new content is added to the page
const observer = new MutationObserver(async function (mutations) {
    let shouldReinitialize = false;
    mutations.forEach(function (mutation) {
        if (mutation.addedNodes.length > 0) {
            for (let node of mutation.addedNodes) {
                if (node.nodeType === 1) { // Element node
                    if (node.hasAttribute('data-bs-toggle') ||
                        node.hasAttribute('data-tooltip') ||
                        node.hasAttribute('title') ||
                        node.querySelector('[data-bs-toggle="tooltip"], [data-tooltip], [title]')) {
                        shouldReinitialize = true;
                        break;
                    }
                }
            }
        }
    });

    if (shouldReinitialize) {
        // Only reinitialize if tooltips are enabled
        const tooltipsEnabled = await tooltipSystem.isTooltipsEnabled();
        if (tooltipsEnabled) {
            setTimeout(async () => {
                await initializeDelayedTooltips();
            }, 100);
        }
    }
});

// Start observing for dynamic content
if (document.body) {
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
}

// Enhanced MiniMax API functions with tooltips
function createMinimaxTooltip(title, content, type = 'info', position = null, autoHideDelay = 3000) {
    const id = `minimax_tooltip_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    position = position || { x: 100, y: 100 };

    tooltipSystem.createTooltip(id, {
        title,
        content,
        type,
        position,
        autoHideDelay
    });

    return id;
}

async function showMinimaxErrorTooltip(errorDetails) {
    // Check if tooltips are enabled
    const tooltipsEnabled = await tooltipSystem.isTooltipsEnabled();
    if (!tooltipsEnabled) {
        console.log('🔍 Tooltips are disabled, not showing MiniMax error tooltip');
        return;
    }

    const id = createMinimaxTooltip(
        'MiniMax API Error',
        `Error details: ${errorDetails}\n\nHover for troubleshooting tips...`,
        'error',
        null,
        5000
    );
    await tooltipSystem.startHover(id);
    return id;
}

async function showMinimaxSuccessTooltip(successMessage) {
    // Check if tooltips are enabled
    const tooltipsEnabled = await tooltipSystem.isTooltipsEnabled();
    if (!tooltipsEnabled) {
        console.log('🔍 Tooltips are disabled, not showing MiniMax success tooltip');
        return;
    }

    const id = createMinimaxTooltip(
        'MiniMax Success',
        `Operation completed: ${successMessage}`,
        'success',
        null,
        3000
    );
    await tooltipSystem.startHover(id);
    return id;
}

async function showMinimaxWarningTooltip(warningMessage) {
    // Check if tooltips are enabled
    const tooltipsEnabled = await tooltipSystem.isTooltipsEnabled();
    if (!tooltipsEnabled) {
        console.log('🔍 Tooltips are disabled, not showing MiniMax warning tooltip');
        return;
    }

    const id = createMinimaxTooltip(
        'MiniMax Warning',
        `Warning: ${warningMessage}\n\nHover for more details...`,
        'warning',
        null,
        4000
    );
    await tooltipSystem.startHover(id);
    return id;
}

async function showMinimaxDebugTooltip(debugInfo) {
    // Check if tooltips are enabled
    const tooltipsEnabled = await tooltipSystem.isTooltipsEnabled();
    if (!tooltipsEnabled) {
        console.log('🔍 Tooltips are disabled, not showing MiniMax debug tooltip');
        return;
    }

    const id = createMinimaxTooltip(
        'MiniMax Debug Info',
        `Debug information:\n${debugInfo}`,
        'debug',
        { x: 50, y: 50 },
        6000
    );
    await tooltipSystem.startHover(id);
    return id;
}

async function showMinimaxInfoTooltip(infoMessage) {
    // Check if tooltips are enabled
    const tooltipsEnabled = await tooltipSystem.isTooltipsEnabled();
    if (!tooltipsEnabled) {
        console.log('🔍 Tooltips are disabled, not showing MiniMax info tooltip');
        return;
    }

    const id = createMinimaxTooltip(
        'MiniMax Information',
        infoMessage,
        'info',
        null,
        3000
    );
    await tooltipSystem.startHover(id);
    return id;
}

// Add CSS styles for tooltips with liquid glass effects
function addTooltipStyles() {
    const style = document.createElement('style');
    style.textContent = `
        .minimax-tooltip {
            background: linear-gradient(145deg,
                rgba(0, 0, 0, 0.85) 0%,
                rgba(0, 0, 0, 0.7) 50%,
                rgba(0, 0, 0, 0.85) 100%);
            border: 1px solid rgba(255, 255, 255, 0.25);
            border-radius: 14px;
            padding: 14px 18px;
            color: white;
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            box-shadow:
                0 12px 32px rgba(0, 0, 0, 0.4),
                inset 0 0 40px rgba(255, 255, 255, 0.12),
                inset 0 0 80px rgba(255, 255, 255, 0.06);
            max-width: 320px;
            font-size: 14px;
            line-height: 1.4;
            opacity: 0;
            transform: translateY(-12px) scale(0.95);
            transition: all 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
            z-index: 10001;
            pointer-events: auto;
            will-change: transform, opacity;
        }
        
        .minimax-tooltip.show {
            opacity: 1;
            transform: translateY(0) scale(1);
        }
        
        .minimax-tooltip.hide {
            opacity: 0;
            transform: translateY(-12px) scale(0.95);
        }
        
        /* Auto-hide animation with liquid effect */
        @keyframes tooltipFadeOut {
            0% {
                opacity: 1;
                transform: translateY(0) scale(1);
                filter: blur(0px);
            }
            50% {
                opacity: 0.8;
                transform: translateY(-6px) scale(0.98);
                filter: blur(0.5px);
            }
            100% {
                opacity: 0;
                transform: translateY(-12px) scale(0.95);
                filter: blur(1px);
            }
        }
        
        .minimax-tooltip.auto-hide {
            animation: tooltipFadeOut 0.6s ease forwards;
        }
        
        /* Tooltip content styling */
        .minimax-tooltip .tooltip-title {
            font-weight: 700;
            font-size: 14px;
            margin-bottom: 6px;
            color: #ffffff;
            text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
            animation: titleSlideIn 0.4s ease-out 0.1s both;
        }
        
        .minimax-tooltip .tooltip-content {
            font-size: 13px;
            line-height: 1.4;
            color: #e6e6e6;
            opacity: 0.95;
            animation: contentSlideIn 0.4s ease-out 0.2s both;
        }
        
        @keyframes titleSlideIn {
            from {
                opacity: 0;
                transform: translateY(-8px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        @keyframes contentSlideIn {
            from {
                opacity: 0;
                transform: translateY(-6px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        /* Tooltip arrow with liquid effect */
        .tooltip-arrow {
            position: absolute;
            width: 0;
            height: 0;
            border-left: 10px solid transparent;
            border-right: 10px solid transparent;
            border-top: 10px solid;
            border-top-color: rgba(0, 0, 0, 0.85);
            bottom: -8px;
            left: 20px;
            filter: drop-shadow(0 2px 2px rgba(0, 0, 0, 0.3));
            transition: all 0.4s ease;
        }
        
        .minimax-tooltip.show .tooltip-arrow {
            animation: arrowPulse 2s ease-in-out infinite;
        }
        
        @keyframes arrowPulse {
            0%, 100% {
                transform: translateY(0) scale(1);
                opacity: 1;
            }
            50% {
                transform: translateY(-2px) scale(1.05);
                opacity: 0.8;
            }
        }
        
        /* Different tooltip types with liquid glass effects */
        .minimax-tooltip-error {
            background: linear-gradient(145deg,
                rgba(162, 58, 58, 0.9) 0%,
                rgba(162, 58, 58, 0.7) 50%,
                rgba(162, 58, 58, 0.9) 100%);
            border-color: rgba(255, 255, 255, 0.3);
            box-shadow:
                0 12px 32px rgba(162, 58, 58, 0.4),
                inset 0 0 40px rgba(255, 255, 255, 0.15);
        }
        
        .minimax-tooltip-success {
            background: linear-gradient(145deg,
                rgba(25, 135, 84, 0.9) 0%,
                rgba(25, 135, 84, 0.7) 50%,
                rgba(25, 135, 84, 0.9) 100%);
            border-color: rgba(255, 255, 255, 0.3);
            box-shadow:
                0 12px 32px rgba(25, 135, 84, 0.4),
                inset 0 0 40px rgba(255, 255, 255, 0.15);
        }
        
        .minimax-tooltip-warning {
            background: linear-gradient(145deg,
                rgba(181, 134, 0, 0.9) 0%,
                rgba(181, 134, 0, 0.7) 50%,
                rgba(181, 134, 0, 0.9) 100%);
            border-color: rgba(255, 255, 255, 0.3);
            box-shadow:
                0 12px 32px rgba(181, 134, 0, 0.4),
                inset 0 0 40px rgba(255, 255, 255, 0.15);
        }
        
        .minimax-tooltip-info {
            background: linear-gradient(145deg,
                rgba(30, 91, 184, 0.9) 0%,
                rgba(30, 91, 184, 0.7) 50%,
                rgba(30, 91, 184, 0.9) 100%);
            border-color: rgba(255, 255, 255, 0.3);
            box-shadow:
                0 12px 32px rgba(30, 91, 184, 0.4),
                inset 0 0 40px rgba(255, 255, 255, 0.15);
        }
        
        .minimax-tooltip-debug {
            background: linear-gradient(145deg,
                rgba(124, 58, 237, 0.9) 0%,
                rgba(124, 58, 237, 0.7) 50%,
                rgba(124, 58, 237, 0.9) 100%);
            border-color: rgba(255, 255, 255, 0.3);
            box-shadow:
                0 12px 32px rgba(124, 58, 237, 0.4),
                inset 0 0 40px rgba(255, 255, 255, 0.15);
        }
        
        /* Tooltip hover interaction for extended visibility */
        .minimax-tooltip.interactive {
            pointer-events: auto;
            opacity: 1;
            transform: translateY(0) scale(1);
        }
        
        .minimax-tooltip.interactive:hover {
            transform: translateY(-2px) scale(1.02);
            box-shadow:
                0 16px 40px rgba(0, 0, 0, 0.5),
                inset 0 0 50px rgba(255, 255, 255, 0.2);
        }
        
        /* Tooltip positioning variants */
        .minimax-tooltip.position-top {
            transform-origin: bottom center;
        }
        
        .minimax-tooltip.position-bottom {
            transform-origin: top center;
        }
        
        .minimax-tooltip.position-left {
            transform-origin: center right;
        }
        
        .minimax-tooltip.position-right {
            transform-origin: center left;
        }
        
        /* Liquid ripple effect on tooltip creation */
        @keyframes tooltipRipple {
            0% {
                opacity: 0;
                transform: translateY(-12px) scale(0.9);
                filter: blur(2px);
            }
            50% {
                opacity: 0.8;
                transform: translateY(-6px) scale(0.95);
                filter: blur(1px);
            }
            100% {
                opacity: 1;
                transform: translateY(0) scale(1);
                filter: blur(0px);
            }
        }
        
        .minimax-tooltip.ripple-in {
            animation: tooltipRipple 0.5s ease-out;
        }
    `;
    document.head.appendChild(style);
}

// Initialize styles
addTooltipStyles();

// Export for use in other modules
window.MinimaxTooltips = {
    tooltipSystem,
    createMinimaxTooltip,
    showMinimaxErrorTooltip,
    showMinimaxSuccessTooltip,
    showMinimaxWarningTooltip,
    showMinimaxDebugTooltip,
    showMinimaxInfoTooltip,
    initializeDelayedTooltips,
    // Add new methods to the export
    reinitializeTooltips: () => tooltipSystem.reinitializeTooltips(),
    disableAllTooltips: () => tooltipSystem.disableAllTooltips()
};

// Override Bootstrap tooltips to use delayed system
function overrideBootstrapTooltips() {
    // Disable Bootstrap tooltips for elements we're handling
    const style = document.createElement('style');
    style.textContent = `
        [data-tooltip-processed="true"] + .tooltip,
        [data-tooltip-processed="true"] .tooltip,
        [data-tooltip-processed="true"][data-bs-toggle="tooltip"] {
            display: none !important;
        }
    `;
    document.head.appendChild(style);
}

// Initialize override
overrideBootstrapTooltips();