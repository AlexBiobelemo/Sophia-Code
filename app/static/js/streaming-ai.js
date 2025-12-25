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
    }

    /**
     * Initialize streaming AI manager
     */
    init() {
        console.log('Streaming AI Manager initialized');
        this.setupEventListeners();
        this.loadModelTieringConfig();

        // Initialize Bootstrap tooltips
        this.initTooltips();
    }

    /**
     * Initialize Bootstrap tooltips
     */
    initTooltips() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                this.initializeTooltips();
            });
        } else {
            this.initializeTooltips();
        }
    }

    /**
     * Initialize tooltips for dynamically created elements
     */
    initializeTooltips() {
        var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        // Tooltips are now handled by the custom tooltip system with 3-second delay
        // No need for Bootstrap tooltip initialization - our system handles all tooltips automatically
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

        // Initialize tooltips for the newly created elements
        this.initializeTooltips();

        return ui;
    }

    /**
     * Create default container if none specified
     */
    createDefaultContainer() {
        const container = document.createElement('div');
        container.id = `streaming-ui-${Date.now()}`;
        container.className = 'streaming-ai-container';

        // Insert after the generate button or at the top of the main content
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

        container.innerHTML = `
            <div class="streaming-ai-panel card">
                <div class="card-header d-flex justify-content-between align-items-center flex-wrap">
                    <h5 class="mb-0">
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
                    <!-- Progress indicator -->
                    <div class="mb-3">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <span class="step-indicator text-light">
                                <span class="step-number text-light">1</span> Code Generation
                                <i class="fas fa-arrow-right mx-2 text-muted"></i>
                                <span class="step-number text-light">2</span> Explanation
                            </span>
                            <span class="status-text" id="status-${ui.sessionId}">Initializing...</span>
                        </div>
                        <div class="progress" style="height: 6px;">
                            <div class="progress-bar progress-bar-striped progress-bar-animated" 
                                 role="progressbar" style="width: 0%" id="progress-${ui.sessionId}"></div>
                        </div>
                    </div>

                    <!-- Current step description -->
                    <div class="step-description mb-3 text-light">
                        <i class="fas fa-info-circle text-primary me-2"></i>
                        <span id="step-desc-${ui.sessionId}" class="text-light">Preparing pipeline...</span>
                    </div>

                    <!-- Token efficiency indicator -->
                    <div class="token-efficiency mb-3">
                        <div class="alert alert-info py-2 mb-0">
                            <small class="text-dark">
                                <i class="fas fa-lightbulb me-1"></i>
                                <strong>Token-Efficient Mode:</strong> 
                                <span id="token-benefits-${ui.sessionId}" class="text-dark">
                                    Generating optimized prompts to reduce token usage by ~40%
                                </span>
                            </small>
                        </div>
                    </div>

                    <!-- Code output -->
                    <div class="code-output mb-3" style="display: none;">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <h6 class="mb-0">
                                <i class="fas fa-code me-2 text-success"></i>Generated Code
                                <small class="text-muted ms-2">(Step 1/2)</small>
                            </h6>
                            <button class="btn btn-sm btn-outline-success" onclick="streamingAI.copyCode('${ui.sessionId}')"
                                    data-bs-toggle="tooltip" title="Copy generated code to clipboard">
                                <i class="fas fa-copy me-1"></i>Copy
                            </button>
                        </div>
                        <pre class="bg-dark text-light p-3 rounded" style="max-height: 300px; overflow-y: auto;">
                            <code id="code-content-${ui.sessionId}"></code>
                        </pre>
                    </div>

                    <!-- Explanation output -->
                    <div class="explanation-output" style="display: none;">
                        <div class="d-flex justify-content-between align-items-center mb-2 flex-wrap">
                            <h6 class="mb-0 text-light">
                                <i class="fas fa-book me-2 text-info"></i>Explanation
                                <small class="text-muted ms-2">(Step 2/2)</small>
                            </h6>
                            <button class="btn btn-sm btn-outline-info" onclick="streamingAI.copyExplanation('${ui.sessionId}')"
                                    data-bs-toggle="tooltip" title="Copy explanation to clipboard">
                                <i class="fas fa-copy me-1"></i>Copy
                            </button>
                        </div>
                        <div class="markdown-content bg-dark text-light p-3 rounded border" style="max-height: 400px; overflow-y: auto; border-color: var(--bs-border-color) !important;">
                            <div id="explanation-content-${ui.sessionId}" class="text-light" style="color: inherit !important;"></div>
                        </div>
                    </div>

                    <!-- Action buttons (shown when complete) -->
                    <div class="action-buttons mt-3" style="display: none;" id="actions-${ui.sessionId}">
                        <div class="d-flex flex-wrap gap-2">
                            <button class="btn btn-success" onclick="streamingAI.saveAsSnippet('${ui.sessionId}')"
                                    data-bs-toggle="tooltip" title="Save generated code as a snippet">
                                <i class="fas fa-save me-1"></i>Save as Snippet
                            </button>
                            <button class="btn btn-warning" onclick="streamingAI.retryGeneration('${ui.sessionId}')"
                                    data-bs-toggle="tooltip" title="Retry generation with the same prompt">
                                <i class="fas fa-redo me-1"></i>Retry Generation
                            </button>
                            <button class="btn btn-outline-primary" onclick="streamingAI.generateNew('${ui.sessionId}')"
                                    data-bs-toggle="tooltip" title="Start a new generation">
                                <i class="fas fa-plus me-1"></i>Generate Another
                            </button>
                            <button class="btn btn-outline-secondary" onclick="streamingAI.shareResults('${ui.sessionId}')"
                                    data-bs-toggle="tooltip" title="Share results with others">
                                <i class="fas fa-share me-1"></i>Share
                            </button>
                        </div>
                    </div>

                    <!-- Error display -->
                    <div class="error-display alert alert-danger" style="display: none;" id="error-${ui.sessionId}">
                        <h6><i class="fas fa-exclamation-triangle me-2"></i>Generation Error</h6>
                        <p class="mb-0" id="error-message-${ui.sessionId}"></p>
                    </div>
                </div>
            </div>
        `;

        // Store element references
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
            // Ensure the explanation content has proper dark mode styling
            elements.explanationContent.classList.add('text-light');
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

        sessionStorage.setItem(`streaming_result_${sessionId}`, JSON.stringify(results));
        this.sessionData.set(sessionId, results);
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
                // Get the code content, handling both textContent and innerHTML
                let codeText = ui.state.codeContent;

                // If the code is in a <code> element, get the text content
                if (ui.elements.codeContent) {
                    const codeElement = ui.elements.codeContent;
                    codeText = codeElement.textContent || codeElement.innerText || codeElement.innerHTML || ui.state.codeContent;
                }

                await navigator.clipboard.writeText(codeText);
                this.showCopyFeedback(ui.elements.codeOutput, 'Code copied!');
            } catch (error) {
                console.error('Failed to copy code:', error);
                // Fallback to raw content if HTML parsing fails
                try {
                    await navigator.clipboard.writeText(ui.state.codeContent);
                    this.showCopyFeedback(ui.elements.codeOutput, 'Code copied!');
                } catch (fallbackError) {
                    console.error('Failed to copy code (fallback):', fallbackError);
                }
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
                // Get the rendered HTML content instead of raw markdown
                const renderedContent = ui.elements.explanationContent.innerHTML || this.renderMarkdown(ui.state.explanationContent);

                // Create a temporary element to get plain text from HTML
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = renderedContent;
                const plainText = tempDiv.textContent || tempDiv.innerText || '';

                await navigator.clipboard.writeText(plainText);
                this.showCopyFeedback(ui.elements.explanationOutput, 'Explanation copied!');
            } catch (error) {
                console.error('Failed to copy explanation:', error);
                // Fallback to raw content if HTML parsing fails
                try {
                    await navigator.clipboard.writeText(ui.state.explanationContent);
                    this.showCopyFeedback(ui.elements.explanationOutput, 'Explanation copied!');
                } catch (fallbackError) {
                    console.error('Failed to copy explanation (fallback):', fallbackError);
                }
            }
        }
    }

    /**
     * Show copy feedback
     */
    showCopyFeedback(element, message) {
        // Create a temporary feedback element instead of modifying the content
        const feedback = document.createElement('div');
        feedback.className = 'copy-feedback alert alert-success py-1 px-2 mb-2';
        feedback.style.fontSize = '0.875rem';
        feedback.style.margin = '0';
        feedback.style.transition = 'opacity 0.3s ease';
        feedback.textContent = message;

        // Insert feedback at the top of the container
        const container = element.closest('.card-body') || element.parentElement;
        if (container) {
            container.insertBefore(feedback, container.firstChild);

            // Fade out and remove after 2 seconds
            setTimeout(() => {
                feedback.style.opacity = '0';
                setTimeout(() => {
                    if (feedback.parentNode) {
                        feedback.parentNode.removeChild(feedback);
                    }
                }, 300);
            }, 2000);
        }
    }

    /**
     * Save as snippet
     */
    saveAsSnippet(sessionId) {
        const results = this.sessionData.get(sessionId);
        if (results) {
            const params = new URLSearchParams({
                generated_code: results.code,
                generated_explanation: results.explanation,
                thinking_steps: JSON.stringify({
                    streaming_optimization: results.optimizations,
                    timestamp: results.timestamp
                })
            });

            window.location.href = `/create_snippet?${params.toString()}`;
        }
    }

    /**
     * Generate new (reset UI)
     */
    generateNew(sessionId) {
        this.stopStream(sessionId);
        // Reset form or redirect to generate page
        window.location.reload();
    }

    /**
     * Retry generation with the same prompt
     */
    async retryGeneration(sessionId) {
        const ui = this.getStreamingUI(sessionId);
        if (!ui || !ui.originalPrompt) {
            console.error('No UI or original prompt found for session:', sessionId);
            return;
        }

        console.log('Retrying generation with prompt:', ui.originalPrompt);

        try {
            // Show loading state
            this.updateUIState(ui, {
                status: 'starting',
                currentStep: 0,
                stepDescription: 'Retrying generation...',
                codeContent: '',
                explanationContent: ''
            });

            // Clear previous results
            ui.elements.codeContent.textContent = '';
            ui.elements.explanationContent.innerHTML = '';
            ui.elements.codeOutput.style.display = 'none';
            ui.elements.explanationOutput.style.display = 'none';
            ui.elements.actions.style.display = 'none';

            // Restart streaming with the same prompt
            await this.startChainedStreaming(ui.originalPrompt, {
                sessionId: sessionId,
                containerId: ui.container.id
            });

        } catch (error) {
            console.error('Retry generation failed:', error);
            this.handleStreamError(sessionId, error);
        }
    }

    /**
     * Share results
     */
    shareResults(sessionId) {
        const results = this.sessionData.get(sessionId);
        if (results && navigator.share) {
            navigator.share({
                title: 'AI Generated Code',
                text: 'Check out this AI-generated code with streaming optimization!',
                url: window.location.href
            });
        } else {
            // Fallback to copying URL
            navigator.clipboard.writeText(window.location.href).then(() => {
                alert('URL copied to clipboard!');
            });
        }
    }

    /**
     * Pause stream
     */
    pauseStream(sessionId) {
        const ui = this.getStreamingUI(sessionId);
        if (ui) {
            // Implementation would depend on stream control capabilities
            console.log('Pausing stream:', sessionId);
        }
    }

    /**
     * Stop stream
     */
    stopStream(sessionId) {
        const ui = this.activeStreams.get(sessionId);
        if (ui) {
            ui.container.remove();
            this.activeStreams.delete(sessionId);
            console.log('Stopped stream:', sessionId);
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
        // Implementation for resuming streams
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
                let html = marked.parse(content);
                // Add dark mode compatible classes to markdown-rendered content
                html = this.addDarkModeClasses(html);
                return html;
            } catch (error) {
                console.warn('Markdown rendering failed:', error);
            }
        }
        return content.replace(/\n/g, '<br>');
    }

    /**
     * Add dark mode compatible classes to HTML content
     */
    addDarkModeClasses(html) {
        // Create a temporary DOM element to manipulate the HTML
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = html;

        // Find all elements and add appropriate dark mode classes
        const elements = tempDiv.querySelectorAll('*');
        elements.forEach(element => {
            // Add text-light class to all text elements for dark mode
            if (element.children.length === 0) { // Text nodes
                element.classList.add('text-light');
            }

            // Handle specific markdown elements
            if (element.tagName === 'H1' || element.tagName === 'H2' ||
                element.tagName === 'H3' || element.tagName === 'H4' ||
                element.tagName === 'H5' || element.tagName === 'H6') {
                element.classList.add('text-light', 'fw-bold');
            }

            if (element.tagName === 'P') {
                element.classList.add('text-light');
            }

            if (element.tagName === 'CODE') {
                element.classList.add('bg-secondary', 'text-light', 'px-1', 'py-0', 'rounded');
            }

            if (element.tagName === 'PRE') {
                element.classList.add('bg-secondary', 'text-light', 'p-2', 'rounded');
            }

            if (element.tagName === 'UL' || element.tagName === 'OL') {
                element.classList.add('text-light');
            }

            if (element.tagName === 'LI') {
                element.classList.add('text-light');
            }

            if (element.tagName === 'BLOCKQUOTE') {
                element.classList.add('text-light', 'border-start', 'border-secondary', 'ps-3');
            }

            if (element.tagName === 'A') {
                element.classList.add('text-info', 'text-decoration-none');
                element.addEventListener('mouseenter', () => element.classList.add('text-light'));
                element.addEventListener('mouseleave', () => element.classList.remove('text-light'));
            }

            if (element.tagName === 'STRONG' || element.tagName === 'B') {
                element.classList.add('text-light', 'fw-bold');
            }

            if (element.tagName === 'EM' || element.tagName === 'I') {
                element.classList.add('text-light', 'fst-italic');
            }
        });

        return tempDiv.innerHTML;
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

    /**
     * Get session results
     */
    getSessionResults(sessionId) {
        return this.sessionData.get(sessionId);
    }

    /**
     * Clear session data
     */
    clearSession(sessionId) {
        sessionStorage.removeItem(`streaming_result_${sessionId}`);
        this.sessionData.delete(sessionId);
        this.stopStream(sessionId);
    }
}

// Initialize streaming AI manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.streamingAI = new StreamingAIManager();
    window.streamingAI.init();
});

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = StreamingAIManager;
}