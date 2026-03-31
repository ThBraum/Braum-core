/**
 * Responsabilidade: Gerenciar visibilidade e toggle de campos de senha
 */

const EYE_OPEN_SVG =
	'<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/></svg>';

const EYE_CLOSED_SVG =
	'<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" opacity="0.5"><path d="M11.83 9L15.64 12.81c.04-.25.08-.5.08-.81 0-1.66-1.34-3-3-3-.29 0-.54.04-.79.08M7.4 6.75c.52-.4 1.08-.77 1.7-1.08C10.44 5.41 11.18 5 12 5c3.31 0 6 2.69 6 6 0 .82-.41 1.56-.97 2.9l2.85 2.85c.37-.53.73-1.12 1.07-1.75 1.73-4.39 6-7.5 11-7.5-1.73-4.39-6-7.5-11-7.5-4.21 0-7.87 2.11-10.07 5.2l2.52 2.5zM2 4.27l2.28 2.28.46.46A11.804 11.804 0 001 12c1.73 4.39 6 7.5 11 7.5 1.55 0 3.03-.3 4.38-.84l.42.42L19.73 22 21 20.73 3.27 3 2 4.27zM7.53 9.8l1.55 1.55c-.05-.2-.08-.4-.08-.65 0-1.66 1.34-3 3-3 .25 0 .45.03.65.08l1.55-1.55C11.6 5.1 11.82 5 12 5c-1.66 0-3 1.34-3 3 0 .18.1.4.53.8z"/></svg>';

class PasswordField {
	/**
	 * Setup toggle para um campo de senha
	 * @param {HTMLInputElement} inputEl - Input de senha
	 * @param {HTMLButtonElement} toggleBtn - Botão de toggle
	 */
	static setupToggle(inputEl, toggleBtn) {
		if (!inputEl || !toggleBtn) return;

		toggleBtn.addEventListener("click", (e) => {
			e.preventDefault();
			PasswordField.toggle(inputEl, toggleBtn);
		});

		PasswordField.resetIcon(toggleBtn);
	}

	/**
	 * Toggle visibilidade da senha
	 */
	static toggle(inputEl, toggleBtn) {
		const isPassword = inputEl.type === "password";
		inputEl.type = isPassword ? "text" : "password";
		toggleBtn.innerHTML = isPassword ? EYE_CLOSED_SVG : EYE_OPEN_SVG;
	}

	/**
	 * Reset para ícone padrão (olho aberto)
	 */
	static resetIcon(toggleBtn) {
		toggleBtn.innerHTML = EYE_OPEN_SVG;
	}

	/**
	 * Reset todos os campos de senha para visibilidade oculta
	 */
	static resetAll(passwordFields) {
		passwordFields.forEach(({ input, toggle }) => {
			input.type = "password";
			this.resetIcon(toggle);
		});
	}
}

export default PasswordField;
