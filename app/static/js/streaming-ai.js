/**
 * Streaming AI Pipeline - Client-side implementation for Token-Efficient Chaining
 * Handles real-time streaming of AI responses with state management and UI updates.
 */

class StreamingAIManager {
    constructor() {
        this.activeStreams = new Map();
        this.sessionData = new Map();
        this.eventHandlers = new Map();
        this.retryConfig = {
            maxRetries: 3,
            retryDelay: 1000,
            backoffMultiplier: 2
        };
        // Detect current theme
        this.isDarkMode = document.documentElement.getAttribute('data-bs-theme') === 'dark';
    }

    /**
     * Initialize streaming AI manager
     */
    init() {
        console.log('Streaming AI Manager initialized');
        this.setupEventListeners();
        this.loadModelTieringConfig();
        // Watch for theme changes
        this.watchThemeChanges();
    }

    /**
     * Watch for theme changes and update accordingly
     */
    watchThemeChanges() {
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === 'attributes' && mutation.attributeName === 'data-bs-theme') {
                    this.isDarkMode = document.documentElement.getAttribute('data-bs-theme') === 'dark';
                    this.updateThemeForActiveStreams();
                }
            });
        });
        
        observer.observe(document.documentElement, {
            attributes: true,
            attributeFilter: ['data-bs-theme']
        });
    }

    /**
     * Update theme for all active streams
     */
    updateThemeForActiveStreams() {
        this.activeStreams.forEach((ui) => {
            this.applyThemeToElements(ui);
        });
    }

    /**
     * Apply current theme to streaming UI elements
     */
    applyThemeToElements(ui) {
        if (!ui || !ui.elements) return;
        
        const elements = ui.elements;
        const themeClass = this.isDarkMode ? 'text-light' : 'text-dark';
        const oppositeClass = this.isDarkMode ? 'text-dark' : 'text-light';
        
        // Update step description
        if (elements.stepDesc) {
            elements.stepDesc.classList.remove(oppositeClass);
            elements.stepDesc.classList.add(themeClass);
        }
        
        // Update status text
        if (elements.statusText) {
            elements.statusText.classList.remove(oppositeClass);
            elements.statusText.classList.add(themeClass);
        }
        
        // Update explanation content
        if (elements.explanationContent) {
            elements.explanationContent.classList.remove(oppositeClass);
            elements.explanationContent.classList.add(themeClass);
            
            // Update markdown content container
            const markdownContainer = elements.explanationContent.parentElement;
            if (markdownContainer) {
                if (this.isDarkMode) {
                    markdownContainer.classList.add('markdown-dark-mode');
                    markdownContainer.classList.remove('markdown-light-mode');
                } else {
                    markdownContainer.classList.add('markdown-light-mode');
                    markdownContainer.classList.remove('markdown-dark-mode');
                }
            }
        }
        
        // Update code content
        if (elements.codeContent) {
            elements.codeContent.classList.remove(oppositeClass);
            elements.codeContent.classList.add(themeClass);
        }
    }

    /**
     * Set up global event listeners for streaming events
     */
    setupEventListeners() {
        // Handle beforeunload to clean up active streams
        window.addEventListener('beforeunload', () => {
            this.cleanupAllStreams();
        });

        // Handle visibility change to pause/resume streams if needed
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.pauseAllStreams();
            } else {
                this.resumeAllStreams();
            }
        });
    }

    /**
     * Load model tiering configuration from server
     */
    async loadModelTieringConfig() {
        try {
            const response = await fetch('/api/model-tiering-config');
            const data = await response.json();
            if (data.success) {
                this.modelConfig = data.config;
                console.log('Model tiering config loaded:', this.modelConfig);
            }
        } catch (error) {
            console.warn('Failed to load model tiering config:', error);
        }
    }

    /**
     * Start chained streaming generation (token-efficient pipeline)
     */
    async startChainedStreaming(prompt, options = {}) {
        const sessionId = options.sessionId || this.generateSessionId();
        const codeModel = options.codeModel;
        const explanationModel = options.explanationModel;

        console.log('Starting chained streaming with session:', sessionId);

        try {
            // Set up UI first
            const ui = this.setupStreamingUI(sessionId, options.containerId);

            // Store the original prompt for retry functionality
            ui.originalPrompt = prompt;

            // Create stream
            const stream = await this.createChainedStream(prompt, sessionId, codeModel, explanationModel);

            // Process stream
            await this.processChainedStream(stream, sessionId, options);

            return sessionId;
        } catch (error) {
            console.error('Failed to start chained streaming:', error);
            this.handleStreamError(sessionId, error);
            throw error;
        }
    }

    /**
     * Create chained streaming connection
     */
    async createChainedStream(prompt, sessionId, codeModel, explanationModel) {
        const requestBody = {
            prompt: prompt,
            session_id: sessionId,
            code_model: codeModel,
            explanation_model: explanationModel
        };

        const response = await fetch('/api/chained-streaming-generation', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return response.body.getReader();
    }

    /**
     * Process chained streaming response
     */
    async processChainedStream(reader, sessionId, options) {
        const decoder = new TextDecoder();
        let buffer = '';
        let isProcessing = true;

        try {
            while (isProcessing) {
                const { done, value } = await reader.read();

                if (done) {
                    isProcessing = false;
                    this.handleStreamComplete(sessionId);
                    break;
                }

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            await this.handleStreamChunk(sessionId, data, options);
                        } catch (parseError) {
                            console.warn('Failed to parse streaming data:', parseError);
                        }
                    }
                }
            }
        } catch (error) {
            console.error('Stream processing error:', error);
            this.handleStreamError(sessionId, error);
        } finally {
            reader.releaseLock();
        }
    }

    /**
     * Handle individual streaming chunks
     */
    async handleStreamChunk(sessionId, data, options) {
        const ui = this.getStreamingUI(sessionId);
        if (!ui) return;

        switch (data.type) {
            case 'pipeline_start':
                this.updateUIState(ui, {
                    status: 'starting',
                    currentStep: 1,
                    stepDescription: 'Initializing code generation...'
                });
                break;

            case 'code_progress':
                this.updateUIState(ui, {
                    status: 'generating_code',
                    currentStep: 1,
                    codeContent: data.accumulated,
                    progress: data.progress
                });
                this.emitEvent('codeProgress', { sessionId, data });
                break;

            case 'step_complete':
                if (data.step === 1) {
                    this.updateUIState(ui, {
                        status: 'code_complete',
                        currentStep: 2,
                        stepDescription: 'Code generated successfully. Starting explanation...'
                    });
                }
                break;

            case 'pipeline_progress':
                this.updateUIState(ui, {
                    status: 'generating_explanation',
                    currentStep: 2,
                    stepDescription: 'Generating explanation...'
                });
                break;

            case 'explanation_progress':
                this.updateUIState(ui, {
                    status: 'generating_explanation',
                    currentStep: 2,
                    explanationContent: data.accumulated,
                    progress: data.progress
                });
                this.emitEvent('explanationProgress', { sessionId, data });
                break;

            case 'pipeline_complete':
                this.updateUIState(ui, {
                    status: 'complete',
                    currentStep: 2,
                    codeContent: data.code,
                    explanationContent: data.explanation,
                    optimizations: data.optimizations,
                    stepDescription: 'Generation complete!'
                });
                this.saveFinalResults(sessionId, data);
                this.emitEvent('pipelineComplete', { sessionId, data });
                break;

            case 'error':
                this.handleStreamError(sessionId, new Error(data.error));
                break;
        }
    }

    /**
     * Set up streaming UI for a session
     */
    setupStreamingUI(sessionId, containerId) {
        const container = document.getElementById(containerId) || this.createDefaultContainer();

        const ui = {
            sessionId,
            container,
            elements: {},
            state: {
                status: 'initializing',
                currentStep: 0,
                codeContent: '',
                explanationContent: '',
                progress: ''
            }
        };

        this.createStreamingElements(ui);
        this.activeStreams.set(sessionId, ui);

        return ui;
    }

    /**
     * Create default container if none specified
     */
    createDefaultContainer() {
        const container = document.createElement('div');
        container.id = `streaming-ui-${Date.now()}`;
        container.className = 'streaming-ai-container';

        const generateButton = document.getElementById('generateButton');
        if (generateButton) {
            generateButton.parentNode.insertBefore(container, generateButton.nextSibling);
        } else {
            const mainContent = document.querySelector('.container, .row, main');
            if (mainContent) {
                mainContent.insertBefore(container, mainContent.firstChild);
            } else {
                document.body.insertBefore(container, document.body.firstChild);
            }
        }

        return container;
    }

    /**
     * Create streaming UI elements
     */
    createStreamingElements(ui) {
        const { container } = ui;
        const themeClass = this.isDarkMode ? 'text-light' : 'text-dark';
        const markdownThemeClass = this.isDarkMode ? 'markdown-dark-mode' : 'markdown-light-mode';

        container.innerHTML = `
            <div class="streaming-ai-panel card">
                <div class="card-header d-flex justify-content-between align-items-center flex-wrap">
                    <h5 class="mb-0 ${themeClass}">
                        <i class="fas fa-stream me-2"></i>Token-Efficient AI Generation
                        <small class="text-muted ms-2">(Streaming)</small>
                    </h5>
                    <div class="streaming-controls d-flex gap-2">
                        <button class="btn btn-sm btn-outline-secondary" onclick="streamingAI.pauseStream('${ui.sessionId}')"
                                data-bs-toggle="tooltip" title="Pause the streaming generation">
                            <i class="fas fa-pause"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-danger" onclick="streamingAI.stopStream('${ui.sessionId}')"
                                data-bs-toggle="tooltip" title="Stop the streaming generation">
                            <i class="fas fa-stop"></i>
                        </button>
                    </div>
                </div>

                <div class="card-body">
                    <div class="mb-3">
                        <div class="d-flex justify-content-between align-items-center mb-2 flex-wrap gap-2">
                            <span class="step-indicator ${themeClass}">
                                <span class="step-number">1</span> Code Generation
                                <i class="fas fa-arrow-right mx-2 text-muted"></i>
                                <span class="step-number">2</span> Explanation
                            </span>
                            <span class="status-text ${themeClass}" id="status-${ui.sessionId}">Initializing...</span>
                        </div>
                        <div class="progress" style="height: 6px;">
                            <div class="progress-bar progress-bar-striped progress-bar-animated"
                                 role="progressbar" style="width: 0%" id="progress-${ui.sessionId}"></div>
                        </div>
                    </div>

                    <div class="step-description mb-3 ${themeClass}">
                        <i class="fas fa-info-circle text-primary me-2"></i>
                        <span id="step-desc-${ui.sessionId}" class="${themeClass}">Preparing pipeline...</span>
                    </div>

                    <div class="token-efficiency mb-3">
                        <div class="alert ${this.isDarkMode ? 'alert-info' : 'alert-light'} py-2 mb-0">
                            <small class="${this.isDarkMode ? 'text-dark' : 'text-dark'}">
                                <i class="fas fa-lightbulb me-1"></i>
                                <strong>Token-Efficient Mode:</strong>
                                <span id="token-benefits-${ui.sessionId}">
                                    Generating optimized prompts to reduce token usage by ~40%
                                </span>
                            </small>
                        </div>
                    </div>

                    <div class="code-output mb-3" style="display: none;">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <h6 class="mb-0 ${themeClass}">
                                <i class="fas fa-code me-2 text-success"></i>Generated Code
                            </h6>
                            <button class="btn btn-sm btn-outline-success" onclick="streamingAI.copyCode('${ui.sessionId}')">
                                <i class="fas fa-copy me-1"></i>Copy
                            </button>
                        </div>
                        <pre class="${this.isDarkMode ? 'bg-dark text-light' : 'bg-light text-dark'} p-3 rounded" style="max-height: 300px; overflow-y: auto;">
                            <code id="code-content-${ui.sessionId}" class="${themeClass}"></code>
                        </pre>
                    </div>

                    <div class="explanation-output" style="display: none;">
                        <div class="d-flex justify-content-between align-items-center mb-2 flex-wrap gap-2">
                            <h6 class="mb-0 ${themeClass}">
                                <i class="fas fa-book me-2 text-info"></i>Explanation
                            </h6>
                            <button class="btn btn-sm btn-outline-info" onclick="streamingAI.copyExplanation('${ui.sessionId}')">
                                <i class="fas fa-copy me-1"></i>Copy
                            </button>
                        </div>
                        <div class="markdown-content ${this.isDarkMode ? 'bg-dark text-light' : 'bg-light text-dark'} p-3 rounded border ${markdownThemeClass}" style="max-height: 400px; overflow-y: auto; border-color: var(--bs-border-color) !important;">
                            <div id="explanation-content-${ui.sessionId}" class="${themeClass}" style="color: inherit !important;"></div>
                        </div>
                    </div>

                    <div class="action-buttons mt-3" style="display: none;" id="actions-${ui.sessionId}">
                        <div class="d-flex flex-wrap gap-2">
                            <button class="btn btn-success" onclick="streamingAI.saveAsSnippet('${ui.sessionId}')">
                                <i class="fas fa-save me-1"></i>Save as Snippet
                            </button>
                            <button class="btn btn-warning" onclick="streamingAI.retryGeneration('${ui.sessionId}')">
                                <i class="fas fa-redo me-1"></i>Retry Generation
                            </button>
                            <button class="btn btn-outline-primary" onclick="streamingAI.generateNew('${ui.sessionId}')">
                                <i class="fas fa-plus me-1"></i>Generate Another
                            </button>
                        </div>
                    </div>

                    <div class="error-display alert alert-danger" style="display: none;" id="error-${ui.sessionId}">
                        <h6 class="${themeClass}"><i class="fas fa-exclamation-triangle me-2"></i>Generation Error</h6>
                        <p class="mb-0 ${themeClass}" id="error-message-${ui.sessionId}"></p>
                    </div>
                </div>
            </div>
        `;

        ui.elements = {
            progressBar: container.querySelector(`#progress-${ui.sessionId}`),
            statusText: container.querySelector(`#status-${ui.sessionId}`),
            stepDesc: container.querySelector(`#step-desc-${ui.sessionId}`),
            codeOutput: container.querySelector('.code-output'),
            explanationOutput: container.querySelector('.explanation-output'),
            codeContent: container.querySelector(`#code-content-${ui.sessionId}`),
            explanationContent: container.querySelector(`#explanation-content-${ui.sessionId}`),
            actions: container.querySelector(`#actions-${ui.sessionId}`),
            errorDisplay: container.querySelector(`#error-${ui.sessionId}`),
            errorMessage: container.querySelector(`#error-message-${ui.sessionId}`),
            tokenBenefits: container.querySelector(`#token-benefits-${ui.sessionId}`)
        };
    }

    /**
     * Update UI state based on streaming data
     */
    updateUIState(ui, newState) {
        ui.state = { ...ui.state, ...newState };
        this.renderUIState(ui);
    }

    /**
     * Render current UI state
     */
    renderUIState(ui) {
        const { elements, state } = ui;
        if (!elements) return;

        // Throttle UI updates to once per frame
        if (ui.renderPending) return;
        ui.renderPending = true;
        
        requestAnimationFrame(() => {
            // Update progress
            if (elements.progressBar) {
                const progressPercent = state.currentStep === 1 ? 50 : 100;
                elements.progressBar.style.width = `${progressPercent}%`;
                elements.progressBar.setAttribute('aria-valuenow', progressPercent);
            }

            // Update status
            if (elements.statusText) {
                const statusMap = {
                    'starting': 'Initializing...',
                    'generating_code': 'Generating code...',
                    'code_complete': 'Code generated ✓',
                    'generating_explanation': 'Generating explanation...',
                    'complete': 'Complete!',
                    'error': 'Error occurred'
                };
                elements.statusText.textContent = statusMap[state.status] || state.status;
            }

            // Update step description
            if (elements.stepDesc && state.stepDescription) {
                elements.stepDesc.textContent = state.stepDescription;
            }

            // Show/hide outputs
            if (state.codeContent && elements.codeOutput) {
                elements.codeOutput.style.display = 'block';
                elements.codeContent.textContent = state.codeContent;
            }

            if (state.explanationContent && elements.explanationOutput) {
                elements.explanationOutput.style.display = 'block';
                elements.explanationContent.innerHTML = this.renderMarkdown(state.explanationContent);
                elements.explanationContent.classList.add('markdown-dark-mode');
            }

            // Show actions when complete
            if (state.status === 'complete' && elements.actions) {
                elements.actions.style.display = 'block';
            }

            // Update token benefits
            if (elements.tokenBenefits && state.optimizations) {
                const benefits = [];
                if (state.optimizations.token_efficient) benefits.push('~40% fewer tokens');
                if (state.optimizations.context_pruned) benefits.push('context optimized');
                if (state.optimizations.streaming_enabled) benefits.push('real-time streaming');

                elements.tokenBenefits.textContent = `Optimized: ${benefits.join(', ')}`;
            }
            
            ui.renderPending = false;
        });
    }

    /**
     * Handle stream completion
     */
    handleStreamComplete(sessionId) {
        console.log('Stream completed for session:', sessionId);

        setTimeout(() => {
            const ui = this.getStreamingUI(sessionId);
            if (ui) {
                this.updateUIState(ui, {
                    status: 'complete',
                    stepDescription: 'Pipeline completed successfully!'
                });
            }
        }, 500);
    }

    /**
     * Handle stream errors
     */
    handleStreamError(sessionId, error) {
        console.error('Stream error for session:', sessionId, error);

        const ui = this.getStreamingUI(sessionId);
        if (ui && ui.elements) {
            ui.elements.errorDisplay.style.display = 'block';
            ui.elements.errorMessage.textContent = error.message || 'An unknown error occurred';
            this.updateUIState(ui, { status: 'error' });
        }

        this.emitEvent('streamError', { sessionId, error });
    }

    /**
     * Save final results to session storage
     */
    saveFinalResults(sessionId, data) {
        const results = {
            sessionId,
            timestamp: new Date().toISOString(),
            code: data.code,
            explanation: data.explanation,
            optimizations: data.optimizations
        };

        // Store in sessionStorage for client-side access
        sessionStorage.setItem(`streaming_result_${sessionId}`, JSON.stringify(results));
        this.sessionData.set(sessionId, results);
        
        // Also save to server session via API to avoid URL size limits
        this.saveToServerSession(sessionId, results);
    }

    /**
     * Save results to server session storage
     */
    async saveToServerSession(sessionId, data) {
        try {
            const response = await fetch('/api/save_streaming_result', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: sessionId,
                    code: data.code,
                    explanation: data.explanation
                })
            });
            
            if (response.ok) {
                const result = await response.json();
                // Store the code key for later retrieval
                this.serverSessionKey = result.code_key;
                console.log('Saved to server session with key:', result.code_key);
            }
        } catch (error) {
            console.error('Failed to save to server session:', error);
        }
    }

    /**
     * Get streaming UI for session
     */
    getStreamingUI(sessionId) {
        return this.activeStreams.get(sessionId);
    }

    /**
     * Copy code to clipboard
     */
    async copyCode(sessionId) {
        const ui = this.getStreamingUI(sessionId);
        if (ui && ui.state.codeContent) {
            try {
                await navigator.clipboard.writeText(ui.state.codeContent);
                this.showCopyFeedback(ui.elements.codeOutput, 'Code copied!');
            } catch (error) {
                console.error('Failed to copy code:', error);
            }
        }
    }

    /**
     * Copy explanation to clipboard
     */
    async copyExplanation(sessionId) {
        const ui = this.getStreamingUI(sessionId);
        if (ui && ui.state.explanationContent) {
            try {
                // Strip HTML for plain text clipboard
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = this.renderMarkdown(ui.state.explanationContent);
                await navigator.clipboard.writeText(tempDiv.textContent || tempDiv.innerText || '');
                this.showCopyFeedback(ui.elements.explanationOutput, 'Explanation copied!');
            } catch (error) {
                console.error('Failed to copy explanation:', error);
            }
        }
    }

    /**
     * Show copy feedback
     */
    showCopyFeedback(element, message) {
        const feedback = document.createElement('div');
        feedback.className = 'copy-feedback alert alert-success py-1 px-2 mb-2';
        feedback.style.fontSize = '0.875rem';
        feedback.textContent = message;

        const container = element.closest('.card-body') || element.parentElement;
        if (container) {
            container.insertBefore(feedback, container.firstChild);
            setTimeout(() => {
                feedback.style.opacity = '0';
                setTimeout(() => feedback.remove(), 300);
            }, 2000);
        }
    }

    /**
     * Save as snippet - uses server session to avoid URL size limits
     */
    saveAsSnippet(sessionId) {
        const results = this.sessionData.get(sessionId);
        if (!results) {
            alert('No generated code found. Please wait for generation to complete.');
            return;
        }
        
        // If we have a server session key, use it to save
        if (this.serverSessionKey) {
            // Create a form and submit with the key
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = '/save_streaming_as_snippet';
            
            const keyInput = document.createElement('input');
            keyInput.type = 'hidden';
            keyInput.name = 'code_key';
            keyInput.value = this.serverSessionKey;
            
            const codeInput = document.createElement('input');
            codeInput.type = 'hidden';
            codeInput.name = 'code';
            codeInput.value = results.code;
            
            const explanationInput = document.createElement('input');
            explanationInput.type = 'hidden';
            explanationInput.name = 'explanation';
            explanationInput.value = results.explanation;
            
            form.appendChild(keyInput);
            form.appendChild(codeInput);
            form.appendChild(explanationInput);
            document.body.appendChild(form);
            form.submit();
        } else {
            // Fallback: save directly via POST with form
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = '/save_streaming_as_snippet';
            
            const codeInput = document.createElement('input');
            codeInput.type = 'hidden';
            codeInput.name = 'code';
            codeInput.value = results.code;
            
            const explanationInput = document.createElement('input');
            explanationInput.type = 'hidden';
            explanationInput.name = 'explanation';
            explanationInput.value = results.explanation;
            
            form.appendChild(codeInput);
            form.appendChild(explanationInput);
            document.body.appendChild(form);
            form.submit();
        }
    }

    /**
     * Generate new (reset UI)
     */
    generateNew(sessionId) {
        this.stopStream(sessionId);
        window.location.reload();
    }

    /**
     * Retry generation with the same prompt
     */
    async retryGeneration(sessionId) {
        const ui = this.getStreamingUI(sessionId);
        if (!ui || !ui.originalPrompt) return;

        try {
            this.updateUIState(ui, {
                status: 'starting',
                currentStep: 0,
                stepDescription: 'Retrying generation...',
                codeContent: '',
                explanationContent: ''
            });

            ui.elements.codeOutput.style.display = 'none';
            ui.elements.explanationOutput.style.display = 'none';
            ui.elements.actions.style.display = 'none';

            await this.startChainedStreaming(ui.originalPrompt, {
                sessionId: sessionId,
                containerId: ui.container.id
            });

        } catch (error) {
            this.handleStreamError(sessionId, error);
        }
    }

    /**
     * Pause stream
     */
    pauseStream(sessionId) {
        console.log('Pausing stream:', sessionId);
    }

    /**
     * Stop stream
     */
    stopStream(sessionId) {
        const ui = this.activeStreams.get(sessionId);
        if (ui) {
            ui.container.remove();
            this.activeStreams.delete(sessionId);
        }
    }

    /**
     * Clean up all streams
     */
    cleanupAllStreams() {
        for (const [sessionId, ui] of this.activeStreams) {
            this.stopStream(sessionId);
        }
    }

    /**
     * Pause all streams
     */
    pauseAllStreams() {
        for (const [sessionId, ui] of this.activeStreams) {
            this.pauseStream(sessionId);
        }
    }

    /**
     * Resume all streams
     */
    resumeAllStreams() {
        console.log('Resuming all streams');
    }

    /**
     * Generate unique session ID
     */
    generateSessionId() {
        return `stream_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    /**
     * Render markdown content
     */
    renderMarkdown(content) {
        if (typeof marked !== 'undefined') {
            try {
                return marked.parse(content);
            } catch (error) {
                console.warn('Markdown rendering failed:', error);
            }
        }
        return content.replace(/\n/g, '<br>');
    }

    /**
     * Event system for external listeners
     */
    on(event, handler) {
        if (!this.eventHandlers.has(event)) {
            this.eventHandlers.set(event, []);
        }
        this.eventHandlers.get(event).push(handler);
    }

    /**
     * Emit events to handlers
     */
    emitEvent(event, data) {
        const handlers = this.eventHandlers.get(event);
        if (handlers) {
            handlers.forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    console.error('Event handler error:', error);
                }
            });
        }
    }
}

// Initialize streaming AI manager
document.addEventListener('DOMContentLoaded', () => {
    window.streamingAI = new StreamingAIManager();
    window.streamingAI.init();
});