import streamlit as st
import sqlite3
import hashlib
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import os

# ============ CONFIGURACIÓN ============
st.set_page_config(
    page_title="Sistema Hospitalario",
    page_icon="🏥",
    layout="wide"
)

# ============ BASE DE DATOS ============
DB_NAME = "hospital.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def init_db():
    """Crea la base de datos con toda la estructura necesaria"""
    conn = get_connection()
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

    # Tabla de medicamentos CON categoría
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
        hashed = hashlib.sha256("admin123".encode()).hexdigest()
        cursor.execute("INSERT INTO usuarios (username, password, rol) VALUES (?, ?, ?)",
                       ('admin', hashed, 'admin'))

    conn.commit()
    conn.close()
    print("Base de datos inicializada correctamente")


def verificar_y_actualizar_db():
    """Verifica si la base de datos tiene todas las columnas necesarias"""
    conn = get_connection()
    cursor = conn.cursor()

    # Verificar columnas de medicamentos
    cursor.execute("PRAGMA table_info(medicamentos)")
    columnas = [col[1] for col in cursor.fetchall()]

    if 'categoria' not in columnas:
        print("Agregando columna 'categoria'...")
        cursor.execute("ALTER TABLE medicamentos ADD COLUMN categoria TEXT DEFAULT 'farmaco'")

    if 'stock_minimo' not in columnas:
        print("Agregando columna 'stock_minimo'...")
        cursor.execute("ALTER TABLE medicamentos ADD COLUMN stock_minimo INTEGER DEFAULT 10")

    # Crear tablas nuevas si no existen
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

    # Verificar columna tipo en movimientos
    cursor.execute("PRAGMA table_info(movimientos)")
    col_mov = [col[1] for col in cursor.fetchall()]
    if 'tipo' not in col_mov:
        cursor.execute("ALTER TABLE movimientos ADD COLUMN tipo TEXT DEFAULT 'ingreso'")

    conn.commit()
    conn.close()
    print("Base de datos verificada y actualizada")


# Inicializar la base de datos
if not os.path.exists(DB_NAME):
    init_db()
else:
    verificar_y_actualizar_db()


# ============ FUNCIONES DE AUTENTICACIÓN ============
def hacer_login(username, password):
    hashed = hashlib.sha256(password.encode()).hexdigest()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, rol FROM usuarios WHERE username = ? AND password = ? AND activo = 1",
                   (username, hashed))
    result = cursor.fetchone()
    conn.close()
    return result


def login_form():
    st.title("🏥 Sistema de Control de Medicamentos")
    st.subheader("Iniciar Sesión")

    username = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")

    if st.button("Ingresar"):
        if username and password:
            user_data = hacer_login(username, password)
            if user_data:
                st.session_state['logged_in'] = True
                st.session_state['username'] = user_data[0]
                st.session_state['rol'] = user_data[1]
                st.session_state['login_time'] = datetime.now()
                st.success(f"¡Bienvenido {user_data[0]}!")
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos")


def logout():
    if st.sidebar.button("Cerrar sesión", use_container_width=True):
        for key in ['logged_in', 'username', 'rol', 'login_time']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()


def verificar_permiso(rol_necesario):
    if st.session_state.get('rol') == 'admin':
        return True
    return st.session_state.get('rol') == rol_necesario


def cambiar_password(username, old_password, new_password):
    conn = get_connection()
    cursor = conn.cursor()
    hashed_old = hashlib.sha256(old_password.encode()).hexdigest()
    cursor.execute("SELECT password FROM usuarios WHERE username = ?", (username,))
    row = cursor.fetchone()
    if row and row[0] == hashed_old:
        hashed_new = hashlib.sha256(new_password.encode()).hexdigest()
        cursor.execute("UPDATE usuarios SET password = ? WHERE username = ?", (hashed_new, username))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False


def gestionar_usuarios():
    st.header("👥 Gestión de Usuarios")

    conn = get_connection()
    df = pd.read_sql_query("SELECT id, username, rol, activo FROM usuarios", conn)
    st.dataframe(df, use_container_width=True)
    conn.close()

    st.markdown("---")

    with st.expander("➕ Agregar nuevo usuario"):
        with st.form("nuevo_usuario"):
            col1, col2 = st.columns(2)
            with col1:
                nuevo_user = st.text_input("Usuario")
                nuevo_pass = st.text_input("Contraseña", type="password")
            with col2:
                nuevo_rol = st.selectbox("Rol", ["enfermeria", "farmaceutico", "admin"])
                activo = st.checkbox("Activo", value=True)

            if st.form_submit_button("Crear usuario"):
                if nuevo_user and nuevo_pass:
                    hashed = hashlib.sha256(nuevo_pass.encode()).hexdigest()
                    try:
                        conn = get_connection()
                        conn.execute(
                            "INSERT INTO usuarios (username, password, rol, activo) VALUES (?, ?, ?, ?)",
                            (nuevo_user, hashed, nuevo_rol, 1 if activo else 0)
                        )
                        conn.commit()
                        conn.close()
                        st.success(f"✅ Usuario {nuevo_user} creado")
                        st.rerun()
                    except:
                        st.error("❌ El usuario ya existe")
                else:
                    st.warning("Complete todos los campos")


