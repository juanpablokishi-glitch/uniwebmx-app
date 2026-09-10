import streamlit as st
from datetime import datetime, timezone, timedelta
import secrets as _secrets
import bcrypt
import re as _re_pass
from core.database import supabase_client
from core.config import BASE_URL

def render_olvide_contrasena():
    col_img, col_form = st.columns([1.1, 0.9], gap="large")
    with col_img:
        st.markdown('<div class="auth-img-box" style="background-color: #EFEFEF;"></div>', unsafe_allow_html=True)

    with col_form:
        st.markdown("<div style='padding-top: 60px;'></div>", unsafe_allow_html=True)
        st.markdown("<h1 style='font-size: 2.8rem; font-weight: 400; color: #333333; margin-bottom: 0.5rem;'>¿Olvidaste tu contraseña?</h1>", unsafe_allow_html=True)
        st.markdown("<p style='font-size:1rem;color:#666;margin-bottom:2rem;'>Escribe tu correo y te enviaremos un enlace para restablecerla.</p>", unsafe_allow_html=True)

        with st.form("form_reset_request"):
            reset_email = st.text_input("Correo electrónico o usuario", placeholder="ejemplo@correo.com o tu_usuario", key="reset_email_input")
            _reset_clicked = st.form_submit_button("Enviar enlace", use_container_width=True)

        if _reset_clicked:
            if not reset_email.strip():
                st.error("Por favor ingresa tu correo o usuario.")
            else:
                _input = reset_email.strip()
                res = supabase_client.table("usuarios").select("username, email").eq("email", _input).execute()
                if not res.data:
                    res = supabase_client.table("usuarios").select("username, email").eq("username", _input).execute()
                if res.data:
                    _email_destino = res.data[0].get("email") or ""
                    _username_reset2 = res.data[0]["username"]
                    if _email_destino:
                        token = _secrets.token_urlsafe(32)
                        expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
                        supabase_client.table("usuarios").update({
                            "reset_token": None,
                            "reset_token_expiry": None,
                        }).eq("username", _username_reset2).execute()
                        supabase_client.table("usuarios").update({
                            "reset_token": token,
                            "reset_token_expiry": expiry
                        }).eq("username", _username_reset2).execute()
                        reset_link = f"{BASE_URL}/?page=reset_contrasena&token={token}"
                        # We use the email service helper
                        from services.email_resend import _enviar_correo
                        _enviar_correo(
                            to=_email_destino,
                            subject="Restablece tu contrasena de Uniwebmx",
                            html=f"""
                            <div style="font-family:Montserrat,Arial,sans-serif;max-width:560px;margin:0 auto;
                                background:#fff;border:1px solid #EAEAEA;border-radius:16px;overflow:hidden;">
                                <div style="text-align:center;padding:28px 32px 20px;border-bottom:1px solid #EAEAEA;margin-bottom:28px;">
                                    <img src="https://qbtbcvwwfqoghgvyhztd.supabase.co/storage/v1/object/public/assets/logo.png" alt="Uniwebmx" style="height:36px;display:inline-block;">
                                </div>
                                <div style="padding:0 32px 36px;">
                                    <h1 style="font-size:1.4rem;font-weight:700;color:#1A1A1A;margin-bottom:0.75rem;">
                                        Restablece tu contrasena
                                    </h1>
                                    <p style="font-size:0.9rem;color:#444;line-height:1.7;margin-bottom:1.5rem;">
                                        Recibimos una solicitud para restablecer la contrasena de tu cuenta.
                                        El enlace es valido por <strong>1 hora</strong>.
                                    </p>
                                    <a href="{reset_link}" style="display:inline-block;background:#4A5D32;color:#fff;
                                        font-size:0.9rem;font-weight:600;padding:13px 32px;border-radius:8px;
                                        text-decoration:none;">
                                        Restablecer contrasena
                                    </a>
                                    <p style="font-size:0.78rem;color:#999;margin-top:2rem;line-height:1.6;">
                                        Si no solicitaste esto, ignora este correo.<br>— El equipo de Uniwebmx
                                    </p>
                                </div>
                            </div>
                            """,
                        )
                st.success("Si ese correo está registrado, recibirás el enlace en unos minutos.")

        st.markdown("""
        <div style="text-align:center;margin-top:1.5rem;">
            <a href="/?page=login" target="_self"
               style="font-family:Montserrat,sans-serif;font-size:0.85rem;color:#888;text-decoration:none;">
               ← Volver a iniciar sesión
            </a>
        </div>
        """, unsafe_allow_html=True)

def render_reset_contrasena():
    _token_url = st.query_params.get("token", "") or st.session_state.get("_token_url_pendiente", "")

    col_img, col_form = st.columns([1.1, 0.9], gap="large")
    with col_img:
        st.markdown('<div class="auth-img-box" style="background-color: #EFEFEF;"></div>', unsafe_allow_html=True)

    with col_form:
        st.markdown("<div style='padding-top: 60px;'></div>", unsafe_allow_html=True)
        st.markdown("<h1 style='font-size: 2.8rem; font-weight: 400; color: #333333; margin-bottom: 0.5rem;'>Nueva contraseña</h1>", unsafe_allow_html=True)

        if not _token_url:
            st.error("Enlace inválido. Solicita uno nuevo.")
        else:
            res = supabase_client.table("usuarios").select("username, reset_token_expiry").eq("reset_token", _token_url).execute()
            if not res.data:
                st.error("Este enlace no es válido o ya fue usado.")
            else:
                _expiry_str = res.data[0].get("reset_token_expiry", "")
                _username_reset = res.data[0]["username"]
                _expiry_dt = datetime.fromisoformat(_expiry_str) if _expiry_str else None
                _now = datetime.now(timezone.utc)
                if _expiry_dt and _now > _expiry_dt:
                    st.error("El enlace expiró. Solicita uno nuevo desde la página de login.")
                else:
                    st.markdown("<p style='font-size:1rem;color:#666;margin-bottom:2rem;'>Elige una nueva contraseña para tu cuenta.</p>", unsafe_allow_html=True)
                    with st.form("form_nueva_pass"):
                        nueva_pass = st.text_input("Nueva contraseña", type="password", key="nueva_pass_input")
                        confirmar_pass = st.text_input("Confirmar contraseña", type="password", key="confirmar_pass_input")
                        _nueva_clicked = st.form_submit_button("Guardar contraseña", use_container_width=True)
                    if _nueva_clicked:
                        _pass_reset_ok = (
                            len(nueva_pass) >= 8
                            and bool(_re_pass.search(r"[A-Za-z]", nueva_pass))
                            and bool(_re_pass.search(r"\d", nueva_pass))
                        )
                        if not nueva_pass or not _pass_reset_ok:
                            st.error("La contraseña debe tener al menos 8 caracteres, una letra y un número.")
                        elif nueva_pass != confirmar_pass:
                            st.error("Las contraseñas no coinciden.")
                        else:
                            nuevo_hash = bcrypt.hashpw(nueva_pass.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
                            supabase_client.table("usuarios").update({
                                "password_hash": nuevo_hash,
                                "reset_token": None,
                                "reset_token_expiry": None,
                            }).eq("username", _username_reset).execute()
                            st.success("¡Contraseña actualizada! Ya puedes iniciar sesión.")
                            st.markdown('<div style="text-align:center;margin-top:1rem;"><a href="/?page=login" target="_self" style="font-family:Montserrat,sans-serif;font-size:0.9rem;font-weight:600;color:#4A5D32;text-decoration:none;">Ir a iniciar sesión →</a></div>', unsafe_allow_html=True)
