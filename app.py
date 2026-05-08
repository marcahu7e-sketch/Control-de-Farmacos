import streamlit as st
import sqlite3
import hashlib
import pandas as pd
from datetime import datetime

# Configuración de la página
st.set_page_config(page_title="Hospital App", layout="wide")


# ============ BASE DE DATOS ============
def init_db():
    conn = sqlite3.connect('hospital.db')
    c = conn.cursor()

    # Tabla de medicamentos
    c.execute('''
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
                  stock
                  INTEGER
                  DEFAULT
                  0,
                  stock_minimo
                  INTEGER
                  DEFAULT
                  10
              )
              ''')

    # Tabla de usuarios
    c.execute('''
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

    # Insertar usuario admin por defecto
    c.execute("SELECT * FROM usuarios WHERE username = 'admin'")
    if not c.fetchone():
        # Contraseña: admin123
        password_hash = hashlib.sha256("admin123".encode()).hexdigest()
        c.execute("INSERT INTO usuarios (username, password, rol) VALUES (?, ?, ?)",
                  ('admin', password_hash, 'admin'))

    conn.commit()
    conn.close()


init_db()


# ============ FUNCIONES DE LOGIN ============
def hacer_login(username, password):
    hashed = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect('hospital.db')
    c = conn.cursor()
    c.execute("SELECT username, rol FROM usuarios WHERE username = ? AND password = ? AND activo = 1",
              (username, hashed))
    result = c.fetchone()
    conn.close()
    return result


def login_form():
    st.title("🏥 Sistema de Control de Medicamentos")
    st.subheader("Iniciar Sesión")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username = st.text_input("👤 Usuario")
        password = st.text_input("🔒 Contraseña", type="password")

        if st.button("✅ Ingresar", type="primary", use_container_width=True):
            if username and password:
                user_data = hacer_login(username, password)
                if user_data:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = user_data[0]
                    st.session_state['rol'] = user_data[1]
                    st.session_state['login_time'] = datetime.now()
                    st.success(f"✅ ¡Bienvenido {user_data[0]}!")
                    st.rerun()
                else:
                    st.error("❌ Usuario o contraseña incorrectos")
            else:
                st.warning("⚠️ Complete todos los campos")


def logout():
    if st.sidebar.button("🚪 Cerrar sesión", use_container_width=True):
        for key in ['logged_in', 'username', 'rol', 'login_time']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()


def verificar_permiso(rol_necesario):
    if st.session_state.get('rol') == 'admin':
        return True
    return st.session_state.get('rol') == rol_necesario


# ============ FUNCIONES DE LA APP ============
def mostrar_dashboard():
    conn = sqlite3.connect('hospital.db')
    df = pd.read_sql_query("SELECT * FROM medicamentos", conn)
    conn.close()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Medicamentos", len(df))
    if not df.empty:
        stock_total = df['stock'].sum()
        col2.metric("Stock Total", f"{stock_total} unidades")
        stock_bajo = len(df[df['stock'] <= df['stock_minimo']])
        col3.metric("Stock Bajo", stock_bajo)

    st.markdown("---")
    st.subheader("Últimos movimientos")
    st.info("Funcionalidad en desarrollo")


def ver_stock():
    st.header("📊 Stock de Medicamentos")

    conn = sqlite3.connect('hospital.db')
    df = pd.read_sql_query("SELECT nombre, stock, stock_minimo FROM medicamentos", conn)
    conn.close()

    if df.empty:
        st.info("No hay medicamentos cargados")
    else:
        # Alertas
        alerta = df[df['stock'] <= df['stock_minimo']]
        if not alerta.empty:
            st.warning("⚠️ Medicamentos con stock bajo:")
            for _, row in alerta.iterrows():
                st.write(f"- **{row['nombre']}**: {row['stock']} / {row['stock_minimo']}")

        st.dataframe(df, use_container_width=True)

        csv = df.to_csv(index=False)
        st.download_button("📥 Descargar CSV", csv, "stock.csv", "text/csv")


def agregar_medicamento():
    st.header("➕ Agregar Nuevo Medicamento")

    with st.form("nuevo_med"):
        nombre = st.text_input("Nombre del medicamento")
        stock_inicial = st.number_input("Stock inicial", min_value=0, value=0, step=1)
        stock_minimo = st.number_input("Stock mínimo de alerta", min_value=0, value=10, step=5)

        if st.form_submit_button("💾 Guardar"):
            if nombre:
                try:
                    conn = sqlite3.connect('hospital.db')
                    conn.execute(
                        "INSERT INTO medicamentos (nombre, stock, stock_minimo) VALUES (?, ?, ?)",
                        (nombre, stock_inicial, stock_minimo)
                    )
                    conn.commit()
                    conn.close()
                    st.success(f"✅ Medicamento '{nombre}' agregado")
                    st.rerun()
                except:
                    st.error("❌ Este medicamento ya existe")
            else:
                st.warning("Ingrese un nombre")


def registrar_movimiento():
    st.header("📦 Registrar Movimiento")

    conn = sqlite3.connect('hospital.db')
    df = pd.read_sql_query("SELECT nombre, stock FROM medicamentos", conn)
    conn.close()

    if df.empty:
        st.warning("Primero debe agregar medicamentos")
    else:
        medicamento = st.selectbox("Seleccionar medicamento", df['nombre'].tolist())
        stock_actual = df[df['nombre'] == medicamento]['stock'].values[0]

        st.info(f"Stock actual: **{stock_actual}** unidades")

        tipo = st.radio("Tipo de movimiento", ["📥 Ingreso", "📤 Egreso"])
        cantidad = st.number_input("Cantidad", min_value=1, step=1)

        if tipo == "📤 Egreso" and cantidad > stock_actual:
            st.error(f"❌ Stock insuficiente. Solo hay {stock_actual} unidades")
        else:
            if st.button("Registrar Movimiento", type="primary"):
                if tipo == "📥 Ingreso":
                    nuevo_stock = stock_actual + cantidad
                else:
                    nuevo_stock = stock_actual - cantidad

                conn = sqlite3.connect('hospital.db')
                conn.execute("UPDATE medicamentos SET stock = ? WHERE nombre = ?",
                             (nuevo_stock, medicamento))
                conn.commit()
                conn.close()

                st.success(f"✅ Movimiento registrado: {tipo} {cantidad} {medicamento}")
                st.balloons()
                st.rerun()


def cambiar_password():
    st.header("🔐 Cambiar Contraseña")

    with st.form("cambiar_pass"):
        password_actual = st.text_input("Contraseña actual", type="password")
        password_nueva = st.text_input("Contraseña nueva", type="password")
        password_confirmar = st.text_input("Confirmar contraseña nueva", type="password")

        if st.form_submit_button("Cambiar contraseña"):
            if not password_actual or not password_nueva:
                st.warning("Complete todos los campos")
            elif password_nueva != password_confirmar:
                st.error("Las contraseñas nuevas no coinciden")
            else:
                hashed_actual = hashlib.sha256(password_actual.encode()).hexdigest()
                hashed_nueva = hashlib.sha256(password_nueva.encode()).hexdigest()

                conn = sqlite3.connect('hospital.db')
                c = conn.cursor()
                c.execute("SELECT * FROM usuarios WHERE username = ? AND password = ?",
                          (st.session_state['username'], hashed_actual))
                if c.fetchone():
                    c.execute("UPDATE usuarios SET password = ? WHERE username = ?",
                              (hashed_nueva, st.session_state['username']))
                    conn.commit()
                    st.success("✅ Contraseña cambiada exitosamente")
                    st.info("Vuelve a iniciar sesión con tu nueva contraseña")
                    if st.button("Cerrar sesión ahora"):
                        for key in list(st.session_state.keys()):
                            del st.session_state[key]
                        st.rerun()
                else:
                    st.error("❌ Contraseña actual incorrecta")
                conn.close()


def gestionar_usuarios():
    if not verificar_permiso('admin'):
        st.error("❌ Solo administradores pueden gestionar usuarios")
        return

    st.header("👥 Gestión de Usuarios")

    conn = sqlite3.connect('hospital.db')
    df = pd.read_sql_query("SELECT id, username, rol, activo FROM usuarios", conn)
    st.dataframe(df, use_container_width=True)
    conn.close()

    with st.expander("➕ Agregar nuevo usuario"):
        with st.form("nuevo_usuario"):
            nuevo_user = st.text_input("Usuario")
            nuevo_pass = st.text_input("Contraseña", type="password")
            nuevo_rol = st.selectbox("Rol", ["enfermeria", "farmaceutico", "admin"])

            if st.form_submit_button("Crear usuario"):
                if nuevo_user and nuevo_pass:
                    hashed = hashlib.sha256(nuevo_pass.encode()).hexdigest()
                    try:
                        conn = sqlite3.connect('hospital.db')
                        conn.execute(
                            "INSERT INTO usuarios (username, password, rol) VALUES (?, ?, ?)",
                            (nuevo_user, hashed, nuevo_rol)
                        )
                        conn.commit()
                        conn.close()
                        st.success(f"✅ Usuario {nuevo_user} creado")
                        st.rerun()
                    except:
                        st.error("❌ El usuario ya existe")
                else:
                    st.warning("Complete todos los campos")


# ============ APP PRINCIPAL ============
def main():
    # Verificar login
    if 'logged_in' not in st.session_state or not st.session_state['logged_in']:
        login_form()
        return

    # Sidebar con información del usuario
    st.sidebar.markdown(f"""
    ### 👤 {st.session_state['username']}
    **Rol:** {st.session_state['rol'].upper()}
    ---
    """)

    # Tiempo de sesión
    if 'login_time' in st.session_state:
        tiempo = datetime.now() - st.session_state['login_time']
        st.sidebar.caption(f"Sesión: {tiempo.seconds // 60} minutos")

    logout()
    st.sidebar.markdown("---")

    # Título
    st.title("🏥 Sistema de Control de Medicamentos")

    # Menú según rol
    menu_options = ["Dashboard", "Ver Stock", "Agregar Medicamento", "Movimiento", "Cambiar Contraseña"]

    if verificar_permiso('admin'):
        menu_options.append("Gestionar Usuarios")

    menu = st.sidebar.radio("📋 Menú", menu_options)

    # Ejecutar según opción
    if menu == "Dashboard":
        mostrar_dashboard()
    elif menu == "Ver Stock":
        ver_stock()
    elif menu == "Agregar Medicamento":
        agregar_medicamento()
    elif menu == "Movimiento":
        registrar_movimiento()
    elif menu == "Cambiar Contraseña":
        cambiar_password()
    elif menu == "Gestionar Usuarios":
        gestionar_usuarios()


if __name__ == "__main__":
    main()