/**
 * Responsabilidade: Gerenciar estado da aplicação com pub/sub pattern
 */

class StateManager {
	constructor() {
		this.state = this._initState();
		this.subscribers = new Map();
	}

	/**
	 * Inicializa estado com valores padrão e localStorage
	 */
	_initState() {
		const storedWebSearch = localStorage.getItem("braum.webSearchEnabled");

		return {
			// Session
			clientId: localStorage.getItem("braum.clientId") || crypto.randomUUID(),
			accessToken: localStorage.getItem("braum.accessToken") || "",
			currentUser: null,

			// Conversation
			currentConversationId: null,
			conversations: [],

			// Mode e Settings
			mode: "general", // 'general' | 'rag' | 'sql'
			webSearchEnabled: storedWebSearch === null ? true : storedWebSearch === "true",

			// UI State
			authModalMode: "login", // 'login' | 'register'
			uploadContext: "chat", // 'chat' | 'sources'

			// Files
			documents: [],
			tables: [],
		};
	}

	/**
	 * Get state (imutável do ponto de vista do subscriber)
	 */
	getState() {
		return Object.freeze({ ...this.state });
	}

	/**
	 * Get valor específico do state
	 */
	get(key) {
		return this.state[key];
	}

	/**
	 * Update state com validações
	 */
	update(updates = {}) {
		const previousState = { ...this.state };
		Object.assign(this.state, updates);

		// Persist to localStorage
		if (updates.clientId) {
			localStorage.setItem("braum.clientId", updates.clientId);
		}
		if (updates.accessToken !== undefined) {
			if (updates.accessToken) {
				localStorage.setItem("braum.accessToken", updates.accessToken);
			} else {
				localStorage.removeItem("braum.accessToken");
			}
		}
		if (updates.webSearchEnabled !== undefined) {
			localStorage.setItem("braum.webSearchEnabled", String(updates.webSearchEnabled));
		}

		// Notify subscribers
		Object.keys(updates).forEach((key) => {
			this._notify(key, updates[key], previousState[key]);
		});
	}

	/**
	 * Subscribe para mudanças em chave específica
	 * @param {string} key - Chave a monitorar
	 * @param {function} callback - Função chamada quando muda
	 * @returns {function} - Unsubscribe
	 */
	subscribe(key, callback) {
		if (!this.subscribers.has(key)) {
			this.subscribers.set(key, new Set());
		}

		this.subscribers.get(key).add(callback);

		// Return unsubscribe function
		return () => {
			this.subscribers.get(key).delete(callback);
		};
	}

	/**
	 * Notifica todos subscribers de uma chave
	 */
	_notify(key, newValue, oldValue) {
		if (this.subscribers.has(key)) {
			this.subscribers.get(key).forEach((callback) => {
				callback(newValue, oldValue);
			});
		}
	}

	/**
	 * Reset state para valores iniciais
	 */
	reset() {
		this.state = this._initState();
		this._notify("*", this.state, null);
	}
}

// Export singleton
const stateManager = new StateManager();
export default stateManager;
