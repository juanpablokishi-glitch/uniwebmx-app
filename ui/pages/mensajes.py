import streamlit as st
import imaplib
from core.config import PROVEEDORES_IMAP
from core.database import guardar_datos_usuario
from services.email_imap import conectar_correo_imap, buscar_correos_universidades

def render_mensajes():
    _user = st.session_state.get("user")
    st.session_state.setdefault("correo_conectado", "")
    st.session_state.setdefault("proveedor_correo", "")
    st.session_state.setdefault("correo_password_sesion", "")
    st.session_state.setdefault("mensajes_universidades", {})

    st.markdown("""
    <div class="hero-section-locker">
        <h1 style='font-size: 3.5rem; margin-bottom: 1.5rem; max-width: 900px; margin-left: auto; margin-right: auto;'>Centro de Mensajes</h1>
        <p style='font-size: 1.35rem; color: #1A1A1A; max-width: 850px; margin: 0 auto; line-height: 1.6; font-weight: 400; opacity: 0.9;'>
            Conecta tu correo y revisa en un solo lugar los mensajes que te lleguen de las universidades a las que estás aplicando.
        </p>
    </div>
    """, unsafe_allow_html=True)

    correo_activo = st.session_state.correo_conectado and st.session_state.correo_password_sesion

    if not correo_activo:
        st.info(
            "Tu contraseña **nunca se guarda en disco**: solo vive en esta sesión mientras tienes la pestaña abierta. "
            "Si usas Gmail u Outlook, necesitas generar una **contraseña de aplicación** (no la de tu cuenta normal) "
            "porque ambos bloquean el acceso de apps externas con la contraseña regular."
        )

        with st.expander("📖 ¿Cómo genero una contraseña de aplicación? (Gmail)"):
            st.markdown("""
1. Entra a tu cuenta de Google y abre **myaccount.google.com/security**.
2. Activa la **Verificación en dos pasos** si todavía no la tienes activada (es obligatoria para poder crear contraseñas de aplicación).
3. Busca la sección **"Contraseñas de aplicaciones"** (puedes escribir "contraseñas de aplicaciones" en el buscador de Configuración de tu cuenta de Google).
4. Escribe un nombre para identificarla, por ejemplo `Uniwebmx`, y da clic en **Crear**.
5. Google te mostrará una contraseña de 16 letras. **Cópiala**, esa es la que debes pegar en el campo "Contraseña de aplicación" de aquí abajo — no la contraseña normal con la que entras a Gmail.
6. Por último, entra a **Configuración de Gmail → Ver toda la configuración → Reenvío y correo POP/IMAP**, y confirma que la opción **"Habilitar IMAP"** esté activada. Guarda los cambios.

Esa contraseña de aplicación solo le da acceso a Uniwebmx para leer tu correo por IMAP — puedes revocarla en cualquier momento desde la misma sección de Google sin afectar tu contraseña normal.
            """)

        with st.expander("📖 ¿Cómo genero una contraseña de aplicación? (Outlook / Hotmail)"):
            st.markdown("""
1. Entra a **account.microsoft.com/security** con tu cuenta de Outlook/Hotmail.
2. Activa la **verificación en dos pasos** si aún no la tienes.
3. Busca la opción **"Contraseñas de aplicación"** dentro de las opciones de seguridad avanzada.
4. Genera una contraseña nueva y dale un nombre, por ejemplo `Uniwebmx`.
5. Copia la contraseña generada y pégala en el campo "Contraseña de aplicación" de aquí abajo.
6. Verifica también que el **IMAP esté habilitado** en la configuración de tu correo (Configuración → Correo → Sincronizar correo electrónico).
            """)

        with st.form("form_conectar_correo"):
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                correo_input = st.text_input("Tu correo", value=st.session_state.correo_conectado, placeholder="tunombre@gmail.com")
            with col_e2:
                proveedor_input = st.selectbox("Proveedor", options=list(PROVEEDORES_IMAP.keys()))

            servidor_personalizado = ""
            if proveedor_input == "Otro (servidor personalizado)":
                servidor_personalizado = st.text_input("Servidor IMAP (ej. mail.miuniversidad.mx)")

            password_input = st.text_input("Contraseña de aplicación", type="password")
            conectar_btn = st.form_submit_button("Conectar correo")

        if conectar_btn:
            servidor = PROVEEDORES_IMAP.get(proveedor_input) or servidor_personalizado
            if not correo_input or not password_input or not servidor:
                st.error("Completa correo, contraseña y servidor antes de conectar.")
            else:
                with st.spinner("Conectando con tu correo..."):
                    try:
                        conn = conectar_correo_imap(correo_input, password_input, servidor)
                        conn.logout()
                        st.session_state.correo_conectado = correo_input
                        st.session_state.proveedor_correo = proveedor_input
                        st.session_state.correo_password_sesion = password_input
                        guardar_datos_usuario(_user, st.session_state.__dict__)
                        st.toast("¡Correo conectado!")
                        st.rerun()
                    except imaplib.IMAP4.error:
                        st.error("No se pudo iniciar sesión. Revisa el correo y la contraseña (recuerda usar una contraseña de aplicación).")
                    except Exception as e:
                        st.error(f"No se pudo conectar: {e}")

    else:
        col_estado, col_desconectar = st.columns([4, 1])
        with col_estado:
            st.success(f"Conectada como **{st.session_state.correo_conectado}** ({st.session_state.proveedor_correo})")
        with col_desconectar:
            if st.button("Desconectar"):
                st.session_state.correo_password_sesion = ""
                st.session_state.mensajes_universidades = {}
                st.rerun()

        col_buscar, col_dias = st.columns([1, 2])
        with col_dias:
            dias_atras = st.slider("Buscar mensajes de los últimos (días)", min_value=15, max_value=365, value=120, step=15)
        with col_buscar:
            st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
            buscar_btn = st.button("🔄 Buscar mensajes de universidades")

        if buscar_btn:
            with st.spinner("Revisando tu bandeja de entrada..."):
                try:
                    conn = conectar_correo_imap(
                        st.session_state.correo_conectado,
                        st.session_state.correo_password_sesion,
                        PROVEEDORES_IMAP.get(st.session_state.proveedor_correo) or "",
                    )
                    resultados = buscar_correos_universidades(conn, dias_atras=dias_atras)
                    conn.logout()
                    st.session_state.mensajes_universidades = resultados
                    total = sum(len(v) for v in resultados.values())
                    st.toast(f"Se encontraron {total} mensajes de universidades.")
                except imaplib.IMAP4.error:
                    st.error("Tu sesión de correo expiró o la contraseña ya no es válida. Vuelve a conectar tu correo.")
                    st.session_state.correo_password_sesion = ""
                except Exception as e:
                    st.error(f"No se pudo revisar el correo: {e}")

        mensajes = st.session_state.mensajes_universidades
        if not mensajes or not any(mensajes.values()):
            st.info("Da clic en \"Buscar mensajes de universidades\" para ver aquí los correos que te han llegado de cada una.")
        else:
            for nombre_uni, lista_correos in mensajes.items():
                if not lista_correos:
                    continue
                with st.expander(f"📧 {nombre_uni}  —  {len(lista_correos)} mensaje(s)", expanded=False):
                    for i, msg in enumerate(lista_correos):
                        st.markdown(
                            f"""<div style="border-bottom:0.5px solid #EAEAEA;padding:10px 0;">
                                   <p style="font-weight:600;font-size:0.95rem;margin:0;">{msg['asunto']}</p>
                                   <p style="font-size:0.8rem;color:#888;margin:2px 0 6px;">{msg['de']} &nbsp;·&nbsp; {msg['fecha']}</p>
                               </div>""",
                            unsafe_allow_html=True,
                        )
                        with st.expander("Ver mensaje completo", expanded=False):
                            st.markdown(f"<p style='white-space:pre-line;font-size:0.9rem;'>{msg['cuerpo']}</p>", unsafe_allow_html=True)

            st.caption("Solo se muestran correos de dominios conocidos de cada universidad (ej. @tec.mx, @unam.mx, @ibero.mx, etc.).")
