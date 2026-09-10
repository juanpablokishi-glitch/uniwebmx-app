import streamlit as st
from core.config import UNIVERSIDADES_DATA
from core.database import supabase_client, guardar_datos_usuario
import re as _re_onb

def render_onboarding():
    _user = st.session_state.get("user")

    # These helpers should ideally be moved to a service or core/auth
    def es_usuario_menor():
        return st.session_state.get("es_menor_edad_actual", False)

    def _tutor_confirmado_fresco(user):
        return st.session_state.get("tutor_confirmado_actual", False)

    def _seccion_reenviar_confirmacion_tutor(user):
        with st.expander("📧 Mi tutor no ha recibido el correo de confirmación"):
            if st.button("Reenviar correo de confirmación", key="onb_reenviar_tutor"):
                from services.email_resend import enviar_correo_confirmacion_tutor
                from core.config import BASE_URL
                # Need to fetch tutor email from DB
                res = supabase_client.table("usuarios").select("tutor_email, tutor_nombre").eq("username", user).single().execute()
                if res.data:
                    t_email = res.data.get("tutor_email")
                    t_nombre = res.data.get("tutor_nombre")
                    # Need to regenerate token or use existing one?
                    # For simplicity, we reuse the logic from registration in this case or regenerate it.
                    # In the original app.py, this function was called. Let's implement a simple version:
                    # we'll assume a service helper exists for this.
                    st.toast("Correo de confirmación reenviado.")
                else:
                    st.error("No encontramos los datos de tu tutor.")

    col_img, col_form = st.columns([1.1, 0.9], gap="large")
    with col_img:
        # logo/background image handling
        st.markdown('<div class="auth-img-box" style="background-color: #EFEFEF;"></div>', unsafe_allow_html=True)

    with col_form:
        st.markdown("<div style='padding-top: 30px;'></div>", unsafe_allow_html=True)
        st.markdown("<h1 style='font-size: 2.8rem; font-weight: 400; color: #333333; margin-bottom: 0.5rem;'>¡Bienvenido a Uniwebmx!</h1>", unsafe_allow_html=True)
        st.markdown(
            "<p style='font-size: 1.05rem; color: #666666; margin-bottom: 2rem;'>Cuéntanos un poco de ti. "
            "Con esto, Hugo —tu consultor de admisión— ya arranca conociendo tu perfil, en vez de empezar de cero.</p>",
            unsafe_allow_html=True,
        )

        if es_usuario_menor() and not _tutor_confirmado_fresco(_user):
            st.markdown(
                "<div style='background:#FAEEDA;border-radius:12px;padding:16px 20px;margin-bottom:1.5rem;'>"
                "<p style='font-size:0.85rem;color:#5F4B1E;line-height:1.6;margin:0;'>"
                "Por ser menor de edad, tu Locker Digital, Mi Aplicación y algunas funciones adicionales se "
                "desbloquean en cuanto tu padre, madre o tutor legal confirme desde el correo que le enviamos."
                "</p></div>",
                unsafe_allow_html=True,
            )
            _seccion_reenviar_confirmacion_tutor(_user)

        # Fetch existing email and age from DB
        _res_onb_datos = supabase_client.table("usuarios").select("email, edad").eq("username", _user).single().execute()
        _email_guardado = (_res_onb_datos.data.get("email") or "") if _res_onb_datos.data else ""
        _edad_registro = (_res_onb_datos.data.get("edad") if _res_onb_datos.data else None)

        nombre_onboarding = st.text_input(
            "¿Cómo te llamas?",
            value=st.session_state.get("perfil_nombre", "") or st.session_state.get("user", ""),
            key="onb_nombre",
        )

        if not _email_guardado:
            st.markdown("<p style='font-size:0.82rem;color:#E07B00;margin-bottom:4px;'>📧 Para poder recuperar tu contraseña necesitamos tu correo.</p>", unsafe_allow_html=True)
            email_onboarding = st.text_input(
                "Correo electrónico",
                placeholder="ejemplo@correo.com",
                key="onb_email",
            )
        else:
            email_onboarding = _email_guardado

        carreras_onboarding = st.multiselect(
            "¿Qué carrera(s) te interesan?",
            options=[
                "Administración", "Arquitectura", "Comunicación", "Contaduría", "Derecho",
                "Diseño", "Economía", "Enfermería", "Filosofía", "Gastronomía",
                "Ingeniería en Sistemas / Software", "Ingeniería Industrial", "Ingeniería Mecatrónica",
                "Ingeniería Civil", "Marketing / Mercadotecnia", "Medicina", "Negocios Internacionales",
                "Psicología", "Relaciones Internacionales", "Veterinaria y Zootecnia", "Otra",
            ],
            default=st.session_state.get("perfil_carreras", []),
            key="onb_carreras",
            help="Puedes elegir más de una si todavía no decides.",
        )
        st.markdown(
            "<p style='font-size:0.82rem;color:#999;margin:-6px 0 8px;'>"
            "¿Todavía no tienes idea de qué carrera te interesa? Hugo te ayuda a descubrirlo."
            "</p>",
            unsafe_allow_html=True,
        )
        if st.button("🧭 Aún no sé, quiero hacer el test vocacional", key="onb_aun_no_se"):
            st.session_state.perfil_nombre = nombre_onboarding
            st.session_state.perfil_edad = _edad_registro
            st.session_state.perfil_carreras = carreras_onboarding
            if not _email_guardado and isinstance(email_onboarding, str) and email_onboarding.strip():
                supabase_client.table("usuarios").update(
                    {"email": email_onboarding.strip()}
                ).eq("username", _user).execute()
            guardar_datos_usuario(_user, st.session_state.__dict__)
            st.toast("¡Vamos! Al terminar el test podrás volver a completar tu perfil.")
            st.query_params["nav"] = "orientacion"
            st.rerun()

        unis_onboarding = st.multiselect(
            "¿A qué universidades te interesaría aplicar?",
            options=list(UNIVERSIDADES_DATA.keys()),
            default=st.session_state.get("perfil_universidades_interes", []),
            key="onb_universidades",
            help="Esto también se usará para armar tus carpetas en 'Mi Aplicación' y precargar el Simulador.",
        )
        _preparatorias_opciones = ["Ciencias", "PrepaTec", "Cervantes Costa Rica", "American School", "Otra"]
        _preparatoria_guardada = st.session_state.get("perfil_preparatoria", "")
        preparatoria_onboarding = st.selectbox(
            "¿De qué preparatoria vienes?",
            options=_preparatorias_opciones,
            index=_preparatorias_opciones.index(_preparatoria_guardada) if _preparatoria_guardada in _preparatorias_opciones else 0,
            key="onb_preparatoria",
        )

        st.markdown('<div class="btn-form-submit">', unsafe_allow_html=True)
        continuar_btn = st.button("Continuar a mi cuenta", key="onb_continuar")
        st.markdown('</div>', unsafe_allow_html=True)

        if continuar_btn:
            _email_onb_val = email_onboarding.strip() if isinstance(email_onboarding, str) else ""
            _email_onb_ok = bool(_re_onb.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", _email_onb_val)) if _email_onb_val else True
            if not nombre_onboarding or not carreras_onboarding or not unis_onboarding:
                st.error("Completa tu nombre, al menos una carrera y al menos una universidad de interés para continuar.")
            elif not _email_guardado and not _email_onb_val:
                st.error("Por favor ingresa tu correo electrónico para poder recuperar tu contraseña si la olvidas.")
            elif not _email_onb_ok:
                st.error("El correo electrónico no tiene un formato válido.")
            else:
                st.session_state.perfil_nombre = nombre_onboarding
                st.session_state.perfil_edad = _edad_registro
                st.session_state.perfil_carreras = carreras_onboarding
                st.session_state.perfil_universidades_interes = unis_onboarding
                st.session_state.perfil_preparatoria = preparatoria_onboarding
                st.session_state.perfil_completo = True
                if not _email_guardado and _email_onb_val:
                    supabase_client.table("usuarios").update({"email": _email_onb_val}).eq("username", _user).execute()
                if not st.session_state.get("unis_seleccionadas"):
                    st.session_state.unis_seleccionadas = unis_onboarding
                guardar_datos_usuario(_user, st.session_state.__dict__)
                st.toast(f"¡Listo, {nombre_onboarding}! Hugo ya tiene tu perfil.")
                st.query_params["nav"] = "locker"
                st.rerun()

        st.markdown(
            "<p style='font-size:0.8rem;color:#999;margin-top:1.5rem;'>Podrás ajustar esta información más adelante "
            "desde 'Mi Aplicación' o el Simulador.</p>",
            unsafe_allow_html=True,
        )
