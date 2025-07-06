import streamlit as st
from supabase import create_client, Client
import pandas as pd
from fpdf import FPDF
from PIL import Image
from io import BytesIO
from datetime import date
import base64

# ---------- CONFIGURACIÓN INICIAL ----------
st.set_page_config(page_title="Control de Acueducto", layout="wide")

# ---------- CONEXIÓN A SUPABASE ----------
SUPABASE_URL = "https://pxrzgpnkigsdxvbnhcgz.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InB4cnpncG5raWdzZHh2Ym5oY2d6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTE4MzMyMTEsImV4cCI6MjA2NzQwOTIxMX0.loF6OLX2fik1jH9b-j1d61rQhait-noNSQHa-MIJs14"

@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_connection()

# ---------- TÍTULO ----------
st.title("💧 Control de Acueducto - ADI Colonia Carvajal")

# ---------- MENÚ PRINCIPAL ----------
menu = st.sidebar.radio(
    "Selecciona una pestaña",
    ["➕ Agregar Abonado", "👥 Gestión de Abonados", "💵 Pagos", "📤 Respaldo"]
)
# ---------- PESTAÑA: AGREGAR ABONADO ----------
if menu == "➕ Agregar Abonado":
    st.subheader("Registro de nuevo abonado")

    with st.form("form_agregar_abonado", clear_on_submit=True):
        numero_abonado = st.number_input("Número de Abonado", min_value=1, step=1)
        cedula = st.text_input("Cédula", max_chars=20)
        nombre_completo = st.text_input("Nombre completo y apellidos", max_chars=100)

        submitted = st.form_submit_button("Registrar Abonado")

        if submitted:
            # Validar campos obligatorios
            if not cedula or not nombre_completo:
                st.warning("⚠️ Todos los campos son obligatorios.")
            else:
                # Verificar que no exista ya el número de abonado
                existing = supabase.table("abonados").select("*").eq("numero_abonado", numero_abonado).execute()
                if existing.data:
                    st.error(f"Ya existe un abonado con el número {numero_abonado}.")
                else:
                    # Insertar nuevo abonado
                    result = supabase.table("abonados").insert({
                        "numero_abonado": numero_abonado,
                        "cedula": cedula,
                        "nombre_completo": nombre_completo
                    }).execute()
                    if result.data:
                        st.success("✅ Abonado registrado exitosamente.")
                    else:
                        st.error("❌ Ocurrió un error al registrar el abonado.")
# ---------- PESTAÑA: GESTIÓN DE ABONADOS ----------
if menu == "👥 Gestión de Abonados":
    st.subheader("Lista de Abonados Registrados")

    abonados_data = supabase.table("abonados").select("*").order("numero_abonado", desc=False).execute()

    if not abonados_data.data:
        st.info("No hay abonados registrados.")
    else:
        df_abonados = pd.DataFrame(abonados_data.data)
        df_abonados["Acción"] = ""

        abonado_seleccionado = st.selectbox(
            "Selecciona un abonado para gestionar:",
            df_abonados["numero_abonado"].astype(str) + " - " + df_abonados["nombre_completo"],
            index=0
        )

        # Obtener ID real del abonado
        seleccionado_id = df_abonados.loc[
            df_abonados["numero_abonado"].astype(str) + " - " + df_abonados["nombre_completo"] == abonado_seleccionado,
            "id"
        ].values[0]

        datos_abonado = df_abonados[df_abonados["id"] == seleccionado_id].iloc[0]

        st.write("### Editar Información")
        nuevo_numero = st.number_input("Número de Abonado", value=datos_abonado["numero_abonado"], step=1)
        nueva_cedula = st.text_input("Cédula", value=datos_abonado["cedula"])
        nuevo_nombre = st.text_input("Nombre completo y apellidos", value=datos_abonado["nombre_completo"])

        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Guardar Cambios"):
                update = supabase.table("abonados").update({
                    "numero_abonado": nuevo_numero,
                    "cedula": nueva_cedula,
                    "nombre_completo": nuevo_nombre
                }).eq("id", seleccionado_id).execute()
                if update.data:
                    st.success("✅ Abonado actualizado.")
                    st.experimental_rerun()
                else:
                    st.error("❌ No se pudieron guardar los cambios.")

        with col2:
            if st.button("🗑️ Eliminar Abonado"):
                confirm = st.confirm("¿Estás seguro de eliminar este abonado? Esta acción no se puede deshacer.")
                if confirm:
                    supabase.table("abonados").delete().eq("id", seleccionado_id).execute()
                    st.success("✅ Abonado eliminado.")
                    st.experimental_rerun()
