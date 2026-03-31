/**
 * Responsabilidade: Coordenar inicialização e conexões entre módulos
 */

import apiClient from "./api.js";
import stateManager from "./state.js";
import authService from "./auth.js";
import authForm from "./auth-form.js";
import modalManager from "./modal.js";
import tabSwitcher from "./tab-switcher.js";
import PasswordField from "./password-field.js";

class BraumApp {
	constructor() {
		this.isInitialized = false;
	}

	async init() {
		console.log("Inicializando App...");

		try {
			// 1. Setup DOM elements
			this._cacheElements();

			// 2. Initialize managers
			this._initModals();
			this._initAuthForm();
			this._initTabSwitcher();
			this._initEventListeners();

			// 3. Load user session
			await authService.fetchCurrentUser();
			this._updateAuthUI();

			// 4. Setup state subscriptions
			this._setupStateSubscriptions();

			// 5. Load initial data
			await this._loadInitialData();

			this.isInitialized = true;
			console.log("App initialized");
		} catch (error) {
			console.error("Erro ao inicializar:", error);
		}
	}

	/**
	 * Cache elementos do DOM
	 */
	_cacheElements() {
		this.elements = {
			// Auth Modal
			authModal: document.getElementById("authModal"),
			authModalTitle: document.getElementById("authModalTitle"),
			authContent: document.getElementById("authContent"),
			authLoginInput: document.getElementById("authLoginInput"),
			authPasswordInput: document.getElementById("authPasswordInput"),
			authPasswordToggle: document.getElementById("authPasswordToggle"),
			loginForm: document.getElementById("loginForm"),
			registerForm: document.getElementById("registerForm"),
			registerEmailInput: document.getElementById("registerEmailInput"),
			registerUsernameInput: document.getElementById("registerUsernameInput"),
			registerPasswordInput: document.getElementById("registerPasswordInput"),
			registerPasswordConfirmInput: document.getElementById("registerPasswordConfirmInput"),
			registerPasswordToggle: document.getElementById("registerPasswordToggle"),
			registerPasswordConfirmToggle: document.getElementById("registerPasswordConfirmToggle"),
			tabLogin: document.getElementById("tabLogin"),
			tabRegister: document.getElementById("tabRegister"),

			// Other Modals
			sourcesModal: document.getElementById("sourcesModal"),
			userInfoModal: document.getElementById("userInfoModal"),

			// Buttons
			authModalCancelBtn: document.getElementById("authModalCancelBtn"),
			authModalSubmitBtn: document.getElementById("authModalSubmitBtn"),
			topAuthBtn: document.getElementById("topAuthBtn"),
			mobileAuthBtn: document.getElementById("mobileAuthBtn"),
		};
	}

	/**
	 * Inicializa modal manager
	 */
	_initModals() {
		modalManager.register("auth", this.elements.authModal);
		modalManager.register("sources", this.elements.sourcesModal);
		modalManager.register("userInfo", this.elements.userInfoModal);

		// Setup close buttons
		modalManager.setupCloseButton("auth", "authModalCancelBtn", () => {
			authForm.clearFields();
		});
		modalManager.setupCloseButton("sources", "sourcesCloseBtn");
		modalManager.setupCloseButton("userInfo", "userInfoCloseBtn");
	}

	/**
	 * Inicializa form de autenticação
	 */
	_initAuthForm() {
		authForm.init(this.elements);

		// Submit button
		this.elements.authModalSubmitBtn?.addEventListener("click", async () => {
			const result = await authForm.submit();
			if (result?.success) {
				modalManager.close("auth");
				this._updateAuthUI();
			}
		});
	}

	/**
	 * Inicializa tab switcher
	 */
	_initTabSwitcher() {
		tabSwitcher.init(this.elements);

		// Register password fields
		tabSwitcher.registerPasswordFields([
			{ input: this.elements.authPasswordInput, toggle: this.elements.authPasswordToggle },
			{ input: this.elements.registerPasswordInput, toggle: this.elements.registerPasswordToggle },
			{
				input: this.elements.registerPasswordConfirmInput,
				toggle: this.elements.registerPasswordConfirmToggle,
			},
		]);
	}

	/**
	 * Setup password field toggles
	 */
	_initEventListeners() {
		// Password toggles
		PasswordField.setupToggle(this.elements.authPasswordInput, this.elements.authPasswordToggle);
		PasswordField.setupToggle(
			this.elements.registerPasswordInput,
			this.elements.registerPasswordToggle,
		);
		PasswordField.setupToggle(
			this.elements.registerPasswordConfirmInput,
			this.elements.registerPasswordConfirmToggle,
		);

		// Auth buttons
		this.elements.topAuthBtn?.addEventListener("click", () => this._handleAuthButtonClick());
		this.elements.mobileAuthBtn?.addEventListener("click", () => this._handleAuthButtonClick());

		console.log("Event listeners configured");
	}

	/**
	 * Handle auth button click
	 */
	_handleAuthButtonClick() {
		if (authService.isAuthenticated()) {
			this._showUserInfo();
		} else {
			modalManager.open("auth");
			tabSwitcher.switchTo("login");
		}
	}

	/**
	 * Mostra informações do usuário
	 */
	_showUserInfo() {
		const user = stateManager.get("currentUser");
		if (user) {
			document.getElementById("userInfoUsername").textContent = `Username: ${user.username}`;
			document.getElementById("userInfoEmail").textContent = `Email: ${user.email}`;
			modalManager.open("userInfo");
		}
	}

	/**
	 * Atualiza UI de autenticação
	 */
	_updateAuthUI() {
		const user = stateManager.get("currentUser");
		const buttonText = user ? user.username : "Entrar";

		if (this.elements.topAuthBtn) {
			this.elements.topAuthBtn.textContent = buttonText;
		}
		if (this.elements.mobileAuthBtn) {
			this.elements.mobileAuthBtn.textContent = buttonText;
		}
	}

	/**
	 * Setup subscriptions para mudanças de state
	 */
	_setupStateSubscriptions() {
		stateManager.subscribe("currentUser", () => {
			this._updateAuthUI();
		});

		console.log("State subscriptions configured");
	}

	/**
	 * Carrega dados iniciais
	 */
	async _loadInitialData() {
		// Pode ser expandido para carregar conversas, arquivos, etc
		console.log("Initial data loaded");
	}
}

// Auto-initialize quando DOM estiver pronto
document.addEventListener("DOMContentLoaded", () => {
	const app = new BraumApp();
	app.init();

	// Exponha para debugging
	if (typeof window !== "undefined") {
		window.app = app;
		window.stateManager = stateManager;
		window.authService = authService;
	}
});

export default BraumApp;