# ============ FUNCIONES DE MEDICAMENTOS ============
def agregar_medicamento(nombre, categoria, stock_inicial, stock_minimo):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO medicamentos (nombre, categoria, stock, stock_minimo) VALUES (?, ?, ?, ?)",
            (nombre, categoria, stock_inicial, stock_minimo)
        )
        med_id = cursor.lastrowid
        cursor.execute("INSERT OR IGNORE INTO carro_paro (medicamento_id, cantidad, cantidad_minima) VALUES (?, 0, 5)",
                       (med_id,))
        conn.commit()
        conn.close()
        return True
    except:
        conn.close()
        return False


def obtener_medicamentos():
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT id, nombre, categoria, stock, stock_minimo FROM medicamentos ORDER BY categoria, nombre", conn)
    conn.close()
    return df


def obtener_stock_bajo():
    conn = get_connection()
    try:
        df = pd.read_sql_query(
            "SELECT nombre, categoria, stock, stock_minimo FROM medicamentos WHERE stock <= stock_minimo", conn)
    except:
        df = pd.DataFrame()
    conn.close()
    return df


# ============ FUNCIONES DE LOTES ============
def registrar_ingreso(medicamento_id, numero_lote, fecha_vencimiento, cantidad, motivo, usuario):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
                   INSERT INTO lotes (medicamento_id, numero_lote, fecha_vencimiento, cantidad, cantidad_restante)
                   VALUES (?, ?, ?, ?, ?)
                   ''', (medicamento_id, numero_lote, fecha_vencimiento, cantidad, cantidad))

    cursor.execute("UPDATE medicamentos SET stock = stock + ? WHERE id = ?", (cantidad, medicamento_id))

    cursor.execute('''
                   INSERT INTO movimientos (medicamento_id, lote_id, tipo, cantidad, motivo, usuario)
                   VALUES (?, ?, 'ingreso', ?, ?, ?)
                   ''', (medicamento_id, cursor.lastrowid, cantidad, motivo, usuario))

    conn.commit()
    conn.close()
    return True


def registrar_egreso(medicamento_id, cantidad, motivo, usuario):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT stock FROM medicamentos WHERE id = ?", (medicamento_id,))
    stock_actual = cursor.fetchone()[0]

    if stock_actual < cantidad:
        conn.close()
        return False, "Stock insuficiente"

    cursor.execute("UPDATE medicamentos SET stock = stock - ? WHERE id = ?", (cantidad, medicamento_id))

    cursor.execute('''
                   INSERT INTO movimientos (medicamento_id, tipo, cantidad, motivo, usuario)
                   VALUES (?, 'egreso', ?, ?, ?)
                   ''', (medicamento_id, cantidad, motivo, usuario))

    conn.commit()
    conn.close()
    return True, "Egreso registrado"


def obtener_lotes_proximos_vencer(dias=30):
    conn = get_connection()
    fecha_limite = (datetime.now() + timedelta(days=dias)).strftime('%Y-%m-%d')
    try:
        df = pd.read_sql_query('''
                               SELECT m.nombre, m.categoria, l.numero_lote, l.fecha_vencimiento, l.cantidad_restante
                               FROM lotes l
                                        JOIN medicamentos m ON l.medicamento_id = m.id
                               WHERE l.fecha_vencimiento <= ?
                                 AND l.cantidad_restante > 0
                               ORDER BY l.fecha_vencimiento ASC
                               ''', conn, params=(fecha_limite,))
    except:
        df = pd.DataFrame()
    conn.close()
    return df


# ============ FUNCIONES CARRO DE PARO ============
def obtener_carro_paro():
    conn = get_connection()
    try:
        df = pd.read_sql_query('''
                               SELECT m.id,
                                      m.nombre,
                                      m.categoria,
                                      COALESCE(cp.cantidad, 0)        as cantidad,
                                      COALESCE(cp.cantidad_minima, 5) as cantidad_minima,
                                      cp.ultima_revision
                               FROM medicamentos m
                                        LEFT JOIN carro_paro cp ON m.id = cp.medicamento_id
                               ORDER BY m.categoria, m.nombre
                               ''', conn)
    except:
        df = pd.DataFrame()
    conn.close()
    return df


# ============ FUNCIONES DE REPORTES ============
def generar_reporte_pdf():
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    story = []
    styles = getSampleStyleSheet()

    story.append(Paragraph("Reporte de Stock de Medicamentos", styles['Title']))
    story.append(Spacer(1, 20))
    story.append(Paragraph(f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
    story.append(Spacer(1, 20))

    conn = get_connection()
    df = pd.read_sql_query("SELECT nombre, categoria, stock, stock_minimo FROM medicamentos ORDER BY categoria, nombre",
                           conn)
    conn.close()

    data = [['Medicamento', 'Categoría', 'Stock', 'Stock Mínimo']]
    for _, row in df.iterrows():
        cat = "💊 Fármaco" if row['categoria'] == 'farmaco' else "🧠 Psicofármaco"
        data.append([row['nombre'], cat, str(row['stock']), str(row['stock_minimo'])])

    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(table)

    doc.build(story)
    buffer.seek(0)
    return buffer


# ============ FUNCIONES DE GRÁFICOS ============
def grafico_stock_por_categoria():
    conn = get_connection()
    df = pd.read_sql_query('''
                           SELECT categoria, SUM(stock) as total
                           FROM medicamentos
                           GROUP BY categoria
                           ''', conn)
    conn.close()

    if not df.empty:
        fig = px.pie(df, values='total', names='categoria', title='Stock por Categoría',
                     color_discrete_sequence=['#2E86AB', '#A23B72'])
        return fig
    return None


# ============ APP PRINCIPAL ============
def main():
    # Verificar login
    if 'logged_in' not in st.session_state or not st.session_state['logged_in']:
        login_form()
        return

    # Sidebar
    st.sidebar.markdown(f"""
    ### 👤 {st.session_state['username']}
    **Rol:** {st.session_state['rol'].upper()}
    ---
    """)

    if 'login_time' in st.session_state:
        tiempo = datetime.now() - st.session_state['login_time']
        st.sidebar.caption(f"Sesión: {tiempo.seconds // 60} minutos")

    logout()
    st.sidebar.markdown("---")

    # Alertas
    stock_bajo = obtener_stock_bajo()
    lotes_vencer = obtener_lotes_proximos_vencer(30)

    if not stock_bajo.empty:
        st.sidebar.warning(f"⚠️ {len(stock_bajo)} medicamentos con stock bajo")
    if not lotes_vencer.empty:
        st.sidebar.warning(f"⚠️ {len(lotes_vencer)} lotes próximos a vencer")

    st.sidebar.markdown("---")
    st.title("🏥 Sistema de Control de Medicamentos y Psicofármacos")

    # Métricas
    medicamentos = obtener_medicamentos()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💊 Fármacos",
                len(medicamentos[medicamentos['categoria'] == 'farmaco']) if not medicamentos.empty else 0)
    col2.metric("🧠 Psicofármacos",
                len(medicamentos[medicamentos['categoria'] == 'psicofarmaco']) if not medicamentos.empty else 0)
    col3.metric("⚠️ Stock Bajo", len(stock_bajo))
    col4.metric("📦 Lotes por Vencer", len(lotes_vencer))

    st.markdown("---")

    # Menú
    menu_options = [
        "📊 Dashboard",
        "💊 Gestión de Medicamentos",
        "📥 Ingreso con Lote",
        "📤 Egreso",
        "🚑 Carro de Paro",
        "📦 Lotes y Vencimientos",
        "📈 Reportes",
        "🔐 Cambiar Contraseña"
    ]

    if verificar_permiso('admin'):
        menu_options.append("👥 Gestión de Usuarios")

    menu = st.sidebar.radio("📋 Menú", menu_options)

    # Dashboard
    if menu == "📊 Dashboard":
        st.header("📊 Dashboard")

        col1, col2 = st.columns(2)
        with col1:
            fig = grafico_stock_por_categoria()
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No hay datos para mostrar")

        with col2:
            if not stock_bajo.empty:
                st.subheader("⚠️ Stock Bajo")
                st.dataframe(stock_bajo, use_container_width=True)

        if not lotes_vencer.empty:
            st.subheader("📦 Próximos a Vencer")
            st.dataframe(lotes_vencer, use_container_width=True)

    # Gestión de Medicamentos
    elif menu == "💊 Gestión de Medicamentos":
        st.header("💊 Gestión de Medicamentos")

        tab1, tab2 = st.tabs(["➕ Agregar Medicamento", "📋 Listado"])

        with tab1:
            with st.form("nuevo_medicamento"):
                col1, col2 = st.columns(2)
                with col1:
                    nombre = st.text_input("Nombre del medicamento *")
                    categoria = st.selectbox("Categoría", ["farmaco", "psicofarmaco"],
                                             format_func=lambda x: "💊 Fármaco" if x == "farmaco" else "🧠 Psicofármaco")
                with col2:
                    stock_inicial = st.number_input("Stock inicial", min_value=0, value=0)
                    stock_minimo = st.number_input("Stock mínimo de alerta", min_value=0, value=10)

                if st.form_submit_button("💾 Guardar Medicamento"):
                    if nombre:
                        if agregar_medicamento(nombre, categoria, stock_inicial, stock_minimo):
                            st.success(f"✅ Medicamento '{nombre}' agregado")
                            st.rerun()
                        else:
                            st.error("❌ Ya existe")
                    else:
                        st.warning("Ingrese un nombre")

        with tab2:
            if medicamentos.empty:
                st.info("No hay medicamentos")
            else:
                st.dataframe(medicamentos, use_container_width=True)
                csv = medicamentos.to_csv(index=False)
                st.download_button("📥 Descargar CSV", csv, "medicamentos.csv")

    # Ingreso con Lote
    elif menu == "📥 Ingreso con Lote":
        st.header("📥 Registrar Ingreso con Lote")

        if medicamentos.empty:
            st.warning("Primero agregue medicamentos")
        else:
            with st.form("ingreso_lote"):
                col1, col2 = st.columns(2)
                with col1:
                    med = st.selectbox("Medicamento", medicamentos['nombre'].tolist())
                    med_id = medicamentos[medicamentos['nombre'] == med]['id'].values[0]
                    lote = st.text_input("Número de Lote *")
                    venc = st.date_input("Fecha Vencimiento", min_value=datetime.now())
                with col2:
                    cant = st.number_input("Cantidad", min_value=1, step=1)
                    motivo = st.text_area("Motivo")

                if st.form_submit_button("✅ Registrar"):
                    if not lote:
                        st.error("Número de lote obligatorio")
                    else:
                        registrar_ingreso(med_id, lote, venc, cant, motivo, st.session_state['username'])
                        st.success(f"✅ Ingreso registrado: +{cant} {med}")
                        st.balloons()
                        st.rerun()

    # Egreso
    elif menu == "📤 Egreso":
        st.header("📤 Registrar Egreso")

        if medicamentos.empty:
            st.warning("No hay medicamentos")
        else:
            med = st.selectbox("Medicamento", medicamentos['nombre'].tolist())
            med_id = medicamentos[medicamentos['nombre'] == med]['id'].values[0]
            stock_actual = medicamentos[medicamentos['id'] == med_id]['stock'].values[0]

            st.info(f"💊 Stock disponible: **{stock_actual}**")
            cant = st.number_input("Cantidad", min_value=1, max_value=stock_actual if stock_actual > 0 else 1)
            motivo = st.text_area("Motivo")

            if st.button("✅ Confirmar Egreso"):
                exito, msg = registrar_egreso(med_id, cant, motivo, st.session_state['username'])
                if exito:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    # Carro de Paro
    elif menu == "🚑 Carro de Paro":
        st.header("🚑 Carro de Paro")
        carro = obtener_carro_paro()
        if carro.empty:
            st.info("No hay medicamentos")
        else:
            st.dataframe(carro, use_container_width=True)

    # Lotes y Vencimientos
    elif menu == "📦 Lotes y Vencimientos":
        st.header("📦 Lotes Próximos a Vencer")
        if lotes_vencer.empty:
            st.success("✅ No hay lotes próximos a vencer")
        else:
            st.dataframe(lotes_vencer, use_container_width=True)

    # Reportes
    elif menu == "📈 Reportes":
        st.header("📈 Reportes")
        if st.button("📄 Generar Reporte PDF"):
            pdf = generar_reporte_pdf()
            st.download_button("📥 Descargar PDF", pdf, "reporte.pdf")

    # Cambiar Contraseña
    elif menu == "🔐 Cambiar Contraseña":
        st.header("🔐 Cambiar Contraseña")
        with st.form("cambiar_pass"):
            old_pass = st.text_input("Contraseña actual", type="password")
            new_pass = st.text_input("Contraseña nueva", type="password")
            confirm_pass = st.text_input("Confirmar contraseña", type="password")

            if st.form_submit_button("Cambiar"):
                if new_pass == confirm_pass:
                    if cambiar_password(st.session_state['username'], old_pass, new_pass):
                        st.success("✅ Contraseña cambiada")
                    else:
                        st.error("❌ Contraseña actual incorrecta")
                else:
                    st.error("❌ Las contraseñas no coinciden")

    # Gestión de Usuarios
    elif menu == "👥 Gestión de Usuarios":
        if verificar_permiso('admin'):
            gestionar_usuarios()
        else:
            st.error("❌ Sin permiso")


if __name__ == "__main__":
    main()