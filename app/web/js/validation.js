/**
 * Responsabilidade: Centralizar lógica de validação de formulários
 */

class Validator {
	static email(email) {
		const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
		return re.test(email);
	}

	static username(username) {
		return username.length >= 3 && username.length <= 50;
	}

	/*mínimo 6 caracteres*/
	static password(password) {
		return password.length >= 6;
	}

	static matches(value1, value2) {
		return value1 === value2;
	}

	static required(value) {
		return Boolean(value && value.trim());
	}

	static getErrorMessage(field, type, options = {}) {
		const messages = {
			email: {
				required: `Email é obrigatório`,
				invalid: `Email inválido`,
				exists: `Email já registrado ou inválido`,
			},
			username: {
				required: `Username é obrigatório`,
				invalid: `Username deve ter 3-50 caracteres`,
				exists: `Username já em uso`,
			},
			password: {
				required: `Senha é obrigatória`,
				invalid: `Senha deve ter no mínimo 6 caracteres`,
				mismatch: `Senhas não correspondem`,
			},
			emailOrUsername: {
				required: `Email ou username é obrigatório`,
			},
		};

		return messages[field]?.[type] || "Erro de validação";
	}
}

export default Validator;
