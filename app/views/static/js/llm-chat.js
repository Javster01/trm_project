// Gestor de chat con LLM
class LLMChatManager {
    constructor() {
        this.selectedModel = null;
        this.models = [];
        this.isLoading = false;
        this.initializeElements();
        this.attachEventListeners();
        this.loadModels();
    }

    initializeElements() {
        this.modelSelector = document.getElementById('modelSelector');
        this.chatMessages = document.getElementById('chatMessages');
        this.chatInput = document.getElementById('chatInput');
        this.chatSendBtn = document.getElementById('chatSendBtn');
    }

    attachEventListeners() {
        this.chatSendBtn.addEventListener('click', () => this.sendMessage());
        this.chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !this.isLoading) {
                this.sendMessage();
            }
        });
    }

    async loadModels() {
        try {
            const response = await fetch('/api/llm/models');
            const data = await response.json();

            if (data.success) {
                this.models = data.models;
                this.renderModelSelector();
            }
        } catch (error) {
            console.error('Error cargando modelos:', error);
            this.addSystemMessage('❌ Error al cargar los modelos disponibles.');
        }
    }

    renderModelSelector() {
        this.modelSelector.innerHTML = '';

        this.models.forEach((model) => {
            const modelDiv = document.createElement('div');
            modelDiv.className = 'model-option';
            modelDiv.innerHTML = `
                <div class="model-option-name">${model.name}</div>
                <div class="model-option-provider">${model.provider}</div>
                <div class="model-option-desc">${model.description}</div>
            `;

            modelDiv.addEventListener('click', () => this.selectModel(model, modelDiv));
            this.modelSelector.appendChild(modelDiv);
        });
    }

    selectModel(model, element) {
        // Remover clase selected de todos los elementos
        document.querySelectorAll('.model-option').forEach(el => {
            el.classList.remove('selected');
        });

        // Agregar clase selected al elemento clickeado
        element.classList.add('selected');

        this.selectedModel = model;
        this.chatInput.disabled = false;
        this.chatSendBtn.disabled = false;

        // Limpiar mensajes previos
        this.chatMessages.innerHTML = '';
        this.addSystemMessage(`✅ Modelo "${model.name}" seleccionado. ¡Escribe tu pregunta!`);
    }

    async sendMessage() {
        const message = this.chatInput.value.trim();

        if (!message || !this.selectedModel || this.isLoading) {
            return;
        }

        this.isLoading = true;
        this.chatSendBtn.disabled = true;

        // Mostrar mensaje del usuario
        this.addUserMessage(message);
        this.chatInput.value = '';

        // Mostrar indicador de carga
        const loadingId = this.addLoadingMessage();

        try {
            const response = await fetch('/api/llm/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    model: this.selectedModel.id,
                    use_random_forest_prediction: true,
                }),
            });

            const data = await response.json();

            // Remover mensaje de carga
            this.removeLoadingMessage(loadingId);

            if (data.success && data.response) {
                this.addAssistantMessage(data.response, data.investment_recommendations);
            } else {
                this.addErrorMessage(data.error || 'Error desconocido del servidor');
            }
        } catch (error) {
            this.removeLoadingMessage(loadingId);
            console.error('Error enviando mensaje:', error);
            this.addErrorMessage('Error de conexión. Intenta de nuevo.');
        } finally {
            this.isLoading = false;
            this.chatSendBtn.disabled = false;
            this.chatInput.focus();
        }
    }

    addUserMessage(text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-message user';
        messageDiv.innerHTML = `<div class="chat-message-content">${this.escapeHtml(text)}</div>`;
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    addAssistantMessage(text, investmentRecs = null) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-message assistant';

        let content = `<div class="chat-message-content">${this.escapeHtml(text)}`;

        // Agregar recomendaciones de inversión si existen
        if (investmentRecs) {
            content += '<div style="margin-top: 1rem; border-top: 1px solid #ddd; padding-top: 0.75rem;">';
            
            // Random Forest
            if (investmentRecs.random_forest) {
                const rfRec = investmentRecs.random_forest;
                const rfClass = this.getRecommendationClass(rfRec.recommendation);
                content += `
                    <div style="margin-bottom: 0.75rem;">
                        <strong>🤖 Random Forest:</strong>
                        <div class="investment-recommendation ${rfClass}" style="margin-top: 0.25rem;">
                            <strong>${rfRec.recommendation}</strong><br>
                            Cambio: ${rfRec.change_percentage > 0 ? '+' : ''}${rfRec.change_percentage}%<br>
                            <small>${rfRec.reasoning}</small>
                        </div>
                    </div>
                `;
            }
            
            // Monte Carlo
            if (investmentRecs.monte_carlo) {
                const mcRec = investmentRecs.monte_carlo;
                const mcClass = this.getRecommendationClass(mcRec.recommendation);
                content += `
                    <div>
                        <strong>🎲 Monte Carlo:</strong>
                        <div class="investment-recommendation ${mcClass}" style="margin-top: 0.25rem;">
                            <strong>${mcRec.recommendation}</strong><br>
                            Cambio: ${mcRec.change_percentage > 0 ? '+' : ''}${mcRec.change_percentage}%<br>
                            <small>${mcRec.reasoning}</small>
                        </div>
                    </div>
                `;
            }
            
            content += '</div>';
        }

        content += '</div>';
        messageDiv.innerHTML = content;
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    addSystemMessage(text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-message system';
        messageDiv.innerHTML = `<div class="chat-message-content">${this.escapeHtml(text)}</div>`;
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    addErrorMessage(text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-message system';
        messageDiv.innerHTML = `<div class="chat-message-content">❌ ${this.escapeHtml(text)}</div>`;
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    addLoadingMessage() {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-message assistant';
        const id = `loading-${Date.now()}`;
        messageDiv.id = id;
        messageDiv.innerHTML = `
            <div class="chat-message-content">
                <div class="loading-spinner"></div>
                <span> Pensando...</span>
            </div>
        `;
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
        return id;
    }

    removeLoadingMessage(id) {
        const element = document.getElementById(id);
        if (element) {
            element.remove();
        }
    }

    scrollToBottom() {
        setTimeout(() => {
            this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
        }, 0);
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    getRecommendationClass(recommendation) {
        const recUpper = recommendation.toUpperCase();
        if (recUpper.includes('COMPRA')) return 'buy';
        if (recUpper.includes('VENTA')) return 'sell';
        return 'hold';
    }
}

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    new LLMChatManager();
});
