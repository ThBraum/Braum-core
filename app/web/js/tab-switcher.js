/**
 * Responsabilidade: Gerenciar troca entre abas Login/Registro com animações
 */

import stateManager from "./state.js";
import PasswordField from "./password-field.js";
import authForm from "./auth-form.js";

class TabSwitcher {
	constructor() {
		this.passwordFields = [];
	}

	/**
	 * Inicializa tab switcher
	 */
	init(elements) {
		this.elements = elements;
		this._setupEventListeners();
	}

	/**
	 * Setup event listeners
	 */
	_setupEventListeners() {
		const { tabLogin, tabRegister } = this.elements;

		if (tabLogin) {
			tabLogin.addEventListener("click", () => this.switchTo("login"));
		}

		if (tabRegister) {
			tabRegister.addEventListener("click", () => this.switchTo("register"));
		}
	}

	/**Muda para abas específica*/
	switchTo(mode) {
		const isRegister = mode === "register";
		stateManager.update({ authModalMode: mode });

		const { authModalTitle, loginForm, registerForm, tabLogin, tabRegister, authContent } =
			this.elements;

		// Update title
		authModalTitle.textContent = isRegister ? "Criar conta" : "Entrar";

		// Show/hide forms
		loginForm.hidden = isRegister;
		registerForm.hidden = !isRegister;

		// Update active tab
		tabLogin.classList.toggle("active", !isRegister);
		tabRegister.classList.toggle("active", isRegister);

		// Trigger flip animation
		this._triggerFlipAnimation(authContent);

		// Clear errors
		authForm.clearErrors();

		// Reset password visibility
		PasswordField.resetAll(this.passwordFields);

		// Focus first input
		setTimeout(() => {
			const firstInput = isRegister
				? this.elements.registerEmailInput
				: this.elements.authLoginInput;

			if (firstInput) firstInput.focus();
		}, 100);
	}

	/**
	 * Flip 180
	 */
	_triggerFlipAnimation(element) {
		if (!element) return;

		element.style.animation = "none";
		void element.offsetWidth;
		element.style.animation = "flip 0.4s ease-out";
	}

	/**
	 * Registra campos de senha para reset em grupo
	 */
	registerPasswordFields(fieldsArray) {
		this.passwordFields = fieldsArray;
	}
}

// Export singleton
const tabSwitcher = new TabSwitcher();
export default tabSwitcher;
