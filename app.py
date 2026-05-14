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

    with st.expander("🔐 Resetear contraseña de usuario"):
        with st.form("reset_pass"):
            usuario_reset = st.text_input("Usuario")
            nueva_pass = st.text_input("Nueva contraseña", type="password")

            if st.form_submit_button("Resetear contraseña"):
                if usuario_reset and nueva_pass:
                    hashed = hashlib.sha256(nueva_pass.encode()).hexdigest()
                    conn = get_connection()
                    conn.execute("UPDATE usuarios SET password = ? WHERE username = ?", (hashed, usuario_reset))
                    conn.commit()
                    conn.close()
                    st.success(f"✅ Contraseña de {usuario_reset} actualizada")
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
        # Agregar al carro de paro automáticamente
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
    df = pd.read_sql_query(
        "SELECT nombre, categoria, stock, stock_minimo FROM medicamentos WHERE stock <= stock_minimo", conn)
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
    df = pd.read_sql_query('''
                           SELECT m.nombre, m.categoria, l.numero_lote, l.fecha_vencimiento, l.cantidad_restante
                           FROM lotes l
                                    JOIN medicamentos m ON l.medicamento_id = m.id
                           WHERE l.fecha_vencimiento <= ?
                             AND l.cantidad_restante > 0
                           ORDER BY l.fecha_vencimiento ASC
                           ''', conn, params=(fecha_limite,))
    conn.close()
    return df


# ============ FUNCIONES CARRO DE PARO ============
def obtener_carro_paro():
    conn = get_connection()
    df = pd.read_sql_query('''
                           SELECT m.id, m.nombre, m.categoria, cp.cantidad, cp.cantidad_minima, cp.ultima_revision
                           FROM carro_paro cp
                                    JOIN medicamentos m ON cp.medicamento_id = m.id
                           ORDER BY m.categoria, m.nombre
                           ''', conn)
    conn.close()
    return df


def reponer_carro_paro(medicamento_id, cantidad):
    conn = get_connection()
    conn.execute("UPDATE carro_paro SET cantidad = cantidad + ? WHERE medicamento_id = ?", (cantidad, medicamento_id))
    conn.commit()
    conn.close()


def usar_carro_paro(medicamento_id, cantidad, motivo, usuario):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT cantidad FROM carro_paro WHERE medicamento_id = ?", (medicamento_id,))
    stock_actual = cursor.fetchone()[0]

    if stock_actual < cantidad:
        conn.close()
        return False, "Stock insuficiente en carro de paro"

    cursor.execute("UPDATE carro_paro SET cantidad = cantidad - ? WHERE medicamento_id = ?", (cantidad, medicamento_id))

    cursor.execute('''
                   INSERT INTO movimientos (medicamento_id, tipo, cantidad, motivo, usuario)
                   VALUES (?, 'carro_egreso', ?, ?, ?)
                   ''', (medicamento_id, cantidad, motivo, usuario))

    conn.commit()
    conn.close()
    return True, "Uso registrado"


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
        data.append([row['nombre'], row['categoria'], str(row['stock']), str(row['stock_minimo'])])

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


