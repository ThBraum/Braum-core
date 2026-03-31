/**
 * Responsabilidade: Centralizar e padronizar todas as requisições HTTP
 */

class APIClient {
	constructor(config = {}) {
		this.baseURL = config.baseURL || "";
		this.timeout = config.timeout || 30000;
		this.headers = config.headers || {};
	}

	/**
	 * Requisição genérica com tratamento de erro
	 * @param {string} path - Caminho da API
	 * @param {object} options - Opções de fetch
	 * @returns {Promise<object>} - Response parsed JSON
	 */
	async request(path, options = {}) {
		const url = `${this.baseURL}${path}`;
		const finalOptions = {
			...options,
			headers: { ...this.headers, ...options.headers },
		};

		try {
			const response = await this._fetchWithTimeout(url, finalOptions);

			if (!response.ok) {
				return this._handleError(response);
			}

			if (response.status === 204) {
				return null;
			}

			return await response.json();
		} catch (error) {
			throw new Error(error.message || "Erro na requisição");
		}
	}

	/**
	 * GET com tratamento de params
	 */
	async get(path, params = {}) {
		const query = new URLSearchParams(params).toString();
		const finalPath = query ? `${path}?${query}` : path;
		return this.request(finalPath);
	}

	/**
	 * POST com JSON
	 */
	async post(path, data = {}) {
		return this.request(path, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(data),
		});
	}

	/**
	 * PATCH com JSON
	 */
	async patch(path, data = {}) {
		return this.request(path, {
			method: "PATCH",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(data),
		});
	}

	/**
	 * DELETE
	 */
	async delete(path) {
		return this.request(path, { method: "DELETE" });
	}

	/**
	 * Fetch com timeout
	 */
	async _fetchWithTimeout(url, options) {
		const controller = new AbortController();
		const timeoutId = setTimeout(() => controller.abort(), this.timeout);

		try {
			return await fetch(url, { ...options, signal: controller.signal });
		} finally {
			clearTimeout(timeoutId);
		}
	}

	/**
	 * Tratamento centralizado de erros HTTP
	 */
	async _handleError(response) {
		let detail = `Erro ${response.status}`;

		try {
			const payload = await response.json();
			detail = payload.detail || payload.error?.message || detail;
		} catch (_) {
			// Falha ao parsear JSON, usa mensagem padrão
		}

		throw new Error(detail);
	}
}

// Export singleton
const apiClient = new APIClient();
export default apiClient;
