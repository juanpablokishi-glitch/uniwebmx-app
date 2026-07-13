import streamlit as st
import pandas as pd
import base64
import os
import google.generativeai as genai
import json
import bcrypt
import PyPDF2
import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client
import resend

# --- CONFIGURACIÓN DE LA API DE GEMINI ---
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# --- CLIENTE SUPABASE ---
@st.cache_resource
def get_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase_client = get_supabase()

# --- CLIENTE RESEND ---
resend.api_key = st.secrets["RESEND_API_KEY"]

def _enviar_correo(to: str, subject: str, html: str):
    """Envía un correo vía Resend. Loggea el error en consola si falla."""
    try:
        resend.Emails.send({
            "from": "Uniwebmx <onboarding@resend.dev>",
            "to": [to],
            "subject": subject,
            "html": html,
        })
    except Exception as e:
        print(f"[Resend ERROR] No se pudo enviar a {to}: {e}")


# --- ALERTAS DE ERROR AL ADMIN ---
# Requiere el secret ADMIN_EMAIL en Streamlit Cloud (Settings > Secrets):
#   ADMIN_EMAIL = "tu_correo@ejemplo.com"
# Si no está configurado, las alertas simplemente no se envían (no truena la app).
import traceback as _traceback_mod

_ULTIMA_ALERTA_POR_CONTEXTO = {}  # antispam: no mandar el mismo error 50 veces seguidas

def _notificar_error_admin(contexto: str, error: Exception, extra: str = ""):
    """Manda un correo al admin cuando algo truena en un flujo importante
    (guardar datos, registro, login, pagos). Nunca deja que una falla aquí
    tumbe la app: si Resend o los secrets fallan, solo se queda en consola."""
    try:
        _admin_correo = st.secrets.get("ADMIN_EMAIL", "")
        if not _admin_correo:
            print(f"[ALERTA sin enviar - falta ADMIN_EMAIL] {contexto}: {error}")
            return
        # Antispam simple: máximo una alerta cada 10 minutos por mismo contexto,
        # usando cache de proceso (se resetea si la app se reinicia).
        _ahora = datetime.now(timezone.utc)
        _clave = contexto
        _ultima = _ULTIMA_ALERTA_POR_CONTEXTO.get(_clave)
        if _ultima and (_ahora - _ultima).total_seconds() < 600:
            return
        _ULTIMA_ALERTA_POR_CONTEXTO[_clave] = _ahora

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
    """Correo de bienvenida al crear cuenta."""
    _enviar_correo(
        to=correo_usuario,
        subject="Tu cuenta en Uniwebmx esta lista",
        html=f"""
        <div style="font-family:Montserrat,Arial,sans-serif;max-width:560px;margin:0 auto;
            background:#ffffff;border:1px solid #EAEAEA;border-radius:16px;overflow:hidden;">
        <div style="text-align:center;padding:28px 32px 20px;border-bottom:1px solid #EAEAEA;margin-bottom:28px;">
            <img src="https://qbtbcvwwfqoghgvyhztd.supabase.co/storage/v1/object/public/assets/logo.png" alt="Uniwebmx" style="height:36px;display:inline-block;">
        </div>
            <div style="padding:0 32px 36px;">
            <h1 style="font-size:1.5rem;font-weight:700;color:#1A1A1A;margin-bottom:0.75rem;">
                Bienvenido a Uniwebmx
            </h1>
            <p style="font-size:0.95rem;color:#444;line-height:1.7;margin-bottom:1.5rem;">
                Hola <strong>{correo_usuario}</strong>, tu cuenta fue creada exitosamente.
                Ya puedes iniciar sesion y empezar a organizar tu proceso de admision.
            </p>
            <table style="width:100%;border-collapse:collapse;margin-bottom:1.8rem;">
                <tr><td style="padding:8px 0;border-bottom:1px solid #F0F0F0;font-size:0.9rem;color:#444;">Guarda y organiza tus documentos en el Locker Digital</td></tr>
                <tr><td style="padding:8px 0;border-bottom:1px solid #F0F0F0;font-size:0.9rem;color:#444;">Consulta a Hugo, tu asesor de admisiones con IA</td></tr>
                <tr><td style="padding:8px 0;font-size:0.9rem;color:#444;">Simula tus probabilidades de admision por universidad</td></tr>
            </table>
            <a href="{BASE_URL}" style="display:inline-block;background:#4A5D32;color:#fff;
                font-size:0.9rem;font-weight:600;padding:13px 32px;border-radius:8px;
                text-decoration:none;letter-spacing:0.01em;">
                Ir a Uniwebmx
            </a>
            <p style="font-size:0.78rem;color:#999;margin-top:2rem;line-height:1.6;">
                — El equipo de Uniwebmx
            </p>
            </div>
        </div>
        """,
    )


def enviar_correo_confirmacion_tutor(correo_tutor: str, nombre_tutor: str, username_alumno: str, correo_alumno: str, confirm_link: str):
    """Correo con enlace de confirmación (doble opt-in) enviado al padre/madre/tutor
    tras registrar a un alumno menor de edad. Mientras no se confirme, las
    finalidades secundarias (entrenar a Hugo, compartir con universidades)
    permanecen desactivadas para esa cuenta."""
    _enviar_correo(
        to=correo_tutor,
        subject="Confirma la cuenta de Uniwebmx de tu hijo/a o representado/a",
        html=f"""
        <div style="font-family:Montserrat,Arial,sans-serif;max-width:560px;margin:0 auto;
            background:#ffffff;border:1px solid #EAEAEA;border-radius:16px;overflow:hidden;">
        <div style="text-align:center;padding:28px 32px 20px;border-bottom:1px solid #EAEAEA;margin-bottom:28px;">
            <img src="https://qbtbcvwwfqoghgvyhztd.supabase.co/storage/v1/object/public/assets/logo.png" alt="Uniwebmx" style="height:36px;display:inline-block;">
        </div>
            <div style="padding:0 32px 36px;">
            <h1 style="font-size:1.4rem;font-weight:700;color:#1A1A1A;margin-bottom:0.75rem;">
                Confirma tu autorización
            </h1>
            <p style="font-size:0.95rem;color:#444;line-height:1.7;margin-bottom:1rem;">
                Hola{f' {nombre_tutor}' if nombre_tutor else ''}, este correo fue registrado como el de padre,
                madre o tutor legal de un usuario menor de edad en Uniwebmx.
            </p>
            <table style="width:100%;border-collapse:collapse;margin-bottom:1.5rem;">
                <tr><td style="padding:8px 0;border-bottom:1px solid #F0F0F0;font-size:0.9rem;color:#444;">Usuario del alumno: <strong>{username_alumno}</strong></td></tr>
                <tr><td style="padding:8px 0;font-size:0.9rem;color:#444;">Correo del alumno: <strong>{correo_alumno}</strong></td></tr>
            </table>
            <p style="font-size:0.95rem;color:#444;line-height:1.7;margin-bottom:1.5rem;">
                El alumno ya puede usar las funciones básicas de la plataforma. Para habilitar funciones
                adicionales que involucran el uso de sus datos (como que sus conversaciones con Hugo ayuden a
                mejorar el asistente, o compartir su información con universidades), necesitamos que confirmes
                tu autorización y decidas cada una por separado:
            </p>
            <a href="{confirm_link}" style="display:inline-block;background:#4A5D32;color:#fff;
                font-size:0.9rem;font-weight:600;padding:13px 32px;border-radius:8px;
                text-decoration:none;letter-spacing:0.01em;margin-bottom:1.5rem;">
                Revisar y confirmar
            </a>
            <p style="font-size:0.78rem;color:#999;margin-top:1.5rem;line-height:1.6;">
                Este enlace es válido por 7 días. Si tú no autorizaste este registro, ignora este correo o
                escríbenos para solicitar que eliminemos la cuenta.<br>— El equipo de Uniwebmx
            </p>
            </div>
        </div>
        """,
    )


def guardar_conversacion_entrenamiento(username, mensaje_usuario, respuesta_hugo):
    """Guarda un intercambio con Hugo en la tabla de entrenamiento. Solo se debe
    llamar cuando el usuario (o su tutor, si es menor de edad) dio consentimiento
    explícito para la finalidad secundaria 6.1 (mejorar/entrenar a Hugo).

    Requiere en Supabase la tabla "hugo_entrenamiento" con columnas:
    username (text), mensaje_usuario (text), respuesta_hugo (text),
    created_at (timestamptz, default now()).
    """
    try:
        supabase_client.table("hugo_entrenamiento").insert({
            "username": username,
            "mensaje_usuario": mensaje_usuario,
            "respuesta_hugo": respuesta_hugo,
        }).execute()
    except Exception as e:
        print(f"[hugo_entrenamiento ERROR] No se pudo guardar la conversación de {username}: {e}")

# URL base de la app. En local usa localhost; en producción, define BASE_URL en tus secrets
# (ej. BASE_URL = "https://tuapp.streamlit.app")
BASE_URL = st.secrets.get("BASE_URL", "http://localhost:8501")

# Duración del token de sesión (no del username) que viaja en la URL para los nav links.
SESSION_TOKEN_DIAS = 30

# El entorno donde corre la app no siempre tiene fuentes de emoji a color instaladas,
# así que cualquier emoji que Gemini meta en sus respuestas se ve como un cuadrado
# naranja/rojo roto en vez del emoji real. Los quitamos de raíz de todo lo que Hugo
# genera antes de mostrarlo.
import re as _re_emoji
_EMOJI_PATTERN = _re_emoji.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U00002B00-\U00002BFF"
    "\U0001F900-\U0001F9FF"
    "\U0000FE00-\U0000FE0F"
    "\U0000200D"
    "]+",
    flags=_re_emoji.UNICODE,
)

def _quitar_emojis(texto):
    if not texto:
        return texto
    return _EMOJI_PATTERN.sub("", texto).strip()

def extraer_texto_archivo(archivo):
    """
    Función que lee archivos PDF o TXT y devuelve el texto como string.
    """
    texto = ""
    # Si es un archivo PDF
    if archivo.type == "application/pdf":
        try:
            lector = PyPDF2.PdfReader(archivo)
            for pagina in lector.pages:
                texto += pagina.extract_text() or ""
        except Exception as e:
            st.error(f"Error al leer el PDF: {e}")
    # Si es un archivo de texto plano
    elif archivo.type == "text/plain":
        texto = archivo.read().decode("utf-8")
    return texto

# =================================================================
# CENTRO DE MENSAJES — Conexión IMAP a correo del usuario
# =================================================================

# Servidores IMAP de proveedores comunes (el usuario solo elige el proveedor)
PROVEEDORES_IMAP = {
    "Gmail": "imap.gmail.com",
    "Outlook / Hotmail": "outlook.office365.com",
    "Yahoo": "imap.mail.yahoo.com",
    "iCloud": "imap.mail.me.com",
    "Otro (servidor personalizado)": None,
}

# Dominios de correo conocidos de cada universidad, para filtrar la bandeja
UNIV_DOMINIOS = {
    "Tec de Monterrey": ["tec.mx", "itesm.mx"],
    "UdeG": ["udg.mx"],
    "UP": ["up.edu.mx"],
    "ITESO": ["iteso.mx"],
    "UNAM": ["unam.mx"],
    "UAG": ["uag.mx"],
}


def _decodificar_header(valor):
    """Decodifica encabezados de correo (asunto, remitente) que pueden venir en distintos encodings."""
    if not valor:
        return ""
    partes = decode_header(valor)
    resultado = ""
    for texto, codificacion in partes:
        if isinstance(texto, bytes):
            try:
                resultado += texto.decode(codificacion or "utf-8", errors="ignore")
            except Exception:
                resultado += texto.decode("utf-8", errors="ignore")
        else:
            resultado += texto
    return resultado


def _extraer_cuerpo_correo(msg):
    """Extrae el texto plano (o un extracto del HTML) del cuerpo de un mensaje de correo."""
    cuerpo = ""
    if msg.is_multipart():
        for parte in msg.walk():
            tipo = parte.get_content_type()
            disposicion = str(parte.get("Content-Disposition") or "")
            if tipo == "text/plain" and "attachment" not in disposicion:
                try:
                    cuerpo = parte.get_payload(decode=True).decode(parte.get_content_charset() or "utf-8", errors="ignore")
                    break
                except Exception:
                    continue
        if not cuerpo:
            for parte in msg.walk():
                if parte.get_content_type() == "text/html":
                    try:
                        html = parte.get_payload(decode=True).decode(parte.get_content_charset() or "utf-8", errors="ignore")
                        import re as _re
                        cuerpo = _re.sub("<[^<]+?>", " ", html)
                        break
                    except Exception:
                        continue
    else:
        try:
            cuerpo = msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", errors="ignore")
        except Exception:
            cuerpo = str(msg.get_payload())
    return cuerpo.strip()


def conectar_correo_imap(correo, contrasena, servidor):
    """Abre una conexión IMAP autenticada. Lanza excepción si falla."""
    conn = imaplib.IMAP4_SSL(servidor)
    conn.login(correo, contrasena)
    return conn


def buscar_correos_universidades(conn, dias_atras=120, limite_por_universidad=15):
    """
    Busca en INBOX los correos provenientes de los dominios conocidos de cada universidad.
    Devuelve un dict: {nombre_universidad: [ {de, asunto, fecha, cuerpo}, ... ]}
    """
    resultados = {nombre: [] for nombre in UNIV_DOMINIOS}
    conn.select("INBOX")
    fecha_desde = (datetime.now() - timedelta(days=dias_atras)).strftime("%d-%b-%Y")

    for nombre_uni, dominios in UNIV_DOMINIOS.items():
        vistos = set()
        for dominio in dominios:
            try:
                tipo, datos = conn.search(None, f'(SINCE {fecha_desde} FROM "{dominio}")')
            except Exception:
                continue
            if tipo != "OK":
                continue
            ids_correo = datos[0].split()
            ids_correo = ids_correo[-limite_por_universidad:]  # los más recientes
            for id_correo in reversed(ids_correo):
                if id_correo in vistos:
                    continue
                vistos.add(id_correo)
                try:
                    tipo_f, datos_msg = conn.fetch(id_correo, "(RFC822)")
                    if tipo_f != "OK":
                        continue
                    msg = email.message_from_bytes(datos_msg[0][1])
                    de = _decodificar_header(msg.get("From"))
                    asunto = _decodificar_header(msg.get("Subject"))
                    fecha = msg.get("Date", "")
                    cuerpo = _extraer_cuerpo_correo(msg)
                    resultados[nombre_uni].append({
                        "de": de,
                        "asunto": asunto or "(Sin asunto)",
                        "fecha": fecha,
                        "cuerpo": cuerpo[:3000],
                    })
                except Exception:
                    continue
        resultados[nombre_uni] = resultados[nombre_uni][:limite_por_universidad]

    return resultados

def load_users():
    """Compatibilidad: devuelve dict {username: hash} desde Supabase."""
    res = supabase_client.table("usuarios").select("username, password_hash").execute()
    return {row["username"]: row["password_hash"] for row in (res.data or [])}

def save_user(username, password, email="", edad=None, es_menor_edad=False,
              tutor_nombre="", tutor_email="", tutor_consentimiento=False,
              tutor_confirm_token=None, tutor_confirm_token_expiry=None,
              consentimiento_hugo=False, consentimiento_universidades=False,
              consentimiento_promocional=False, consentimientos_fecha=None):
    """
    Guarda un nuevo usuario.

    Si es menor de edad: se guardan los datos de contacto del padre/madre/tutor
    y el checkbox declarado en el registro (tutor_consentimiento), pero las
    finalidades secundarias (consentimiento_hugo/universidades/promocional)
    quedan en False hasta que el tutor confirme por correo (doble opt-in,
    ver vista "confirmar_tutor") usando tutor_confirm_token.

    Si es mayor de edad: consentimiento_hugo/universidades/promocional se
    guardan directo, según lo que haya marcado en el registro.

    Requiere en Supabase, tabla "usuarios", las columnas adicionales:
    edad (int, nullable), es_menor_edad (bool, default false),
    tutor_nombre (text, nullable), tutor_email (text, nullable),
    tutor_consentimiento (bool, default false),
    tutor_confirmado (bool, default false),
    tutor_confirm_token (text, nullable),
    tutor_confirm_token_expiry (timestamptz, nullable),
    consentimiento_hugo (bool, default false),
    consentimiento_universidades (bool, default false),
    consentimiento_promocional (bool, default false),
    consentimientos_fecha (timestamptz, nullable).
    """
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    datos_usuario = {
        "username": username,
        "password_hash": hashed,
        "email": email,
        "plan": "gratis",
        "edad": edad,
        "es_menor_edad": es_menor_edad,
        "tutor_nombre": tutor_nombre,
        "tutor_email": tutor_email,
        "tutor_consentimiento": tutor_consentimiento,
        "tutor_confirmado": False,
        "tutor_confirm_token": tutor_confirm_token,
        "tutor_confirm_token_expiry": tutor_confirm_token_expiry,
        "consentimiento_hugo": consentimiento_hugo,
        "consentimiento_universidades": consentimiento_universidades,
        "consentimiento_promocional": consentimiento_promocional,
        "consentimientos_fecha": consentimientos_fecha,
    }
    # IMPORTANTE: usamos insert() y no upsert(). Un registro nuevo NUNCA debe poder
    # sobreescribir una cuenta existente (eso borraría su password_hash, plan, etc.
    # si dos personas coincidieran en username). Si alguien más ganó la carrera y
    # ya existe ese username (choque de "usuarios_username_key"), devolvemos False
    # en vez de dejar que el error tumbe la página.
    try:
        supabase_client.table("usuarios").insert(datos_usuario).execute()
        return True
    except Exception as e:
        if "usuarios_username_key" in str(e) or "23505" in str(e):
            return False
        _notificar_error_admin("save_user (registro)", e, extra=f"username={username}")
        return False


def verify_user(username, password):
    try:
        res = supabase_client.table("usuarios").select("password_hash").eq("username", username).execute()
    except Exception as e:
        _notificar_error_admin("verify_user (login)", e, extra=f"username={username}")
        return False
    if res.data:
        stored_hash = res.data[0]["password_hash"].encode('utf-8')
        return bcrypt.checkpw(password.encode('utf-8'), stored_hash)
    return False

# --- RATE LIMITING DE LOGIN (anti fuerza bruta) ---
# Requiere en Supabase, tabla "usuarios": columnas "failed_attempts" (int,
# default 0) y "locked_until" (timestamptz, nullable).
MAX_INTENTOS_LOGIN = 5
BLOQUEO_MINUTOS = 15

def cuenta_bloqueada(username):
    """Devuelve True si la cuenta está temporalmente bloqueada por demasiados
    intentos fallidos de login seguidos."""
    if not username:
        return False
    try:
        res = supabase_client.table("usuarios").select("locked_until").eq("username", username).execute()
    except Exception:
        return False
    if not res.data:
        return False
    locked_until_str = res.data[0].get("locked_until")
    if not locked_until_str:
        return False
    try:
        locked_until_dt = datetime.fromisoformat(locked_until_str)
    except Exception:
        return False
    return datetime.now(timezone.utc) < locked_until_dt

def registrar_intento_fallido(username):
    """Incrementa el contador de intentos fallidos del usuario; si llega al
    máximo, bloquea la cuenta por BLOQUEO_MINUTOS."""
    if not username:
        return
    try:
        res = supabase_client.table("usuarios").select("failed_attempts").eq("username", username).execute()
        if not res.data:
            return  # username no existe; no hay nada que bloquear
        intentos_actuales = res.data[0].get("failed_attempts") or 0
    except Exception:
        return
    nuevos_intentos = intentos_actuales + 1
    update_data = {"failed_attempts": nuevos_intentos}
    if nuevos_intentos >= MAX_INTENTOS_LOGIN:
        update_data["locked_until"] = (
            datetime.now(timezone.utc) + timedelta(minutes=BLOQUEO_MINUTOS)
        ).isoformat()
    try:
        supabase_client.table("usuarios").update(update_data).eq("username", username).execute()
    except Exception:
        pass

def resetear_intentos_fallidos(username):
    """Limpia el contador de intentos fallidos tras un login exitoso."""
    if not username:
        return
    try:
        supabase_client.table("usuarios").update(
            {"failed_attempts": 0, "locked_until": None}
        ).eq("username", username).execute()
    except Exception:
        pass

def crear_sesion_token(username):
    """
    Genera un token de sesión aleatorio (no adivinable) y lo guarda en Supabase
    asociado al usuario, con expiración. Este token —y no el username— es lo
    que viaja en la URL para sobrevivir a los full-reload de los <a href>.
    Sustituye al esquema anterior donde la URL confiaba directamente en
    "u=username" sin ninguna verificación (vulnerabilidad de account takeover).
    """
    import secrets as _secrets_sesion
    token = _secrets_sesion.token_urlsafe(32)
    expiry = (datetime.now(timezone.utc) + timedelta(days=SESSION_TOKEN_DIAS)).isoformat()
    supabase_client.table("usuarios").update({
        "session_token": token,
        "session_token_expiry": expiry,
    }).eq("username", username).execute()
    return token


def validar_sesion_token(token):
    """
    Verifica el token de sesión contra Supabase. Devuelve el username si es
    válido y no ha expirado; devuelve None en cualquier otro caso (token
    inexistente, vencido, o vacío). Nunca confiar en un username que venga
    crudo desde la URL: siempre pasar por aquí primero.
    """
    if not token:
        return None
    try:
        res = supabase_client.table("usuarios").select(
            "username, session_token_expiry"
        ).eq("session_token", token).execute()
    except Exception:
        return None
    if not res.data:
        return None
    expiry_str = res.data[0].get("session_token_expiry")
    if not expiry_str:
        return None
    try:
        expiry_dt = datetime.fromisoformat(expiry_str)
    except Exception:
        return None
    if datetime.now(timezone.utc) > expiry_dt:
        return None
    return res.data[0]["username"]


def invalidar_sesion_token(username):
    """Revoca el token de sesión actual del usuario (logout real, del lado del servidor)."""
    if not username:
        return
    try:
        supabase_client.table("usuarios").update({
            "session_token": None,
            "session_token_expiry": None,
        }).eq("username", username).execute()
    except Exception:
        pass


# Uniwebmx es gratuito para el usuario (el modelo de negocio es cobrar a las
# universidades por leads). Estos son los límites únicos para todas las cuentas,
# equivalentes a lo que antes era el plan "pro":
LIMITE_HUGO_DIARIO = 20


# =================================================================
# PERSISTENCIA DE DATOS POR USUARIO (Supabase)
# =================================================================


def cargar_datos_usuario(username):
    res = supabase_client.table("datos_usuario").select("datos").eq("username", username).execute()
    if res.data:
        return res.data[0]["datos"]
    return {}


def guardar_datos_usuario(username):
    """Toma lo relevante de session_state y lo persiste en Supabase para ese usuario."""
    if not username:
        return
    # Los usuarios menores de edad SIN confirmación de su tutor no tienen Locker
    # Digital persistente: sus documentos (incluyendo identificaciones y
    # comprobantes sensibles) solo viven en session_state durante la sesión
    # activa y no se guardan en Supabase. En cuanto el tutor confirma
    # (tutor_confirmado_actual = True), el locker sí persiste normalmente,
    # igual que para un usuario mayor de edad.
    _bloquear_persistencia_docs = es_usuario_menor() and not _tutor_confirmado_fresco(username)
    _doc_vacio = {"nombre": None, "contenido": ""}
    datos = {
        "historial_chat": st.session_state.get("historial_chat", []),
        "contador_consultas": st.session_state.get("contador_consultas", 0),
        "fecha_contador": st.session_state.get("fecha_contador", ""),
        # Documentos académicos
        "kardex": _doc_vacio if _bloquear_persistencia_docs else st.session_state.get("kárdex", _doc_vacio),
        "ensayo": _doc_vacio if _bloquear_persistencia_docs else st.session_state.get("ensayo", _doc_vacio),
        "curriculum": _doc_vacio if _bloquear_persistencia_docs else st.session_state.get("curriculum", _doc_vacio),
        "cartas": _doc_vacio if _bloquear_persistencia_docs else st.session_state.get("cartas", _doc_vacio),
        "portafolio": _doc_vacio if _bloquear_persistencia_docs else st.session_state.get("portafolio", _doc_vacio),
        # Documentos personales
        "acta": _doc_vacio if _bloquear_persistencia_docs else st.session_state.get("acta", _doc_vacio),
        "curp": _doc_vacio if _bloquear_persistencia_docs else st.session_state.get("curp", _doc_vacio),
        "identificacion": _doc_vacio if _bloquear_persistencia_docs else st.session_state.get("identificacion", _doc_vacio),
        "foto": _doc_vacio if _bloquear_persistencia_docs else st.session_state.get("foto", _doc_vacio),
        "comprobante": _doc_vacio if _bloquear_persistencia_docs else st.session_state.get("comprobante", _doc_vacio),
        "resultados_simulador": st.session_state.get("resultados_simulador", None),
        "unis_seleccionadas": st.session_state.get("unis_seleccionadas", []),
        "correo_conectado": st.session_state.get("correo_conectado", ""),
        "proveedor_correo": st.session_state.get("proveedor_correo", ""),
        "perfil_completo": st.session_state.get("perfil_completo", False),
        "perfil_nombre": st.session_state.get("perfil_nombre", ""),
        "perfil_edad": st.session_state.get("perfil_edad", None),
        "perfil_carreras": st.session_state.get("perfil_carreras", []),
        "perfil_universidades_interes": st.session_state.get("perfil_universidades_interes", []),
        "perfil_preparatoria": st.session_state.get("perfil_preparatoria", ""),
        "simulador_usado": st.session_state.get("simulador_usado", False),
    }
    try:
        # Intentar actualizar primero
        res = supabase_client.table("datos_usuario").update({
            "datos": datos,
            "updated_at": datetime.now().isoformat()
        }).eq("username", username).execute()
        # Si no existe el registro, insertar
        if not res.data:
            supabase_client.table("datos_usuario").insert({
                "username": username,
                "datos": datos,
                "updated_at": datetime.now().isoformat()
            }).execute()
    except Exception as e:
        # Antes esto fallaba en silencio (except: pass) — si Supabase tenía un
        # problema momentáneo, se perdía el progreso del alumno sin que nadie
        # se enterara. Ahora al menos te avisamos por correo.
        _notificar_error_admin("guardar_datos_usuario", e, extra=f"username={username}")


