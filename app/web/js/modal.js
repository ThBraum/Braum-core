/**
 * Responsabilidade: Controlar abertura, fechamento e estados de modais
 */

class ModalManager {
	constructor() {
		this.modals = new Map();
	}

	/**
	 * Registra uma modal
	 * @param {string} name - Nome identificador da modal
	 * @param {HTMLElement} element - Elemento DOM da modal
	 * @param {object} config - Configurações da modal
	 */
	register(name, element, config = {}) {
		this.modals.set(name, {
			element,
			name,
			isOpen: false,
			config,
		});
	}

	/**
	 * Abre uma modal
	 * @param {string} name - Nome da modal a abrir
	 */
	open(name) {
		const modal = this.modals.get(name);
		if (!modal) {
			console.warn(`Modal "${name}" não registrada`);
			return;
		}

		modal.element.hidden = false;
		modal.isOpen = true;
	}

	/**
	 * Fecha uma modal
	 * @param {string} name - Nome da modal a fechar
	 */
	close(name) {
		const modal = this.modals.get(name);
		if (!modal) {
			console.warn(`Modal "${name}" não registrada`);
			return;
		}

		modal.element.hidden = true;
		modal.isOpen = false;
	}

	/**
	 * Verifica se modal está aberta
	 */
	isOpen(name) {
		const modal = this.modals.get(name);
		return modal ? modal.isOpen : false;
	}

	/**
	 * Fecha todas as modais
	 */
	closeAll() {
		this.modals.forEach((modal) => {
			modal.element.hidden = true;
			modal.isOpen = false;
		});
	}

	/**
	 * Toggle uma modal
	 */
	toggle(name) {
		this.isOpen(name) ? this.close(name) : this.open(name);
	}

	/**
	 * Adiciona listener para botão de fechar
	 */
	setupCloseButton(modalName, closeButtonId, onClose = null) {
		const closeBtn = document.getElementById(closeButtonId);
		if (closeBtn) {
			closeBtn.addEventListener("click", () => {
				this.close(modalName);
				if (onClose) onClose();
			});
		}
	}
}

// Export singleton
const modalManager = new ModalManager();
export default modalManager;