def generar_reporte_carro_pdf():
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()

    story.append(Paragraph("Inventario del Carro de Paro", styles['Title']))
    story.append(Spacer(1, 20))
    story.append(Paragraph(f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
    story.append(Spacer(1, 20))

    carro = obtener_carro_paro()

    if not carro.empty:
        data = [['Medicamento', 'Categoría', 'Cantidad', 'Mínimo', 'Última Revisión']]
        for _, row in carro.iterrows():
            data.append([
                row['nombre'], row['categoria'], str(row['cantidad']),
                str(row['cantidad_minima']), row['ultima_revision'] or 'No registrada'
            ])

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


def grafico_movimientos_recientes():
    conn = get_connection()
    df = pd.read_sql_query('''
                           SELECT date (fecha) as dia, SUM (CASE WHEN tipo IN ('ingreso') THEN cantidad ELSE 0 END) as ingresos, SUM (CASE WHEN tipo IN ('egreso') THEN cantidad ELSE 0 END) as egresos
                           FROM movimientos
                           WHERE fecha >= date ('now', '-30 days')
                           GROUP BY date (fecha)
                           ORDER BY dia DESC
                               LIMIT 10
                           ''', conn)
    conn.close()

    if not df.empty:
        fig = go.Figure()
        fig.add_trace(go.Bar(name='Ingresos', x=df['dia'], y=df['ingresos'], marker_color='#2E86AB'))
        fig.add_trace(go.Bar(name='Egresos', x=df['dia'], y=df['egresos'], marker_color='#A23B72'))
        fig.update_layout(title='Últimos movimientos (30 días)',
                          xaxis_title='Fecha', yaxis_title='Cantidad',
                          barmode='group')
        return fig
    return None


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

    # Mostrar tiempo de sesión
    if 'login_time' in st.session_state:
        tiempo = datetime.now() - st.session_state['login_time']
        st.sidebar.caption(f"Sesión: {tiempo.seconds // 60} minutos")

    logout()
    st.sidebar.markdown("---")

    # Mostrar alertas en sidebar
    stock_bajo = obtener_stock_bajo()
    lotes_vencer = obtener_lotes_proximos_vencer(30)

    if not stock_bajo.empty:
        st.sidebar.warning(f"⚠️ {len(stock_bajo)} medicamentos con stock bajo")
    if not lotes_vencer.empty:
        st.sidebar.warning(f"⚠️ {len(lotes_vencer)} lotes próximos a vencer")

    st.sidebar.markdown("---")

    st.title("🏥 Sistema de Control de Medicamentos y Psicofármacos")

    # Métricas rápidas
    medicamentos = obtener_medicamentos()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💊 Fármacos",
                len(medicamentos[medicamentos['categoria'] == 'farmaco']) if not medicamentos.empty else 0)
    col2.metric("🧠 Psicofármacos",
                len(medicamentos[medicamentos['categoria'] == 'psicofarmaco']) if not medicamentos.empty else 0)
    col3.metric("⚠️ Stock Bajo", len(stock_bajo))
    col4.metric("📦 Lotes por Vencer", len(lotes_vencer))

    st.markdown("---")

    # Menú principal
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

    # ============ DASHBOARD ============
    if menu == "📊 Dashboard":
        st.header("📊 Dashboard")

        col1, col2 = st.columns(2)
        with col1:
            fig1 = grafico_stock_por_categoria()
            if fig1:
                st.plotly_chart(fig1, use_container_width=True)
            else:
                st.info("No hay datos para mostrar")

        with col2:
            fig2 = grafico_movimientos_recientes()
            if fig2:
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("No hay movimientos recientes")

        # Mostrar stock bajo
        if not stock_bajo.empty:
            st.subheader("⚠️ Medicamentos con Stock Bajo")
            st.dataframe(stock_bajo, use_container_width=True)

        # Mostrar lotes por vencer
        if not lotes_vencer.empty:
            st.subheader("📦 Lotes Próximos a Vencer")
            st.dataframe(lotes_vencer, use_container_width=True)

    # ============ GESTIÓN DE MEDICAMENTOS ============
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

                submitted = st.form_submit_button("💾 Guardar Medicamento")

                if submitted:
                    if nombre:
                        if agregar_medicamento(nombre, categoria, stock_inicial, stock_minimo):
                            st.success(f"✅ Medicamento '{nombre}' agregado correctamente")
                            st.rerun()
                        else:
                            st.error("❌ Ya existe un medicamento con ese nombre")
                    else:
                        st.warning("Ingrese un nombre")

        with tab2:
            filtro = st.radio("Filtrar por", ["Todos", "Fármacos", "Psicofármacos"], horizontal=True)

            df = obtener_medicamentos()
            if df.empty:
                st.info("No hay medicamentos registrados")
            else:
                if filtro == "Fármacos":
                    df = df[df['categoria'] == 'farmaco']
                elif filtro == "Psicofármacos":
                    df = df[df['categoria'] == 'psicofarmaco']

                st.dataframe(df, use_container_width=True)
                csv = df.to_csv(index=False)
                st.download_button("📥 Descargar CSV", csv, "medicamentos.csv")

    # ============ INGRESO CON LOTE ============
    elif menu == "📥 Ingreso con Lote":
        st.header("📥 Registrar Ingreso con Número de Lote")

        medicamentos = obtener_medicamentos()
        if medicamentos.empty:
            st.warning("Primero debe agregar medicamentos")
        else:
            with st.form("ingreso_lote"):
                col1, col2 = st.columns(2)
                with col1:
                    med = st.selectbox("Medicamento", medicamentos['nombre'].tolist())
                    med_id = medicamentos[medicamentos['nombre'] == med]['id'].values[0]
                    lote = st.text_input("Número de Lote *")
                    venc = st.date_input("Fecha de Vencimiento", min_value=datetime.now())
                with col2:
                    cant = st.number_input("Cantidad", min_value=1, step=1)
                    motivo = st.text_area("Motivo del Ingreso")

                if st.form_submit_button("✅ Registrar Ingreso"):
                    if not lote:
                        st.error("El número de lote es obligatorio")
                    else:
                        registrar_ingreso(med_id, lote, venc, cant, motivo, st.session_state['username'])
                        st.success(f"✅ Ingreso registrado: +{cantidad} {med}")
                        st.balloons()
                        st.rerun()

    # ============ EGRESO ============
    elif menu == "📤 Egreso":
        st.header("📤 Registrar Egreso")

        medicamentos = obtener_medicamentos()
        if medicamentos.empty:
            st.warning("No hay medicamentos registrados")
        else:
            col1, col2 = st.columns([2, 1])
            with col1:
                med = st.selectbox("Medicamento", medicamentos['nombre'].tolist())
                med_id = medicamentos[medicamentos['nombre'] == med]['id'].values[0]
                stock_actual = medicamentos[medicamentos['id'] == med_id]['stock'].values[0]

                st.info(f"💊 Stock disponible: **{stock_actual}** unidades")

                cant = st.number_input("Cantidad a egresar", min_value=1,
                                       max_value=stock_actual if stock_actual > 0 else 1, step=1)
                motivo = st.text_area("Motivo del Egreso")

                if st.button("✅ Confirmar Egreso", type="primary"):
                    exito, msg = registrar_egreso(med_id, cant, motivo, st.session_state['username'])
                    if exito:
                        st.success(f"✅ {msg}: -{cant} {med}")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")

    # ============ CARRO DE PARO ============
    elif menu == "🚑 Carro de Paro":
        st.header("🚑 Gestión del Carro de Paro")

        tab1, tab2, tab3 = st.tabs(["📋 Inventario", "📥 Reponer", "📤 Uso"])

        with tab1:
            carro = obtener_carro_paro()
            if carro.empty:
                st.info("No hay medicamentos en el carro de paro")
            else:
                # Resaltar stock bajo
                for _, row in carro.iterrows():
                    if row['cantidad'] <= row['cantidad_minima']:
                        st.warning(
                            f"⚠️ **{row['nombre']}** - Stock: {row['cantidad']} (Mínimo: {row['cantidad_minima']})")

                st.dataframe(carro, use_container_width=True)

                if st.button("📝 Marcar revisión realizada"):
                    conn = get_connection()
                    conn.execute("UPDATE carro_paro SET ultima_revision = ?", (datetime.now().strftime('%Y-%m-%d'),))
                    conn.commit()
                    conn.close()
                    st.success("✅ Revisión registrada")
                    st.rerun()

        with tab2:
            st.subheader("Reponer medicamento al carro de paro")
            medicamentos = obtener_medicamentos()

            if not medicamentos.empty:
                med = st.selectbox("Medicamento a reponer", medicamentos['nombre'].tolist())
                med_id = medicamentos[medicamentos['nombre'] == med]['id'].values[0]
                stock_farmacia = medicamentos[medicamentos['id'] == med_id]['stock'].values[0]

                st.info(f"Stock en farmacia: {stock_farmacia}")
                cantidad = st.number_input("Cantidad a reponer", min_value=1, max_value=stock_farmacia, step=1)

                if st.button("✅ Reponer"):
                    exito, msg = registrar_egreso(med_id, cantidad, "Reposición carro de paro",
                                                  st.session_state['username'])
                    if exito:
                        reponer_carro_paro(med_id, cantidad)
                        st.success(f"✅ Repuesto {cantidad} {med} al carro de paro")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")

        with tab3:
            st.subheader("Registrar uso desde carro de paro")
            carro = obtener_carro_paro()

            if not carro.empty:
                med = st.selectbox("Medicamento usado", carro['nombre'].tolist())
                med_id = carro[carro['nombre'] == med]['id'].values[0]
                cantidad_actual = carro[carro['nombre'] == med]['cantidad'].values[0]

                st.info(f"Stock actual en carro: {cantidad_actual}")
                cantidad = st.number_input("Cantidad usada", min_value=1, max_value=cantidad_actual, step=1)
                motivo = st.text_input("Motivo del uso")

                if st.button("✅ Registrar uso"):
                    exito, msg = usar_carro_paro(med_id, cantidad, motivo, st.session_state['username'])
                    if exito:
                        st.success(f"✅ {msg}: -{cantidad} {med}")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")

    # ============ LOTES Y VENCIMIENTOS ============
    elif menu == "📦 Lotes y Vencimientos":
        st.header("📦 Control de Lotes y Vencimientos")

        lotes = obtener_lotes_proximos_vencer(30)
        if lotes.empty:
            st.success("✅ No hay lotes próximos a vencer en los próximos 30 días")
        else:
            st.warning(f"⚠️ {len(lotes)} lotes próximos a vencer")
            st.dataframe(lotes, use_container_width=True)

        st.markdown("---")

        with st.expander("📋 Ver todos los lotes"):
            conn = get_connection()
            todos_lotes = pd.read_sql_query('''
                                            SELECT m.nombre,
                                                   m.categoria,
                                                   l.numero_lote,
                                                   l.fecha_vencimiento,
                                                   l.cantidad,
                                                   l.cantidad_restante,
                                                   l.fecha_ingreso
                                            FROM lotes l
                                                     JOIN medicamentos m ON l.medicamento_id = m.id
                                            ORDER BY l.fecha_vencimiento ASC
                                            ''', conn)
            conn.close()
            st.dataframe(todos_lotes, use_container_width=True)

    # ============ REPORTES ============
    elif menu == "📈 Reportes":
        st.header("📈 Generación de Reportes")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("📄 Reporte de Stock (PDF)", use_container_width=True):
                with st.spinner("Generando reporte..."):
                    pdf = generar_reporte_pdf()
                    st.download_button(
                        label="📥 Descargar PDF",
                        data=pdf,
                        file_name=f"reporte_stock_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf"
                    )

        with col2:
            if st.button("🚑 Reporte Carro de Paro (PDF)", use_container_width=True):
                with st.spinner("Generando reporte..."):
                    pdf = generar_reporte_carro_pdf()
                    st.download_button(
                        label="📥 Descargar PDF",
                        data=pdf,
                        file_name=f"reporte_carro_paro_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf"
                    )

        st.markdown("---")

        # Mostrar últimos movimientos
        st.subheader("📜 Últimos movimientos")
        conn = get_connection()
        movimientos = pd.read_sql_query('''
                                        SELECT datetime(fecha, 'localtime') as fecha,
                                               m2.nombre,
                                               tipo,
                                               cantidad,
                                               motivo,
                                               usuario
                                        FROM movimientos m
                                                 JOIN medicamentos m2 ON m.medicamento_id = m2.id
                                        ORDER BY m.fecha DESC LIMIT 50
                                        ''', conn)
        conn.close()

        if not movimientos.empty:
            st.dataframe(movimientos, use_container_width=True)

    # ============ CAMBIAR CONTRASEÑA ============
    elif menu == "🔐 Cambiar Contraseña":
        st.header("🔐 Cambiar Contraseña")

        with st.form("cambiar_password"):
            password_actual = st.text_input("Contraseña actual", type="password")
            password_nueva = st.text_input("Contraseña nueva", type="password")
            password_confirmar = st.text_input("Confirmar contraseña nueva", type="password")

            if st.form_submit_button("Cambiar contraseña", type="primary"):
                if not password_actual or not password_nueva:
                    st.warning("Complete todos los campos")
                elif password_nueva != password_confirmar:
                    st.error("❌ Las contraseñas nuevas no coinciden")
                elif len(password_nueva) < 4:
                    st.error("❌ La contraseña debe tener al menos 4 caracteres")
                else:
                    if cambiar_password(st.session_state['username'], password_actual, password_nueva):
                        st.success("✅ Contraseña cambiada exitosamente")
                        st.info("Vuelve a iniciar sesión con tu nueva contraseña")
                        if st.button("Cerrar sesión ahora"):
                            for key in list(st.session_state.keys()):
                                del st.session_state[key]
                            st.rerun()
                    else:
                        st.error("❌ Contraseña actual incorrecta")

    # ============ GESTIÓN DE USUARIOS ============
    elif menu == "👥 Gestión de Usuarios":
        if verificar_permiso('admin'):
            gestionar_usuarios()
        else:
            st.error("❌ No tienes permiso para acceder a esta sección")


if __name__ == "__main__":
    main()