def restaurar_sesion_usuario(username):
    """Carga de Supabase al session_state. Se llama justo después del login."""
    datos = cargar_datos_usuario(username)
    st.session_state.historial_chat = datos.get(
        "historial_chat",
        [{"role": "assistant", "content": "¡Hola! Soy Hugo, tu consultor de admisión. ¿En qué puedo ayudarte hoy?"}]
    )
    st.session_state.contador_consultas = datos.get("contador_consultas", 0)
    st.session_state.fecha_contador = datos.get("fecha_contador", "")
    # Documentos académicos
    st.session_state["kárdex"]   = datos.get("kardex",    {"nombre": None, "contenido": ""})
    st.session_state.ensayo      = datos.get("ensayo",    {"nombre": None, "contenido": ""})
    st.session_state.curriculum  = datos.get("curriculum",{"nombre": None, "contenido": ""})
    st.session_state.cartas      = datos.get("cartas",    {"nombre": None, "contenido": ""})
    st.session_state.portafolio  = datos.get("portafolio",{"nombre": None, "contenido": ""})
    # Documentos personales
    st.session_state.acta          = datos.get("acta",         {"nombre": None, "contenido": ""})
    st.session_state.curp          = datos.get("curp",         {"nombre": None, "contenido": ""})
    st.session_state.identificacion= datos.get("identificacion",{"nombre": None, "contenido": ""})
    st.session_state.foto          = datos.get("foto",         {"nombre": None, "contenido": ""})
    st.session_state.comprobante   = datos.get("comprobante",  {"nombre": None, "contenido": ""})
    if datos.get("resultados_simulador"):
        st.session_state.resultados_simulador = datos["resultados_simulador"]
    st.session_state.unis_seleccionadas = datos.get("unis_seleccionadas", [])
    st.session_state.correo_conectado = datos.get("correo_conectado", "")
    st.session_state.proveedor_correo = datos.get("proveedor_correo", "")
    # La contraseña del correo NUNCA se persiste; vive solo en session_state de la sesión activa.
    st.session_state.setdefault("correo_password_sesion", "")
    st.session_state.setdefault("mensajes_universidades", {})
    # Perfil inicial (onboarding)
    st.session_state.perfil_completo = datos.get("perfil_completo", False)
    st.session_state.perfil_nombre = datos.get("perfil_nombre", "")
    st.session_state.perfil_edad = datos.get("perfil_edad", None)
    st.session_state.perfil_carreras = datos.get("perfil_carreras", [])
    st.session_state.perfil_universidades_interes = datos.get("perfil_universidades_interes", [])
    st.session_state.perfil_preparatoria = datos.get("perfil_preparatoria", "")
    st.session_state.simulador_usado = datos.get("simulador_usado", False)
    # Estatus de menor de edad y consentimiento del tutor (se leen directo de "usuarios",
    # no de "datos_usuario", porque son datos de cuenta, no de progreso).
    try:
        _res_menor = supabase_client.table("usuarios").select(
            "es_menor_edad, tutor_confirmado, tutor_nombre, tutor_email, "
            "consentimiento_hugo, consentimiento_universidades, consentimiento_promocional, "
            "rol, universidad_asignada"
        ).eq("username", username).execute()
        if _res_menor.data:
            _row_menor = _res_menor.data[0]
            st.session_state.es_menor_edad_actual = bool(_row_menor.get("es_menor_edad", False))
            st.session_state.tutor_confirmado_actual = bool(_row_menor.get("tutor_confirmado", False))
            st.session_state.tutor_nombre_actual = _row_menor.get("tutor_nombre", "") or ""
            st.session_state.tutor_email_actual = _row_menor.get("tutor_email", "") or ""
            st.session_state.consentimiento_hugo_actual = bool(_row_menor.get("consentimiento_hugo", False))
            st.session_state.consentimiento_universidades_actual = bool(_row_menor.get("consentimiento_universidades", False))
            st.session_state.consentimiento_promocional_actual = bool(_row_menor.get("consentimiento_promocional", False))
            st.session_state.rol_usuario = _row_menor.get("rol", "alumno") or "alumno"
            st.session_state.universidad_asignada = _row_menor.get("universidad_asignada", "") or ""
        else:
            st.session_state.es_menor_edad_actual = False
            st.session_state.tutor_confirmado_actual = False
            st.session_state.rol_usuario = "alumno"
            st.session_state.universidad_asignada = ""
    except Exception:
        st.session_state.es_menor_edad_actual = False
        st.session_state.tutor_confirmado_actual = False
        st.session_state.rol_usuario = "alumno"
        st.session_state.universidad_asignada = ""


def es_usuario_menor():
    """True si el usuario en sesión está marcado como menor de edad."""
    return bool(st.session_state.get("es_menor_edad_actual", False))


@st.cache_data(ttl=30, show_spinner=False)
def _tutor_confirmado_fresco(username):
    """Consulta directa a Supabase (cache de solo 30s) para saber si el tutor
    ya confirmó. session_state.tutor_confirmado_actual solo se refresca en el
    login o en una navegación completa por la sidebar, así que si el alumno
    se queda con la sesión abierta mientras su tutor confirma en otra
    pestaña, ese valor se queda desactualizado. Esta función evita ese hueco
    sin tener que golpear Supabase en cada rerun."""
    if not username:
        return False
    try:
        res = supabase_client.table("usuarios").select("tutor_confirmado").eq("username", username).execute()
        if res.data:
            return bool(res.data[0].get("tutor_confirmado", False))
    except Exception:
        pass
    return False


# =================================================================
# ROLES Y PANEL DE ADMINISTRADOR / UNIVERSIDADES
# =================================================================
# Requiere en Supabase, tabla "usuarios", las columnas adicionales:
#   rol (text, default 'alumno')                -> 'alumno' | 'admin' | 'universidad'
#   universidad_asignada (text, nullable)        -> nombre exacto de UNIVERSIDADES_DATA,
#                                                    solo se usa cuando rol='universidad'
# Un usuario con rol='universidad' SOLO ve alumnos que (a) la seleccionaron como de su
# interés y (b) dieron consentimiento explícito para compartir su info con universidades
# (columna consentimiento_universidades). Un usuario con rol='admin' ve todo.

PANEL_ADMIN_PAGES = [
    "panel_admin", "panel_chat", "panel_simulador",
    "panel_carreras", "panel_perfiles", "panel_carreras_perfiles", "panel_consultor", "panel_usuarios",
]


def rol_usuario_actual():
    return st.session_state.get("rol_usuario", "alumno")


def es_admin():
    return rol_usuario_actual() == "admin"


def es_universidad():
    return rol_usuario_actual() == "universidad"


def puede_ver_panel():
    return rol_usuario_actual() in ("admin", "universidad")


# --- Archivos binarios en Supabase Storage ---
BUCKET = "locker-archivos"


def _nombre_seguro(username):
    return "".join(c for c in (username or "usuario") if c.isalnum() or c in ("_", "-")) or "usuario"


def guardar_archivo_original(username, tipo_documento, nombre_archivo, datos_bytes):
    """Sube el archivo a Supabase Storage, reemplazando el anterior del mismo tipo."""
    eliminar_archivo_original(username, tipo_documento)
    carpeta = _nombre_seguro(username)
    path = f"{carpeta}/{tipo_documento}__{nombre_archivo}"
    supabase_client.storage.from_(BUCKET).upload(
        path, datos_bytes,
        {"content-type": "application/octet-stream", "upsert": "true"}
    )
    return path


def obtener_archivo_original(username, tipo_documento):
    """Devuelve (bytes, nombre_original) del archivo guardado, o (None, None)."""
    carpeta = _nombre_seguro(username)
    try:
        archivos = supabase_client.storage.from_(BUCKET).list(carpeta)
    except Exception:
        return None, None
    for archivo in (archivos or []):
        if archivo["name"].startswith(f"{tipo_documento}__"):
            nombre_original = archivo["name"].split("__", 1)[1]
            try:
                datos = supabase_client.storage.from_(BUCKET).download(
                    f"{carpeta}/{archivo['name']}"
                )
            except Exception:
                return None, None
            return datos, nombre_original
    return None, None


def eliminar_archivo_original(username, tipo_documento):
    carpeta = _nombre_seguro(username)
    try:
        archivos = supabase_client.storage.from_(BUCKET).list(carpeta)
    except Exception:
        return
    for archivo in (archivos or []):
        if archivo["name"].startswith(f"{tipo_documento}__"):
            supabase_client.storage.from_(BUCKET).remove(
                [f"{carpeta}/{archivo['name']}"]
            )


def mostrar_visor_documento(username, tipo_documento, titulo_boton="Ver / Descargar documento"):
    """Muestra botón de descarga y, si es PDF, una vista previa incrustada."""
    datos_bytes, nombre_original = obtener_archivo_original(username, tipo_documento)
    if not datos_bytes:
        return
    with st.expander(f"{titulo_boton}: {nombre_original}"):
        st.download_button(
            "Descargar",
            data=datos_bytes,
            file_name=nombre_original,
            key=f"descarga_{tipo_documento}",
        )
        if nombre_original.lower().endswith(".pdf"):
            b64 = base64.b64encode(datos_bytes).decode()
            st.markdown(
                f'<div style="margin-top:12px;"><iframe src="data:application/pdf;base64,{b64}" '
                f'width="100%" height="500" style="border:1px solid #EAEAEA; border-radius:6px; '
                f'display:block;"></iframe></div>',
                unsafe_allow_html=True,
            )
        elif nombre_original.lower().endswith((".jpg", ".jpeg", ".png")):
            st.image(datos_bytes)


# =================================================================
# DATOS DE REFERENCIA POR UNIVERSIDAD (Simulador Estadístico)
# =================================================================
# promedio_min: en escala 0-10 (normalizado, aunque la fuente original use 0-100)
# examen_min: en escala 0-100 normalizada (el alumno captura su "percentil estimado"
#             de examen en 0-100, ya que cada universidad usa un examen distinto
#             con escalas distintas: PAA 200-800x2, EXANI-II 700-1300, etc.)
# tasa_historica: % de aceptación histórico
# confianza: "oficial" si el dato viene confirmado por fuente oficial/confiable,
#            "estimado" si no hay dato público y se usó un valor razonable de referencia
UNIVERSIDADES_DATA = {
    "Tec de Monterrey": {
        "promedio_min": 8.5,
        "examen_min": 82,
        "tasa_historica": 25,
        "confianza": "oficial",
        "fuente": "Promedio mínimo 8.5 y PAA mínimo ~1,320/1,600 pts; tasa de aceptación ~25%.",
        "documentos": ["kardex", "ensayo", "curriculum", "cartas", "acta", "curp", "identificacion", "foto", "comprobante"],
        "documentos_extra": ["Ficha de inscripción pagada", "Resultado oficial del PAA/examen de admisión"],
        "proceso": [
            "Crear solicitud en solicitud.tec.mx",
            "Pagar cuota de admisión (~$1,300 MXN)",
            "Presentar examen PAA (o entregar SAT/ACT convertido a escala PAA)",
            "Llenar currículo y ensayo (pesan en la decisión final, no son trámite)",
            "Recibir resultado en ~15 días por correo y portal",
        ],
        "fechas_clave": "Para becas de talento académico, el PAA debe presentarse antes del 17 de enero 2026 (Medicina: 13 dic 2025). Resultados de becas: 26 feb 2026.",
        "costos": {
            "examen_admision": "$1,300 MXN (cuota de admisión)",
            "reserva_de_lugar": "$7,000–$9,000 MXN según si hay beca",
            "colegiatura": "Variable por campus/carrera — usar cotizador oficial del Tec",
        },
        "becas": ["Beca al Talento Académico (requiere PAA alto, varía por tipo)", "Becas socioeconómicas con préstamo educativo complementario"],
        "notas_hugo": "El 'puntaje PAA mínimo' no es un corte único de admisión — los rangos de 1,000-1,360 que existen son requisitos de BECA, no de entrada. No los presentes como si fueran el mínimo para ser aceptado.",
    },
    "UdeG": {
        "promedio_min": 8.0,
        "examen_min": 70,
        "tasa_historica": 33.5,
        "confianza": "parcial",
        "fuente": "Tasa de aceptación oficial 2026-A: 56,202 admitidos de 167,690 aspirantes (~33.5%). El puntaje mínimo real varía por carrera y centro universitario, no es un número fijo.",
        "documentos": ["kardex", "acta", "curp", "identificacion", "foto", "comprobante"],
        "documentos_extra": ["Ficha PRECOSECH / pago de derechos", "Certificado de bachillerato (no solo kárdex)"],
        "proceso": [
            "Registro PRECOSECH y pago de derechos",
            "Presentar PAA del College Board (la sección de inglés no cuenta para el puntaje final)",
            "Puntaje total = resultado PAA + promedio de bachillerato",
            "Publicación de dictamen (varía por calendario, ~1 semana antes de inicio de clases)",
            "Si no fue admitido: solicitar cambio a carrera con cupo disponible en los días inmediatos al dictamen",
        ],
        "fechas_clave": "Calendario 2026-A: dictamen publicado 12 enero 2026; inicio de clases 19 enero 2026.",
        "costos": {
            "examen_admision": "Costo de trámite PRECOSECH, varía por calendario — confirmar monto vigente",
            "colegiatura": "Universidad pública, cuotas simbólicas comparadas con privadas",
        },
        "becas": ["Becas SEP / gobierno federal para alumnos de universidad pública (sujetas a convocatoria aparte)"],
        "notas_hugo": "El puntaje mínimo por carrera es DINÁMICO: lo define el último aspirante admitido cada ciclo. Nunca lo presentes como una cifra fija año con año — habla de rangos históricos como referencia, no como garantía.",
    },
    "UP": {
        "promedio_min": 8.0,
        "examen_min": 50,
        "tasa_historica": 78,
        "confianza": "estimado",
        "fuente": "No hay tasa de aceptación pública. Estimado a partir de fuentes que describen el ingreso como poco competitivo (excepto Medicina).",
        "documentos": ["kardex", "ensayo", "curriculum", "acta", "curp", "identificacion", "foto", "comprobante"],
        "documentos_extra": ["Entrevista de admisión agendada"],
        "proceso": [
            "Solicitud en línea (mkt.up.edu.mx)",
            "Examen PAA del College Board",
            "Examen psicométrico (día siguiente al PAA)",
            "Entrevista con un miembro de la comunidad académica",
            "Entrega de resultados",
        ],
        "fechas_clave": "Exámenes ordinarios 2026: mayo-junio (fechas específicas: 13, 16, 20, 23, 27, 30 de mayo). Ciencias de la Salud: fechas propias en abril-mayo.",
        "costos": {
            "examen_admision": "Licenciaturas/Ingenierías ~$1,250 MXN; Enfermería ~$2,400; Psicología ~$2,500; Medicina ~$4,050 (confirmar vigencia)",
            "colegiatura": "Por crédito: ~$3,480/crédito en CDMX/GDL, ~$3,185 en Aguascalientes (~468 créditos/carrera) + seguro de orfandad ~$1,513/semestre",
        },
        "becas": ["Beca Panamericana (mérito académico, promedio >9.5)", "~60% de los alumnos de licenciatura tienen algún tipo de beca según la UP"],
        "notas_hugo": "Confirma costos del examen y colegiatura con el cotizador oficial antes de dar una cifra exacta a un alumno — cambian por ciclo y campus.",
    },
    "ITESO": {
        "promedio_min": 8.0,
        "examen_min": 60,
        "tasa_historica": 75,
        "confianza": "estimado",
        "fuente": "No hay tasa de aceptación pública. Estimado: descrita como menos competitiva que universidades públicas.",
        "documentos": ["kardex", "ensayo", "acta", "curp", "identificacion", "foto", "comprobante"],
        "documentos_extra": ["Ficha de admisión pagada"],
        "proceso": [
            "Solicitud en línea (admision.iteso.mx)",
            "Entrega de documentos requeridos",
            "Pago del examen (preferencial si la prepa de origen tiene convenio con ITESO)",
            "Examen PAA presencial (en campus o en 1 de 40+ ciudades con sede)",
            "Pase automático sin examen si la prepa es 'de convenio' y el alumno cumple el promedio requerido",
        ],
        "fechas_clave": "Dos convocatorias al año: ingreso enero e ingreso agosto (la mayoría de licenciaturas inician en agosto). Entrega de documentación de nuevo ingreso agosto 2026: 6, 7, 10 y 11 de agosto.",
        "costos": {
            "examen_admision": "~$700 MXN con convenio de prepa, ~$1,100 MXN sin convenio",
            "curso_preparacion": "$980 MXN (opcional)",
            "colegiatura": "Semestre entre ~$74,000 y $86,000 MXN según carga de créditos",
        },
        "becas": ["Beca de Excelencia Académica (automática, mejores puntajes)", "Becas socioeconómicas (requieren promedio SEP ≥80)", "Financiamiento educativo (crédito + beca combinados)"],
        "notas_hugo": "Si el alumno viene de una prepa con convenio con ITESO y cumple el promedio, probablemente tenga pase directo sin examen — vale la pena preguntarle de qué prepa viene antes de asumir que necesita presentar PAA.",
    },
    "UNAM": {
        "promedio_min": 7.0,
        "examen_min": 88,
        "tasa_historica": 9,
        "confianza": "parcial",
        "fuente": "Promedio mínimo oficial de 7.0. Tasa de aceptación general del Concurso de Selección ≈9%, pero varía desde ~1.4% en Medicina hasta carreras de baja demanda con corte mucho menor.",
        "documentos": ["kardex", "acta", "curp", "identificacion", "foto"],
        "documentos_extra": ["Pago de derecho a examen", "Cita para registro de foto, firma y huella (biométricos)", "Examen diagnóstico de inglés (obligatorio, no elimina)"],
        "proceso": [
            "Registro en el portal DGAE en fechas oficiales",
            "Elegir UNA carrera, UN sistema y UN plantel (no se puede cambiar tras confirmar)",
            "Presentar examen de 120 preguntas (3 horas, presencial)",
            "Resultados publicados en 'Tu Sitio' del DGAE",
        ],
        "fechas_clave": "Examen 2026: 18 mayo al 2 junio (primera vuelta, sistema escolarizado). Resultados: 17 julio 2026. Segunda vuelta (solo SUAyED): noviembre 2026.",
        "costos": {
            "examen_admision": "Cuota de derecho a examen — universidad pública, costo simbólico",
            "colegiatura": "Universidad pública, cuota simbólica",
        },
        "becas": ["Becas SEP / institucionales para alumnos de universidad pública"],
        "notas_hugo": (
            "La UNAM NO tiene puntaje mínimo fijo: admite por mejor desempeño hasta llenar cupo. "
            "Usa estos rangos de aciertos (sobre ~120-128 según facultad, ciclo reciente) SOLO como referencia "
            "histórica, nunca como garantía: Médico Cirujano CU ~111-115 (la más competida, ~1.4% de aceptación "
            "general), FES Iztacala Medicina ~108-110, Cirujano Dentista ~98, Psicología CU ~104, "
            "Arquitectura ~95, Ciencias Genómicas ~70-80, Ingeniería Geofísica ~65-75, Filosofía/Letras "
            "Hispánicas ~55-65, Geografía ~50-60. Aclara siempre que el corte real lo define la demanda del "
            "ciclo en turno."
        ),
    },
    "UAG": {
        "promedio_min": 7.0,
        "examen_min": 45,
        "tasa_historica": 80,
        "confianza": "estimado",
        "fuente": "Sin tasa de aceptación pública. Universidad privada más antigua de México (1935), campus principal en Zapopan, Jalisco. Examen descrito como filtro de aptitud, no muy selectivo salvo Medicina.",
        "documentos": ["kardex", "acta", "curp", "identificacion", "foto", "comprobante"],
        "documentos_extra": ["Autobiografía (mínimo 2 páginas)"],
        "proceso": [
            "Llenar solicitud en admision.uag.mx",
            "Adjuntar autobiografía, acta de nacimiento, fotografía, certificado/constancia de bachillerato con promedio, comprobante de domicilio",
            "Agendar y presentar examen de admisión (PAA del College Board; Medicina puede pedir examen de conocimientos adicional)",
            "Si aprueba: recibe formato de inscripción y entrega documentos de forma presencial",
            "Pago de colegiatura y entrega de credencial",
        ],
        "fechas_clave": "Dos convocatorias al año. Fechas exactas varían entre fuentes (apertura reportada en noviembre o en febrero según el ciclo) — confirmar directamente en uag.mx antes de comunicar a una prepa.",
        "costos": {
            "examen_admision": "~$950 MXN (incluye solicitud, examen y credencial de aspirante)",
            "colegiatura": "Mensualidad ~$9,000–$23,000 MXN según carrera (~$170,000–$240,000 MXN al año). Medicina y Cirujano Dentista tienen esquema propio, más alto.",
        },
        "becas": ["Beca de Excelencia Académica (promedio >9.0 + buen examen)", "Becas deportivas y culturales", "Convenios empresariales/institucionales — ~1 de cada 5 alumnos tiene algún apoyo"],
        "notas_hugo": "Es la universidad privada más antigua de México y tiene su campus principal en Zapopan — muy relevante para alumnos de Guadalajara. Confirma siempre las fechas de convocatoria vigentes antes de darlas como definitivas, las fuentes no coinciden entre sí.",
    },
}


def construir_contexto_universidades(universidades_interes=None):
    """
    Arma un bloque de texto con la información verificada de UNIVERSIDADES_DATA
    para inyectarla al contexto de Hugo. Si el alumno ya eligió universidades de
    interés, solo manda esas (para no inflar tokens); si no, manda todas.
    """
    if universidades_interes:
        nombres = [u for u in universidades_interes if u in UNIVERSIDADES_DATA]
        if not nombres:
            nombres = list(UNIVERSIDADES_DATA.keys())
    else:
        nombres = list(UNIVERSIDADES_DATA.keys())

    bloques = []
    for nombre in nombres:
        datos = UNIVERSIDADES_DATA[nombre]
        costos_txt = "; ".join(f"{k}: {v}" for k, v in datos.get("costos", {}).items())
        becas_txt = "; ".join(datos.get("becas", []))
        proceso_txt = " → ".join(datos.get("proceso", []))
        bloques.append(
            f"### {nombre} (confianza del dato: {datos['confianza']})\n"
            f"- Fuente: {datos['fuente']}\n"
            f"- Promedio mínimo de bachillerato: {datos['promedio_min']}\n"
            f"- Proceso de admisión: {proceso_txt}\n"
            f"- Fechas clave 2026: {datos.get('fechas_clave', 'No disponible, consultar con la universidad.')}\n"
            f"- Costos de referencia: {costos_txt or 'No disponible.'}\n"
            f"- Becas principales: {becas_txt or 'No disponible.'}\n"
            f"- Documentos requeridos: {', '.join(datos.get('documentos', []))}\n"
            f"- INSTRUCCIÓN ESPECÍFICA: {datos.get('notas_hugo', '')}"
        )
    return "\n\n".join(bloques)


# Nombres legibles de cada documento "tipo locker" (para armar las carpetas por universidad)
DOCUMENTOS_LOCKER_INFO = {
    "kardex":         {"label": "Kárdex / Certificado",          "tipo": "académico"},
    "ensayo":         {"label": "Ensayo / Carta de motivos",     "tipo": "académico"},
    "curriculum":     {"label": "Currículum académico",          "tipo": "académico"},
    "cartas":         {"label": "Cartas de recomendación",       "tipo": "académico"},
    "portafolio":     {"label": "Portafolio / Extracurriculares","tipo": "académico"},
    "acta":           {"label": "Acta de nacimiento",            "tipo": "personal"},
    "curp":           {"label": "CURP",                          "tipo": "personal"},
    "identificacion": {"label": "Identificación oficial",        "tipo": "personal"},
    "foto":           {"label": "Foto credencial",                "tipo": "personal"},
    "comprobante":    {"label": "Comprobante de domicilio",      "tipo": "personal"},
}


def calcular_probabilidad_base(promedio_alumno, examen_alumno, datos_uni):
    """
    Fórmula base (sin IA): parte de la tasa histórica de aceptación y la ajusta
    según qué tan por arriba o abajo está el alumno de los mínimos de referencia.
    """
    peso_promedio = 4.0   # puntos % por cada décima de diferencia en promedio (0-10)
    peso_examen = 0.3     # puntos % por cada punto de diferencia en examen (0-100)

    diff_promedio = promedio_alumno - datos_uni["promedio_min"]
    diff_examen = examen_alumno - datos_uni["examen_min"]

    prob = datos_uni["tasa_historica"] + (diff_promedio * peso_promedio) + (diff_examen * peso_examen)
    # Limitar entre 5% y 98% (nunca certeza absoluta ni descarte total)
    return max(5, min(98, round(prob, 1)))


# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
   page_title="Uniwebmx - Admisiones Inteligentes",
   page_icon=None,
   layout="wide",
   initial_sidebar_state="expanded"
)
# --- CAPTURA DE NAVEGACIÓN VIA URL ---

# 1. Interceptor de navegación interna via ?nav=X&t=TOKEN — corre PRIMERO
# Los <a href> de la sidebar hacen un full reload y borran session_state.
# Recuperamos la sesión usando un TOKEN aleatorio (no el username) que se
# valida contra Supabase con validar_sesion_token(). Un username por sí solo
# nunca es suficiente para autenticar: cualquiera podría escribirlo a mano
# en la URL. El token es como una contraseña de un solo propósito: largo,
# aleatorio, con expiración, y revocable en logout.
if "nav" in st.query_params:
   _nav_target = st.query_params.get("nav")
   _nav_token  = st.query_params.get("t", "")
   st.query_params.clear()
   if _nav_target == "__logout__":
       invalidar_sesion_token(st.session_state.get("user"))
       st.session_state.logged_in = False
       st.session_state.pop("user", None)
       st.session_state.pop("session_token", None)
       st.session_state.page = "inicio"
   # Estos flujos (darse de baja de promocionales, eliminar cuenta) antes
   # revisaban st.query_params más abajo en el archivo, pero para entonces
   # ya se había llamado st.query_params.clear() aquí arriba y el valor
   # nunca llegaba. Los guardamos en session_state en su lugar.
   elif _nav_target == "__baja_promocional__":
       st.session_state["_ejecutar_baja_promocional_pendiente"] = True
   elif _nav_target == "__eliminar_cuenta__":
       st.session_state["_confirmar_eliminacion"] = True
   elif _nav_target == "__ejecutar_eliminacion__":
       st.session_state["_ejecutar_eliminacion_pendiente"] = True
   elif _nav_target == "__descartar_accion_cuenta__":
       st.session_state["_mostrar_confirmar_eliminacion"] = False
       st.session_state.page = "locker"
   elif _nav_token:
       _usuario_validado = validar_sesion_token(_nav_token)
       if _usuario_validado:
           st.session_state.logged_in = True
           st.session_state.user = _usuario_validado
           st.session_state.session_token = _nav_token
           restaurar_sesion_usuario(_usuario_validado)
           st.session_state.page = _nav_target
       else:
           # Token inválido, expirado o manipulado: nunca asumir identidad.
           st.session_state.logged_in = False
           st.session_state.pop("user", None)
           st.session_state.page = "login"

# 2. Fallback: primera carga normal sin parámetros nav
if "page" not in st.session_state:
   query_params = st.query_params
   if "page" in query_params:
       _page_val = query_params["page"]
       st.session_state.page = _page_val
       # Los enlaces de "confirmar tutor" y "recuperar contraseña" que se mandan por
       # correo también llegan con ?token=XXX en la URL. st.query_params.clear() de
       # abajo borra ese token antes de que la vista correspondiente lo pueda leer,
       # así que lo guardamos aquí primero en session_state.
       if _page_val in ("confirmar_tutor", "reset_contrasena"):
           st.session_state["_token_url_pendiente"] = query_params.get("token", "")
   else:
       st.session_state.page = "inicio"
   st.query_params.clear()


