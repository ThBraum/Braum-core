/**
 * Responsabilidade: Gerenciar login, registro, logout e sessão do usuário
 */

import apiClient from "./api.js";
import stateManager from "./state.js";

class AuthService {
	constructor() {
		this.apiEndpoint = "/api/v1/auth";
	}

	/**
	isAuthenticated() {
		return Boolean(stateManager.get("accessToken"));
	}

	/**
	 * Realiza login
	 * @param {string} emailOrUsername - Email ou username
	 * @param {string} password - Senha
	 */
	async login(emailOrUsername, password) {
		const response = await apiClient.post(`${this.apiEndpoint}/login`, {
			email_or_username: emailOrUsername,
			password,
		});

		stateManager.update({ accessToken: response.access_token });
		await this.fetchCurrentUser();

		return response;
	}

	/**
	 * Realiza registro
	 * @param {string} email - Email
	 * @param {string} username - Username
	 * @param {string} password - Senha
	 */
	async register(email, username, password) {
		const response = await apiClient.post(`${this.apiEndpoint}/register`, {
			email,
			username,
			password,
		});

		stateManager.update({ accessToken: response.access_token });
		await this.fetchCurrentUser();

		return response;
	}

	logout() {
		stateManager.update({
			accessToken: "",
			currentUser: null,
		});
	}

	async fetchCurrentUser() {
		if (!this.isAuthenticated()) {
			stateManager.update({ currentUser: null });
			return null;
		}

		try {
			const token = stateManager.get("accessToken");
			const user = await apiClient.get(`${this.apiEndpoint}/me`, {
				access_token: token,
			});

			stateManager.update({ currentUser: user });
			return user;
		} catch (error) {
			// Token inválido ou expirado
			this.logout();
			throw error;
		}
	}

	/**
	 * Retorna parâmetros de auth para requisições
	 */
	getAuthParams() {
		const params = new URLSearchParams({
			client_id: stateManager.get("clientId"),
		});

		const token = stateManager.get("accessToken");
		if (token) {
			params.set("access_token", token);
		}

		return params;
	}

	/**
	 * Retorna body de auth para requisições POST
	 */
	getAuthBody() {
		return {
			client_id: stateManager.get("clientId"),
			access_token: stateManager.get("accessToken") || null,
		};
	}
}

// Export singleton
const authService = new AuthService();
export default authService;
