# actualizar_db.py
import sqlite3


def actualizar_db():
    conn = sqlite3.connect('hospital.db')
    cursor = conn.cursor()

    # Tabla de usuarios
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS usuarios
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       username
                       TEXT
                       UNIQUE,
                       password
                       TEXT,
                       rol
                       TEXT,
                       activo
                       INTEGER
                       DEFAULT
                       1
                   )
                   ''')

    # Tabla de medicamentos con categoría
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS medicamentos
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       nombre
                       TEXT
                       UNIQUE,
                       categoria
                       TEXT
                       DEFAULT
                       'farmaco',
                       stock
                       INTEGER
                       DEFAULT
                       0,
                       stock_minimo
                       INTEGER
                       DEFAULT
                       10,
                       created_at
                       TIMESTAMP
                       DEFAULT
                       CURRENT_TIMESTAMP
                   )
                   ''')

    # Tabla de lotes
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS lotes
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       medicamento_id
                       INTEGER,
                       numero_lote
                       TEXT,
                       fecha_vencimiento
                       DATE,
                       cantidad
                       INTEGER,
                       cantidad_restante
                       INTEGER,
                       fecha_ingreso
                       TIMESTAMP
                       DEFAULT
                       CURRENT_TIMESTAMP,
                       FOREIGN
                       KEY
                   (
                       medicamento_id
                   ) REFERENCES medicamentos
                   (
                       id
                   )
                       )
                   ''')

    # Tabla de carro de paro
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS carro_paro
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       medicamento_id
                       INTEGER,
                       cantidad
                       INTEGER
                       DEFAULT
                       0,
                       cantidad_minima
                       INTEGER
                       DEFAULT
                       5,
                       ultima_revision
                       DATE,
                       FOREIGN
                       KEY
                   (
                       medicamento_id
                   ) REFERENCES medicamentos
                   (
                       id
                   )
                       )
                   ''')

    # Tabla de movimientos
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS movimientos
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       medicamento_id
                       INTEGER,
                       lote_id
                       INTEGER,
                       tipo
                       TEXT,
                       cantidad
                       INTEGER,
                       fecha
                       TIMESTAMP
                       DEFAULT
                       CURRENT_TIMESTAMP,
                       motivo
                       TEXT,
                       usuario
                       TEXT,
                       FOREIGN
                       KEY
                   (
                       medicamento_id
                   ) REFERENCES medicamentos
                   (
                       id
                   )
                       )
                   ''')

    # Usuario admin por defecto
    cursor.execute("SELECT * FROM usuarios WHERE username = 'admin'")
    if not cursor.fetchone():
        import hashlib
        hashed = hashlib.sha256("admin123".encode()).hexdigest()
        cursor.execute("INSERT INTO usuarios (username, password, rol) VALUES (?, ?, ?)",
                       ('admin', hashed, 'admin'))

    conn.commit()
    conn.close()
    print("✅ Base de datos creada correctamente")


if __name__ == "__main__":
    actualizar_db()