def cambiar_pagina(nombre_pagina):
   st.session_state.page = nombre_pagina
   st.rerun()


# --- PROCESAMIENTO DE IMÁGENES ---
# IMPORTANTE: cacheado con st.cache_data. Sin esto, Streamlit re-lee y
# re-codifica en base64 estas imágenes en CADA rerun de CADA usuario
# conectado (Streamlit corre el script completo de arriba a abajo en cada
# interacción). Con varios usuarios activos a la vez eso multiplica el uso
# de memoria y es la causa más probable de los avisos de "memory limit
# exceeded" de Render. Con el cache, la lectura + codificación ocurre una
# sola vez por archivo mientras el proceso siga vivo.
@st.cache_data(show_spinner=False)
def get_base64_image(image_path):
   if os.path.exists(image_path):
       with open(image_path, "rb") as img_file:
           return base64.b64encode(img_file.read()).decode()
   return None


logo_encoded = get_base64_image("logo.png")
fondo_inicio_encoded = get_base64_image("fondo_hero.png")
fondo_locker_encoded = get_base64_image("fondo_locker.png")
fondo_auth_encoded = get_base64_image("fondo_auth.png")
# Fotos del carrusel de la landing (sección "Herramientas"). Sube estos 3
# archivos a la raíz del proyecto (junto a fondo_hero.png, logo.png, etc.)
# con estos nombres exactos:
# Fotos del carrusel de la landing (sección "Herramientas"). Ya NO se leen del
# disco ni se codifican en base64: pesan mucho menos servidas como archivo
# real desde Supabase Storage vía URL, tanto para el navegador como para la
# memoria del proceso (antes se re-codificaban en cada rerun de cada
# usuario). Sube los 3 .jpg optimizados al mismo bucket público "assets"
# que ya usas para el logo, con estos nombres exactos:
_SUPABASE_STORAGE_BASE = "https://qbtbcvwwfqoghgvyhztd.supabase.co/storage/v1/object/public/assets/"
carrusel_locker_url = f"{_SUPABASE_STORAGE_BASE}fondo_carrusel_locker.jpg"
carrusel_consultor_url = f"{_SUPABASE_STORAGE_BASE}fondo_carrusel_consultor.jpg"
carrusel_simulador_url = f"{_SUPABASE_STORAGE_BASE}fondo_carrusel_simulador.jpg"


if fondo_inicio_encoded:
   bg_inicio = f"linear-gradient(rgba(255, 255, 255, 0.75), rgba(255, 255, 255, 0.75)), url('data:image/png;base64,{fondo_inicio_encoded}')"
else:
   bg_inicio = "linear-gradient(rgba(243, 239, 234, 0.95), rgba(243, 239, 234, 0.95))"


if fondo_locker_encoded:
   bg_locker = f"linear-gradient(rgba(255, 255, 255, 0.75), rgba(255, 255, 255, 0.75)), url('data:image/png;base64,{fondo_locker_encoded}')"
else:
   bg_locker = "linear-gradient(rgba(238, 240, 236, 0.95), rgba(238, 240, 236, 0.95))"

# Inicializar estado de sesión
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# Filtro de seguridad: Si no está logueado, prohibir acceso al Hub
if not st.session_state.logged_in and st.session_state.page in ["locker", "chat", "simulador", "mi_aplicacion", "mensajes", "onboarding"]:
    st.session_state.page = "login"
# Filtro de seguridad: el Panel (admin/universidades) requiere sesión Y el rol correcto.
# Un alumno normal jamás debe poder entrar tecleando la URL a mano.
if not st.session_state.logged_in and st.session_state.page in PANEL_ADMIN_PAGES:
    st.session_state.page = "login"
elif st.session_state.logged_in and st.session_state.page in PANEL_ADMIN_PAGES and not puede_ver_panel():
    st.session_state.page = "locker" if st.session_state.get("perfil_completo") else "onboarding"
elif st.session_state.page == "panel_usuarios" and not es_admin():
    # Solo el equipo de Uniwebmx puede asignar roles, una universidad no.
    st.session_state.page = "panel_admin"
# Determinar si el usuario está dentro del Hub de alumnos o del Panel admin/universidades
es_hub = st.session_state.page in ["locker", "chat", "simulador", "mi_aplicacion", "mensajes"]
es_panel = st.session_state.page in PANEL_ADMIN_PAGES


# --- INYECCIÓN CSS INTERNA ---
st.markdown(f"""
<style>
   @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght=400;500;600;700&display=swap');
   @import url('https://cdnjs.cloudflare.com/ajax/libs/tabler-icons/2.47.0/tabler-icons.min.css');

   /* La fuente Material Symbols que usa Streamlit internamente (file_uploader,
      expander, etc.) no carga en este entorno y muestra el nombre del icono
      como texto crudo encimado. Mientras eso se resuelve, lo ocultamos para
      que no se vea texto roto — mejor sin icono que con texto encimado. */
   [data-testid="stIconMaterial"] {{
       display: none !important;
   }}

   /* Ocultar el chrome nativo de Streamlit (menú hamburguesa, botón "Deploy",
      ícono de GitHub, footer "Made with Streamlit"). Esto es lo que se veía
      como una "barra rara" arriba en cualquier dispositivo: no es un bug de
      la app, es la interfaz por defecto de Streamlit que nunca se ocultó.
      No tocamos [data-testid="stSidebar"] aquí porque esa sí es nuestra
      navegación propia y se necesita en el Hub/Panel. */
   #MainMenu {{
       visibility: hidden !important;
       display: none !important;
   }}
   header[data-testid="stHeader"] {{
       display: none !important;
       height: 0 !important;
   }}
   [data-testid="stToolbar"] {{
       display: none !important;
   }}
   [data-testid="stDecoration"] {{
       display: none !important;
   }}
   footer {{
       visibility: hidden !important;
       display: none !important;
   }}
   /* Al quitar el header, recuperamos el espacio que dejaba arriba */
   .stApp {{
       margin-top: -3.5rem !important;
   }}
   [data-testid="stAppViewContainer"] {{
       padding-top: 0 !important;
   }}

   /* Aplicación de Tipografía Global */
   .stApp, button, p, span, a, h1, h2, h3, [data-testid="stSidebar"] {{
       font-family: 'Montserrat', sans-serif !important;
   }}


   .stApp {{
       background-color: #FFFFFF;
   }}
   .block-container {{
       padding-top: 1rem !important;
       padding-bottom: 5rem !important;
   }}


   /* Ocultar barra lateral en páginas públicas */
   {"[data-testid='stSidebar'] {display: none;}" if not es_hub and not es_panel else ""}
  
   /* Elminar el texto basura "keyboard_double..." del botón colapsable nativo de Streamlit */
   [data-testid="stSidebarCollapseButton"] button span {{
       font-size: 0px !important;
       color: transparent !important;
       display: none !important;
   }}
   [data-testid="stSidebarCollapseButton"] {{
       background: transparent !important;
   }}


   h1 {{
       font-weight: 700;
       color: #1A1A1A !important;
       letter-spacing: -0.03em;
   }}
   h2 {{
       font-weight: 700;
       color: #1A1A1A !important;
   }}
   h3 {{
       font-weight: 600;
       color: #4A5D32 !important;
       margin-bottom: 12px !important;
       margin-top: 0px !important;
   }}


   /* NAVBAR */
   .navbar-custom {{
       display: flex;
       align-items: center;
       justify-content: space-between;
       padding: 10px 0;
       margin-bottom: 1rem;
   }}
   .nav-logo-link {{
       font-weight: 700;
       color: #374337 !important;
       font-size: 1.8rem;
       letter-spacing: -0.04em;
       text-transform: lowercase;
       text-decoration: none !important;
   }}
   .menu-items-container {{
       display: flex;
       gap: 28px;
       align-items: center;
       margin-top: 12px;
   }}
   .nav-logo-link img {{
       max-height: 45px;
   }}
   .menu-item-link {{
       font-weight: 500;
       color: #1A1A1A !important;
       font-size: 0.95rem;
       text-decoration: none !important;
   }}


   /* Botones Navbar */
   .nav-right div.stButton button {{
       border-radius: 4px !important;
       font-weight: 600 !important;
       height: 40px !important;
       padding: 0 22px !important;
       margin-top: 10px !important;
       font-size: 0.9rem !important;
   }}
   .btn-login div.stButton button {{
       background-color: transparent !important;
       color: #1A1A1A !important;
       border: 1px solid #EAEAEA !important;
   }}
   .btn-register div.stButton button {{
       background-color: #4A5D32 !important;
       color: white !important;
       border: none !important;
   }}


   /* HEROES */
   .hero-section-inicio {{
       background-image: {bg_inicio};
       background-size: cover;
       background-position: center;
       padding: 7rem 4rem 8rem 4rem;
       text-align: center;
       margin-left: -5rem !important;
       margin-right: -5rem !important;
       margin-top: 0.5rem;
       margin-bottom: 4rem;
       width: calc(100% + 10rem);
   }}
   .hero-section-locker {{
       background-image: {bg_locker};
       background-size: cover;
       background-position: center;
       padding: 6rem 4rem;
       text-align: center;
       margin-left: -5rem !important;
       margin-right: -5rem !important;
       margin-top: -1.6rem !important;
       margin-bottom: 4rem;
       width: calc(100% + 10rem);
   }}
   .hero-green-btn {{
       display: inline-block;
       background-color: #4A5D32 !important;
       color: white !important;
       font-weight: 600;
       font-size: 1rem;
       padding: 14px 38px;
       border-radius: 4px;
       text-decoration: none !important;
       margin-top: 2.5rem;
   }}
   .card-beneficio {{
       background-color: #FFFFFF;
       padding: 2.5rem 2rem;
       border-radius: 6px;
       border: 1px solid #EAEAEA;
       height: 100%;
   }}

   /* CARRUSEL CONTINUO DE HERRAMIENTAS (landing) */
   .uw-carrusel-viewport {{
       overflow: hidden;
       background-color: #FAFAF8;
       border-radius: 10px;
       padding: 2rem 0;
       -webkit-mask-image: linear-gradient(90deg, transparent, #000 6%, #000 94%, transparent);
       mask-image: linear-gradient(90deg, transparent, #000 6%, #000 94%, transparent);
   }}
   .uw-carrusel-track {{
       display: flex;
       gap: 18px;
       width: max-content;
       animation: uw-scroll 42s linear infinite;
   }}
   .uw-carrusel-track:hover {{
       animation-play-state: paused;
   }}
   @keyframes uw-scroll {{
       from {{ transform: translateX(0); }}
       to {{ transform: translateX(-50%); }}
   }}
   @media (prefers-reduced-motion: reduce) {{
       .uw-carrusel-track {{ animation: none !important; }}
   }}

   /* =================================================================
      RESPONSIVE MOBILE — antes de esto solo existía la regla de
      prefers-reduced-motion; no había NINGÚN breakpoint real de tamaño
      de pantalla en todo el archivo, por eso se veía mal en celular.
      ================================================================= */
   @media (max-width: 768px) {{
       /* El truco de "sangrado completo" (margin negativo fijo de -5rem)
          asume el padding de escritorio de Streamlit (~5rem). En celular
          ese padding es mucho más chico, así que el margen negativo
          empujaba el hero fuera de la pantalla. Lo ajustamos al padding
          real de mobile. */
       .hero-section-inicio, .hero-section-locker {{
           margin-left: -1rem !important;
           margin-right: -1rem !important;
           width: calc(100% + 2rem) !important;
           padding: 3rem 1.25rem !important;
       }}
       /* Los títulos h1 de cada página están inline a 3.5rem — con
          !important en el media query sí podemos ganarle a ese inline. */
       h1 {{
           font-size: 1.9rem !important;
           line-height: 1.3 !important;
       }}
       .hero-section-inicio p, .hero-section-locker p {{
           font-size: 1rem !important;
           line-height: 1.55 !important;
       }}
       .hero-green-btn {{
           padding: 12px 26px !important;
           font-size: 0.9rem !important;
       }}
       /* Carrusel: tarjetas más chicas para que no se corten feo en pantallas angostas */
       .uw-slide {{
           width: 220px !important;
           height: 160px !important;
       }}
       .uw-carrusel-viewport {{
           padding: 1rem 0 !important;
       }}
       /* Tarjetas y cajas con padding pensado para desktop */
       .card-beneficio {{
           padding: 1.5rem 1.25rem !important;
       }}
       .locker-box-clean {{
           padding: 1.5rem !important;
       }}
       [data-testid="stVerticalBlockBorderWrapper"] {{
           padding: 1.25rem 1.25rem !important;
       }}
       /* La barra inferior fija del perfil y su menú usan anchos fijos en px
          pensados para el ancho de escritorio de la sidebar; en celular la
          sidebar ocupa casi todo el ancho, así que un ancho fijo se ve
          chico y descuadrado — lo hacemos relativo al viewport. */
       .sidebar-bottom-bar {{
           width: 100% !important;
       }}
       .profile-menu {{
           width: min(85vw, 320px) !important;
       }}
   }}
   @media (max-width: 480px) {{
       h1 {{
           font-size: 1.6rem !important;
       }}
       .hero-section-inicio, .hero-section-locker {{
           padding: 2.25rem 1rem !important;
       }}
       .uw-slide {{
           width: 190px !important;
           height: 140px !important;
       }}
   }}
   .uw-slide {{
       flex-shrink: 0;
       width: 320px;
       height: 220px;
       border-radius: 10px;
       overflow: hidden;
       position: relative;
       background-size: cover;
       background-position: center;
   }}
   .uw-slide-overlay {{
       position: absolute;
       inset: 0;
       background: linear-gradient(0deg, rgba(20,24,14,0.75) 0%, rgba(20,24,14,0.15) 55%, rgba(20,24,14,0) 75%);
   }}
   .uw-slide-text {{
       position: absolute;
       left: 0; right: 0; bottom: 0;
       padding: 18px 20px;
   }}
   .uw-somos-icon {{
       width: 34px; height: 34px; border-radius: 8px;
       background: #EEF1E9;
       display: flex; align-items: center; justify-content: center;
       margin-bottom: 12px;
   }}

   /* LOCKER DESIGN */
   .locker-box-clean {{
       background-color: #FFFFFF !important;
       border: 1px solid #EAEAEA !important;
       border-radius: 8px !important;
       padding: 2.5rem !important;
       margin-bottom: 1.5rem !important;
   }}
   /* Contenedor nativo de Streamlit (st.container(border=True)) usado en el Locker */
   [data-testid="stVerticalBlockBorderWrapper"] {{
       background-color: #FFFFFF !important;
       border: 1px solid #EAEAEA !important;
       border-radius: 8px !important;
       margin-bottom: 1.5rem !important;
       padding: 2rem 2.2rem !important;
       min-height: 220px !important;
   }}
   /* Forzar alineación top en columnas dentro de tarjetas del locker */
   [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stHorizontalBlock"] {{
       align-items: flex-start !important;
   }}
   /* Botón Quitar — como link de texto abajo del documento */
   .quitar-link button {{
       all: unset !important;
       cursor: pointer !important;
       font-family: Montserrat, sans-serif !important;
       font-size: 0.78rem !important;
       color: #AAAAAA !important;
       text-decoration: underline !important;
       padding: 0 !important;
       margin-top: 6px !important;
       display: inline !important;
   }}
   .quitar-link button:hover {{
       color: #CC3333 !important;
   }}
   .locker-text-desc {{
       color: #666666;
       font-size: 0.95rem;
       line-height: 1.5;
       margin-bottom: 1.8rem !important;
   }}
   .stFileUploader label {{
       display: none !important;
   }}
   /* Contenedor completo del dropzone: layout vertical limpio, sin texto encimado */
   [data-testid="stFileUploaderDropzone"] {{
       display: flex !important;
       flex-direction: column !important;
       align-items: center !important;
       justify-content: center !important;
       gap: 10px !important;
       padding: 1.5rem 1rem !important;
       background-color: #FBFBFA !important;
       border: 1px dashed #D9D9D3 !important;
       border-radius: 8px !important;
   }}
   [data-testid="stFileUploaderDropzoneInstructions"] {{
       text-align: center !important;
       white-space: normal !important;
       overflow: visible !important;
   }}
   [data-testid="stFileUploaderDropzoneInstructions"] span,
   [data-testid="stFileUploaderDropzoneInstructions"] small {{
       display: block !important;
       white-space: normal !important;
       word-break: break-word !important;
   }}
   .stFileUploader button {{
       background-color: #1A1A1A !important;
       color: #FFFFFF !important;
       border: none !important;
       border-radius: 8px !important;
       padding: 9px 24px !important;
       font-weight: 600 !important;
       font-size: 0.85rem !important;
       font-family: Montserrat, sans-serif !important;
       white-space: nowrap !important;
       transition: background 0.15s !important;
       letter-spacing: 0.01em !important;
   }}
   .stFileUploader button:hover {{
       background-color: #333333 !important;
   }}
   [data-testid="stFileUploaderDropzone"] {{
       border: 1.5px dashed #D0D0D0 !important;
       border-radius: 10px !important;
       background: #FAFAF9 !important;
       padding: 1.8rem 1rem !important;
   }}
   /* Tarjeta del archivo ya subido (nombre + tamaño): que no se encime con nada */
   [data-testid="stFileUploaderFile"] {{
       display: flex !important;
       align-items: center !important;
       gap: 8px !important;
       overflow: hidden !important;
   }}
   [data-testid="stFileUploaderFileName"] {{
       white-space: nowrap !important;
       overflow: hidden !important;
       text-overflow: ellipsis !important;
   }}


   /* --- SOLUCIÓN INTEGRAL AL CORTE DE BORDES EN INPUTS --- */
   .stTextInput input,
   .stTextInput input:focus {{
       border-radius: 24px !important;
       border: 1px solid #777777 !important;
       height: 48px !important;
       padding: 10px 20px !important;
       background-color: #FFFFFF !important;
       box-shadow: none !important;
       outline: none !important;
   }}
   .stTextInput div[data-baseweb="input"] {{
       background-color: transparent !important;
       border: none !important;
       padding: 0 !important;
       overflow: visible !important;
   }}
   .stTextInput > div {{
       overflow: visible !important;
       padding-bottom: 2px !important;
   }}
   .stTextInput label {{
       font-weight: 500 !important;
       color: #1A1A1A !important;
       font-size: 1.1rem !important;
       margin-bottom: 8px !important;
   }}
  
   /* Quitar el botón feo default de Streamlit en todas partes */
   .stButton > button {{
       border-radius: 8px !important;
       font-family: Montserrat, sans-serif !important;
       font-weight: 600 !important;
       font-size: 0.9rem !important;
       border: 1px solid #D0D0D0 !important;
       background: #FFFFFF !important;
       color: #1A1A1A !important;
       padding: 10px 20px !important;
       transition: background 0.15s, border-color 0.15s !important;
   }}
   .stButton > button:hover {{
       background: #F5F5F3 !important;
       border-color: #999 !important;
   }}

   /* Form container: quitar borde y padding de Streamlit */
   [data-testid="stForm"] {{
       border: none !important;
       padding: 0 !important;
       background: transparent !important;
   }}
   /* Botón submit del form */
   [data-testid="stFormSubmitButton"] > button {{
       background-color: #4A5D32 !important;
       color: #FFFFFF !important;
       border: none !important;
       width: 100% !important;
       height: 52px !important;
       margin-top: 1.2rem !important;
       font-size: 1rem !important;
       font-weight: 600 !important;
       font-family: Montserrat, sans-serif !important;
       letter-spacing: 0.01em !important;
       border-radius: 8px !important;
   }}
   [data-testid="stFormSubmitButton"] > button:hover {{
       background-color: #3a4a27 !important;
   }}

   .auth-redirect-text {{
       font-size: 0.9rem;
       color: #999999;
       margin-top: 2rem !important;
       margin-bottom: 0.5rem !important;
       text-align: center;
       font-family: Montserrat, sans-serif;
   }}

   /* --- BARRA LATERAL --- */
   [data-testid="stSidebar"] {{
       background-color: #FFFFFF !important;
       border-right: 0.5px solid #EAEAEA !important;
   }}
   [data-testid="stSidebar"] section[data-testid="stSidebarContent"] > div {{
       padding: 0 !important;
       gap: 0 !important;
   }}

   /* Hover en links de sidebar */
   [data-testid="stSidebar"] a:hover {{
       background: #F5F5F3 !important;
       color: #1A1A1A !important;
   }}

   /* --- IMAGEN DE LOGIN/REGISTRO: altura flexible, ya no se recorta --- */
   .auth-img-box {{
       width: 100%;
       min-height: 560px;
       height: 100%;
       background-size: cover;
       background-position: center;
       border-radius: 8px;
   }}
  
   /* --- CHAT DE HUGO: contenedor tipo tarjeta con marco (no de lado a lado) --- */
   .gemini-chat-container {{
       max-width: 760px;
       margin: 0 auto 1.25rem;
       padding: 1.5rem 1.75rem;
       border: 1px solid #EAEAEA;
       border-radius: 16px;
       background: #FFFFFF;
       box-shadow: 0 2px 10px rgba(0,0,0,0.04);
   }}
   .gemini-row {{
       display: flex;
       margin-bottom: 1.1rem;
   }}
   .gemini-row.gemini-row-user {{
       justify-content: flex-end;
   }}
   .gemini-row.gemini-row-hugo {{
       justify-content: flex-start;
   }}
   .gemini-bubble {{
       max-width: 80%;
   }}
   .gemini-bubble-user {{
       background: #EEF1E9;
       border-radius: 16px 16px 4px 16px;
       padding: 8px 14px;
   }}
   .gemini-bubble-hugo {{
       max-width: 100%;
   }}
   .gemini-user-label {{
       font-weight: 600;
       font-size: 0.72rem;
       color: #666666;
       margin-bottom: 3px;
       text-align: right;
   }}
   .gemini-hugo-label {{
       font-weight: 700;
       font-size: 0.78rem;
       color: #4A5D32;
       margin-bottom: 3px;
   }}
   .gemini-text {{
       font-size: 0.88rem;
       line-height: 1.45;
       color: #202124;
       white-space: pre-line;
   }}
  
   div[data-testid="stChatInput"] {{
       background-color: transparent !important;
       border: none !important;
       padding: 0 !important;
       overflow: visible !important;
   }}
   div[data-testid="stChatInput"] textarea {{
       border-radius: 24px !important;
       border: 1px solid #777777 !important;
       background-color: #FFFFFF !important;
       box-shadow: none !important;
   }}
   div[data-testid="stChatInput"] > div {{
       overflow: visible !important;
       padding-bottom: 2px !important;
   }}
</style>
""", unsafe_allow_html=True)




# =================================================================
# NAV BAR SUPERIOR (SOLO PÚBLICO)
# =================================================================
if not es_hub and not es_panel and st.session_state.page != "onboarding":
   _logo_nav = (
       f'<img src="data:image/png;base64,{logo_encoded}" style="max-height:28px;display:block;">'
       if logo_encoded else
       '<span style="font-size:15px;font-weight:600;color:#1A1A1A;letter-spacing:-0.03em;">uniwebmx</span>'
   )
   st.markdown(f"""
   <div style="display:flex;align-items:center;justify-content:space-between;padding:12px 0 10px;margin-bottom:0.5rem;">
       <div style="display:flex;align-items:center;gap:28px;">
           <a href="/?page=inicio" target="_self" style="text-decoration:none;">{_logo_nav}</a>
           <a href="/?page=ranking" target="_self" style="font-size:0.9rem;font-weight:500;color:#1A1A1A;text-decoration:none;">Ranking</a>
           <a href="/?page=blog" target="_self" style="font-size:0.9rem;font-weight:500;color:#1A1A1A;text-decoration:none;">Blog</a>
           <a href="#" style="font-size:0.9rem;font-weight:500;color:#1A1A1A;text-decoration:none;opacity:0.5;pointer-events:none;">Comunidad</a>
       </div>
       <div style="display:flex;align-items:center;gap:8px;">
           <a href="/?page=login" target="_self" style="text-decoration:none;font-family:Montserrat,sans-serif;font-size:0.85rem;font-weight:500;color:#1A1A1A;padding:7px 16px;border:0.5px solid #DCDCDC;border-radius:6px;white-space:nowrap;">Iniciar sesión</a>
           <a href="/?page=registro" target="_self" style="text-decoration:none;font-family:Montserrat,sans-serif;font-size:0.85rem;font-weight:500;color:#FFFFFF;padding:7px 16px;background:#4A5D32;border-radius:6px;white-space:nowrap;">Registrarse</a>
       </div>
   </div>
   """, unsafe_allow_html=True)




