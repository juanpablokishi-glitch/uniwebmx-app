import streamlit as st
from core.config import UNIVERSIDADES_DATA, DOCUMENTOS_LOCKER_INFO
from core.database import guardar_datos_usuario
from services.documents import generar_zip_carpeta

def _nombre_seguro(nombre):
    """Simple helper to make a filename safe."""
    return nombre.replace(" ", "_").lower()

def render_mi_aplicacion():
    _user = st.session_state.get("user")

    # Helper for minor check (should ideally be in a service)
    def es_usuario_menor():
        return st.session_state.get("es_menor_edad_actual", False)

    def _tutor_confirmado_fresco(user):
        # This logic was in app.py, should be in core/auth or core/database
        # For now, we check the session state.
        return st.session_state.get("tutor_confirmado_actual", False)

    if es_usuario_menor() and not _tutor_confirmado_fresco(_user):
        st.markdown("""
        <div class="hero-section-locker">
            <h1 style='font-size: 3.5rem; margin-bottom: 1.5rem; max-width: 900px; margin-left: auto; margin-right: auto;'>Mi Aplicación</h1>
        </div>
        """, unsafe_allow_html=True)
        st.markdown(
            "<div style='max-width:680px;margin:0 auto;background:#FAEEDA;border-radius:12px;padding:28px 32px;'>"
            "<h3 style='margin-top:0;color:#5F4B1E;font-size:1.15rem;'>Esta sección no está disponible todavía</h3>"
            "<p style='font-size:0.92rem;color:#5F4B1E;line-height:1.7;margin-bottom:0;'>"
            "Las carpetas por universidad se arman con los documentos de tu Locker Digital, que se desbloquea en "
            "cuanto tu padre, madre o tutor legal confirme por correo. Mientras tanto, puedes seguir usando a Hugo "
            "para resolver dudas sobre tu proceso de admisión."
            "</p></div>",
            unsafe_allow_html=True,
        )
    else:
        if "unis_seleccionadas" not in st.session_state:
            st.session_state.unis_seleccionadas = []

        st.markdown("""
        <div class="hero-section-locker">
            <h1 style='font-size: 3.5rem; margin-bottom: 1.5rem; max-width: 900px; margin-left: auto; margin-right: auto;'>Mi Aplicación</h1>
            <p style='font-size: 1.35rem; color: #1A1A1A; max-width: 850px; margin: 0 auto; line-height: 1.6; font-weight: 400; opacity: 0.9;'>
                Elige a qué universidades quieres aplicar. Armamos una carpeta por cada una con los documentos que pide, usando lo que ya subiste a tu Locker Digital.
            </p>
        </div>
        """, unsafe_allow_html=True)

        unis_elegidas = st.multiselect(
            "¿A qué universidades quieres aplicar?",
            options=list(UNIVERSIDADES_DATA.keys()),
            default=st.session_state.unis_seleccionadas,
            key="multiselect_mi_aplicacion",
        )

        if unis_elegidas != st.session_state.unis_seleccionadas:
            st.session_state.unis_seleccionadas = unis_elegidas
            guardar_datos_usuario(_user, st.session_state.__dict__)
            st.rerun()

        st.markdown("<div style='margin-bottom:1.5rem;'></div>", unsafe_allow_html=True)

        if not unis_elegidas:
            st.info("Selecciona una o más universidades arriba para ver sus carpetas de documentos.")
        else:
            for nombre_uni in unis_elegidas:
                datos_uni = UNIVERSIDADES_DATA[nombre_uni]
                docs_requeridos = datos_uni.get("documentos", [])
                docs_extra = datos_uni.get("documentos_extra", [])

                total_items = len(docs_requeridos) + len(docs_extra)
                completos = sum(
                    1 for d in docs_requeridos
                    if st.session_state.get(("kárdex" if d == "kardex" else d), {}).get("nombre")
                )

                with st.expander(f"📁 {nombre_uni}  —  {completos}/{len(docs_requeridos)} documentos listos", expanded=True):
                    st.caption(f"Avance de la carpeta: {completos} de {len(docs_requeridos)} documentos del Locker ya están listos.")
                    st.progress(completos / len(docs_requeridos) if docs_requeridos else 0)

                    for d in docs_requeridos:
                        sk = "kárdex" if d == "kardex" else d
                        info_doc = DOCUMENTOS_LOCKER_INFO.get(d, {"label": d})
                        doc_guardado = st.session_state.get(sk, {})
                        col_check, col_nombre, col_accion = st.columns([0.4, 3, 1.5])
                        with col_check:
                            st.markdown("✅" if doc_guardado.get("nombre") else "⬜")
                        with col_nombre:
                            if doc_guardado.get("nombre"):
                                st.markdown(f"**{info_doc['label']}** — {doc_guardado['nombre']}")
                            else:
                                st.markdown(f"**{info_doc['label']}** — *pendiente*")
                        with col_accion:
                            if not doc_guardado.get("nombre"):
                                if st.button("Subir en Locker", key=f"ir_locker_{nombre_uni}_{d}"):
                                    # The routing is handled by app.py, but since we are in a render function,
                                    # we should use a mechanism to change pages.
                                    # In the current thin entry point design, we might need a helper.
                                    # For now, we'll use st.query_params if available or just rerun.
                                    st.query_params["nav"] = "locker"
                                    st.rerun()

                    if docs_extra:
                        st.markdown("<p style='font-size:0.85rem;color:#888;margin-top:10px;margin-bottom:4px;'>Otros requisitos (gestiónalos directo con la universidad):</p>", unsafe_allow_html=True)
                        for extra in docs_extra:
                            st.markdown(f"<p style='font-size:0.9rem;color:#444;margin:2px 0;'>⬜ {extra}</p>", unsafe_allow_html=True)

                    if completos == len(docs_requeridos) and docs_requeridos:
                        st.success("¡Carpeta completa! Ya tienes todos los documentos del Locker listos para esta universidad.")

                    if completos > 0:
                        zip_bytes, num_incluidos = generar_zip_carpeta(_user, docs_requeridos)
                        st.download_button(
                            f"⬇ Descargar carpeta ZIP ({num_incluidos}/{len(docs_requeridos)} documentos)",
                            data=zip_bytes,
                            file_name=f"Uniwebmx_{_nombre_seguro(nombre_uni)}.zip",
                            mime="application/zip",
                            key=f"zip_{_nombre_seguro(nombre_uni)}",
                        )

        st.markdown("<div style='margin-bottom:2rem;'></div>", unsafe_allow_html=True)
        st.caption("Tip: las carpetas se actualizan solas en cuanto subas o reemplaces un documento en tu Locker Digital.")
