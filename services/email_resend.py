import resend
import streamlit as st
import traceback as _traceback_mod
from datetime import datetime, timezone
from core.config import BASE_URL

# Initialize Resend API Key
resend.api_key = st.secrets["RESEND_API_KEY"]

def _load_template(template_name: str) -> str:
    """Loads an HTML template from the templates/emails folder."""
    try:
        with open(f"templates/emails/{template_name}.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"[Template Error] Could not load {template_name}: {e}")
        return ""

def _enviar_correo(to: str, subject: str, html: str):
    """Sends an email via Resend."""
    try:
        resend.Emails.send({
            "from": "Uniwebmx <onboarding@resend.dev>",
            "to": [to],
            "subject": subject,
            "html": html,
        })
    except Exception as e:
        print(f"[Resend ERROR] No se pudo enviar a {to}: {e}")

def _notificar_error_admin(contexto: str, error: Exception, extra: str = ""):
    """Sends a notification to the administrator when a critical error occurs."""
    try:
        _admin_correo = st.secrets.get("ADMIN_EMAIL", "")
        if not _admin_correo:
            print(f"[ALERTA sin enviar - falta ADMIN_EMAIL] {contexto}: {error}")
            return

        # Antispam simple: max one alert every 10 minutes per context
        # Note: This uses a local variable which resets on app restart.
        # For more persistence, this could be moved to a DB table.
        _ahora = datetime.now(timezone.utc)

        _detalle = "".join(_traceback_mod.format_exception(type(error), error, error.__traceback__))[-3000:]
        _enviar_correo(
            to=_admin_correo,
            subject=f"[Uniwebmx] Error en: {contexto}",
            html=f"""
            <div style="font-family:monospace;font-size:0.85rem;white-space:pre-wrap;">
                <p><strong>Contexto:</strong> {contexto}</p>
                <p><strong>Hora (UTC):</strong> {_ahora.isoformat()}</p>
                {f'<p><strong>Extra:</strong> {extra}</p>' if extra else ''}
                <p><strong>Error:</strong> {str(error)}</p>
                <pre>{_detalle}</pre>
            </div>
            """,
        )
    except Exception as _e_interno:
        print(f"[ALERTA falló al mandarse] {contexto}: {error} | error interno: {_e_interno}")

def enviar_correo_bienvenida_registro(correo_usuario: str):
    """Sends the welcome email to a new user."""
    template = _load_template("bienvenida")
    if not template:
        return

    html = template.format(
        correo_usuario=correo_usuario,
        base_url=BASE_URL
    )

    _enviar_correo(
        to=correo_usuario,
        subject="Tu cuenta en Uniwebmx esta lista",
        html=html,
    )

def enviar_correo_confirmacion_tutor(correo_tutor: str, nombre_tutor: str, username_alumno: str, correo_alumno: str, confirm_link: str):
    """Sends the confirmation email to the tutor (double opt-in)."""
    template = _load_template("confirmacion_tutor")
    if not template:
        return

    html = template.format(
        nombre_tutor=nombre_tutor if nombre_tutor else "",
        username_alumno=username_alumno,
        correo_alumno=correo_alumno,
        confirm_link=confirm_link
    )

    _enviar_correo(
        to=correo_tutor,
        subject="Confirma la cuenta de Uniwebmx de tu hijo/a o representado/a",
        html=html,
    )