# =================================================================
# BARRA LATERAL
# =================================================================
if es_hub:
   _pg   = st.session_state.page
   _user = st.session_state.get("user", "")
   _sesion_t = st.session_state.get("session_token", "")
   _logo_sb = logo_encoded
   _logo_html = (
       f'<img src="data:image/png;base64,{_logo_sb}" style="width:100%;max-width:180px;display:block;">'
       if _logo_sb else
       '<span style="font-size:15px;font-weight:500;color:#1A1A1A;letter-spacing:-0.03em;">uniwebmx</span>'
   )

   def _sb_item(label, page_key, icon_path):
       is_active = _pg == page_key
       bg = "#EEF1E9" if is_active else "transparent"
       color = "#4A5D32" if is_active else "#666666"
       fw = "500" if is_active else "400"
       # IMPORTANTE: todo en una sola línea, sin saltos de línea ni indentación.
       # Un <a> multilínea puede romperse si queda junto a una línea en blanco
       # (p.ej. cuando otro item condicional se vuelve "" y deja una línea de
       # puros espacios), porque eso cierra el bloque de HTML de Markdown y el
       # resto se renderiza como texto/code literal en vez de HTML.
       return (f'<a href="/?nav={page_key}&t={_sesion_t}" target="_self" '
               f'style="display:flex;align-items:center;gap:10px;padding:8px 10px;margin:1px 0;'
               f'border-radius:6px;background:{bg};color:{color};font-family:Montserrat,sans-serif;'
               f'font-size:0.85rem;font-weight:{fw};text-decoration:none;cursor:pointer;'
               f'transition:background 0.1s;">'
               f'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
               f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
               f'style="flex-shrink:0;opacity:0.7;">{icon_path}</svg>{label}</a>')

   _icon_locker = '<path d="M5 8a3 3 0 0 1 3-3h8a3 3 0 0 1 3 3v11a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1z"/><path d="M10 11h4M12 9v4"/>'
   _icon_chat   = '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>'
   _icon_sim    = '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>'
   _icon_app    = '<path d="M3 7l9-4 9 4-9 4-9-4z"/><path d="M3 7v10l9 4 9-4V7"/><path d="M12 11v10"/>'
   _icon_msg    = '<path d="M4 4h16v12H7l-3 3z"/><path d="M7 9h10M7 12h6"/>'

   _label_style = "font-size:10px;letter-spacing:0.09em;text-transform:uppercase;color:#BBBBBB;padding:14px 10px 4px;margin:0;font-family:Montserrat,sans-serif;"

   with st.sidebar:
       _items_espacio = []
       if not es_usuario_menor():
           _items_espacio.append(_sb_item("Locker Digital", "locker", _icon_locker))
       _items_espacio.append(_sb_item("Consultor IA", "chat", _icon_chat))
       _items_espacio.append(_sb_item("Mi Aplicación", "mi_aplicacion", _icon_app))
       _items_espacio.append(_sb_item("Centro de Mensajes", "mensajes", _icon_msg))
       _html_items_espacio = "".join(_items_espacio)
       _html_items_analisis = _sb_item("Simulador", "simulador", _icon_sim)

       st.markdown(
           f'<div style="padding:20px 16px 14px;border-bottom:0.5px solid #EAEAEA;margin-bottom:6px;">{_logo_html}</div>'
           f'<p style="{_label_style}">Tu espacio</p>'
           f'<div style="padding:0 10px;">{_html_items_espacio}</div>'
           f'<p style="{_label_style}">Análisis</p>'
           f'<div style="padding:0 10px;">{_html_items_analisis}</div>'
           f'<div style="border-top:0.5px solid #EAEAEA;margin:12px 16px 8px;"></div>',
           unsafe_allow_html=True,
       )

       # --- Perfil fijo al fondo de la sidebar (menú emergente hacia arriba) ---
       _initials_sb = (_user[:2].upper()) if _user else "U"

       # --- Item: darse de baja de correos promocionales ---
       _consiente_promo_actual = st.session_state.get("consentimiento_promocional_actual", False)
       # En una sola línea (sin saltos internos) para que nunca dependa de que
       # una línea en blanco vecina no rompa el bloque de HTML.
       if _consiente_promo_actual:
           _baja_promo_item = (
               '<a href="/?nav=__baja_promocional__" target="_self" '
               'style="display:flex;align-items:center;gap:8px;padding:7px 10px;border-radius:6px;'
               'color:#555;font-family:Montserrat,sans-serif;font-size:0.82rem;font-weight:400;'
               'text-decoration:none;">'
               '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
               'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
               '<path d="M4 4h16v16H4z"/><path d="M22 6l-10 7L2 6"/><line x1="3" y1="21" x2="21" y2="3"/>'
               '</svg>Dejar de recibir promocionales</a>'
           )
       else:
           _baja_promo_item = (
               '<div style="padding:7px 10px;color:#AAA;font-family:Montserrat,sans-serif;'
               'font-size:0.76rem;">No recibes correos promocionales</div>'
           )

       # --- Item: eliminar cuenta ---
       _eliminar_cuenta_item = (
           '<a href="/?nav=__eliminar_cuenta__" target="_self" '
           'style="display:flex;align-items:center;gap:8px;padding:7px 10px;border-radius:6px;'
           'color:#C0392B;font-family:Montserrat,sans-serif;font-size:0.82rem;font-weight:500;'
           'text-decoration:none;">'
           '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
           'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
           '<polyline points="3 6 5 6 21 6"/>'
           '<path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>'
           '<path d="M10 11v6M14 11v6M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>'
           '</svg>Eliminar mi cuenta</a>'
       )

       with st.sidebar:
           st.markdown(f"""
           <style>
           /* Checkbox oculto como toggle — funciona sin JS en Streamlit */
           #profile-toggle {{ display: none; }}

           .profile-menu {{
               display: none;
               position: fixed;
               bottom: 62px;
               left: 8px;
               width: 236px;
               background: #fff;
               border: 1px solid #EAEAEA;
               border-radius: 12px;
               box-shadow: 0 -6px 28px rgba(0,0,0,0.12);
               z-index: 99999;
               padding: 6px 0;
               font-family: Montserrat, sans-serif;
           }}
           #profile-toggle:checked ~ .sidebar-bottom-bar .profile-menu {{
               display: block;
           }}
           .profile-menu-header {{
               padding: 12px 14px 10px;
               border-bottom: 0.5px solid #EAEAEA;
               margin-bottom: 4px;
           }}
           .sidebar-bottom-bar {{
               position: fixed;
               bottom: 0;
               left: 0;
               width: 252px;
               background: #fff;
               border-top: 0.5px solid #EAEAEA;
               padding: 10px 12px;
               z-index: 9998;
               box-sizing: border-box;
           }}
           .profile-btn {{
               display: flex;
               align-items: center;
               gap: 10px;
               padding: 4px 2px;
               cursor: pointer;
               user-select: none;
               width: 100%;
           }}
           .profile-chevron {{
               transition: transform 0.2s;
           }}
           #profile-toggle:checked ~ .sidebar-bottom-bar .profile-chevron {{
               transform: rotate(180deg);
           }}
           /* Overlay para cerrar al hacer click fuera */
           .profile-overlay {{
               display: none;
               position: fixed;
               inset: 0;
               z-index: 9997;
           }}
           #profile-toggle:checked ~ .profile-overlay {{
               display: block;
           }}
           </style>

           <input type="checkbox" id="profile-toggle">
           <label class="profile-overlay" for="profile-toggle"></label>

           <div class="sidebar-bottom-bar">
             <div class="profile-menu">
               <div class="profile-menu-header">
                 <div style="font-size:0.82rem;font-weight:600;color:#1A1A1A;
                     white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{_user}</div>
               </div>
               <a href="/?nav=__logout__" target="_self" style="display:flex;align-items:center;gap:9px;padding:8px 14px;color:#555;font-family:Montserrat,sans-serif;font-size:0.82rem;font-weight:400;text-decoration:none;"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
                 </svg>Cerrar sesión
               </a>
               <div style="border-top:0.5px solid #EAEAEA;margin:4px 0;padding-top:4px;">
                 {_baja_promo_item}
                 {_eliminar_cuenta_item}
               </div>
             </div>

             <label for="profile-toggle" class="profile-btn">
               <div style="width:32px;height:32px;border-radius:50%;background:#EEF1E9;
                   border:1px solid #C8D4B8;display:flex;align-items:center;justify-content:center;
                   font-size:0.72rem;font-weight:700;color:#4A5D32;flex-shrink:0;">
                 {_initials_sb}
               </div>
               <div style="flex:1;overflow:hidden;">
                 <div style="font-size:0.8rem;font-weight:600;color:#1A1A1A;
                     white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{_user}</div>
               </div>
               <svg class="profile-chevron" width="13" height="13" viewBox="0 0 24 24" fill="none"
                    stroke="#999" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                 <polyline points="18 15 12 9 6 15"/>
               </svg>
             </label>
           </div>
           """, unsafe_allow_html=True)

           # --- Darse de baja de correos promocionales (acción directa, sin confirmación) ---
           if st.session_state.pop("_ejecutar_baja_promocional_pendiente", False):
               try:
                   supabase_client.table("usuarios").update({"consentimiento_promocional": False}).eq("username", _user).execute()
                   st.session_state["consentimiento_promocional_actual"] = False
                   with st.sidebar:
                       st.markdown("""<div style="margin:0 4px;padding:10px 14px;background:#F0FFF4;
                           border:1px solid #C8D4B8;border-radius:10px;font-family:Montserrat,sans-serif;
                           font-size:0.8rem;color:#4A5D32;font-weight:500;">
                           ✓ Ya no recibirás correos promocionales.</div>""", unsafe_allow_html=True)
               except Exception as e:
                   with st.sidebar:
                       st.error(f"No se pudo actualizar: {e}")
                   _notificar_error_admin("baja de correos promocionales", e, extra=f"username={_user}")

           # --- Eliminar cuenta (dos pasos: confirmar y luego ejecutar) ---
           if st.session_state.pop("_confirmar_eliminacion", False):
               st.session_state["_mostrar_confirmar_eliminacion"] = True

           if st.session_state.get("_mostrar_confirmar_eliminacion"):
               with st.sidebar:
                   st.markdown("""
                   <div style="margin:0 4px;padding:12px 14px;background:#FFF5F5;border:1px solid #FECACA;
                       border-radius:10px;font-family:Montserrat,sans-serif;">
                     <div style="font-size:0.82rem;font-weight:600;color:#C0392B;margin-bottom:6px;">
                       ¿Eliminar tu cuenta?
                     </div>
                     <div style="font-size:0.78rem;color:#666;line-height:1.5;">
                       Esto borra tu cuenta, tu historial con Hugo, tus resultados del simulador y todo lo
                       demás que tengamos guardado de ti. No se puede deshacer.
                     </div>
                   </div>
                   """, unsafe_allow_html=True)
                   st.markdown("""
                   <style>
                   div[data-testid="stSidebarContent"] .eliminar-btns a {{
                       display:block;text-align:center;font-family:Montserrat,sans-serif;
                       font-size:0.82rem;font-weight:600;border-radius:8px;
                       padding:9px 0;text-decoration:none;margin-bottom:6px;
                   }}
                   </style>
                   <div class="eliminar-btns" style="margin:8px 4px 0;">
                   """, unsafe_allow_html=True)
                   col_si2, col_no2 = st.columns(2)
                   with col_si2:
                       st.markdown(
                           '<a href="/?nav=__ejecutar_eliminacion__" target="_self" '
                           'style="display:block;text-align:center;font-family:Montserrat,sans-serif;'
                           'font-size:0.8rem;font-weight:600;border-radius:8px;padding:9px 0;'
                           'text-decoration:none;background:#C0392B;color:#fff;">Sí, eliminar</a>',
                           unsafe_allow_html=True,
                       )
                   with col_no2:
                       st.markdown(
                           '<a href="/?nav=__descartar_accion_cuenta__" target="_self" '
                           'style="display:block;text-align:center;font-family:Montserrat,sans-serif;'
                           'font-size:0.8rem;font-weight:600;border-radius:8px;padding:9px 0;'
                           'text-decoration:none;background:#F5F5F3;color:#1A1A1A;border:1px solid #E0E0E0;">'
                           'No, conservar</a>',
                           unsafe_allow_html=True,
                       )
                   st.markdown("</div>", unsafe_allow_html=True)

           if st.session_state.pop("_ejecutar_eliminacion_pendiente", False):
               try:
                   # 1. Borrar todos sus datos.
                   supabase_client.table("datos_usuario").delete().eq("username", _user).execute()
                   try:
                       supabase_client.table("eventos_uso").delete().eq("username", _user).execute()
                   except Exception:
                       pass  # si la tabla no existe todavía, no pasa nada
                   supabase_client.table("usuarios").delete().eq("username", _user).execute()

                   # 2. Cerrar la sesión de verdad y mandarlo a una pantalla de despedida.
                   invalidar_sesion_token(_user)
                   st.session_state.clear()
                   st.session_state.page = "cuenta_eliminada"
                   st.rerun()
               except Exception as e:
                   _notificar_error_admin("eliminar cuenta", e, extra=f"username={_user}")
                   with st.sidebar:
                       st.error(f"No pudimos eliminar tu cuenta por completo: {e}. Escríbenos a hola@uniwebmx.com")



# =================================================================
# BARRA LATERAL DEL PANEL (admin / universidades) — totalmente separada
# del hub de alumnos. Nunca muestra Locker, Consultor IA de alumno,
# Mi Aplicación, Mensajes ni Simulador de alumno.
# =================================================================
if es_panel:
   _pg_panel = st.session_state.page
   _user_panel = st.session_state.get("user", "")
   _sesion_t_panel = st.session_state.get("session_token", "")
   _es_uni_panel = es_universidad()
   _label_style_panel = "font-size:10px;letter-spacing:0.09em;text-transform:uppercase;color:#BBBBBB;padding:14px 10px 4px;margin:0;font-family:Montserrat,sans-serif;"

   def _sb_item_panel(label, page_key, icon_path):
       is_active = _pg_panel == page_key
       bg = "#EEF1E9" if is_active else "transparent"
       color = "#4A5D32" if is_active else "#666666"
       fw = "500" if is_active else "400"
       # En una sola línea: evita que una línea en blanco vecina (p.ej. un item
       # condicional vacío) cierre el bloque de HTML y deje esto como texto crudo.
       return (f'<a href="/?nav={page_key}&t={_sesion_t_panel}" target="_self" '
               f'style="display:flex;align-items:center;gap:10px;padding:8px 10px;margin:1px 0;'
               f'border-radius:6px;background:{bg};color:{color};font-family:Montserrat,sans-serif;'
               f'font-size:0.85rem;font-weight:{fw};text-decoration:none;cursor:pointer;'
               f'transition:background 0.1s;">'
               f'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
               f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
               f'style="flex-shrink:0;opacity:0.7;">{icon_path}</svg>{label}</a>')

   _icon_resumen    = '<rect x="3" y="12" width="4" height="8"/><rect x="10" y="7" width="4" height="13"/><rect x="17" y="3" width="4" height="17"/>'
   _icon_chat_panel = '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>'
   _icon_sim_panel  = '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>'
   _icon_carreras   = '<path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c0 1.5 3 3 6 3s6-1.5 6-3v-5"/>'
   _icon_perfiles   = '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/>'
   _icon_consultor  = '<path d="M12 2a7 7 0 0 0-7 7c0 3 2 4 2 7h10c0-3 2-4 2-7a7 7 0 0 0-7-7z"/><path d="M9 21h6"/>'
   _icon_usuarios   = '<circle cx="9" cy="7" r="4"/><path d="M2 21c0-3.5 3-6 7-6s7 2.5 7 6"/><path d="M17 8a3 3 0 1 1 0 6"/><path d="M22 21c0-2.5-1.8-4.5-4.3-5.4"/>'

   with st.sidebar:
       if _es_uni_panel:
           st.markdown(f"""
           <div style="padding:20px 16px 14px;border-bottom:0.5px solid #EAEAEA;margin-bottom:6px;">
               <span style="font-size:15px;font-weight:600;color:#1A1A1A;letter-spacing:-0.03em;">uniwebmx</span>
               <div style="font-size:0.72rem;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;
                   color:#4A5D32;margin-top:2px;">Panel de la universidad</div>
           </div>
           <div style="padding:12px 10px 0;">
               {_sb_item_panel("Resumen", "panel_admin", _icon_resumen)}
               {_sb_item_panel("Carreras y perfiles", "panel_carreras_perfiles", _icon_carreras)}
               {_sb_item_panel("Hugo", "panel_consultor", _icon_consultor)}
           </div>
           <div style="border-top:0.5px solid #EAEAEA;margin:12px 16px 8px;"></div>
           """, unsafe_allow_html=True)
       else:
           st.markdown(f"""
           <div style="padding:20px 16px 14px;border-bottom:0.5px solid #EAEAEA;margin-bottom:6px;">
               <span style="font-size:15px;font-weight:600;color:#1A1A1A;letter-spacing:-0.03em;">uniwebmx</span>
               <div style="font-size:0.72rem;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;
                   color:#4A5D32;margin-top:2px;">Panel de administrador</div>
           </div>
           <p style="{_label_style_panel}">General</p>
           <div style="padding:0 10px;">
               {_sb_item_panel("Resumen", "panel_admin", _icon_resumen)}
           </div>
           <p style="{_label_style_panel}">Uso del producto</p>
           <div style="padding:0 10px;">
               {_sb_item_panel("Uso de Hugo (chat)", "panel_chat", _icon_chat_panel)}
               {_sb_item_panel("Simulador", "panel_simulador", _icon_sim_panel)}
           </div>
           <p style="{_label_style_panel}">Insights</p>
           <div style="padding:0 10px;">
               {_sb_item_panel("Carreras y universidades", "panel_carreras", _icon_carreras)}
               {_sb_item_panel("Perfiles por universidad", "panel_perfiles", _icon_perfiles)}
               {_sb_item_panel("Consultor Hugo", "panel_consultor", _icon_consultor)}
           </div>"""
           + (f'<p style="{_label_style_panel}">Administración</p>'
              f'<div style="padding:0 10px;">{_sb_item_panel("Usuarios y roles", "panel_usuarios", _icon_usuarios)}</div>'
              if es_admin() else "")
           + """
           <div style="border-top:0.5px solid #EAEAEA;margin:12px 16px 8px;"></div>
           """, unsafe_allow_html=True)

       st.markdown(f"""
       <div style="padding:0 10px;">
           <div style="padding:8px 10px;font-family:Montserrat,sans-serif;font-size:0.78rem;color:#999;">
               Sesión: <strong style="color:#444;">{_user_panel}</strong>
           </div>
           <a href="/?nav=__logout__" target="_self" style="display:flex;align-items:center;gap:8px;
               padding:8px 10px;border-radius:6px;color:#C0392B;font-family:Montserrat,sans-serif;
               font-size:0.85rem;font-weight:500;text-decoration:none;">
               <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                    stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                   <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
               </svg>Cerrar sesión</a>
       </div>
       """, unsafe_allow_html=True)

# =================================================================
# TOPBAR DEL HUB
# =================================================================
if es_hub:
   username = st.session_state.get("user", "")
   initials = (username[:2].upper()) if username else "U"
   col_top_left, col_top_right = st.columns([6, 2])
   with col_top_right:
       st.markdown(f"""
       <div style="display:flex; align-items:center; justify-content:flex-end; gap:10px; padding:6px 0 16px;">
           <div style="
               width: 30px; height: 30px;
               border-radius: 50%;
               background: #EEF1E9;
               border: 0.5px solid #C8D4B8;
               display: flex; align-items: center; justify-content: center;
               font-family: 'Montserrat', sans-serif;
               font-size: 0.65rem;
               font-weight: 600;
               color: #4A5D32;
               flex-shrink: 0;
           ">{initials}</div>
       </div>
       """, unsafe_allow_html=True)




# =================================================================
# CONTENIDO LEGAL: AVISO DE PRIVACIDAD Y TÉRMINOS Y CONDICIONES
# =================================================================
# NOTA INTERNA (no visible al usuario): estos textos fueron completados y
# revisados con ayuda de IA para cubrir los elementos que exige la LFPDPPP
# (identidad del responsable, finalidades primarias/secundarias, consentimiento
# de menores por doble opt-in, transferencias a terceros/internacionales,
# plazo de conservación, derechos ARCO). No sustituyen una revisión legal
# humana formal — se recomienda una revisión puntual y barata (clínica
# jurídica universitaria o abogado freelance por consulta única) más adelante,
# sobre todo antes de firmar el primer convenio con una universidad.

AVISO_PRIVACIDAD_MD = """
*Última actualización: julio de 2026.*

---

## 1. Identidad y domicilio del responsable

**Juan Pablo Kishi Gómez**, operando bajo el nombre comercial **Uniwebmx**, con domicilio en **Zapopan, Jalisco, México**, es responsable del tratamiento de tus datos personales conforme a lo establecido en la Ley Federal de Protección de Datos Personales en Posesión de los Particulares (LFPDPPP) y su Reglamento.

Para cualquier duda sobre este aviso, puedes contactarnos en: **info@uniwebmx.com**.

---

## 2. ¿Esto aplica a menores de edad?

**Sí.** Una parte importante de nuestros usuarios son estudiantes de bachillerato, muchos de ellos menores de 18 años. Por eso:

- Si eres **menor de edad**, el uso de Uniwebmx y el tratamiento de tus datos personales requiere el **consentimiento de tu padre, madre o tutor legal**, particularmente para las finalidades secundarias descritas en la Sección 6 (uso de tus datos para entrenar/mejorar a Hugo y para compartir tu información con universidades).
- Al registrarte como menor de edad, te pediremos el contacto de un padre/tutor. Ese contacto recibe un correo con un enlace de confirmación (doble verificación): mientras el padre/tutor no confirme desde ese enlace, **solo se procesarán tus datos para las finalidades primarias** indispensables para darte el servicio (Sección 5); las finalidades secundarias permanecen desactivadas.
- Al confirmar, el padre/madre/tutor decide, con casillas independientes, si autoriza cada finalidad secundaria (6.1, 6.2, 6.3) por separado.
- **El Locker Digital (almacenamiento permanente de documentos) no está disponible para cuentas de menores de edad mientras su padre, madre o tutor no haya confirmado la cuenta mediante el enlace de verificación.** Dado que ahí se guardan documentos especialmente sensibles (acta de nacimiento, CURP, identificación oficial, comprobante de domicilio), decidimos no almacenarlos de forma persistente hasta contar con esa confirmación. Una vez que el padre/madre/tutor confirma la cuenta, el Locker Digital queda disponible con normalidad, igual que para un usuario mayor de edad. Los alumnos menores de edad sí pueden usar con normalidad a Hugo y el Simulador Estadístico desde el registro, sin necesidad de esta confirmación.
- Un padre, madre o tutor puede en cualquier momento solicitar el acceso, corrección o eliminación de los datos de su hijo/a menor de edad, o revocar el consentimiento otorgado, escribiendo a **info@uniwebmx.com**.

---

## 3. Datos personales que recabamos

Dependiendo de cómo uses la plataforma, podemos recabar:

**Datos de identificación y contacto:**
- Nombre completo, edad, correo electrónico, nombre de usuario, contraseña (almacenada con hash, nunca en texto plano).

**Datos académicos y de tu proceso de admisión:**
- Kárdex/certificado de bachillerato, promedio, ensayo o carta de motivos, currículo, cartas de recomendación, universidades y carreras de tu interés.

**Documentos de identidad (Locker Digital):**
- Acta de nacimiento, CURP, identificación oficial, fotografía, comprobante de domicilio. Si tu cuenta está registrada como menor de edad, esta función queda disponible hasta que tu padre, madre o tutor confirme la cuenta mediante el enlace de verificación (ver Sección 2).

**Datos derivados del uso de la plataforma:**
- Conversaciones con Hugo (nuestro asesor con inteligencia artificial), resultados del simulador de probabilidades, historial de mensajes.

**Datos de correo electrónico (función opcional "Buscador de correos universitarios"):**
- Si decides usar esta función, te pediremos tu correo y contraseña de forma temporal, **únicamente** para conectarnos vía IMAP y buscar mensajes de universidades en tu bandeja. **No almacenamos tu contraseña de correo**; se usa solo durante esa sesión y se descarta al cerrarla. Solo guardamos los resultados de esa búsqueda (remitente, asunto, fecha, fragmento del cuerpo) si tú decides conservarlos.

---

## 4. ¿Cómo obtenemos tus datos?

- Directamente de ti, cuando te registras, llenas tu perfil, subes documentos o conversas con Hugo.
- De forma automática, a través de tu interacción con la plataforma (por ejemplo, los resultados que genera el simulador con base en lo que capturas).

---

## 5. Finalidades primarias (necesarias para darte el servicio)

Sin estas finalidades, no podemos ofrecerte Uniwebmx. **No están sujetas a consentimiento opcional** porque son indispensables para la relación que tienes con nosotros:

- Crear y administrar tu cuenta.
- Almacenar y mostrarte tus propios documentos (Locker Digital).
- Generar tus resultados del Simulador Estadístico.
- Procesar tus conversaciones con Hugo **dentro de tu propia sesión**, para darte retroalimentación personalizada.
- Enviarte correos operativos: confirmación de registro, recuperación de contraseña.
- Cumplir con obligaciones legales y atender requerimientos de autoridad.

---

## 6. Finalidades secundarias (requieren tu consentimiento expreso y son opcionales)

Estas finalidades **no son necesarias para que uses Uniwebmx** y por ley no podemos condicionar el servicio a que las aceptes. Tendrás casillas separadas, sin marcar por defecto, para decidir cada una de forma independiente:

### 6.1 Uso de tus datos para mejorar a Hugo
☐ *Acepto que mis interacciones con Hugo (incluyendo el contenido de mi kárdex y ensayo que comparto en el chat) se usen de forma agregada y/o anonimizada para mejorar la precisión y el entrenamiento del asistente de inteligencia artificial de Uniwebmx.*

Si no marcas esta casilla, tus conversaciones con Hugo se seguirán procesando normalmente para darte el servicio dentro de tu sesión (eso es finalidad primaria), pero **no se usarán para entrenar o mejorar el modelo más allá de tu propia conversación**.

### 6.2 Compartir tu información con universidades
☐ *Acepto que Uniwebmx comparta mi información de perfil y/o mis documentos académicos con las universidades que yo mismo seleccione como de mi interés, con el fin de facilitar mi proceso de admisión.*

Si no marcas esta casilla, tu información **no se comparte con ninguna universidad ni tercero** — solo tú puedes verla y descargarla.

### 6.3 Comunicación promocional
☐ *Acepto recibir correos sobre nuevas funciones, becas, fechas de convocatorias y contenido educativo de Uniwebmx.*

---

## 7. Transferencia de datos a terceros

Compartimos datos únicamente en estos casos:

| Tercero | Qué datos | Para qué |
|---|---|---|
| **Supabase** | Toda tu información almacenada | Es nuestro proveedor de base de datos e infraestructura (almacenamiento técnico, no usan tus datos con fines propios) |
| **Google (Gemini API)** | Tus mensajes a Hugo y el contexto que envías (kárdex, ensayo, perfil) | Generar las respuestas de Hugo |
| **Resend** | Tu correo electrónico | Enviarte correos transaccionales |
| **Universidades de tu interés** | Solo si diste tu consentimiento explícito en la Sección 6.2 | Facilitar tu proceso de admisión |

No vendemos tus datos personales a nadie, bajo ninguna circunstancia.

**Transferencia internacional de datos:** Supabase y Google (Gemini API) almacenan y procesan información en servidores que pueden estar ubicados fuera de México. Esto implica una transferencia internacional de tus datos personales, necesaria para poder prestarte el servicio (finalidad primaria). Estos proveedores actúan como encargados del tratamiento bajo sus propias políticas de seguridad y no están autorizados a usar tus datos para fines distintos a los aquí descritos.

---

## 8. Derechos ARCO y revocación del consentimiento

Tienes derecho a **Acceder, Rectificar, Cancelar u Oponerte** (derechos ARCO) al tratamiento de tus datos personales, así como a **revocar el consentimiento** que hayas otorgado para las finalidades secundarias en cualquier momento.

Para ejercer estos derechos, envía tu solicitud a **info@uniwebmx.com** incluyendo:
1. Tu nombre completo y el correo asociado a tu cuenta.
2. Una descripción clara de tu solicitud.
3. Si actúas en representación de un menor de edad, documento que acredite tu calidad de padre/madre/tutor.

Responderemos en un plazo máximo de 20 días hábiles, conforme establece la LFPDPPP.

Puedes revocar el consentimiento de las finalidades secundarias (6.1, 6.2, 6.3) en cualquier momento desde tu perfil, sin que esto afecte el uso del resto de la plataforma.

---

## 9. Seguridad de tus datos

- Tus contraseñas se almacenan con hash (bcrypt), nunca en texto plano.
- Implementamos bloqueo temporal de cuenta tras intentos fallidos de inicio de sesión repetidos.
- Las sesiones se manejan con tokens aleatorios no adivinables, con expiración.

**Plazo de conservación:** conservamos tus datos personales mientras mantengas una cuenta activa en la Plataforma. Si solicitas la eliminación de tu cuenta, eliminaremos o anonimizaremos tus datos personales en un plazo razonable, salvo que exista una obligación legal de conservarlos por más tiempo.

---

## 10. Uso de cookies y tecnologías similares

Por el momento, Uniwebmx únicamente utiliza las cookies técnicas de sesión necesarias para que la plataforma funcione (por ejemplo, para mantener tu sesión iniciada). **Actualmente no usamos herramientas de analítica como Google Analytics ni cookies de publicidad o rastreo de terceros.** Si en el futuro decidimos incorporar herramientas de analítica para entender el uso de la plataforma, actualizaremos esta sección antes de activarlas y, de ser necesario, te lo notificaremos conforme a la Sección 11.

---

## 11. Cambios a este aviso

Cualquier modificación a este Aviso de Privacidad será publicada en esta misma página, indicando la fecha de la última actualización. Si los cambios afectan las finalidades secundarias, te pediremos tu consentimiento nuevamente.

---

## 12. Contacto

**Uniwebmx** (Juan Pablo Kishi Gómez)
Correo: **info@uniwebmx.com**
Zapopan, Jalisco, México
"""

