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
                supabase.table("pagos").insert({
                    "abonado_id": id_abonado,
                    "mes_pagado": mes_pagado,
                    "fecha_pago": fecha_pago.isoformat(),
                    "estado_pago": "al día"
                }).execute()

                st.success("✅ Pago registrado.")
                st.subheader("📄 Factura generada")

                class FacturaPDF(FPDF):
                    def header(self):
                        self.set_fill_color(220, 230, 255)
                        self.set_text_color(0)
                        self.set_font("Arial", "B", 16)
                        self.cell(0, 12, "Asociación de Desarrollo Integral de Colonia Carvajal", ln=True, align="C")
                        self.set_font("Arial", "", 12)
                        self.cell(0, 10, "Factura por pago de servicio de agua potable", ln=True, align="C")
                        self.ln(10)

                    def footer(self):
                        self.set_y(-15)
                        self.set_font("Arial", "I", 10)
                        self.set_text_color(100)
                        self.cell(0, 10, f"Página {self.page_no()} - Acueducto ADI Colonia Carvajal", 0, 0, "C")

                    def watermark(self, text):
                        self.set_text_color(240, 240, 240)
                        self.set_font("Arial", "B", 40)
                        self.rotate(45, x=self.w/2, y=self.h/2)
                        self.text(x=30, y=self.h/2, txt=text)
                        self.rotate(0)

                    def rotate(self, angle, x=None, y=None):
                        from math import cos, sin, radians
                        angle = radians(angle)
                        c = cos(angle)
                        s = sin(angle)
                        if x is None:
                            x = self.x
                        if y is None:
                            y = self.y
                        self._out(f'q {c:.5f} {s:.5f} {-s:.5f} {c:.5f} {x:.2f} {y:.2f} cm')
                        self._out('Q')

                image_obj = Image.open(imagen)

                pdf = FacturaPDF()
                pdf.add_page()
                pdf.watermark("ADI Colonia Carvajal")

                pdf.set_font("Arial", "B", 12)
                pdf.set_draw_color(200, 0, 0)
                pdf.set_fill_color(220, 255, 220)
                pdf.set_text_color(0, 0, 0)

                pdf.cell(50, 10, "Abonado:", 1, 0, "L", 1)
                pdf.cell(130, 10, abonado_seleccionado, 1, 1, "L")

                pdf.cell(50, 10, "Mes pagado:", 1, 0, "L", 1)
                pdf.cell(130, 10, mes_pagado, 1, 1, "L")

                pdf.cell(50, 10, "Fecha de pago:", 1, 0, "L", 1)
                pdf.cell(130, 10, fecha_pago.strftime('%d/%m/%Y'), 1, 1, "L")

                pdf.ln(10)
                pdf.set_font("Arial", "B", 12)
                pdf.set_text_color(0, 102, 204)
                pdf.cell(0, 10, "Prueba de Pago:", ln=True)

                img_buffer = BytesIO()
                image_obj.save(img_buffer, format="PNG")
                img_buffer.seek(0)
                pdf.image(img_buffer, x=55, y=pdf.get_y() + 5, w=100)

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

        df_abonados["creado_en"] = pd.to_datetime(df_abonados["creado_en"])
        fecha_min = df_abonados["creado_en"].min().date()
        fecha_max = df_abonados["creado_en"].max().date()

        col1, col2 = st.columns(2)
        with col1:
            desde = st.date_input("📅 Mostrar abonados registrados desde:", value=fecha_min, min_value=fecha_min, max_value=fecha_max)
        with col2:
            hasta = st.date_input("📅 Hasta:", value=fecha_max, min_value=fecha_min, max_value=fecha_max)

        mask = (df_abonados["creado_en"].dt.date >= desde) & (df_abonados["creado_en"].dt.date <= hasta)
        df_abonados_filtrado = df_abonados[mask].copy()

        df_abonados_filtrado.rename(columns={
            "numero_abonado": "Número de Abonado",
            "cedula": "Cédula",
            "nombre_completo": "Nombre",
            "creado_en": "Registrado El"
        }, inplace=True)

        df_abonados_filtrado["Registrado El"] = df_abonados_filtrado["Registrado El"].dt.strftime("%d/%m/%Y")

        # Agrupar pagos por abonado y obtener meses
        df_pagos_df = pd.DataFrame(pagos)
        pagos_por_abonado = df_pagos_df.groupby("abonado_id")["mes_pagado"].apply(lambda x: ", ".join(x)).to_dict()
        df_abonados_filtrado["Meses Pagados"] = df_abonados_filtrado["id"].map(pagos_por_abonado).fillna("")

        df_abonados_filtrado.drop(columns=["id"], inplace=True)

        df_pagos.rename(columns={
            "mes_pagado": "Mes Pagado",
            "fecha_pago": "Fecha de Pago",
            "estado_pago": "Estado",
            "abonado_id": "ID Abonado"
        }, inplace=True)

        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_abonados_filtrado.to_excel(writer, sheet_name="Abonados", index=False)
            df_pagos.to_excel(writer, sheet_name="Pagos", index=False)

        output.seek(0)

        st.download_button(
            label="📥 Descargar Excel de respaldo",
            data=output,
            file_name="respaldo_acueducto.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )



