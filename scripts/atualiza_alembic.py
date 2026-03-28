import subprocess
import sys
import time
from pathlib import Path

import sqlalchemy
from sqlalchemy import text

LIB_FOLDER_PATH = Path(__file__).parent
ROOT_FOLDER_PATH = LIB_FOLDER_PATH.parent

if str(ROOT_FOLDER_PATH) not in sys.path:
    sys.path.insert(0, str(ROOT_FOLDER_PATH))

from app.infrastructure.db.database import SessionLocal

# Espera o banco iniciar por no máximo 60 segundos
TOTAL_WAIT_TIME = 120


def verifica_conexao():
    start = time.time()
    while time.time() - start < TOTAL_WAIT_TIME:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
        except sqlalchemy.exc.OperationalError:
            print("Waiting for database to startup...")
            time.sleep(5)
        else:
            print("Database is awake.")
            return
        finally:
            db.close()

    raise RuntimeError(f"Database did not startup in {TOTAL_WAIT_TIME} seconds.")


def executa_migracao():
    print("Starting migration.")

    return_code = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT_FOLDER_PATH,
    ).returncode

    print("Finished migration.")

    return return_code


def main():
    verifica_conexao()
    return executa_migracao()


if __name__ == "__main__":
    raise SystemExit(main())