TERMINOS_MD = """
*Última actualización: julio de 2026.*

---

## 1. Aceptación de los términos

Al crear una cuenta o usar Uniwebmx (la "Plataforma"), aceptas estos Términos y Condiciones y el Aviso de Privacidad. Si no estás de acuerdo, no debes usar la Plataforma.

Si eres **menor de edad**, el uso de la Plataforma requiere el consentimiento de tu padre, madre o tutor legal, conforme se detalla en el Aviso de Privacidad.

---

## 2. ¿Qué es Uniwebmx?

Uniwebmx es una plataforma que ofrece herramientas para apoyar tu proceso de admisión a universidades en México, incluyendo:

- **Locker Digital**: almacenamiento de tus documentos académicos y personales.
- **Hugo**: un asesor de admisiones impulsado por inteligencia artificial (Gemini, de Google).
- **Simulador Estadístico**: una estimación de tus probabilidades de aceptación con base en datos de referencia.
- Funciones complementarias como el buscador de correos universitarios.

---

## 3. Naturaleza de Hugo y del Simulador — qué sí y qué no debes esperar

Esto es importante y lo dejamos explícito para que no haya malentendidos:

- **Hugo es un asistente de inteligencia artificial**, no un consejero humano certificado ni un representante de ninguna universidad. Sus respuestas se basan en la información que tú compartes y en una base de conocimiento que procuramos mantener actualizada, pero **puede cometer errores**.
- **El Simulador Estadístico ofrece estimaciones**, no garantías de admisión. Las probabilidades mostradas se basan en datos históricos y de referencia (algunos oficiales, otros estimados — esto se indica en cada resultado) y **no constituyen una promesa de aceptación a ninguna universidad**.
- Te recomendamos siempre **verificar la información crítica** (fechas límite, requisitos exactos, puntajes de corte) directamente en las fuentes oficiales de cada universidad antes de tomar decisiones importantes.
- Uniwebmx no es una universidad, no toma decisiones de admisión y no tiene ninguna relación oficial con las instituciones educativas mencionadas en la Plataforma, salvo que se indique expresamente lo contrario (por ejemplo, mediante un convenio formal).

---

## 4. Cuentas de usuario

- Debes proporcionar información veraz al registrarte.
- Eres responsable de mantener la confidencialidad de tu contraseña.
- Una cuenta es personal e intransferible.
- Nos reservamos el derecho de suspender cuentas que detectemos con actividad fraudulenta, abuso de la Plataforma, o uso indebido del asistente Hugo (por ejemplo, intentos de manipular el sistema para obtener información fuera del propósito de la Plataforma).

---

## 5. Uso gratuito de la Plataforma

- Uniwebmx es gratuito para los alumnos: no existen planes de pago ni suscripciones.
- Uniwebmx genera ingresos a través de acuerdos con universidades, a las que puede compartir información de alumnos que hayan dado su consentimiento expreso conforme a la Sección 6.2 del Aviso de Privacidad (Sección 7 de estos Términos). No se te cobra nada por usar la Plataforma ni por esta funcionalidad.
- Nos reservamos el derecho de introducir en el futuro funciones adicionales o modelos de negocio distintos; de hacerlo, actualizaremos estos Términos con anticipación razonable conforme a la Sección 13.

---

## 6. Uso de tus datos por inteligencia artificial

- Las funciones de Hugo y del Simulador utilizan modelos de IA de terceros (Google Gemini) para procesar la información que tú proporcionas (incluyendo el contenido de tu kárdex y ensayo, si decides compartirlos en el chat).
- El uso de tus datos para mejorar/entrenar al asistente más allá de tu propia sesión **es opcional** y depende del consentimiento que otorgues conforme al Aviso de Privacidad (Sección 6.1).
- No debes compartir con Hugo información sensible de terceros (por ejemplo, datos de otras personas) sin su consentimiento.

---

## 7. Compartir información con universidades

Uniwebmx **no comparte tu información con universidades a menos que tú (o tu padre/tutor, si eres menor de edad) lo autorices explícitamente** conforme a la Sección 6.2 del Aviso de Privacidad. Si en el futuro Uniwebmx establece convenios formales con universidades o instituciones educativas para facilitar procesos de admisión, dichos convenios y el alcance exacto del intercambio de datos serán comunicados de forma clara antes de que se active cualquier intercambio.

---

## 8. Propiedad intelectual

- El contenido, diseño, marca y software de Uniwebmx son propiedad de **Juan Pablo Kishi Gómez** o de sus licenciantes.
- Los documentos que subas (kárdex, ensayo, identificaciones, etc.) siguen siendo de tu propiedad; nos das una licencia limitada para almacenarlos y procesarlos únicamente con el fin de prestarte el servicio, conforme al Aviso de Privacidad.

---

## 9. Conducta del usuario

Al usar la Plataforma, te comprometes a no:

- Subir documentos falsos o de terceros sin autorización.
- Usar Hugo para obtener o generar contenido fuera del propósito educativo de la Plataforma.
- Intentar vulnerar la seguridad de la Plataforma o acceder a cuentas de otros usuarios.
- Usar la Plataforma con fines ilegales.

---

## 10. Limitación de responsabilidad

- Uniwebmx se ofrece "tal cual" y "según disponibilidad". No garantizamos que el servicio esté libre de errores o interrupciones.
- **No somos responsables** por decisiones de admisión tomadas por universidades, ni por errores u omisiones en datos de referencia marcados como "estimados" en el Simulador o en las respuestas de Hugo.
- En la máxima medida permitida por la ley, la responsabilidad total de Uniwebmx frente a un usuario se limita al monto pagado por dicho usuario en los últimos 12 meses.
- Nada en esta sección limita responsabilidades que no puedan limitarse conforme a la legislación mexicana aplicable.

---

## 11. Menores de edad

El uso de la Plataforma por menores de edad está sujeto al consentimiento de su padre, madre o tutor legal, conforme se detalla en el Aviso de Privacidad. Ese consentimiento se verifica mediante un enlace de confirmación enviado al correo del padre/madre/tutor; mientras no se confirme, las funciones que impliquen el tratamiento de datos sensibles o su transferencia a terceros permanecen desactivadas. Esto incluye al Locker Digital (almacenamiento permanente de documentos de identidad): no está disponible para cuentas registradas como menores de edad hasta que su padre, madre o tutor confirme la cuenta mediante ese enlace; a partir de ese momento, el Locker Digital queda disponible con normalidad.

---

## 12. Terminación

Puedes dejar de usar la Plataforma y solicitar la eliminación de tu cuenta en cualquier momento. Nos reservamos el derecho de suspender o terminar cuentas que incumplan estos Términos, notificándolo cuando sea razonablemente posible.

---

## 13. Modificaciones a estos Términos

Podemos actualizar estos Términos. Te notificaremos los cambios relevantes y, en su caso, te pediremos aceptarlos nuevamente para continuar usando la Plataforma.

---

## 14. Ley aplicable y jurisdicción

Estos Términos se rigen por las leyes de los Estados Unidos Mexicanos. Para cualquier controversia, las partes se someten a los tribunales competentes de **Zapopan, Jalisco**, renunciando a cualquier otro fuero que pudiera corresponderles.

---

## 15. Contacto

**Uniwebmx** (Juan Pablo Kishi Gómez)
Correo: **info@uniwebmx.com**
"""


# =================================================================
# DATOS Y ANÁLISIS DEL PANEL (admin / universidades)
# =================================================================

@st.cache_data(ttl=300, show_spinner=False)
def _panel_cargar_datos_crudos():
    """Trae todos los alumnos + sus datos de uso (chat, simulador, perfil).
    Cacheado 5 min para no golpear Supabase en cada click del panel."""
    try:
        res_usuarios = supabase_client.table("usuarios").select(
            "username, email, plan, edad, es_menor_edad, rol, universidad_asignada, "
            "consentimiento_universidades, consentimiento_hugo, created_at"
        ).execute()
        usuarios_rows = res_usuarios.data or []
    except Exception:
        usuarios_rows = []
    try:
        res_datos = supabase_client.table("datos_usuario").select("username, datos, updated_at").execute()
        datos_rows = res_datos.data or []
    except Exception:
        datos_rows = []

    datos_por_usuario = {r["username"]: r for r in datos_rows}
    filas = []
    for u in usuarios_rows:
        _reg = datos_por_usuario.get(u["username"], {})
        d = _reg.get("datos") or {}
        filas.append({
            "username": u["username"],
            "email": u.get("email", "") or "",
            "plan": u.get("plan", "gratis") or "gratis",
            "edad": u.get("edad"),
            "es_menor_edad": bool(u.get("es_menor_edad", False)),
            "rol": u.get("rol", "alumno") or "alumno",
            "universidad_asignada": u.get("universidad_asignada") or "",
            "consentimiento_universidades": bool(u.get("consentimiento_universidades", False)),
            "consentimiento_hugo": bool(u.get("consentimiento_hugo", False)),
            "creado": u.get("created_at"),
            "historial_chat": d.get("historial_chat", []) or [],
            "contador_consultas": d.get("contador_consultas", 0) or 0,
            "simulador_usado": bool(d.get("simulador_usado", False)),
            "resultados_simulador": d.get("resultados_simulador") or {},
            "unis_seleccionadas": d.get("unis_seleccionadas", []) or [],
            "perfil_completo": bool(d.get("perfil_completo", False)),
            "perfil_edad": d.get("perfil_edad"),
            "perfil_carreras": d.get("perfil_carreras", []) or [],
            "perfil_universidades_interes": d.get("perfil_universidades_interes", []) or [],
            "perfil_preparatoria": d.get("perfil_preparatoria") or "",
            "actualizado": _reg.get("updated_at"),
        })
    return pd.DataFrame(filas)


def _panel_dataframe_alumnos():
    """DataFrame de alumnos, filtrado según quién está viendo el panel:
    - admin: ve a todos los alumnos.
    - universidad: SOLO ve alumnos que la seleccionaron como de interés Y dieron
      consentimiento explícito para compartir su info con universidades."""
    df = _panel_cargar_datos_crudos()
    if df.empty:
        return df
    df = df[df["rol"] == "alumno"].copy()
    if es_universidad():
        uni = st.session_state.get("universidad_asignada", "")
        if not uni:
            return df.iloc[0:0]
        def _le_interesa(row):
            return bool(row["consentimiento_universidades"]) and (
                uni in (row["unis_seleccionadas"] or []) or uni in (row["perfil_universidades_interes"] or [])
            )
        df = df[df.apply(_le_interesa, axis=1)]
    return df


def _panel_contar_frecuencias(df, columna):
    """Cuenta frecuencias de listas (perfil_carreras, unis_seleccionadas, etc.)."""
    contador = {}
    for lista in df[columna]:
        for item in (lista or []):
            item = (item or "").strip()
            if item:
                contador[item] = contador.get(item, 0) + 1
    return dict(sorted(contador.items(), key=lambda x: x[1], reverse=True))


def _panel_contar_frecuencias_simple(df, columna):
    """Cuenta frecuencias de un campo de texto simple (no lista), como perfil_preparatoria."""
    contador = {}
    for valor in df[columna]:
        valor = (valor or "").strip()
        if valor:
            contador[valor] = contador.get(valor, 0) + 1
    return dict(sorted(contador.items(), key=lambda x: x[1], reverse=True))


def _panel_universidades_de_interes(df):
    """Unión de unis_seleccionadas + perfil_universidades_interes por alumno (sin duplicar)."""
    contador = {}
    for _, row in df.iterrows():
        unis = set((row["unis_seleccionadas"] or [])) | set((row["perfil_universidades_interes"] or []))
        for uni in unis:
            uni = (uni or "").strip()
            if uni:
                contador[uni] = contador.get(uni, 0) + 1
    return dict(sorted(contador.items(), key=lambda x: x[1], reverse=True))


def _panel_alumnos_de_universidad(df, nombre_uni):
    """Sub-dataframe de alumnos interesados en una universidad específica."""
    def _interesado(row):
        return nombre_uni in (row["unis_seleccionadas"] or []) or nombre_uni in (row["perfil_universidades_interes"] or [])
    return df[df.apply(_interesado, axis=1)]


def _panel_generar_perfil_universidad_ia(nombre_uni, sub_df):
    """Le pide a Hugo (Gemini) que describa, en agregado y de forma anónima, qué tipo
    de alumnos aplican a esta universidad y por qué — sin exponer nombres ni datos
    identificables, solo patrones estadísticos."""
    if sub_df.empty:
        return "Todavía no hay suficientes alumnos interesados en esta universidad para generar un análisis."

    edades = [e for e in sub_df["perfil_edad"].tolist() if isinstance(e, (int, float))]
    carreras_contador = _panel_contar_frecuencias(sub_df, "perfil_carreras")
    top_carreras = ", ".join(f"{c} ({n})" for c, n in list(carreras_contador.items())[:8]) or "no especificadas"
    prepas_contador = _panel_contar_frecuencias_simple(sub_df, "perfil_preparatoria")
    top_prepas = ", ".join(f"{p} ({n})" for p, n in list(prepas_contador.items())[:8]) or "no especificadas"
    n_total = len(sub_df)
    n_simulador = int(sub_df["simulador_usado"].sum())
    promedios = []
    for res in sub_df["resultados_simulador"]:
        info = (res or {}).get(nombre_uni)
        if isinstance(info, dict) and info.get("prob_final") is not None:
            promedios.append(info["prob_final"])
    prob_promedio = round(sum(promedios) / len(promedios), 1) if promedios else None

    resumen_stats = (
        f"Universidad: {nombre_uni}\n"
        f"Alumnos interesados en la plataforma: {n_total}\n"
        f"Edad promedio: {round(sum(edades)/len(edades),1) if edades else 'sin dato'}\n"
        f"Carreras de interés más comunes entre ellos: {top_carreras}\n"
        f"Preparatorias de origen más comunes entre ellos: {top_prepas}\n"
        f"Usaron el simulador de admisión: {n_simulador} de {n_total}\n"
        f"Probabilidad de admisión estimada promedio (simulador): "
        f"{prob_promedio if prob_promedio is not None else 'sin dato suficiente'}%"
    )

    try:
        model = genai.GenerativeModel(
            "gemini-2.5-flash",
            system_instruction=(
                "Eres Hugo, analizando datos agregados y anónimos de una plataforma de "
                "orientación universitaria para describirle a un equipo de admisiones (o al equipo "
                "interno de Uniwebmx) qué tipo de perfil de alumno está aplicando a una universidad "
                "específica. NUNCA inventes nombres ni datos individuales: trabaja solo con los "
                "agregados que se te dan. Responde en español, en un párrafo de 4-6 líneas, tono "
                "profesional y directo, tipo 'insight de negocio': qué perfil predomina, qué "
                "carreras buscan y por qué crees (con base en los datos) que eligen esta "
                "universidad. Si los datos son insuficientes para algo, dilo brevemente en vez de "
                "inventar. No uses emojis."
            ),
        )
        respuesta = model.generate_content(resumen_stats)
        return _quitar_emojis(respuesta.text)
    except Exception as e:
        return f"No se pudo generar el análisis con Hugo en este momento ({e})."


def _panel_render_bloque_perfil_ia(_uni, _df_panel, expanded=True):
    """Renderiza el bloque expandible de 'análisis de perfil con Hugo' para una
    universidad específica. Reutilizado tanto en el panel de admin (una vez por
    universidad) como en el panel de universidad (una sola vez, para la suya)."""
    _sub = _panel_alumnos_de_universidad(_df_panel, _uni)
    with st.expander(f"{_uni}  ·  {len(_sub)} alumno(s) interesado(s)", expanded=expanded):
        if _sub.empty:
            st.caption("Todavía no hay alumnos interesados en esta universidad en este alcance.")
            return
        _clave_cache = f"panel_perfil_ia_{_uni}_{len(_sub)}"
        col_btn, _ = st.columns([1, 3])
        with col_btn:
            _generar = st.button("Generar análisis con Hugo", key=f"btn_{_clave_cache}")
        if _generar or _clave_cache in st.session_state:
            if _generar:
                with st.spinner("Hugo está analizando el perfil..."):
                    st.session_state[_clave_cache] = _panel_generar_perfil_universidad_ia(_uni, _sub)
            st.markdown(f"""<div style="background:#F5F5F3;border-radius:10px;padding:14px 18px;
                font-size:0.9rem;color:#333;line-height:1.6;margin-top:0.5rem;">
                <strong style="color:#4A5D32;">Hugo dice:</strong> {st.session_state.get(_clave_cache, "")}
                </div>""", unsafe_allow_html=True)
            _texto_descarga = (
                f"Perfil de alumnos interesados en {_uni} — Uniwebmx\n"
                f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"Alumnos analizados: {len(_sub)}\n\n"
                f"{st.session_state.get(_clave_cache, '')}\n"
            )
            st.download_button(
                "Descargar este análisis (.txt)",
                data=_texto_descarga.encode("utf-8"),
                file_name=f"perfil_{_uni.replace(' ', '_')}.txt",
                mime="text/plain",
                key=f"dl_{_clave_cache}",
            )
        else:
            st.caption("Da clic para que Hugo te resuma el perfil típico de quienes aplican aquí.")


def _panel_responder_consultor(pregunta, df, historial):
    """Chat de 'Hugo consultor' para el panel: responde preguntas sobre los datos
    agregados y filtrados que le corresponde ver a quien está en sesión (admin ve todo,
    universidad solo lo suyo)."""
    top_carreras = _panel_contar_frecuencias(df, "perfil_carreras")
    top_unis = _panel_universidades_de_interes(df)
    total_mensajes = sum(
        1 for h in df["historial_chat"] for m in (h or []) if m.get("role") == "user"
    )
    contexto = (
        f"Alcance de estos datos: {'TODA la plataforma (vista de administrador)' if es_admin() else 'solo alumnos interesados en ' + rol_universidad_nombre()}\n"
        f"Total de alumnos en este alcance: {len(df)}\n"
        f"Perfil completo: {int(df['perfil_completo'].sum())}\n"
        f"Usaron el simulador: {int(df['simulador_usado'].sum())}\n"
        f"Mensajes totales enviados a Hugo: {total_mensajes}\n"
        f"Top carreras de interés: {list(top_carreras.items())[:10]}\n"
        f"Top universidades de interés: {list(top_unis.items())[:10]}\n"
    )
    historial_gemini = [
        {"role": ("user" if m["role"] == "user" else "model"), "parts": [m["content"]]}
        for m in historial
    ]
    try:
        model = genai.GenerativeModel(
            "gemini-2.5-flash",
            system_instruction=(
                "Eres Hugo, pero ahora en modo 'consultor de datos' para el equipo interno de "
                "Uniwebmx o para una universidad socia. Te dan estadísticas agregadas y anónimas "
                "de uso de la plataforma; tu trabajo es ayudar a interpretarlas, encontrar patrones "
                "y sugerir acciones. Responde en español, de forma concisa y concreta. Si te "
                "preguntan algo que no puedes saber con estos datos (por ejemplo información "
                "individual de un alumno específico), dilo claramente en vez de inventar. No uses "
                "emojis en tus respuestas.\n\n"
                f"[DATOS DISPONIBLES]\n{contexto}"
            ),
        )
        chat = model.start_chat(history=historial_gemini[:-1])
        respuesta = chat.send_message(pregunta)
        return _quitar_emojis(respuesta.text)
    except Exception as e:
        return f"No pude procesar tu pregunta en este momento ({e})."


@st.cache_data(ttl=300, show_spinner=False)
def _panel_cargar_eventos(dias=30):
    """Trae los eventos de los últimos N días desde eventos_uso. Si la tabla
    todavía no existe (no has corrido el SQL), regresa un DataFrame vacío en
    vez de tronar el Panel."""
    try:
        _desde = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()
        res = supabase_client.table("eventos_uso").select("username, tipo_evento, creado_en").gte("creado_en", _desde).execute()
        df = pd.DataFrame(res.data or [])
        if not df.empty:
            df["fecha"] = pd.to_datetime(df["creado_en"]).dt.date
        return df
    except Exception:
        return pd.DataFrame()


def _panel_serie_diaria(df_eventos, tipo_evento, usernames_permitidos=None):
    """Serie de conteo diario para un tipo de evento, opcionalmente filtrada a
    un conjunto de usernames (para el alcance de una cuenta 'universidad')."""
    if df_eventos.empty:
        return pd.DataFrame(columns=["Fecha", "Eventos"]).set_index("Fecha")
    df = df_eventos[df_eventos["tipo_evento"] == tipo_evento]
    if usernames_permitidos is not None:
        df = df[df["username"].isin(usernames_permitidos)]
    if df.empty:
        return pd.DataFrame(columns=["Fecha", "Eventos"]).set_index("Fecha")
    serie = df.groupby("fecha").size().reset_index(name="Eventos").rename(columns={"fecha": "Fecha"})
    return serie.set_index("Fecha")


def rol_universidad_nombre():
    return st.session_state.get("universidad_asignada", "") or "tu universidad"


# --- REGISTRO DE EVENTOS (para ver tendencias en el Panel) ---
# Requiere en Supabase una tabla nueva:
#   create table eventos_uso (
#       id bigint generated always as identity primary key,
#       username text,
#       tipo_evento text not null,
#       detalle jsonb,
#       creado_en timestamptz not null default now()
#   );
# Tipos de evento que se registran: 'registro', 'login', 'mensaje_chat',
# 'simulador_usado'.
def _log_evento(username, tipo_evento, detalle=None):
    """Guarda un evento con fecha/hora. Nunca debe tumbar la app si falla:
    si la tabla no existe todavía (no has corrido el SQL de arriba) o hay
    un problema de red, simplemente no se registra ese evento."""
    try:
        supabase_client.table("eventos_uso").insert({
            "username": username,
            "tipo_evento": tipo_evento,
            "detalle": detalle or {},
        }).execute()
    except Exception:
        pass


def _panel_header(titulo, subtitulo=""):
    st.markdown(f"""
    <div style="padding-top:1.5rem;margin-bottom:1.5rem;">
        <h1 style="font-size:1.8rem;font-weight:700;color:#1A1A1A;letter-spacing:-0.02em;margin-bottom:0.2rem;">{titulo}</h1>
        {f'<p style="font-size:0.9rem;color:#888;">{subtitulo}</p>' if subtitulo else ''}
    </div>
    """, unsafe_allow_html=True)


# =================================================================
# VISTAS DEL SISTEMA
# =================================================================


# --- VISTA: INICIO ---
if st.session_state.page == "inicio":
   st.markdown("""
   <div class="hero-section-inicio">
       <h1 style='font-size: 3.5rem; margin-bottom: 1.5rem; max-width: 900px; margin-left: auto; margin-right: auto;'>Simplifica tu aplicación universitaria en un solo lugar.</h1>
       <p style='font-size: 1.35rem; color: #1A1A1A; max-width: 850px; margin: 0 auto; line-height: 1.6; font-weight: 400; opacity: 0.9;'>
           Una plataforma inteligente diseñada para guiarte en tu ingreso a las mejores instituciones de México.
           Controla tus documentos, mide tus posibilidades y redacta perfiles de éxito con asistencia experta.
       </p>
       <a href="/?page=login" target="_self" class="hero-green-btn">Comienza tu viaje</a>
   </div>
   """, unsafe_allow_html=True)
  
   st.markdown("<h2 style='text-align: center; margin-top: 1rem; margin-bottom: 2.5rem;'>Herramientas diseñadas para tu admisión</h2>", unsafe_allow_html=True)

   # --- CARRUSEL CONTINUO ---
   # Cada tarjeta usa la foto real servida por URL desde Supabase Storage
   # (ya no base64 local). Si el archivo aún no está subido al bucket, la
   # imagen del navegador simplemente no carga y cae al degradado de color
   # vía el atributo onerror, para que la página nunca se rompa por una
   # imagen faltante.
   _carrusel_slides = [
       ("Locker digital", "Kárdex, ensayos y diplomas en un solo lugar.", carrusel_locker_url, "linear-gradient(135deg,#5C6B4A,#7C8A6A)"),
       ("Consultor IA", "Retroalimentación en tiempo real de Hugo.", carrusel_consultor_url, "linear-gradient(135deg,#6B5D3F,#8C7B54)"),
       ("Simulador estadístico", "Tus probabilidades reales de aceptación.", carrusel_simulador_url, "linear-gradient(135deg,#4A5A5C,#6B8083)"),
   ]

   def _uw_slide_html(titulo, desc, img_url, fallback_bg):
       # Usamos background-image por CSS (no <img> con onerror) porque
       # Streamlit puede sanear atributos onXXX aunque unsafe_allow_html
       # esté activo, dejando visible el ícono de "imagen rota" si la URL
       # falla. Con background-image, si la foto no carga, simplemente no
       # se ve nada y queda el degradado de color de abajo, sin ícono raro.
       return (
           f'<div class="uw-slide" '
           f'style="background-image:url(\'{img_url}\'), {fallback_bg};'
           f'background-size:cover;background-position:center;">'
           f'<div class="uw-slide-overlay"></div>'
           f'<div class="uw-slide-text">'
           f'<div style="font-size:15px;font-weight:600;color:#fff;margin-bottom:4px;">{titulo}</div>'
           f'<div style="font-size:12px;color:rgba(255,255,255,0.85);line-height:1.5;">{desc}</div>'
           f'</div></div>'
       )



   _uw_slides_html = "".join(_uw_slide_html(*s) for s in _carrusel_slides) * 2  # x2 para el loop continuo

   st.markdown(
       f'<div class="uw-carrusel-viewport"><div class="uw-carrusel-track">{_uw_slides_html}</div></div>'
       f'<div style="text-align:center;font-size:11px;color:#999;margin-top:14px;">pasa el mouse encima para pausar</div>',
       unsafe_allow_html=True,
   )




   # --- SECCIÓN ADICIONAL: QUIÉNES SOMOS Y MISIÓN ---
   st.markdown('<div class="divider-olivo"></div>', unsafe_allow_html=True)
   col_qs, col_ms = st.columns(2, gap="large")
   with col_qs:
       st.markdown("""
       <div class="uw-somos-icon">
           <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#4A5D32" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
               <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
           </svg>
       </div>
       <h2>Quiénes Somos</h2>
       """, unsafe_allow_html=True)
       st.markdown("""
       <p style='color: #444444; line-height: 1.7; font-size: 1.05rem;'>
           Somos un equipo interdisciplinario apasionado por democratizar y optimizar el acceso a la educación superior en México.
           Creamos tecnología con un enfoque humano para dotar a los estudiantes de herramientas de análisis y edición que antes eran exclusivas de consultorías privadas.
       </p>
       """, unsafe_allow_html=True)
   with col_ms:
       st.markdown("""
       <div class="uw-somos-icon">
           <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#4A5D32" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
               <circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>
           </svg>
       </div>
       <h2>Nuestra Misión</h2>
       """, unsafe_allow_html=True)
       st.markdown("""
       <p style='color: #444444; line-height: 1.7; font-size: 1.05rem;'>
           Transformar los procesos de admisión universitaria en experiencias claras, organizadas y equitativas.
           Buscamos potenciar las capacidades de cada aspirante, ayudándoles a estructurar sus logros y perfiles para maximizar su aceptación en las instituciones de sus sueños.
       </p>
       """, unsafe_allow_html=True)




# --- VISTA: RANKING ---
elif st.session_state.page == "ranking":
    st.markdown("""
    <div style="max-width:900px;margin:0 auto;padding-top:2rem;">
        <p style="font-size:0.8rem;font-weight:600;letter-spacing:0.12em;text-transform:uppercase;color:#4A5D32;margin-bottom:0.5rem;">Ranking 2026</p>
        <h1 style="font-size:2.8rem;font-weight:700;color:#1A1A1A;letter-spacing:-0.03em;margin-bottom:0.5rem;">Las mejores universidades de México</h1>
        <p style="font-size:1.1rem;color:#666666;line-height:1.7;margin-bottom:3rem;">Basado en el QS World University Rankings 2027, colegiaturas reales 2026 y tasas de aceptación verificadas.</p>
    </div>
    """, unsafe_allow_html=True)

    universidades_ranking = [
        {
            "pos": 1, "nombre": "UNAM", "tipo": "Pública", "qs": "#145 mundial",
            "aceptacion": "~9%", "colegiatura": "Gratuita (cuota simbólica)",
            "examen": "Propio UNAM — 120 reactivos, 3 hrs",
            "fortalezas": "Medicina · Derecho · Ciencias · Humanidades",
            "color": "#1A3A5C",
        },
        {
            "pos": 2, "nombre": "Tec de Monterrey", "tipo": "Privada", "qs": "#188 mundial",
            "aceptacion": "~25%", "colegiatura": "$155k–$189k / semestre",
            "examen": "PAA (College Board) — mín. 1,320 pts",
            "fortalezas": "Negocios · Ingeniería · Arquitectura · Medicina",
            "color": "#003057",
        },
        {
            "pos": 3, "nombre": "UAG (Universidad Autónoma de Guadalajara)", "tipo": "Privada", "qs": "#1201–1400 mundial",
            "aceptacion": "~80%", "colegiatura": "$27k–$69k / semestre (según carrera)",
            "examen": "PAA (College Board) + autobiografía",
            "fortalezas": "Medicina · Odontología · Negocios · Arquitectura",
            "color": "#2C2C2C",
        },
        {
            "pos": 4, "nombre": "Universidad Panamericana (UP)", "tipo": "Privada", "qs": "Top México",
            "aceptacion": "~78%", "colegiatura": "$177k / semestre (la más cara del país)",
            "examen": "Examen propio + entrevista",
            "fortalezas": "Derecho · Filosofía · Medicina · Negocios",
            "color": "#5A1A1A",
        },
        {
            "pos": 5, "nombre": "Universidad de Guadalajara (UdeG)", "tipo": "Pública", "qs": "#1001–1200 mundial",
            "aceptacion": "~34.5%", "colegiatura": "Gratuita (cuota mínima)",
            "examen": "CUAAD / examen propio por centro universitario",
            "fortalezas": "Ciencias de la Salud · Exactas · Sociales · Artes",
            "color": "#1B4D3E",
        },
        {
            "pos": 6, "nombre": "ITESO", "tipo": "Privada", "qs": "#1201–1400 mundial",
            "aceptacion": "~75%", "colegiatura": "$90k–$130k / semestre",
            "examen": "Examen propio + ficha de admisión",
            "fortalezas": "Ingeniería · Negocios · Diseño · Comunicación",
            "color": "#1A3A5C",
        },
    ]

    for u in universidades_ranking:
        tipo_badge = f'<span style="background:#F0F4EB;color:#4A5D32;font-size:0.72rem;font-weight:600;padding:3px 10px;border-radius:12px;">{u["tipo"]}</span>'
        st.markdown(f"""
        <div style="display:flex;align-items:flex-start;gap:20px;padding:24px;border:1px solid #EAEAEA;border-radius:10px;margin-bottom:14px;background:#FFFFFF;">
            <div style="min-width:36px;height:36px;border-radius:50%;background:{u['color']};display:flex;align-items:center;justify-content:center;color:#FFF;font-weight:700;font-size:0.9rem;flex-shrink:0;">{u['pos']}</div>
            <div style="flex:1;">
                <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
                    <span style="font-size:1.15rem;font-weight:700;color:#1A1A1A;">{u['nombre']}</span>
                    {tipo_badge}
                    <span style="font-size:0.78rem;color:#888888;">{u['qs']}</span>
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px 24px;margin-top:10px;">
                    <div><span style="font-size:0.75rem;color:#AAAAAA;text-transform:uppercase;letter-spacing:.08em;">Tasa de aceptación</span><br><span style="font-size:0.9rem;color:#1A1A1A;font-weight:500;">{u['aceptacion']}</span></div>
                    <div><span style="font-size:0.75rem;color:#AAAAAA;text-transform:uppercase;letter-spacing:.08em;">Colegiatura</span><br><span style="font-size:0.9rem;color:#1A1A1A;font-weight:500;">{u['colegiatura']}</span></div>
                    <div><span style="font-size:0.75rem;color:#AAAAAA;text-transform:uppercase;letter-spacing:.08em;">Examen de admisión</span><br><span style="font-size:0.9rem;color:#1A1A1A;font-weight:500;">{u['examen']}</span></div>
                    <div><span style="font-size:0.75rem;color:#AAAAAA;text-transform:uppercase;letter-spacing:.08em;">Áreas fuertes</span><br><span style="font-size:0.9rem;color:#1A1A1A;font-weight:500;">{u['fortalezas']}</span></div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <p style="font-size:0.78rem;color:#AAAAAA;margin-top:1rem;text-align:center;">
        Fuentes: QS World University Rankings 2027 · Portales oficiales de admisiones · Datos de colegiatura 2026 verificados.
    </p>
    """, unsafe_allow_html=True)


# --- VISTA: BLOG ---
elif st.session_state.page == "blog":
    st.markdown("""
    <div style="max-width:860px;margin:0 auto;padding-top:2rem;">
        <p style="font-size:0.8rem;font-weight:600;letter-spacing:0.12em;text-transform:uppercase;color:#4A5D32;margin-bottom:0.5rem;">Recursos</p>
        <h1 style="font-size:2.8rem;font-weight:700;color:#1A1A1A;letter-spacing:-0.03em;margin-bottom:0.5rem;">Blog de Admisiones</h1>
        <p style="font-size:1.1rem;color:#666666;line-height:1.7;margin-bottom:3rem;">Guías, datos reales y estrategias para mejorar tus probabilidades de ingreso.</p>
    </div>
    """, unsafe_allow_html=True)

    articulos = [
        {
            "tag": "Examen de admisión",
            "titulo": "Cómo prepararte para el examen de la UNAM en 2026",
            "resumen": "El examen consta de 120 reactivos de opción múltiple en 9 materias, divididos en 4 áreas según tu carrera. La clave no es estudiar todo: es identificar las materias con más reactivos en tu área y atacarlas primero. Empieza al menos 4 meses antes, usa simulacros semanales y descarga la guía oficial en dgae.unam.mx al momento de registrarte.",
            "minutos": "5 min",
            "datos": ["120 reactivos · 3 horas", "4 áreas de conocimiento", "Tasa de aceptación: ~9%"],
        },
        {
            "tag": "Costos",
            "titulo": "Cuánto cuesta realmente estudiar en las universidades privadas top de México",
            "resumen": "Muchos aspirantes se enfocan en la colegiatura pero olvidan los gastos asociados. En el Tec de Monterrey el semestre va de $155k a $189k MXN dependiendo del campus, pero hay que sumar seguro médico, materiales y, si te mudas, aproximadamente $6,400 mensuales en vivienda. La UP es técnicamente la más cara del país en 2026 con $177k por semestre, mientras que UAG es de las opciones privadas más accesibles en Guadalajara, con semestres desde $27k MXN según la carrera.",
            "minutos": "4 min",
            "datos": ["UP: $177k/sem (la más cara)", "Tec: $155k–$189k/sem", "UdeG y UNAM: prácticamente gratuitas"],
        },
        {
            "tag": "Estrategia",
            "titulo": "Qué buscan realmente las universidades en tu expediente",
            "resumen": "Las privadas top valoran tres cosas sobre todo: consistencia académica (no perfección, sino tendencia), actividades extracurriculares con compromiso real (no una lista de logros de una sola vez), y un ensayo personal que conecte tu historia con tu carrera elegida. En el Tec, el PAA pesa mucho; en la UAG, la autobiografía es parte central del expediente. Conocer la fórmula de cada universidad te permite enfocar tus energías correctamente.",
            "minutos": "6 min",
            "datos": ["UAG: autobiografía + PAA", "Tec: PAA mínimo 1,320 pts", "UNAM: solo aciertos, sin promedio"],
        },
        {
            "tag": "Guía",
            "titulo": "UdeG vs UNAM: ¿cuál es la mejor pública para estudiar en Jalisco?",
            "resumen": "Ambas son gratuitas y prestigiosas, pero muy diferentes. La UNAM tiene mayor reconocimiento internacional (posición #145 QS vs #1001–1200 de UdeG), pero sus campus están principalmente en CDMX. La UdeG es la segunda más grande de México con más de 100,000 estudiantes y una tasa de aceptación del 34.5% — mucho más accesible que el 9% de la UNAM. Si vives en Guadalajara o el Bajío, la UdeG es una opción sólida sin necesidad de mudarte.",
            "minutos": "5 min",
            "datos": ["UNAM: #145 QS mundial", "UdeG: +100,000 estudiantes", "UdeG acepta 34.5% vs 9% UNAM"],
        },
        {
            "tag": "Becas",
            "titulo": "Cómo conseguir beca en el Tec de Monterrey",
            "resumen": "El Tec ofrece becas por talento académico, atlético, artístico, liderazgo y emprendimiento. La beca socioeconómica cubre entre el 5% y el 25% de la colegiatura y casi siempre viene combinada con un préstamo educativo del mismo porcentaje, que se paga después de graduarte en máximo 1.5 veces la duración de la carrera. El ITAM otorga becas a fondo perdido a aproximadamente el 30% de sus estudiantes.",
            "minutos": "4 min",
            "datos": ["Becas del 5% al 70%", "Préstamo educativo post-graduación", "ITAM: 30% de alumnos con beca"],
        },
    ]

    for art in articulos:
        datos_html = "".join([f'<span style="background:#F7F7F5;color:#444;font-size:0.75rem;padding:4px 10px;border-radius:8px;margin-right:6px;">{d}</span>' for d in art["datos"]])
        st.markdown(f"""
        <div style="padding:28px;border:1px solid #EAEAEA;border-radius:10px;margin-bottom:16px;background:#FFFFFF;">
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
                <span style="background:#EEF1E9;color:#4A5D32;font-size:0.72rem;font-weight:600;padding:3px 10px;border-radius:12px;">{art['tag']}</span>
                <span style="font-size:0.78rem;color:#AAAAAA;">{art['minutos']} de lectura</span>
            </div>
            <h3 style="font-size:1.2rem;font-weight:700;color:#1A1A1A;margin-bottom:10px;">{art['titulo']}</h3>
            <p style="font-size:0.95rem;color:#555555;line-height:1.7;margin-bottom:14px;">{art['resumen']}</p>
            <div>{datos_html}</div>
        </div>
        """, unsafe_allow_html=True)