# ---------- PESTAÑA: PAGOS ----------
if menu == "💵 Pagos":
    st.subheader("Registrar Pago de Abonado")

    # Cargar abonados
    abonados = supabase.table("abonados").select("*").order("numero_abonado", desc=False).execute().data
    if not abonados:
        st.info("Primero debes registrar abonados.")
    else:
        abonado_dict = {f'{a["numero_abonado"]} - {a["nombre_completo"]}': a["id"] for a in abonados}
        abonado_seleccionado = st.selectbox("Selecciona un abonado", list(abonado_dict.keys()))
        id_abonado = abonado_dict[abonado_seleccionado]

        mes_pagado = st.text_input("Mes o meses pagados (Ej: Julio 2025)")
        fecha_pago = st.date_input("Fecha de pago", value=date.today())
        imagen = st.file_uploader("Pantallazo del SINPE (imagen JPG o PNG)", type=["png", "jpg", "jpeg"])

        if st.button("💾 Registrar Pago y Generar Factura"):
            if not mes_pagado or not imagen:
                st.warning("Debes ingresar todos los datos y subir el comprobante.")
            else:
                # ✅ Registrar pago (con fecha en formato ISO)
                supabase.table("pagos").insert({
                    "abonado_id": id_abonado,
                    "mes_pagado": mes_pagado,
                    "fecha_pago": fecha_pago.isoformat(),
                    "estado_pago": "al día"
                }).execute()

                st.success("✅ Pago registrado.")

                # Mostrar PDF generado
                st.subheader("📄 Factura generada")

                image = Image.open(imagen)

                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", "B", 14)

                # Marca de agua
                pdf.set_text_color(230, 230, 230)
                for y in range(30, 280, 50):
                    pdf.set_xy(30, y)
                    pdf.cell(0, 10, "ADI Colonia Carvajal", 0, 0, 'C')

                pdf.set_text_color(0, 0, 0)
                pdf.set_xy(10, 20)
                pdf.cell(0, 10, "Asociación de Desarrollo Integral de Colonia Carvajal", ln=True)
                pdf.set_font("Arial", "", 12)
                pdf.cell(0, 10, f"Abonado: {abonado_seleccionado}", ln=True)
                pdf.cell(0, 10, f"Mes pagado: {mes_pagado}", ln=True)
                pdf.cell(0, 10, f"Fecha de pago: {fecha_pago.strftime('%d/%m/%Y')}", ln=True)

                img_buffer = BytesIO()
                image.save(img_buffer, format="PNG")
                img_buffer.seek(0)

                pdf.image(img_buffer, x=30, y=90, w=150)

                pdf_output = BytesIO()
                pdf.output(pdf_output)
                pdf_output.seek(0)

                st.download_button(
                    label="📥 Descargar Factura PDF",
                    data=pdf_output,
                    file_name=f"factura_{abonado_seleccionado.replace(' ', '_')}.pdf",
                    mime="application/pdf"
                )

# ---------- PESTAÑA: RESPALDO ----------
if menu == "📤 Respaldo":
    st.subheader("📦 Descargar respaldo en Excel")

    abonados = supabase.table("abonados").select("*").execute().data
    pagos = supabase.table("pagos").select("*").execute().data

    if not abonados:
        st.info("No hay datos para exportar.")
    else:
        df_abonados = pd.DataFrame(abonados)
        df_pagos = pd.DataFrame(pagos)

        df_abonados.rename(columns={
            "numero_abonado": "Número de Abonado",
            "cedula": "Cédula",
            "nombre_completo": "Nombre",
            "creado_en": "Registrado En"
        }, inplace=True)

        df_pagos.rename(columns={
            "mes_pagado": "Mes Pagado",
            "fecha_pago": "Fecha de Pago",
            "estado_pago": "Estado",
            "abonado_id": "ID Abonado"
        }, inplace=True)

        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_abonados.to_excel(writer, sheet_name="Abonados", index=False)
            df_pagos.to_excel(writer, sheet_name="Pagos", index=False)

        output.seek(0)

        st.download_button(
            label="📥 Descargar Excel de respaldo",
            data=output,
            file_name="respaldo_acueducto.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


