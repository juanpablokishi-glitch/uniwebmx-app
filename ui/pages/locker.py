import streamlit as st
from services.documents import obtener_archivo_original, guardar_archivo_original, eliminar_archivo_original, generar_zip_carpeta, get_signed_url_for_pdf
from services.ai_hugo import get_hugo_response_stream
from core.database import guardar_datos_usuario, cargar_datos_usuario
from core.config import DOCUMENTOS_LOCKER_INFO
import base64

def render_locker():
    username = st.session_state.user
    st.markdown(f'<div class="hero-section-locker"> <h1 style="color:white; font-size:3rem;">Locker Digital de {st.session_state.get("perfil_nombre", username)}</h1> <p style="color:rgba(255,255,255,0.9); font-size:1.2rem;">Tus documentos académicos y personales organizados y seguros.</p> </div>', unsafe_allow_html=True)

    # Check for minor without tutor confirmation
    if st.session_state.get("es_menor_edad_actual") and not st.session_state.get("tutor_confirmado_actual"):
        st.warning("Tu Locker Digital está temporalmente desactivado. Una vez que tu tutor confirme la cuenta vía correo, podrás subir y guardar tus documentos aquí.")
        return

    # Render academic documents
    for key, info in DOCUMENTOS_LOCKER_INFO.items():
        render_document_slot(username, key, info["label"])

    # Export All Academic Documents
    st.markdown("---")
    st.subheader("Exportación Masiva")
    academic_keys = [k for k, v in DOCUMENTOS_LOCKER_INFO.items() if v["tipo"] == "académico"]
    if st.button("Descargar todos mis documentos académicos (.zip)"):
        zip_data, count = generar_zip_carpeta(username, academic_keys)
        if count > 0:
            st.download_button("Descargar ZIP", data=zip_data, file_name=f"documentos_{username}.zip", mime="application/zip")
        else:
            st.error("No hay documentos académicos para exportar.")

def render_document_slot(username, key, label):
    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**{label}**")
            # Input for uploading
            uploaded_file = st.file_uploader(f"Subir {label}", type=["pdf", "jpg", "jpeg", "png"], key=f"up_{key}")
            if uploaded_file:
                # Save to Supabase
                guardar_archivo_original(username, key, uploaded_file.name, uploaded_file.getvalue())
                st.success(f"Archivo {uploaded_file.name} guardado.")
                st.rerun()

        with col2:
            # View/Download existing
            datos, nombre = obtener_archivo_original(username, key)
            if datos:
                st.download_button("Descargar", data=datos, file_name=nombre, key=f"dl_{key}")
                if nombre.lower().endswith(".pdf"):
                    # Use signed URL for preview
                    url = get_signed_url_for_pdf(username, key)
                    if url:
                        with st.expander("Vista Previa"):
                            st.markdown(f'<iframe src="{url}" width="100%" height="500" style="border:1px solid #EAEAEA; border-radius:6px;"></iframe>', unsafe_allow_html=True)
                elif nombre.lower().endswith((".jpg", ".jpeg", ".png")):
                    st.image(datos, caption=nombre)

                if st.button("Quitar", key=f"rm_{key}"):
                    eliminar_archivo_original(username, key)
                    st.rerun()