# --- VISTA: REGISTRO ---
elif st.session_state.page == "registro":
    col_img, col_form = st.columns([1.1, 0.9], gap="large")
    with col_img:
        if fondo_auth_encoded:
            st.markdown(f'<div class="auth-img-box" style="background-image: url(\'data:image/png;base64,{fondo_auth_encoded}\');"></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="auth-img-box" style="background-color: #EFEFEF;"></div>', unsafe_allow_html=True)
    with col_form:
        st.markdown("<div style='padding-top: 40px;'></div>", unsafe_allow_html=True)
        st.markdown("<h1 style='font-size: 3.5rem; font-weight: 400; color: #333333; margin-bottom: 2.5rem;'>Registro</h1>", unsafe_allow_html=True)
        
        reg_nombre = st.text_input("Usuario", placeholder="", key="reg_nom_input")
        reg_email  = st.text_input("Correo electrónico", placeholder="", key="reg_email_input")
        reg_pass   = st.text_input("Contraseña", type="password", placeholder="", key="reg_pass_input")
        reg_edad   = st.number_input(
            "¿Cuántos años tienes?",
            min_value=10, max_value=99, value=17, step=1,
            key="reg_edad_input",
        )

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
            reg_tutor_nombre = st.text_input("Nombre del padre, madre o tutor legal", placeholder="", key="reg_tutor_nombre_input")
            reg_tutor_email  = st.text_input("Correo electrónico del padre, madre o tutor legal", placeholder="", key="reg_tutor_email_input")
        else:
            st.markdown(
                "<p style='font-size:0.82rem;color:#666;margin:0.6rem 0 0.3rem;'>Al crear tu cuenta, aceptas nuestro "
                "<a href='/?page=aviso_privacidad' target='_blank' style='color:#4A5D32;font-weight:600;text-decoration:none;'>Aviso de Privacidad</a> "
                "y nuestros "
                "<a href='/?page=terminos' target='_blank' style='color:#4A5D32;font-weight:600;text-decoration:none;'>Términos y Condiciones</a>.</p>",
                unsafe_allow_html=True,
            )
            reg_acepta_legal = st.checkbox(
                "He leído y acepto el Aviso de Privacidad y los Términos y Condiciones",
                key="reg_acepta_legal",
            )
            st.markdown(
                "<p style='font-size:0.78rem;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;color:#999;margin:1.2rem 0 0.4rem;'>Opcional — tú decides</p>",
                unsafe_allow_html=True,
            )
            reg_consiente_hugo = st.checkbox(
                "Acepto que mis interacciones con Hugo se usen para mejorar y entrenar al asistente de IA de Uniwebmx.",
                key="reg_consiente_hugo_input",
            )
            reg_consiente_unis = st.checkbox(
                "Acepto que Uniwebmx comparta mi información con las universidades que yo seleccione como de mi interés.",
                key="reg_consiente_unis_input",
            )
            reg_consiente_promo = st.checkbox(
                "Acepto recibir correos sobre nuevas funciones, becas y contenido educativo de Uniwebmx.",
                key="reg_consiente_promo_input",
            )

        _reg_clicked = st.button("Crear cuenta", use_container_width=True, key="reg_submit_btn")
        if _reg_clicked:
            import re as _re_email
            import secrets as _secrets_reg
            _email_val = reg_email.strip()
            _email_ok = bool(_re_email.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", _email_val))
            _pass_ok  = len(reg_pass) >= 8 and bool(_re_email.search(r"[A-Za-z]", reg_pass)) and bool(_re_email.search(r"\d", reg_pass))
            _tutor_email_val = reg_tutor_email.strip()
            _tutor_email_ok = bool(_re_email.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", _tutor_email_val)) if _es_menor else True

            if not reg_nombre or not reg_pass or not _email_val:
                st.error("Por favor completa todos los campos (usuario, correo y contraseña).")
            elif not _email_ok:
                st.error("El correo electrónico no tiene un formato válido.")
            elif not _pass_ok:
                st.error("La contraseña debe tener al menos 8 caracteres, una letra y un número.")
            elif _es_menor and not reg_tutor_nombre.strip():
                st.error("Al ser menor de edad, necesitamos el nombre de tu padre, madre o tutor legal.")
            elif _es_menor and not _tutor_email_ok:
                st.error("El correo del padre, madre o tutor legal no tiene un formato válido.")
            elif not _es_menor and not reg_acepta_legal:
                st.error("Debes aceptar el Aviso de Privacidad y los Términos y Condiciones para crear tu cuenta.")
            else:
                reg_nombre_limpio = reg_nombre.strip()
                # Antes se usaba load_users() (traía TODA la tabla a memoria); eso se corta
                # en tablas grandes por el límite de filas de PostgREST y podía dejar pasar
                # usernames que sí existían. Ahora preguntamos directo por ese username.
                _username_existente = supabase_client.table("usuarios").select("username").eq("username", reg_nombre_limpio).execute()
                if _username_existente.data:
                    st.error("El usuario ya existe, intenta con otro.")
                else:
                    # Verificar que el correo no esté ya registrado
                    _email_existente = supabase_client.table("usuarios").select("username").eq("email", _email_val).execute()
                    if _email_existente.data:
                        st.error("Ya existe una cuenta con ese correo electrónico.")
                    else:
                        _token_tutor = None
                        _token_tutor_expiry = None
                        if _es_menor:
                            _token_tutor = _secrets_reg.token_urlsafe(32)
                            _token_tutor_expiry = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

                        _creado_ok = save_user(
                            reg_nombre_limpio, reg_pass, _email_val,
                            edad=int(reg_edad),
                            es_menor_edad=_es_menor,
                            tutor_nombre=reg_tutor_nombre.strip() if _es_menor else "",
                            tutor_email=_tutor_email_val if _es_menor else "",
                            tutor_consentimiento=reg_tutor_consiente if _es_menor else False,
                            tutor_confirm_token=_token_tutor,
                            tutor_confirm_token_expiry=_token_tutor_expiry,
                            # Para menores, las finalidades secundarias arrancan en False y solo
                            # se activan cuando el tutor confirma desde el correo (doble opt-in).
                            consentimiento_hugo=reg_consiente_hugo if not _es_menor else False,
                            consentimiento_universidades=reg_consiente_unis if not _es_menor else False,
                            consentimiento_promocional=reg_consiente_promo if not _es_menor else False,
                            consentimientos_fecha=datetime.now(timezone.utc).isoformat() if not _es_menor else None,
                        )
                        if not _creado_ok:
                            # Puede ser que alguien más se haya registrado con ese username justo
                            # en este instante (carrera), o que algo haya tronado en Supabase — en
                            # ese segundo caso ya se le avisó al admin por correo.
                            st.error("No pudimos crear tu cuenta. Es posible que ese usuario se haya registrado justo ahora; intenta con otro nombre de usuario o vuelve a intentarlo en un momento.")
                        else:
                            enviar_correo_bienvenida_registro(_email_val)
                            _log_evento(reg_nombre_limpio, "registro", {"es_menor_edad": _es_menor})
                            if _es_menor:
                                _confirm_link = f"{BASE_URL}/?page=confirmar_tutor&token={_token_tutor}"
                                enviar_correo_confirmacion_tutor(
                                    _tutor_email_val, reg_tutor_nombre.strip(), reg_nombre_limpio, _email_val, _confirm_link
                                )
                            st.success("Cuenta creada exitosamente.")
                            if _es_menor:
                                st.info("Le enviamos un correo a tu padre, madre o tutor para que confirme y decida sobre el uso adicional de tus datos. Mientras tanto, ya puedes iniciar sesión y usar las funciones básicas.")
                            else:
                                st.info("Ahora puedes iniciar sesión.")
        
        st.markdown("""
        <p class='auth-redirect-text'>¿Ya tienes cuenta?</p>
        <div style="text-align:center;">
            <a href="/?page=login" target="_self" style="display:inline-block;text-decoration:none;font-family:Montserrat,sans-serif;font-size:0.88rem;font-weight:600;color:#1A1A1A;padding:10px 28px;border:1px solid #D0D0D0;border-radius:8px;transition:background 0.15s;">Inicia sesión aquí</a>
        </div>
        """, unsafe_allow_html=True)

# --- VISTA: LOGIN ---
elif st.session_state.page == "login":
    col_img, col_form = st.columns([1.1, 0.9], gap="large")
    with col_img:
        if fondo_auth_encoded:
            st.markdown(f'<div class="auth-img-box" style="background-image: url(\'data:image/png;base64,{fondo_auth_encoded}\');"></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="auth-img-box" style="background-color: #EFEFEF;"></div>', unsafe_allow_html=True)
            
    with col_form:
        st.markdown("<div style='padding-top: 60px;'></div>", unsafe_allow_html=True)
        st.markdown("<h1 style='font-size: 3.5rem; font-weight: 400; color: #333333; margin-bottom: 3rem;'>Inicio de sesión</h1>", unsafe_allow_html=True)
        
        with st.form("form_login"):
            login_email = st.text_input("Correo electrónico o usuario", placeholder="ejemplo@correo.com o tu_usuario", key="login_email_input")
            login_pass  = st.text_input("Contraseña", type="password", placeholder="Tu contraseña", key="login_pass_input")
            _login_clicked = st.form_submit_button("Iniciar sesión", use_container_width=True)
        if _login_clicked:
            # Resolver el username real primero (puede haber escrito su correo)
            _login_username = login_email.strip()
            _res_by_email = supabase_client.table("usuarios").select("username").eq("email", _login_username).execute()
            if _res_by_email.data:
                _login_username = _res_by_email.data[0]["username"]

            if cuenta_bloqueada(_login_username):
                st.error("Demasiados intentos fallidos. Por seguridad, esta cuenta quedó bloqueada temporalmente. Intenta de nuevo en unos minutos o restablece tu contraseña.")
            elif verify_user(_login_username, login_pass):
                resetear_intentos_fallidos(_login_username)
                st.session_state.logged_in = True
                st.session_state.user = _login_username
                st.session_state.session_token = crear_sesion_token(_login_username)
                restaurar_sesion_usuario(_login_username)
                _log_evento(_login_username, "login")
                if puede_ver_panel():
                    cambiar_pagina("panel_admin")
                elif st.session_state.get("perfil_completo"):
                    cambiar_pagina("locker")
                else:
                    cambiar_pagina("onboarding")
            else:
                registrar_intento_fallido(_login_username)
                st.error("Los datos ingresados no coinciden con ninguna cuenta. Verifica tu correo/usuario y contraseña.")
        
        st.markdown("""
        <div style="text-align:center;margin-top:0.5rem;">
            <a href="/?page=olvide_contrasena" target="_self"
               style="font-family:Montserrat,sans-serif;font-size:0.82rem;color:#888;text-decoration:none;">
               ¿Olvidaste tu contraseña?
            </a>
        </div>
        <p class='auth-redirect-text'>¿No tienes cuenta?</p>
        <div style="text-align:center;">
            <a href="/?page=registro" target="_self" style="display:inline-block;text-decoration:none;font-family:Montserrat,sans-serif;font-size:0.88rem;font-weight:600;color:#1A1A1A;padding:10px 28px;border:1px solid #D0D0D0;border-radius:8px;transition:background 0.15s;">Registro</a>
        </div>
        """, unsafe_allow_html=True)


# --- VISTA: OLVIDÉ MI CONTRASEÑA ---
elif st.session_state.page == "olvide_contrasena":
    import secrets as _secrets
    from datetime import timezone as _tz

    col_img, col_form = st.columns([1.1, 0.9], gap="large")
    with col_img:
        if fondo_auth_encoded:
            st.markdown(f'<div class="auth-img-box" style="background-image: url(\'data:image/png;base64,{fondo_auth_encoded}\');"></div>', unsafe_allow_html=True)
        else:
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
                # Busca primero por email, luego por username
                res = supabase_client.table("usuarios").select("username, email").eq("email", _input).execute()
                if not res.data:
                    res = supabase_client.table("usuarios").select("username, email").eq("username", _input).execute()
                if res.data:
                    _email_destino = res.data[0].get("email") or ""
                    _username_reset2 = res.data[0]["username"]
                    if _email_destino:
                        token = _secrets.token_urlsafe(32)
                        expiry = (datetime.now(_tz.utc) + timedelta(hours=1)).isoformat()
                        # Invalida cualquier token anterior y asigna el nuevo
                        supabase_client.table("usuarios").update({
                            "reset_token": None,
                            "reset_token_expiry": None,
                        }).eq("username", _username_reset2).execute()
                        supabase_client.table("usuarios").update({
                            "reset_token": token,
                            "reset_token_expiry": expiry
                        }).eq("username", _username_reset2).execute()
                        reset_link = f"{BASE_URL}/?page=reset_contrasena&token={token}"
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
                # Siempre mostramos el mismo mensaje (no revelar si el usuario existe)
                st.success("Si ese correo está registrado, recibirás el enlace en unos minutos.")

        st.markdown("""
        <div style="text-align:center;margin-top:1.5rem;">
            <a href="/?page=login" target="_self"
               style="font-family:Montserrat,sans-serif;font-size:0.85rem;color:#888;text-decoration:none;">
               ← Volver a iniciar sesión
            </a>
        </div>
        """, unsafe_allow_html=True)

# --- VISTA: RESET CONTRASEÑA (desde link del correo) ---
elif st.session_state.page == "reset_contrasena":
    from datetime import timezone as _tz2

    _token_url = st.query_params.get("token", "") or st.session_state.get("_token_url_pendiente", "")

    col_img, col_form = st.columns([1.1, 0.9], gap="large")
    with col_img:
        if fondo_auth_encoded:
            st.markdown(f'<div class="auth-img-box" style="background-image: url(\'data:image/png;base64,{fondo_auth_encoded}\');"></div>', unsafe_allow_html=True)
        else:
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
                _now = datetime.now(_tz2.utc)
                if _expiry_dt and _now > _expiry_dt:
                    st.error("El enlace expiró. Solicita uno nuevo desde la página de login.")
                else:
                    st.markdown("<p style='font-size:1rem;color:#666;margin-bottom:2rem;'>Elige una nueva contraseña para tu cuenta.</p>", unsafe_allow_html=True)
                    with st.form("form_nueva_pass"):
                        nueva_pass = st.text_input("Nueva contraseña", type="password", key="nueva_pass_input")
                        confirmar_pass = st.text_input("Confirmar contraseña", type="password", key="confirmar_pass_input")
                        _nueva_clicked = st.form_submit_button("Guardar contraseña", use_container_width=True)
                    if _nueva_clicked:
                        import re as _re_pass
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

# --- VISTA: ONBOARDING (perfil inicial, una sola vez tras el primer login) ---
elif st.session_state.page == "onboarding":
    _user = st.session_state.get("user")

    col_img, col_form = st.columns([1.1, 0.9], gap="large")
    with col_img:
        if fondo_auth_encoded:
            st.markdown(f'<div class="auth-img-box" style="background-image: url(\'data:image/png;base64,{fondo_auth_encoded}\');"></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="auth-img-box" style="background-color: #EFEFEF;"></div>', unsafe_allow_html=True)

    with col_form:
        st.markdown("<div style='padding-top: 30px;'></div>", unsafe_allow_html=True)
        st.markdown("<h1 style='font-size: 2.8rem; font-weight: 400; color: #333333; margin-bottom: 0.5rem;'>¡Bienvenido a Uniwebmx!</h1>", unsafe_allow_html=True)
        st.markdown(
            "<p style='font-size: 1.05rem; color: #666666; margin-bottom: 2rem;'>Cuéntanos un poco de ti. "
            "Con esto, Hugo —tu consultor de admisión— ya arranca conociendo tu perfil, en vez de empezar de cero.</p>",
            unsafe_allow_html=True,
        )

        # Verificar si el usuario ya tiene email guardado
        _res_onb_email = supabase_client.table("usuarios").select("email").eq("username", _user).execute()
        _email_guardado = (_res_onb_email.data[0].get("email") or "") if _res_onb_email.data else ""

        nombre_onboarding = st.text_input(
            "¿Cómo te llamas?",
            value=st.session_state.get("perfil_nombre", "") or st.session_state.get("user", ""),
            key="onb_nombre",
        )

        # Mostrar campo de email solo si no lo tienen guardado
        if not _email_guardado:
            st.markdown("<p style='font-size:0.82rem;color:#E07B00;margin-bottom:4px;'>📧 Para poder recuperar tu contraseña necesitamos tu correo.</p>", unsafe_allow_html=True)
            email_onboarding = st.text_input(
                "Correo electrónico",
                placeholder="ejemplo@correo.com",
                key="onb_email",
            )
        else:
            email_onboarding = _email_guardado

        edad_onboarding = st.number_input(
            "¿Cuántos años tienes?",
            min_value=14, max_value=99,
            value=st.session_state.get("perfil_edad") or 17,
            step=1,
            key="onb_edad",
        )
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
            import re as _re_onb
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
                st.session_state.perfil_edad = int(edad_onboarding)
                st.session_state.perfil_carreras = carreras_onboarding
                st.session_state.perfil_universidades_interes = unis_onboarding
                st.session_state.perfil_preparatoria = preparatoria_onboarding
                st.session_state.perfil_completo = True
                # Guardar email si no lo tenían
                if not _email_guardado and _email_onb_val:
                    supabase_client.table("usuarios").update({"email": _email_onb_val}).eq("username", _user).execute()
                # Precargamos también las universidades de interés en "Mi Aplicación" / Simulador
                if not st.session_state.get("unis_seleccionadas"):
                    st.session_state.unis_seleccionadas = unis_onboarding
                guardar_datos_usuario(_user)
                st.toast(f"¡Listo, {nombre_onboarding}! Hugo ya tiene tu perfil.")
                cambiar_pagina("locker")

        st.markdown(
            "<p style='font-size:0.8rem;color:#999;margin-top:1.5rem;'>Podrás ajustar esta información más adelante "
            "desde 'Mi Aplicación' o el Simulador.</p>",
            unsafe_allow_html=True,
        )


# --- VISTA: LOCKER DIGITAL ---
elif st.session_state.page == "locker":
   _user = st.session_state.get("user")

   if es_usuario_menor():
       st.markdown("""
       <div class="hero-section-locker">
           <h1 style='font-size: 3.5rem; margin-bottom: 1.5rem; max-width: 900px; margin-left: auto; margin-right: auto;'>Tu Locker Digital</h1>
       </div>
       """, unsafe_allow_html=True)
       st.markdown(
           "<div style='max-width:680px;margin:0 auto;background:#FAEEDA;border-radius:12px;padding:28px 32px;'>"
           "<h3 style='margin-top:0;color:#5F4B1E;font-size:1.15rem;'>El Locker Digital no está disponible para tu cuenta</h3>"
           "<p style='font-size:0.92rem;color:#5F4B1E;line-height:1.7;margin-bottom:0;'>"
           "Por ser menor de edad, y dado que el Locker guarda documentos sensibles como tu acta de nacimiento, "
           "CURP, identificación oficial y comprobante de domicilio, Uniwebmx <strong>no almacena de forma permanente "
           "esos documentos</strong> en tu cuenta. Puedes seguir usando a Hugo y el Simulador con normalidad — solo el "
           "almacenamiento persistente de documentos está desactivado para proteger tu información."
           "</p></div>",
           unsafe_allow_html=True,
       )
   else:
    st.markdown("""
    <div class="hero-section-locker">
        <h1 style='font-size: 3.5rem; margin-bottom: 1.5rem; max-width: 900px; margin-left: auto; margin-right: auto;'>Tu Locker Digital</h1>
        <p style='font-size: 1.35rem; color: #1A1A1A; max-width: 850px; margin: 0 auto; line-height: 1.6; font-weight: 400; opacity: 0.9;'>
            Centraliza tus documentos. Súbelos una vez y la app los empaquetará por universidad cuando estés listo.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── helper ────────────────────────────────────────────────────────────────
    def _doc_slot(key, label, desc, tipos, session_key=None):
        """Renderiza una tarjeta de documento reutilizable."""
        sk = session_key or key
        if sk not in st.session_state:
            st.session_state[sk] = {"nombre": None, "contenido": ""}

        with st.container(border=True):
            st.markdown(f"<h4 style='margin-bottom:4px;'>{label}</h4>", unsafe_allow_html=True)
            st.markdown(f'<p class="locker-text-desc">{desc}</p>', unsafe_allow_html=True)

            doc = st.session_state[sk]
            if doc.get("nombre"):
                st.success(f"✓ {doc['nombre']}", icon=None)
                mostrar_visor_documento(_user, key)
                st.markdown('<div class="quitar-link">', unsafe_allow_html=True)
                if st.button("✕ Quitar documento", key=f"quitar_{key}"):
                    st.session_state[sk] = {"nombre": None, "contenido": ""}
                    eliminar_archivo_original(_user, key)
                    guardar_datos_usuario(_user)
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

            archivo = st.file_uploader(
                "Reemplazar" if doc.get("nombre") else "",
                type=tipos,
                key=f"up_{key}"
            )
            if archivo is not None and doc.get("nombre") != archivo.name:
                with st.spinner("Guardando..."):
                    guardar_archivo_original(_user, key, archivo.name, archivo.getvalue())
                    texto = extraer_texto_archivo(archivo) if archivo.type in ["application/pdf","text/plain"] else ""
                    st.session_state[sk] = {"nombre": archivo.name, "contenido": texto}
                    guardar_datos_usuario(_user)
                st.toast(f"'{archivo.name}' guardado.")

    # ── Sección: Documentos académicos ───────────────────────────────────────
    st.markdown("""
    <div style="margin: 2rem 0 1rem;">
        <p style="font-size:10px;letter-spacing:0.09em;text-transform:uppercase;color:#AAAAAA;margin-bottom:6px;font-family:Montserrat,sans-serif;">Documentos académicos</p>
        <p style="font-size:0.9rem;color:#666;margin:0;">Los que tú produces o tu escuela expide. Claves para tu expediente.</p>
    </div>
    """, unsafe_allow_html=True)

    ca1, ca2, ca3 = st.columns(3)
    with ca1:
        _doc_slot("kardex", "Kárdex / Certificado", "Tu historial académico oficial. PDF o TXT.", ["pdf","txt"], session_key="kárdex")
    with ca2:
        _doc_slot("ensayo", "Ensayo / Carta de motivos", "Tu carta personal o declaración de propósito.", ["pdf","txt"])
    with ca3:
        _doc_slot("curriculum", "Currículum académico", "Logros, extracurriculares y actividades relevantes.", ["pdf","txt","docx"])

    ca4, ca5, ca6 = st.columns(3)
    with ca4:
        _doc_slot("cartas", "Cartas de recomendación", "Expedidas por profesores, directores o tutores.", ["pdf","docx"])
    with ca5:
        _doc_slot("portafolio", "Portafolio / Extracurriculares", "Diplomas, reconocimientos, proyectos, voluntariados.", ["pdf","zip","jpg","png"])
    with ca6:
        st.markdown("<div style='height:100%;'></div>", unsafe_allow_html=True)  # espacio vacío

    # ── Sección: Documentos personales ───────────────────────────────────────
    st.markdown("""
    <div style="margin: 2.5rem 0 1rem;">
        <p style="font-size:10px;letter-spacing:0.09em;text-transform:uppercase;color:#AAAAAA;margin-bottom:6px;font-family:Montserrat,sans-serif;">Documentos personales</p>
        <p style="font-size:0.9rem;color:#666;margin:0;">Los que el gobierno expide. Súbelos escaneados o en foto.</p>
    </div>
    """, unsafe_allow_html=True)

    cp1, cp2, cp3 = st.columns(3)
    with cp1:
        _doc_slot("acta", "Acta de nacimiento", "Original escaneada o copia certificada.", ["pdf","jpg","png"])
    with cp2:
        _doc_slot("curp", "CURP", "Descárgala en gob.mx si no la tienes.", ["pdf","jpg","png"])
    with cp3:
        _doc_slot("identificacion", "Identificación oficial", "INE, pasaporte o credencial de tu prepa.", ["pdf","jpg","png"])

    cp4, cp5, cp6 = st.columns(3)
    with cp4:
        _doc_slot("foto", "Foto credencial", "Fondo blanco, reciente, formato infantil o credencial.", ["jpg","png"])
    with cp5:
        _doc_slot("comprobante", "Comprobante de domicilio", "Recibo de luz, agua o teléfono reciente.", ["pdf","jpg","png"])
    with cp6:
        st.markdown("<div style='height:100%;'></div>", unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom:3rem;'></div>", unsafe_allow_html=True)


# --- VISTA: MI APLICACIÓN (carpetas por universidad) ---
elif st.session_state.page == "mi_aplicacion":
   _user = st.session_state.get("user")

   if es_usuario_menor():
       st.markdown("""
       <div class="hero-section-locker">
           <h1 style='font-size: 3.5rem; margin-bottom: 1.5rem; max-width: 900px; margin-left: auto; margin-right: auto;'>Mi Aplicación</h1>
       </div>
       """, unsafe_allow_html=True)
       st.markdown(
           "<div style='max-width:680px;margin:0 auto;background:#FAEEDA;border-radius:12px;padding:28px 32px;'>"
           "<h3 style='margin-top:0;color:#5F4B1E;font-size:1.15rem;'>Esta sección no está disponible para tu cuenta</h3>"
           "<p style='font-size:0.92rem;color:#5F4B1E;line-height:1.7;margin-bottom:0;'>"
           "Las carpetas por universidad se arman con los documentos de tu Locker Digital, que no está disponible "
           "para cuentas de menores de edad. Puedes seguir usando a Hugo para resolver dudas sobre tu proceso de "
           "admisión."
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
        guardar_datos_usuario(_user)
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
                                cambiar_pagina("locker")

                if docs_extra:
                    st.markdown("<p style='font-size:0.85rem;color:#888;margin-top:10px;margin-bottom:4px;'>Otros requisitos (gestiónalos directo con la universidad):</p>", unsafe_allow_html=True)
                    for extra in docs_extra:
                        st.markdown(f"<p style='font-size:0.9rem;color:#444;margin:2px 0;'>⬜ {extra}</p>", unsafe_allow_html=True)

                if completos == len(docs_requeridos) and docs_requeridos:
                    st.success("¡Carpeta completa! Ya tienes todos los documentos del Locker listos para esta universidad.")

        st.markdown("<div style='margin-bottom:2rem;'></div>", unsafe_allow_html=True)
        st.caption("Tip: las carpetas se actualizan solas en cuanto subas o reemplaces un documento en tu Locker Digital.")


# --- VISTA: CENTRO DE MENSAJES (conexión IMAP al correo del usuario) ---
elif st.session_state.page == "mensajes":
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
                       guardar_datos_usuario(_user)  # solo guarda el correo y proveedor, nunca la contraseña
                       st.toast("¡Correo conectado!")
                       st.rerun()
                   except imaplib.IMAP4.error:
                       st.error("No se pudo iniciar sesión. Revisa el correo y la contraseña (recuerda usar una contraseña de aplicación).")
                   except Exception as e:
                       st.error(f"No se pudo conectar: {e}")

   else:
       col_estado, col_desconectar = st.columns([4, 1])
       with col_estado:
           st.success(f"Conectado como **{st.session_state.correo_conectado}** ({st.session_state.proveedor_correo})")
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


# --- VISTA: CONSULTOR IA ---
# --- VISTA: CONSULTOR IA ---
elif st.session_state.page == "chat":
    # --- CONFIGURACIÓN DEL LÍMITE (real, por fecha, no por sesión) ---
    from datetime import date
    hoy_str = date.today().isoformat()

    if "contador_consultas" not in st.session_state:
        st.session_state.contador_consultas = 0
    if "fecha_contador" not in st.session_state:
        st.session_state.fecha_contador = hoy_str

    # Si cambió el día desde la última consulta, se reinicia el contador
    if st.session_state.fecha_contador != hoy_str:
        st.session_state.contador_consultas = 0
        st.session_state.fecha_contador = hoy_str

    LIMITE_DIARIO = LIMITE_HUGO_DIARIO

    st.markdown('<div class="gemini-chat-container">', unsafe_allow_html=True)
  
    if "historial_chat" not in st.session_state:
        st.session_state.historial_chat = [
            {"role": "assistant", "content": "¡Hola! Soy Hugo, tu consultor de admisión. ¿En qué puedo ayudarte hoy?"}
        ]
  
    for msg in st.session_state.historial_chat:
        if msg["role"] == "user":
            st.markdown(f"""
            <div class="gemini-row gemini-row-user">
                <div class="gemini-bubble gemini-bubble-user">
                    <div class="gemini-user-label">Tú</div>
                    <div class="gemini-text">{msg["content"]}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="gemini-row gemini-row-hugo">
                <div class="gemini-bubble gemini-bubble-hugo">
                    <div class="gemini-hugo-label">Hugo</div>
                    <div class="gemini-text">{msg["content"]}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
          
    st.markdown('</div>', unsafe_allow_html=True)
  
    prompt_chat = st.chat_input("Pregúntale a Hugo...", key="chat_gemini_input_real")
    
    if prompt_chat:
        # VERIFICACIÓN DE LÍMITE
        if st.session_state.contador_consultas >= LIMITE_DIARIO:
            st.warning(f"Has alcanzado tu límite diario de {LIMITE_DIARIO} consultas con Hugo. Intenta mañana.")
        else:
            st.session_state.historial_chat.append({"role": "user", "content": prompt_chat})
            _log_evento(st.session_state.get("user", ""), "mensaje_chat")
            
            with st.spinner("Hugo está revisando..."):
                try:
                    # --- CONTEXTO DEL LOCKER (kárdex + ensayo, solo si tienen contenido real) ---
                    contenido_kardex = st.session_state.get("kárdex", {}).get("contenido", "")
                    contenido_ensayo = st.session_state.get("ensayo", {}).get("contenido", "")

                    partes_contexto = []

                    # --- PERFIL INICIAL DEL ALUMNO (capturado en el onboarding) ---
                    if st.session_state.get("perfil_completo"):
                        nombre_perfil = st.session_state.get("perfil_nombre", "")
                        edad_perfil = st.session_state.get("perfil_edad", "")
                        carreras_perfil = ", ".join(st.session_state.get("perfil_carreras", [])) or "no especificadas"
                        unis_perfil = ", ".join(st.session_state.get("perfil_universidades_interes", [])) or "no especificadas"
                        partes_contexto.append(
                            f"--- PERFIL DEL ALUMNO ---\n"
                            f"Nombre: {nombre_perfil}\nEdad: {edad_perfil}\n"
                            f"Carreras de interés: {carreras_perfil}\n"
                            f"Universidades de interés: {unis_perfil}"
                        )

                    if contenido_kardex:
                        partes_contexto.append(f"--- KÁRDEX DEL ALUMNO ---\n{contenido_kardex}")
                    if contenido_ensayo:
                        partes_contexto.append(f"--- ENSAYO DE MOTIVOS DEL ALUMNO ---\n{contenido_ensayo}")

                    # --- BASE DE CONOCIMIENTO VERIFICADA DE UNIVERSIDADES ---
                    # Antes Hugo solo usaba esta info en el simulador. Ahora se manda en
                    # cada mensaje del chat para que sus respuestas estén ancladas a datos
                    # reales y no a lo que Gemini "recuerde" de memoria (que puede estar
                    # desactualizado o inventado).
                    universidades_interes_alumno = st.session_state.get("perfil_universidades_interes", [])
                    contexto_unis = construir_contexto_universidades(universidades_interes_alumno)
                    if contexto_unis:
                        partes_contexto.append(f"--- BASE DE CONOCIMIENTO VERIFICADA DE UNIVERSIDADES ---\n{contexto_unis}")

                    info_doc = ""
                    if partes_contexto:
                        info_doc = "\n\n[CONTEXTO DEL ALUMNO]\n" + "\n\n".join(partes_contexto)

                    # --- RECONSTRUIR HISTORIAL PARA QUE HUGO TENGA MEMORIA ---
                    # Tomamos todo el historial previo (sin contar el mensaje que acabamos
                    # de agregar, que se manda aparte con send_message) y lo convertimos
                    # al formato que espera la API de Gemini.
                    historial_previo = st.session_state.historial_chat[:-1]
                    historial_gemini = []
                    for msg in historial_previo:
                        rol_gemini = "user" if msg["role"] == "user" else "model"
                        historial_gemini.append({"role": rol_gemini, "parts": [msg["content"]]})

                    model = genai.GenerativeModel(
                        "gemini-2.5-flash",
                        system_instruction=(
                            "Eres Hugo, un consultor experto en admisiones universitarias en México. "
                            "Usa el perfil del alumno (nombre, edad, carreras de interés, universidades de "
                            "interés) y el contexto de documentos (si está disponible) para dar "
                            "retroalimentación específica y personalizada, no genérica. Dirígete al alumno "
                            "por su nombre cuando lo tengas disponible.\n\n"
                            "REGLAS SOBRE DATOS DE UNIVERSIDADES (muy importantes):\n"
                            "1. Cuando hables de requisitos, puntajes, costos, fechas o becas de una "
                            "universidad, básate SIEMPRE en la 'BASE DE CONOCIMIENTO VERIFICADA DE "
                            "UNIVERSIDADES' que viene en el contexto. No inventes ni completes con tu "
                            "conocimiento general si el dato no está ahí.\n"
                            "2. Respeta el nivel de confianza de cada dato: si dice 'oficial', puedes "
                            "darlo con seguridad; si dice 'parcial' o 'estimado', acláraselo al alumno "
                            "(ej. 'esto es un rango de referencia, no un mínimo garantizado').\n"
                            "3. Sigue al pie de la letra cualquier 'INSTRUCCIÓN ESPECÍFICA' que venga "
                            "junto a una universidad en la base de conocimiento.\n"
                            "4. Si te preguntan sobre una universidad que no está en tu base de "
                            "conocimiento, dilo explícitamente y ofrece ayudar con lo que sí tienes "
                            "verificado, en vez de inventar cifras.\n\n"
                            "No uses emojis en tus respuestas."
                        ),
                    )
                    chat = model.start_chat(history=historial_gemini)
                    respuesta = chat.send_message(prompt_chat + info_doc)
                    texto_hugo = _quitar_emojis(respuesta.text)
                    
                    # INCREMENTAR CONTADOR SOLO SI LA LLAMADA ES EXITOSA
                    st.session_state.contador_consultas += 1
                    
                    st.session_state.historial_chat.append({"role": "assistant", "content": texto_hugo})

                    # Finalidad secundaria 6.1: solo se guarda esta conversación en la tabla
                    # de entrenamiento si el usuario (o su tutor, si es menor de edad) dio
                    # consentimiento explícito. Para menores, este flag solo se activa cuando
                    # el tutor confirma vía el correo de doble opt-in.
                    if st.session_state.get("consentimiento_hugo_actual", False):
                        guardar_conversacion_entrenamiento(
                            st.session_state.get("user"), prompt_chat, texto_hugo
                        )

                except Exception as e:
                    if "429" in str(e):
                        msg_error = "**Hugo está tomando un descanso.** Has alcanzado el límite de velocidad de la API. Intenta en un momento."
                    else:
                        msg_error = "Lo siento, hubo un problema al conectar con Hugo. Inténtalo de nuevo."
                    st.session_state.historial_chat.append({"role": "assistant", "content": msg_error})
            
            guardar_datos_usuario(st.session_state.get("user"))
            st.rerun()
# --- VISTA: SIMULADOR ESTADÍSTICO ---
elif st.session_state.page == "simulador":
    st.markdown("""
    <div class="hero-section-locker">
        <h1 style='font-size: 3.5rem; margin-bottom: 1.5rem; max-width: 900px; margin-left: auto; margin-right: auto;'>Simulador Estadístico</h1>
        <p style='font-size: 1.35rem; color: #1A1A1A; max-width: 850px; margin: 0 auto; line-height: 1.6; font-weight: 400; opacity: 0.9;'>
            Captura tu promedio y tu desempeño esperado en el examen de admisión para calcular tus probabilidades reales con base en datos de referencia por universidad.
        </p>
    </div>
    """, unsafe_allow_html=True)

    if "unis_seleccionadas" not in st.session_state:
        st.session_state.unis_seleccionadas = []

    unis_para_simular = st.multiselect(
        "¿A qué universidades quieres aplicar? (puedes ajustarlo también en 'Mi Aplicación')",
        options=list(UNIVERSIDADES_DATA.keys()),
        default=st.session_state.unis_seleccionadas if st.session_state.unis_seleccionadas else list(UNIVERSIDADES_DATA.keys()),
        key="multiselect_simulador",
    )

    with st.form("form_simulador"):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            promedio_alumno = st.number_input(
                "Tu promedio de bachillerato (escala 0-10)",
                min_value=0.0, max_value=10.0, value=9.0, step=0.1
            )
        with col_f2:
            examen_alumno = st.slider(
                "Tu desempeño esperado en el examen de admisión (percentil estimado, 0-100)",
                min_value=0, max_value=100, value=70,
                help="Como cada universidad usa un examen distinto (PAA, EXANI-II, etc.) con escalas diferentes, usa un estimado de 0 a 100 de qué tan bien crees que te irá comparado con otros aspirantes."
            )
        calcular = st.form_submit_button("Calcular mis probabilidades")

    if calcular:
        if not unis_para_simular:
            st.warning("Selecciona al menos una universidad para calcular tus probabilidades.")
        else:
            if unis_para_simular != st.session_state.unis_seleccionadas:
                st.session_state.unis_seleccionadas = unis_para_simular
            with st.spinner("Calculando con base en datos de referencia y tu perfil..."):
                resultados = {}
                for nombre_uni in unis_para_simular:
                    datos_uni = UNIVERSIDADES_DATA[nombre_uni]
                    resultados[nombre_uni] = {
                        "prob_base": calcular_probabilidad_base(promedio_alumno, examen_alumno, datos_uni),
                        "confianza": datos_uni["confianza"],
                        "fuente": datos_uni["fuente"],
                        "ajuste_ia": 0,
                        "justificacion_ia": "",
                    }

                # --- AJUSTE CUALITATIVO DE HUGO (vía Gemini, JSON estricto) ---
                contenido_kardex = st.session_state.get("kárdex", {}).get("contenido", "")
                contenido_ensayo = st.session_state.get("ensayo", {}).get("contenido", "")

                if contenido_kardex or contenido_ensayo:
                    try:
                        lista_unis_txt = ", ".join(unis_para_simular)
                        prompt_ajuste = (
                            f"Eres Hugo, consultor de admisiones. Con base en este kárdex y/o ensayo del "
                            f"alumno, da un AJUSTE cualitativo (entero, entre -8 y 8) a la probabilidad base "
                            f"de aceptación para cada una de estas universidades: {lista_unis_txt}. "
                            f"Un ajuste positivo significa que el perfil cualitativo (logros, narrativa del "
                            f"ensayo, actividades) suma a favor del alumno; negativo si hay señales débiles. "
                            f"Responde ÚNICAMENTE con un JSON válido, sin texto adicional, sin markdown, con "
                            f"este formato exacto, usando exactamente estos nombres de universidad como claves: "
                            f'{{"{unis_para_simular[0]}": {{"ajuste": 0, "justificacion": "..."}}, ...}}. '
                            f"La justificación debe ser de máximo 15 palabras.\n\n"
                            f"KÁRDEX: {contenido_kardex}\n\nENSAYO: {contenido_ensayo}"
                        )
                        model_ajuste = genai.GenerativeModel("gemini-2.5-flash")
                        respuesta_ajuste = model_ajuste.generate_content(prompt_ajuste)
                        texto_limpio = respuesta_ajuste.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                        datos_ia = json.loads(texto_limpio)

                        for nombre_uni in resultados:
                            if nombre_uni in datos_ia:
                                ajuste = max(-8, min(8, int(datos_ia[nombre_uni].get("ajuste", 0))))
                                resultados[nombre_uni]["ajuste_ia"] = ajuste
                                resultados[nombre_uni]["justificacion_ia"] = datos_ia[nombre_uni].get("justificacion", "")
                    except Exception:
                        # Si Hugo falla o no responde JSON válido, nos quedamos solo con la fórmula base
                        pass

                for nombre_uni, r in resultados.items():
                    r["prob_final"] = max(5, min(98, round(r["prob_base"] + r["ajuste_ia"], 1)))

                st.session_state.resultados_simulador = resultados
                st.session_state.simulador_usado = True
                _log_evento(st.session_state.get("user", ""), "simulador_usado", {"universidades": list(resultados.keys())})
                guardar_datos_usuario(st.session_state.get("user"))

    if "resultados_simulador" in st.session_state:
        resultados = st.session_state.resultados_simulador

        df_grafica = pd.DataFrame({
            "Universidad": list(resultados.keys()),
            "Probabilidad (%)": [r["prob_final"] for r in resultados.values()],
        })

        import altair as alt
        chart = alt.Chart(df_grafica).mark_line(point=True, color='#4A5D32', strokeWidth=3).encode(
            x=alt.X('Universidad:N', sort=list(resultados.keys())),
            y=alt.Y('Probabilidad (%):Q', scale=alt.Scale(domain=[0, 100]))
        ).properties(height=300)

        st.subheader("Curva de Probabilidad por Institución")
        st.altair_chart(chart, use_container_width=True)

        col_tabla, col_explicacion = st.columns([1.2, 0.8], gap="large")
        with col_tabla:
            st.subheader("Porcentajes de Aceptación Estimados")
            st.table(df_grafica)
        with col_explicacion:
            st.subheader("Análisis de Resultados")
            colores_confianza = {
                "oficial": ("#E1F5EE", "#0F6E56", "Dato oficial"),
                "parcial": ("#FAEEDA", "#854F0B", "Parcialmente oficial"),
                "estimado": ("#F1EFE8", "#5F5E5A", "Estimado, sin fuente pública"),
            }
            for nombre_uni, r in resultados.items():
                bg, color_texto, etiqueta = colores_confianza.get(r["confianza"], ("#F1EFE8", "#5F5E5A", ""))
                st.markdown(
                    f"""<div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:6px;">
                        <span style="font-weight:600; font-size:0.95rem;">{nombre_uni}</span>
                        <span style="font-weight:600; font-size:0.95rem;">{r['prob_final']}%</span>
                    </div>
                    <span style="background:{bg}; color:{color_texto}; font-size:0.72rem; font-weight:600;
                        padding:3px 10px; border-radius:12px;">{etiqueta}</span>""",
                    unsafe_allow_html=True,
                )
                if r["justificacion_ia"]:
                    st.caption(f"Hugo: {r['justificacion_ia']}")
                st.markdown("<div style='margin-bottom:14px;'></div>", unsafe_allow_html=True)
            st.caption("Las probabilidades 'estimadas' usan referencias razonables ante la falta de datos públicos de la universidad; no representan una cifra oficial.")
    else:
        st.info("Captura tu promedio y examen arriba y da clic en \"Calcular mis probabilidades\" para ver tu gráfica personalizada.")

# =================================================================
# PANEL DE ADMINISTRADOR / UNIVERSIDADES
# =================================================================
# Todas estas vistas están protegidas por el guard de acceso definido junto a
# PANEL_ADMIN_PAGES (arriba): solo entra quien tiene rol 'admin' o 'universidad'.

# --- VISTA: RESUMEN GENERAL ---
elif st.session_state.page == "panel_admin":
    _df_panel = _panel_dataframe_alumnos()
    if es_universidad():
        _panel_header(f"Resumen — {rol_universidad_nombre()}", "Solo alumnos que te seleccionaron como universidad de interés y dieron su consentimiento.")
    else:
        _panel_header("Resumen general", "Qué tanto se está usando Uniwebmx ahora mismo.")

    if _df_panel.empty:
        st.info("Todavía no hay datos de alumnos en este alcance.")
    else:
        _total = len(_df_panel)
        _perfil_ok = int(_df_panel["perfil_completo"].sum())
        _simulador = int(_df_panel["simulador_usado"].sum())
        _mensajes = sum(1 for h in _df_panel["historial_chat"] for m in (h or []) if m.get("role") == "user")
        _con_chat = sum(1 for h in _df_panel["historial_chat"] if any(m.get("role") == "user" for m in (h or [])))

        c1, c2, c3 = st.columns(3)
        c1.metric("Alumnos", _total)
        c2.metric("Perfil completo", f"{_perfil_ok}/{_total}")
        c3.metric("Usaron el simulador", f"{_simulador}/{_total}")

        c5, c6, c7 = st.columns(3)
        c5.metric("Mensajes enviados a Hugo", _mensajes)
        c6.metric("Alumnos que le han hablado a Hugo", f"{_con_chat}/{_total}")
        c7.metric("Promedio de mensajes por alumno activo", round(_mensajes / _con_chat, 1) if _con_chat else 0)

        st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)
        _df_export = _df_panel.copy()
        _df_export["mensajes_a_hugo"] = _df_export["historial_chat"].apply(
            lambda h: sum(1 for m in (h or []) if m.get("role") == "user")
        )
        _cols_export = ["username", "perfil_edad", "perfil_carreras", "perfil_universidades_interes",
                        "perfil_preparatoria", "perfil_completo", "simulador_usado", "mensajes_a_hugo"]
        st.download_button(
            "Descargar reporte (CSV)",
            data=_df_export[_cols_export].to_csv(index=False).encode("utf-8"),
            file_name=f"uniwebmx_resumen_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )

        st.markdown("<div style='margin-top:0.5rem;'></div>", unsafe_allow_html=True)
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("##### Top 5 carreras de interés")
            _tc = list(_panel_contar_frecuencias(_df_panel, "perfil_carreras").items())[:5]
            if _tc:
                st.bar_chart(pd.DataFrame(_tc, columns=["Carrera", "Alumnos"]).set_index("Carrera"))
            else:
                st.caption("Aún no hay suficientes datos.")
        with col_b:
            st.markdown("##### Top 5 universidades de interés")
            _tu = list(_panel_universidades_de_interes(_df_panel).items())[:5]
            if _tu:
                st.bar_chart(pd.DataFrame(_tu, columns=["Universidad", "Alumnos"]).set_index("Universidad"))
            else:
                st.caption("Aún no hay suficientes datos.")

        st.markdown("<div style='margin-top:0.5rem;'></div>", unsafe_allow_html=True)
        st.markdown("##### Preparatorias de origen")
        _tp = list(_panel_contar_frecuencias_simple(_df_panel, "perfil_preparatoria").items())
        if _tp:
            col_tp1, col_tp2 = st.columns([1.3, 1])
            with col_tp1:
                st.bar_chart(pd.DataFrame(_tp, columns=["Preparatoria", "Alumnos"]).set_index("Preparatoria"))
            with col_tp2:
                st.dataframe(pd.DataFrame(_tp, columns=["Preparatoria", "Alumnos"]), use_container_width=True, hide_index=True)
        else:
            st.caption("Aún no hay suficientes datos.")

        st.caption("Los datos se actualizan cada 5 minutos. Si acabas de registrar un alumno nuevo, puede tardar en aparecer.")

        st.markdown("<div style='margin-top:2rem;'></div>", unsafe_allow_html=True)
        st.markdown("##### Tendencia — últimos 30 días")
        _usernames_scope = set(_df_panel["username"]) if es_universidad() else None
        _eventos_30d = _panel_cargar_eventos(30)
        if _eventos_30d.empty:
            st.caption("Todavía no hay eventos registrados con fecha. Esto empieza a llenarse a partir de ahora (registros, logins, mensajes a Hugo, uso del simulador).")
        else:
            _tabs_tend = st.tabs(["Registros", "Logins", "Mensajes a Hugo", "Uso del simulador"])
            for _tab, _tipo in zip(_tabs_tend, ["registro", "login", "mensaje_chat", "simulador_usado"]):
                with _tab:
                    _serie = _panel_serie_diaria(_eventos_30d, _tipo, _usernames_scope)
                    if _serie.empty:
                        st.caption("Sin datos todavía en los últimos 30 días.")
                    else:
                        st.line_chart(_serie)

# --- VISTA: USO DE HUGO (CHAT) ---
elif st.session_state.page == "panel_chat":
    _df_panel = _panel_dataframe_alumnos()
    _panel_header("Uso de Hugo (chat)", "Qué tan útil y qué tanto se está usando el consultor de IA.")
    if _df_panel.empty:
        st.info("Todavía no hay datos de alumnos en este alcance.")
    else:
        _df_panel = _df_panel.copy()
        _df_panel["mensajes_usuario"] = _df_panel["historial_chat"].apply(
            lambda h: sum(1 for m in (h or []) if m.get("role") == "user")
        )
        _total = len(_df_panel)
        _activos = int((_df_panel["mensajes_usuario"] > 0).sum())
        c1, c2, c3 = st.columns(3)
        c1.metric("Alumnos que han usado a Hugo", f"{_activos}/{_total}")
        c2.metric("Mensajes totales", int(_df_panel["mensajes_usuario"].sum()))
        c3.metric("Consultas registradas hoy (contador diario)", int(_df_panel["contador_consultas"].sum()))

        st.markdown("##### Alumnos más activos con Hugo")
        _top_activos = _df_panel[_df_panel["mensajes_usuario"] > 0].sort_values("mensajes_usuario", ascending=False)
        _cols_mostrar = ["username", "mensajes_usuario"] if es_admin() else ["mensajes_usuario"]
        if not _top_activos.empty:
            st.dataframe(_top_activos[_cols_mostrar].head(20), use_container_width=True, hide_index=True)
        else:
            st.caption("Todavía nadie le ha escrito a Hugo en este alcance.")
        st.caption("Nota: el 'contador diario' se reinicia cada día, así que puede ser menor a los mensajes totales acumulados.")

        st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)
        st.markdown("##### Mensajes a Hugo por día (últimos 30 días)")
        _usernames_scope_chat = set(_df_panel["username"]) if es_universidad() else None
        _serie_chat = _panel_serie_diaria(_panel_cargar_eventos(30), "mensaje_chat", _usernames_scope_chat)
        if _serie_chat.empty:
            st.caption("Todavía no hay suficientes datos de los últimos 30 días.")
        else:
            st.line_chart(_serie_chat)

# --- VISTA: USO DEL SIMULADOR ---
elif st.session_state.page == "panel_simulador":
    _df_panel = _panel_dataframe_alumnos()
    _panel_header("Uso del simulador", "Qué tanto se usa y qué tan optimistas o realistas son los resultados.")
    if _df_panel.empty:
        st.info("Todavía no hay datos de alumnos en este alcance.")
    else:
        _total = len(_df_panel)
        _usado = int(_df_panel["simulador_usado"].sum())
        c1, c2 = st.columns(2)
        c1.metric("Alumnos que usaron el simulador", f"{_usado}/{_total}")
        c2.metric("% de adopción", f"{round(100*_usado/_total, 1) if _total else 0}%")

        st.markdown("##### Probabilidad promedio estimada por universidad (según el simulador)")
        _promedios_uni = {}
        for res in _df_panel["resultados_simulador"]:
            for uni, info in (res or {}).items():
                if isinstance(info, dict) and info.get("prob_final") is not None:
                    _promedios_uni.setdefault(uni, []).append(info["prob_final"])
        if _promedios_uni:
            _tabla = pd.DataFrame(
                [(u, round(sum(v)/len(v), 1), len(v)) for u, v in _promedios_uni.items()],
                columns=["Universidad", "Probabilidad promedio (%)", "Alumnos"],
            ).sort_values("Alumnos", ascending=False)
            st.dataframe(_tabla, use_container_width=True, hide_index=True)
        else:
            st.caption("Todavía no hay suficientes resultados del simulador en este alcance.")

        st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)
        st.markdown("##### Uso del simulador por día (últimos 30 días)")
        _usernames_scope_sim = set(_df_panel["username"]) if es_universidad() else None
        _serie_sim = _panel_serie_diaria(_panel_cargar_eventos(30), "simulador_usado", _usernames_scope_sim)
        if _serie_sim.empty:
            st.caption("Todavía no hay suficientes datos de los últimos 30 días.")
        else:
            st.line_chart(_serie_sim)

# --- VISTA: CARRERAS Y UNIVERSIDADES ---
elif st.session_state.page == "panel_carreras":
    _df_panel = _panel_dataframe_alumnos()
    _panel_header("Carreras y universidades", "Quién aplica a qué, en números.")
    if _df_panel.empty:
        st.info("Todavía no hay datos de alumnos en este alcance.")
    else:
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("##### Top carreras de interés")
            _tc = _panel_contar_frecuencias(_df_panel, "perfil_carreras")
            if _tc:
                _df_tc = pd.DataFrame(list(_tc.items()), columns=["Carrera", "Alumnos"])
                st.bar_chart(_df_tc.set_index("Carrera"))
                st.dataframe(_df_tc, use_container_width=True, hide_index=True)
                st.download_button(
                    "Descargar carreras (CSV)",
                    data=_df_tc.to_csv(index=False).encode("utf-8"),
                    file_name="uniwebmx_top_carreras.csv",
                    mime="text/csv",
                    key="dl_carreras",
                )
            else:
                st.caption("Aún no hay suficientes datos.")
        with col_b:
            st.markdown("##### Top universidades de interés")
            _tu = _panel_universidades_de_interes(_df_panel)
            if _tu:
                _df_tu = pd.DataFrame(list(_tu.items()), columns=["Universidad", "Alumnos"])
                st.bar_chart(_df_tu.set_index("Universidad"))
                st.dataframe(_df_tu, use_container_width=True, hide_index=True)
                st.download_button(
                    "Descargar universidades (CSV)",
                    data=_df_tu.to_csv(index=False).encode("utf-8"),
                    file_name="uniwebmx_top_universidades.csv",
                    mime="text/csv",
                    key="dl_universidades",
                )
            else:
                st.caption("Aún no hay suficientes datos.")

# --- VISTA: PERFILES POR UNIVERSIDAD (análisis con Hugo) ---

# --- VISTA: PERFILES POR UNIVERSIDAD (análisis con Hugo) — solo panel de administrador ---
elif st.session_state.page == "panel_perfiles":
    _df_panel = _panel_dataframe_alumnos()
    _panel_header("Perfiles por universidad", "Hugo analiza, en agregado y de forma anónima, quién y por qué aplica a cada universidad.")
    if _df_panel.empty:
        st.info("Todavía no hay datos de alumnos en este alcance.")
    else:
        for _uni in list(UNIVERSIDADES_DATA.keys()):
            _panel_render_bloque_perfil_ia(_uni, _df_panel, expanded=False)

# --- VISTA: CARRERAS Y PERFILES — vista combinada para el panel de universidad ---
elif st.session_state.page == "panel_carreras_perfiles":
    _df_panel = _panel_dataframe_alumnos()
    _panel_header("Carreras y perfiles", "Qué carreras buscan tus alumnos interesados, y el análisis de perfil que arma Hugo.")
    if _df_panel.empty:
        st.info("Todavía no hay datos de alumnos en este alcance.")
    else:
        st.markdown("##### Top carreras de interés")
        _tc_cp = _panel_contar_frecuencias(_df_panel, "perfil_carreras")
        if _tc_cp:
            _df_tc_cp = pd.DataFrame(list(_tc_cp.items()), columns=["Carrera", "Alumnos"])
            st.bar_chart(_df_tc_cp.set_index("Carrera"))
            st.dataframe(_df_tc_cp, use_container_width=True, hide_index=True)
            st.download_button(
                "Descargar carreras (CSV)",
                data=_df_tc_cp.to_csv(index=False).encode("utf-8"),
                file_name="uniwebmx_top_carreras.csv",
                mime="text/csv",
                key="dl_carreras_cp",
            )
        else:
            st.caption("Aún no hay suficientes datos.")

        st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)
        st.markdown("##### Perfil de tus alumnos, analizado por Hugo")
        _panel_render_bloque_perfil_ia(rol_universidad_nombre(), _df_panel, expanded=True)

