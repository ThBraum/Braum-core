/**
 * Responsabilidade: Gerenciar validação, submissão e UI do formulário de auth
 */

import authService from "./auth.js";
import stateManager from "./state.js";
import Validator from "./validation.js";

class AuthForm {
	constructor() {
		this.formElements = {};
		this.errors = new Map();
		this.isSubmitting = false;
	}

	/**
	 * Inicializa formulário
	 */
	init(elements) {
		this.formElements = elements;
		this._setupEventListeners();
	}

	/**
	 * Setup event listeners para inputs
	 */
	_setupEventListeners() {
		// Allow Enter key to submit
		const inputFields = [
			this.formElements.authLoginInput,
			this.formElements.authPasswordInput,
			this.formElements.registerEmailInput,
			this.formElements.registerUsernameInput,
			this.formElements.registerPasswordInput,
			this.formElements.registerPasswordConfirmInput,
		];

		inputFields.forEach((input) => {
			if (input) {
				input.addEventListener("keydown", (e) => {
					if (e.key === "Enter") {
						this.submit();
					}
				});
			}
		});
	}

	/**
	 * Valida formulário de login
	 */
	validateLogin() {
		this.errors.clear();
		let isValid = true;

		const emailOrUsername = this.formElements.authLoginInput.value.trim();
		if (!Validator.required(emailOrUsername)) {
			this.addError("authLoginInput", "emailOrUsername", "required");
			isValid = false;
		}

		const password = this.formElements.authPasswordInput.value;
		if (!Validator.required(password)) {
			this.addError("authPasswordInput", "password", "required");
			isValid = false;
		}

		return isValid;
	}

	/**
	 * Valida formulário de registro
	 */
	validateRegister() {
		this.errors.clear();
		let isValid = true;

		// Email
		const email = this.formElements.registerEmailInput.value.trim();
		if (!Validator.required(email)) {
			this.addError("registerEmailInput", "email", "required");
			isValid = false;
		} else if (!Validator.email(email)) {
			this.addError("registerEmailInput", "email", "invalid");
			isValid = false;
		}

		// Username
		const username = this.formElements.registerUsernameInput.value.trim();
		if (!Validator.required(username)) {
			this.addError("registerUsernameInput", "username", "required");
			isValid = false;
		} else if (!Validator.username(username)) {
			this.addError("registerUsernameInput", "username", "invalid");
			isValid = false;
		}

		// Password
		const password = this.formElements.registerPasswordInput.value;
		if (!Validator.required(password)) {
			this.addError("registerPasswordInput", "password", "required");
			isValid = false;
		} else if (!Validator.password(password)) {
			this.addError("registerPasswordInput", "password", "invalid");
			isValid = false;
		}

		// Password Confirm
		const passwordConfirm = this.formElements.registerPasswordConfirmInput.value;
		if (!Validator.required(passwordConfirm)) {
			this.addError("registerPasswordConfirmInput", "password", "required");
			isValid = false;
		} else if (!Validator.matches(password, passwordConfirm)) {
			this.addError("registerPasswordConfirmInput", "password", "mismatch");
			isValid = false;
		}

		return isValid;
	}

	/**
	 * Adiciona erro e atualiza UI
	 */
	addError(inputId, field, type) {
		const errorId = inputId.replace("Input", "Error");
		const errorEl = document.getElementById(errorId);
		const inputEl = document.getElementById(inputId);

		const message = Validator.getErrorMessage(field, type);

		if (errorEl) {
			errorEl.textContent = message;
			errorEl.classList.add("show");
		}
		if (inputEl) {
			inputEl.classList.add("error");
		}

		this.errors.set(inputId, message);
	}

	/**
	 * Limpa todos os erros
	 */
	clearErrors() {
		document.querySelectorAll(".error-message").forEach((el) => {
			el.textContent = "";
			el.classList.remove("show");
		});
		document.querySelectorAll(".modal-input").forEach((el) => {
			el.classList.remove("error");
		});
		this.errors.clear();
	}

	/**
	 * Aplica animação de erro
	 */
	triggerErrorAnimation() {
		const authContent = document.getElementById("authContent");
		if (authContent) {
			authContent.classList.add("error");
			setTimeout(() => authContent.classList.remove("error"), 400);
		}
	}

	/**
	 * Limpa campos do formulário
	 */
	clearFields() {
		this.formElements.authLoginInput.value = "";
		this.formElements.authPasswordInput.value = "";
		this.formElements.registerEmailInput.value = "";
		this.formElements.registerUsernameInput.value = "";
		this.formElements.registerPasswordInput.value = "";
		this.formElements.registerPasswordConfirmInput.value = "";
	}

	/**
	 * Submete formulário
	 */
	async submit() {
		if (this.isSubmitting) return;

		const isRegister = stateManager.get("authModalMode") === "register";
		this.clearErrors();

		// Validação
		const isValid = isRegister ? this.validateRegister() : this.validateLogin();

		if (!isValid) {
			this.triggerErrorAnimation();
			return;
		}

		this.isSubmitting = true;

		try {
			if (isRegister) {
				await authService.register(
					this.formElements.registerEmailInput.value.trim(),
					this.formElements.registerUsernameInput.value.trim(),
					this.formElements.registerPasswordInput.value,
				);
			} else {
				await authService.login(
					this.formElements.authLoginInput.value.trim(),
					this.formElements.authPasswordInput.value,
				);
			}

			this.clearFields();
			// Modal será fechada externamente por app.js
			return { success: true };
		} catch (error) {
			this._handleSubmitError(error, isRegister);
			this.triggerErrorAnimation();
			return { success: false, error: error.message };
		} finally {
			this.isSubmitting = false;
		}
	}

	/**
	 * Trata erros de submissão mapeando para campos específicos
	 */
	_handleSubmitError(error, isRegister) {
		const errorMsg = error.message || "Erro desconhecido";

		if (isRegister) {
			if (errorMsg.includes("email")) {
				this.addError("registerEmailInput", "email", "exists");
			} else if (errorMsg.includes("username")) {
				this.addError("registerUsernameInput", "username", "exists");
			} else if (errorMsg.includes("password")) {
				this.addError("registerPasswordInput", "password", "invalid");
			}
		} else {
			if (
				errorMsg.includes("credenciais") ||
				errorMsg.includes("não encontrado") ||
				errorMsg.includes("inválido")
			) {
				this.addError("authLoginInput", "emailOrUsername", "invalid");
			}
		}
	}
}

// Export singleton
const authForm = new AuthForm();
export default authForm;
