import streamlit as st
from core.auth import verify_user, registrar_intento_fallido, resetear_intentos_fallidos, cuenta_bloqueada
from core.database import save_user
from services.email_resend import enviar_correo_bienvenida_registro, enviar_correo_confirmacion_tutor
from core.database import supabase_client
from datetime import datetime, timedelta, timezone
import secrets

def render_login():
    st.markdown("<h1 style='font-size: 3.5rem; font-weight: 400; color: #333333; margin-bottom: 2.5rem;'>Login</h1>", unsafe_allow_html=True)

    with st.form("login_form"):
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        submit = st.form_submit_button("Iniciar Sesión")

        if submit:
            if not username or not password:
                st.error("Por favor, ingresa tu usuario y contraseña.")
                return

            if cuenta_bloqueada(username):
                st.error("Cuenta bloqueada temporalmente por demasiados intentos fallidos. Intenta más tarde.")
                return

            if verify_user(username, password):
                resetear_intentos_fallidos(username)
                from core.auth import crear_sesion_token
                from core.database import restaurar_sesion_usuario

                token = crear_sesion_token(username)
                st.session_state.logged_in = True
                st.session_state.user = username
                st.session_state.session_token = token
                restaurar_sesion_usuario(username)
                st.session_state.page = "locker"
                st.rerun()
            else:
                registrar_intento_fallido(username)
                st.error("Usuario o contraseña incorrectos.")

    st.markdown('<div class="auth-redirect-text">¿No tienes cuenta? <a href="/?page=registro" target="_self" style="color:#4A5D32;font-weight:600;text-decoration:none;">Regístrate aquí</a></div>', unsafe_allow_html=True)

def render_registro():
    col_img, col_form = st.columns([1.1, 0.9], gap="large")
    with col_img:
        # handled by CSS and background images in app.py/components.py
        st.markdown('<div class="auth-img-box"></div>', unsafe_allow_html=True)

    with col_form:
        st.markdown("<div style='padding-top: 40px;'></div>", unsafe_allow_html=True)
        st.markdown("<h1 style='font-size: 3.5rem; font-weight: 400; color: #333333; margin-bottom: 2.5rem;'>Registro</h1>", unsafe_allow_html=True)

        with st.form("registro_form"):
            reg_nombre = st.text_input("Usuario")
            reg_email  = st.text_input("Correo electrónico")
            reg_pass   = st.text_input("Contraseña", type="password")
            reg_edad   = st.number_input("¿Cuántos años tienes?", min_value=10, max_value=99, value=17, step=1)

            _es_menor = reg_edad < 18
            reg_tutor_nombre = ""
            reg_tutor_email = ""
            reg_tutor_consiente = False
            reg_acepta_legal = False
            reg_consiente_hugo = False
            reg_consiente_unis = False
            reg_consiente_promo = False

            if _es_menor:
                st.markdown(
                    "<div style='background:#FAEEDA;border-radius:8px;padding:14px 16px;margin:0.8rem 0;'>"
                    "<p style='font-size:0.85rem;color:#5F4B1E;line-height:1.6;margin:0;'>"
                    "Como indicaste que eres menor de edad, el uso de Uniwebmx requiere el consentimiento de tu "
                    "padre, madre o tutor legal. Escribe sus datos abajo: en cuanto crees la cuenta, le enviaremos "
                    "un correo para que confirme y decida sobre el uso adicional de tus datos, incluyendo el "
                    "<a href='/?page=aviso_privacidad' target='_blank' style='color:#4A5D32;font-weight:600;'>Aviso de Privacidad</a> "
                    "y los <a href='/?page=terminos' target='_blank' style='color:#4A5D32;font-weight:600;'>Términos y Condiciones</a>. "
                    "Mientras no confirme, algunas funciones seguirán desactivadas."
                    "</p></div>",
                    unsafe_allow_html=True,
                )
                reg_tutor_nombre = st.text_input("Nombre del padre, madre o tutor legal")
                reg_tutor_email  = st.text_input("Correo electrónico del padre, madre o tutor legal")
            else:
                st.markdown(
                    "<p style='font-size:0.82rem;color:#666;margin:0.6rem 0 0.3rem;'>Al crear tu cuenta, aceptas nuestro "
                    "<a href='/?page=aviso_privacidad' target='_blank' style='color:#4A5D32;font-weight:600;text-decoration:none;'>Aviso de Privacidad</a> "
                    "y nuestros "
                    "<a href='/?page=terminos' target='_blank' style='color:#4A5D32;font-weight:600;text-decoration:none;'>Términos y Condiciones</a>.</p>",
                    unsafe_allow_html=True,
                )

            # Consent checkboxes
            reg_acepta_legal = st.checkbox("Acepto los Términos y Condiciones y el Aviso de Privacidad", value=True)
            reg_consiente_hugo = st.checkbox("Acepto que mis datos y conversaciones con Hugo se usen para mejorar el asistente", value=True)
            reg_consiente_unis = st.checkbox("Acepto que mi perfil sea compartido con universidades interesadas", value=True)
            reg_consiente_promo = st.checkbox("Deseo recibir noticias y promociones de Uniwebmx", value=True)

            submit = st.form_submit_button("Crear Cuenta")

            if submit:
                if not reg_nombre or not reg_email or not reg_pass:
                    st.error("Por favor, llena todos los campos obligatorios.")
                    return

                if not reg_acepta_legal:
                    st.error("Debes aceptar los términos y condiciones para continuar.")
                    return

                if _es_menor and (not reg_tutor_nombre or not reg_tutor_email):
                    st.error("Por favor, ingresa los datos de tu tutor legal.")
                    return

                # Generate tutor token if minor
                tutor_token = None
                tutor_expiry = None
                if _es_menor:
                    tutor_token = secrets.token_urlsafe(32)
                    tutor_expiry = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

                from core.database import save_user
                success = save_user(
                    username=reg_nombre, password=reg_pass, email=reg_email, edad=reg_edad,
                    es_menor_edad=_es_menor, tutor_nombre=reg_tutor_nombre, tutor_email=reg_tutor_email,
                    tutor_consentimiento=True, tutor_confirm_token=tutor_token, tutor_confirm_token_expiry=tutor_expiry,
                    consentimiento_hugo=reg_consiente_hugo if not _es_menor else False,
                    consentimiento_universidades=reg_consiente_unis if not _es_menor else False,
                    consentimiento_promocional=reg_consiente_promo if not _es_menor else False,
                    consentimientos_fecha=datetime.now(timezone.utc).isoformat() if not _es_menor else None
                )

                if success:
                    st.success("Cuenta creada exitosamente. ¡Ahora puedes iniciar sesión!")
                    enviar_correo_bienvenida_registro(reg_email)
                    if _es_menor:
                        from core.config import BASE_URL
                        confirm_link = f"{BASE_URL}/?page=confirmar_tutor&token={tutor_token}"
                        enviar_correo_confirmacion_tutor(reg_tutor_email, reg_tutor_nombre, reg_nombre, reg_email, confirm_link)
                    st.session_state.page = "login"
                    st.rerun()
                else:
                    st.error("El nombre de usuario ya está en uso. Elige otro.")

    st.markdown('<div class="auth-redirect-text">¿Ya tienes cuenta? <a href="/?page=login" target="_self" style="color:#4A5D32;font-weight:600;text-decoration:none;">Inicia sesión aquí</a></div>', unsafe_allow_html=True)