# --- VISTA: CONSULTOR HUGO (chat sobre los datos agregados) ---
elif st.session_state.page == "panel_consultor":
    _df_panel = _panel_dataframe_alumnos()
    _panel_header("Consultor Hugo", "Pregúntale a Hugo sobre el uso y los perfiles de tus alumnos.")

    if "panel_historial_consultor" not in st.session_state:
        st.session_state.panel_historial_consultor = [
            {"role": "assistant", "content": "Hola, soy Hugo en modo consultor. Puedo ayudarte a interpretar el uso de la plataforma, qué carreras y universidades son más populares, o qué tan bien está funcionando el producto. ¿Qué quieres saber?"}
        ]

    for _msg in st.session_state.panel_historial_consultor:
        with st.chat_message(_msg["role"]):
            st.write(_msg["content"])

    _pregunta_panel = st.chat_input("Pregúntale algo a Hugo sobre tus datos...")
    if _pregunta_panel:
        st.session_state.panel_historial_consultor.append({"role": "user", "content": _pregunta_panel})
        with st.chat_message("user"):
            st.write(_pregunta_panel)
        with st.chat_message("assistant"):
            with st.spinner("Pensando..."):
                _respuesta_panel = _panel_responder_consultor(_pregunta_panel, _df_panel, st.session_state.panel_historial_consultor)
                st.write(_respuesta_panel)
        st.session_state.panel_historial_consultor.append({"role": "assistant", "content": _respuesta_panel})

# --- VISTA: USUARIOS Y ROLES (solo admin) ---
elif st.session_state.page == "panel_usuarios":
    _panel_header("Usuarios y roles", "Dale acceso al Panel a tu equipo o a una universidad, sin tocar Supabase directamente.")

    st.markdown("##### Cuentas con acceso al Panel")
    try:
        _res_roles = supabase_client.table("usuarios").select(
            "username, email, rol, universidad_asignada"
        ).neq("rol", "alumno").execute()
        _df_roles = pd.DataFrame(_res_roles.data or [])
    except Exception as e:
        _df_roles = pd.DataFrame()
        st.error(f"No se pudo cargar la lista: {e}")
    if not _df_roles.empty:
        st.dataframe(_df_roles, use_container_width=True, hide_index=True)
    else:
        st.caption("Todavía nadie más tiene rol admin o universidad.")

    st.markdown("<div style='margin-top:1.8rem;'></div>", unsafe_allow_html=True)
    st.markdown("##### Cambiar el rol de una cuenta")
    _buscar_user = st.text_input("Usuario o correo exacto", key="panel_usuarios_buscar", placeholder="ej. jpkishi o jp@correo.com")

    if _buscar_user.strip():
        _term = _buscar_user.strip()
        try:
            _res_buscar = supabase_client.table("usuarios").select(
                "username, email, rol, universidad_asignada"
            ).or_(f"username.eq.{_term},email.eq.{_term}").execute()
        except Exception as e:
            _res_buscar = None
            st.error(f"No se pudo buscar: {e}")

        if _res_buscar is not None and not _res_buscar.data:
            st.warning("No encontré ninguna cuenta con ese usuario o correo (debe ser exacto).")
        elif _res_buscar is not None:
            _fila = _res_buscar.data[0]
            _opciones_rol = ["alumno", "admin", "universidad"]
            _opciones_uni = [""] + list(UNIVERSIDADES_DATA.keys())
            _rol_actual = _fila.get("rol", "alumno") or "alumno"
            _uni_actual = _fila.get("universidad_asignada") or ""

            st.markdown(f"**Usuario:** {_fila['username']}  ·  **Correo:** {_fila.get('email', '') or 'sin correo'}  ·  **Rol actual:** `{_rol_actual}`" + (f" ({_uni_actual})" if _uni_actual else ""))

            with st.form(f"form_rol_{_fila['username']}"):
                _nuevo_rol = st.selectbox("Nuevo rol", _opciones_rol, index=_opciones_rol.index(_rol_actual) if _rol_actual in _opciones_rol else 0)
                _nueva_uni = st.selectbox(
                    "Universidad asignada (solo si el rol es 'universidad')",
                    _opciones_uni,
                    index=_opciones_uni.index(_uni_actual) if _uni_actual in _opciones_uni else 0,
                )
                _guardar_rol = st.form_submit_button("Guardar cambios", use_container_width=True)

            if _guardar_rol:
                if _nuevo_rol == "universidad" and not _nueva_uni:
                    st.error("Selecciona a qué universidad corresponde esta cuenta.")
                elif _fila["username"] == st.session_state.get("user") and _nuevo_rol != "admin":
                    st.error("No puedes quitarte el rol de admin a ti mismo desde aquí (para que no te quedes fuera del Panel por accidente). Pídele a otro admin que lo haga.")
                else:
                    try:
                        supabase_client.table("usuarios").update({
                            "rol": _nuevo_rol,
                            "universidad_asignada": _nueva_uni if _nuevo_rol == "universidad" else None,
                        }).eq("username", _fila["username"]).execute()
                        _panel_cargar_datos_crudos.clear()
                        st.success(
                            f"Listo: {_fila['username']} ahora tiene rol '{_nuevo_rol}'"
                            + (f" asignado a {_nueva_uni}." if _nuevo_rol == "universidad" else ".")
                        )
                    except Exception as e:
                        st.error(f"No se pudo actualizar: {e}")
    else:
        st.caption("Escribe el usuario o correo exacto de la cuenta a la que le quieres cambiar el rol.")

# --- VISTA: CONFIRMACIÓN DEL TUTOR (doble opt-in para cuentas de menores de edad) ---
elif st.session_state.page == "confirmar_tutor":
    _token_tutor_url = st.query_params.get("token", "") or st.session_state.get("_token_url_pendiente", "")

    st.markdown("<div style='max-width:640px;margin:0 auto;padding-top:3rem;'>", unsafe_allow_html=True)
    st.markdown("<h1 style='font-size:2.2rem;font-weight:700;color:#1A1A1A;margin-bottom:0.4rem;'>Confirmación de tutor</h1>", unsafe_allow_html=True)

    if not _token_tutor_url:
        st.error("Enlace inválido. Revisa que copiaste el enlace completo del correo.")
    else:
        _res_tutor = supabase_client.table("usuarios").select(
            "username, email, tutor_nombre, tutor_email, tutor_confirmado, tutor_confirm_token_expiry"
        ).eq("tutor_confirm_token", _token_tutor_url).execute()

        if not _res_tutor.data:
            st.error("Este enlace no es válido o ya fue utilizado. Si crees que es un error, escríbenos.")
        else:
            _fila_tutor = _res_tutor.data[0]
            _expiry_tutor = _fila_tutor.get("tutor_confirm_token_expiry", "")
            _expiry_tutor_dt = datetime.fromisoformat(_expiry_tutor) if _expiry_tutor else None
            _ahora_tutor = datetime.now(timezone.utc)

            if _fila_tutor.get("tutor_confirmado"):
                st.success("Esta cuenta ya fue confirmada anteriormente. No necesitas hacer nada más.")
            elif _expiry_tutor_dt and _ahora_tutor > _expiry_tutor_dt:
                st.error("Este enlace expiró. Escríbenos para que te enviemos uno nuevo.")
            else:
                _alumno_username = _fila_tutor["username"]
                _alumno_email = _fila_tutor.get("email", "")
                _tutor_nombre_conf = _fila_tutor.get("tutor_nombre", "") or "tutor/a"

                st.markdown(
                    f"<p style='font-size:0.95rem;color:#444;line-height:1.7;margin-bottom:1.5rem;'>"
                    f"Hola {_tutor_nombre_conf}, estás confirmando la cuenta de <strong>{_alumno_username}</strong> "
                    f"({_alumno_email}). Antes de continuar, puedes revisar el "
                    f"<a href='/?page=aviso_privacidad' target='_blank' style='color:#4A5D32;font-weight:600;'>Aviso de Privacidad</a> "
                    f"y los <a href='/?page=terminos' target='_blank' style='color:#4A5D32;font-weight:600;'>Términos y Condiciones</a>.</p>",
                    unsafe_allow_html=True,
                )

                st.markdown(
                    "<p style='font-size:0.85rem;color:#666;line-height:1.6;margin-bottom:0.8rem;'>"
                    "Estas finalidades son opcionales e independientes entre sí. Puedes revocarlas cuando quieras "
                    "escribiéndonos.</p>",
                    unsafe_allow_html=True,
                )

                conf_hugo = st.checkbox(
                    "Acepto que las interacciones de mi hijo/a o representado/a con Hugo se usen para mejorar y "
                    "entrenar al asistente de IA de Uniwebmx.",
                    key="conf_tutor_hugo",
                )
                conf_unis = st.checkbox(
                    "Acepto que Uniwebmx comparta su información con las universidades que él/ella seleccione como "
                    "de su interés.",
                    key="conf_tutor_unis",
                )
                conf_promo = st.checkbox(
                    "Acepto que reciba correos sobre nuevas funciones, becas y contenido educativo de Uniwebmx.",
                    key="conf_tutor_promo",
                )

                if st.button("Confirmar autorización", use_container_width=True, key="conf_tutor_btn"):
                    supabase_client.table("usuarios").update({
                        "tutor_confirmado": True,
                        "consentimiento_hugo": conf_hugo,
                        "consentimiento_universidades": conf_unis,
                        "consentimiento_promocional": conf_promo,
                        "consentimientos_fecha": datetime.now(timezone.utc).isoformat(),
                        "tutor_confirm_token": None,
                        "tutor_confirm_token_expiry": None,
                    }).eq("username", _alumno_username).execute()
                    st.success("¡Listo! Tu confirmación quedó registrada. Gracias por acompañar a tu hijo/a en este proceso.")

    st.markdown("</div>", unsafe_allow_html=True)


elif st.session_state.page == "aviso_privacidad":
    st.markdown("""
    <div style="max-width:820px;margin:0 auto;padding-top:2rem;">
        <a href="/?page=inicio" target="_self" style="text-decoration:none;font-family:Montserrat,sans-serif;
            font-size:0.85rem;font-weight:600;color:#4A5D32;">&larr; Volver al inicio</a>
        <p style="font-size:0.8rem;font-weight:600;letter-spacing:0.12em;text-transform:uppercase;color:#4A5D32;margin-top:1.5rem;margin-bottom:0.5rem;">Legal</p>
        <h1 style="font-size:2.4rem;font-weight:700;color:#1A1A1A;letter-spacing:-0.02em;margin-bottom:0.3rem;">Aviso de Privacidad</h1>
        <p style="font-size:0.85rem;color:#999999;margin-bottom:2rem;">Última actualización: [fecha de publicación]</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(AVISO_PRIVACIDAD_MD)

# --- VISTA: TÉRMINOS Y CONDICIONES ---
elif st.session_state.page == "terminos":
    st.markdown("""
    <div style="max-width:820px;margin:0 auto;padding-top:2rem;">
        <a href="/?page=inicio" target="_self" style="text-decoration:none;font-family:Montserrat,sans-serif;
            font-size:0.85rem;font-weight:600;color:#4A5D32;">&larr; Volver al inicio</a>
        <p style="font-size:0.8rem;font-weight:600;letter-spacing:0.12em;text-transform:uppercase;color:#4A5D32;margin-top:1.5rem;margin-bottom:0.5rem;">Legal</p>
        <h1 style="font-size:2.4rem;font-weight:700;color:#1A1A1A;letter-spacing:-0.02em;margin-bottom:0.3rem;">Términos y Condiciones</h1>
        <p style="font-size:0.85rem;color:#999999;margin-bottom:2rem;">Última actualización: [fecha de publicación]</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(TERMINOS_MD)

# --- VISTA: CUENTA ELIMINADA ---
elif st.session_state.page == "cuenta_eliminada":
    st.markdown("""
    <div style="max-width:520px;margin:4rem auto;text-align:center;">
        <h1 style="font-size:1.8rem;font-weight:700;color:#1A1A1A;margin-bottom:0.8rem;">Tu cuenta fue eliminada</h1>
        <p style="font-size:0.95rem;color:#666;line-height:1.6;margin-bottom:2rem;">
            Borramos tu cuenta, tu historial con Hugo, tus resultados del simulador y el resto de tu
            información. Si cambias de opinión, siempre puedes crear una cuenta nueva.
        </p>
        <a href="/?page=inicio" target="_self" style="display:inline-block;background:#4A5D32;color:#fff;
            padding:12px 28px;border-radius:8px;text-decoration:none;font-family:Montserrat,sans-serif;
            font-size:0.9rem;font-weight:600;">Volver al inicio</a>
    </div>
    """, unsafe_allow_html=True)

# =================================================================
# PIE DE PÁGINA (SOLO PÚBLICO)
# =================================================================
if not es_hub and not es_panel:
   st.markdown('<div style="margin-top: 5rem;"></div>', unsafe_allow_html=True)
   col_foot1, col_foot2, col_foot3 = st.columns([3, 3, 2])
   with col_foot1:
       st.markdown("<p style='color: #666666; font-size: 0.85rem;'>© 2026 Uniwebmx. Todos los derechos reservados.</p>", unsafe_allow_html=True)
   with col_foot2:
       st.markdown("""<p style='color: #666666; font-size: 0.85rem; text-align: center;'>
           <a href="/?page=aviso_privacidad" target="_self" style="color:#666666;text-decoration:none;">Aviso de Privacidad</a>
           &nbsp;|&nbsp;
           <a href="/?page=terminos" target="_self" style="color:#666666;text-decoration:none;">Términos y Condiciones</a>
       </p>""", unsafe_allow_html=True)
   with col_foot3:
       st.markdown("<p style='font-size: 0.85rem; text-align: right;'><a href='https://www.instagram.com/uniwebmx/' target='_blank' style='color:#4A5D32;font-weight:bold;text-decoration:none;'>Instagram</a> | <span style='color:#BBBBBB;'>LinkedIn</span> | <span style='color:#BBBBBB;'>TikTok</span></p>", unsafe_allow_html=True)