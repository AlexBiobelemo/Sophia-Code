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

        // Get CSRF token from meta tag or cookie
        let csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
        if (!csrfToken) {
            csrfToken = this.getCookie('csrf_token');
        }

        const response = await fetch('/api/chained-streaming-generation', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken || ''
            },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP error! status: ${response.status} - ${errorText.substring(0, 100)}`);
        }

        return response.body.getReader();
    }
    
    /**
     * Get cookie by name
     */
    getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return null;
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

        // Handle the actual event types sent by the backend
        switch (data.type) {
            case 'pipeline_start':
                this.updateUIState(ui, {
                    status: 'starting',
                    currentStep: 1,
                    stepDescription: 'Initializing code generation...'
                });
                break;

            case 'chunk':
                // Handle code generation chunks
                if (ui.state.currentStep === 1 || !ui.state.currentStep) {
                    ui.state.currentStep = 1;
                    ui.state.codeContent = (ui.state.codeContent || '') + (data.content || '');
                    this.updateUIState(ui, {
                        status: 'generating_code',
                        currentStep: 1,
                        codeContent: ui.state.codeContent
                    });
                    this.emitEvent('codeProgress', { sessionId, data });
                }
                // Handle explanation chunks
                else if (ui.state.currentStep === 2) {
                    ui.state.explanationContent = (ui.state.explanationContent || '') + (data.content || '');
                    this.updateUIState(ui, {
                        status: 'generating_explanation',
                        currentStep: 2,
                        explanationContent: ui.state.explanationContent
                    });
                    this.emitEvent('explanationProgress', { sessionId, data });
                }
                break;

            case 'code_complete':
                this.updateUIState(ui, {
                    status: 'code_complete',
                    currentStep: 2,
                    codeContent: data.content,
                    stepDescription: 'Code generated! Generating explanation...'
                });
                break;

            case 'explanation_complete':
                this.updateUIState(ui, {
                    status: 'complete',
                    currentStep: 2,
                    codeContent: ui.state.codeContent,
                    explanationContent: data.content,
                    stepDescription: 'Generation complete!'
                });
                this.saveFinalResults(sessionId, {
                    code: ui.state.codeContent,
                    explanation: data.content
                });
                this.emitEvent('pipelineComplete', { sessionId, data });
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
                
            case 'stream_end':
                this.handleStreamComplete(sessionId);
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
     * Create streaming UI elements with MODERN design and micro-animations
     */
    createStreamingElements(ui) {
        const { container } = ui;

        container.innerHTML = `
            <div class="ai-generation-result">
                <!-- Success Header -->
                <div class="result-success-header">
                    <div class="success-badge">
                        <div class="checkmark-icon">
                            <i class="bi bi-check-lg"></i>
                        </div>
                        <span>Generation Complete!</span>
                    </div>
                    <div class="header-actions">
                        <button class="btn btn-outline-light btn-sm" onclick="streamingAI.copyCode('${ui.sessionId}')">
                            <i class="bi bi-clipboard me-1"></i>Copy Code
                        </button>
                        <button class="btn btn-outline-info btn-sm" onclick="streamingAI.copyExplanation('${ui.sessionId}')">
                            <i class="bi bi-clipboard me-1"></i>Copy Explanation
                        </button>
                    </div>
                </div>

                <!-- Content Sections -->
                <div class="result-content-section">
                    <!-- Code Section -->
                    <div class="content-section code-section" style="display: none;">
                        <div class="section-title">
                            <i class="bi bi-code-slash"></i>
                            <span>Generated Code</span>
                        </div>
                        <div class="code-block-wrapper">
                            <div class="code-block-header">
                                <span class="code-language-badge">Python</span>
                                <button class="copy-code-btn" onclick="streamingAI.copyCode('${ui.sessionId}')">
                                    <i class="bi bi-clipboard"></i>
                                    <span>Copy</span>
                                </button>
                            </div>
                            <pre><code id="code-content-${ui.sessionId}" class="language-python"></code></pre>
                        </div>
                    </div>

                    <!-- Explanation Section -->
                    <div class="content-section explanation-section" style="display: none;">
                        <div class="section-title">
                            <i class="bi bi-lightbulb"></i>
                            <span>Explanation</span>
                        </div>
                        <div class="explanation-content markdown-content">
                            <div id="explanation-content-${ui.sessionId}"></div>
                        </div>
                    </div>
                </div>

                <!-- Action Buttons -->
                <div class="result-action-buttons" id="actions-${ui.sessionId}" style="display: none;">
                    <button class="btn btn-save" onclick="streamingAI.saveAsSnippet('${ui.sessionId}')">
                        <i class="bi bi-save me-2"></i>Save as Snippet
                    </button>
                    <button class="btn btn-retry" onclick="streamingAI.retryGeneration('${ui.sessionId}')">
                        <i class="bi bi-arrow-clockwise me-1"></i>Retry Generation
                    </button>
                    <button class="btn btn-generate-another" onclick="streamingAI.generateNew('${ui.sessionId}')">
                        <i class="bi bi-plus-circle me-1"></i>Generate Another
                    </button>
                </div>

                <!-- Error Display -->
                <div class="alert alert-danger m-3" id="error-${ui.sessionId}" style="display: none;">
                    <i class="bi bi-exclamation-triangle me-2"></i>
                    <span id="error-message-${ui.sessionId}"></span>
                </div>
            </div>
        `;

        ui.elements = {
            codeSection: container.querySelector('.code-section'),
            explanationSection: container.querySelector('.explanation-section'),
            codeContent: container.querySelector(`#code-content-${ui.sessionId}`),
            explanationContent: container.querySelector(`#explanation-content-${ui.sessionId}`),
            actions: container.querySelector(`#actions-${ui.sessionId}`),
            errorDisplay: container.querySelector(`#error-${ui.sessionId}`),
            errorMessage: container.querySelector(`#error-message-${ui.sessionId}`)
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
     * Render current UI state - MODERN VERSION
     */
    renderUIState(ui) {
        const { elements, state } = ui;
        if (!elements) return;

        // Throttle UI updates to once per frame
        if (ui.renderPending) return;
        ui.renderPending = true;

        requestAnimationFrame(() => {
            // Show code section when content exists
            if (state.codeContent && state.codeContent.trim().length > 0 && elements.codeSection) {
                elements.codeSection.style.display = 'block';
                if (elements.codeContent) {
                    elements.codeContent.textContent = state.codeContent;
                    if (window.Prism) {
                        Prism.highlightElement(elements.codeContent);
                    }
                }
            }

            // Show explanation section when content exists
            if (state.explanationContent && state.explanationContent.trim().length > 0 && elements.explanationSection) {
                elements.explanationSection.style.display = 'block';
                if (elements.explanationContent) {
                    elements.explanationContent.innerHTML = this.renderMarkdown(state.explanationContent);
                }
            }

            // Show actions when complete
            if (state.status === 'complete' && elements.actions) {
                elements.actions.style.display = 'flex';
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
                this.showCopyFeedback(ui.elements.codeSection, 'Code copied!');
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
                this.showCopyFeedback(ui.elements.explanationSection, 'Explanation copied!');
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

            if (ui.elements.codeSection) {
                ui.elements.codeSection.style.display = 'none';
            }
            if (ui.elements.explanationSection) {
                ui.elements.explanationSection.style.display = 'none';
            }
            if (ui.elements.actions) {
                ui.elements.actions.style.display = 'none';
            }

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