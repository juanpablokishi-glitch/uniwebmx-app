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
import stripe
import resend

# --- CONFIGURACIÓN DE LA API DE GEMINI ---
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# --- CLIENTE SUPABASE ---
@st.cache_resource
def get_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase_client = get_supabase()

# --- CLIENTE STRIPE ---
stripe.api_key = st.secrets["STRIPE_SECRET_KEY"]

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


def enviar_correo_bienvenida_pro(correo_usuario: str):
    """Correo de confirmación de pago Pro."""
    _enviar_correo(
        to=correo_usuario,
        subject="Tu cuenta Pro en Uniwebmx esta activa",
        html=f"""
        <div style="font-family:Montserrat,Arial,sans-serif;max-width:560px;margin:0 auto;
            background:#ffffff;border:1px solid #EAEAEA;border-radius:16px;overflow:hidden;">
        <div style="text-align:center;padding:28px 32px 20px;border-bottom:1px solid #EAEAEA;margin-bottom:28px;">
            <img src="https://qbtbcvwwfqoghgvyhztd.supabase.co/storage/v1/object/public/assets/logo.png" alt="Uniwebmx" style="height:36px;display:inline-block;">
        </div>
            <div style="padding:0 32px 36px;">
            <h1 style="font-size:1.5rem;font-weight:700;color:#1A1A1A;margin-bottom:0.75rem;">
                Bienvenido a Uniwebmx Pro
            </h1>
            <p style="font-size:0.95rem;color:#444;line-height:1.7;margin-bottom:1.5rem;">
                Hola <strong>{correo_usuario}</strong>, tu pago fue confirmado. Tu cuenta
                ya tiene acceso completo a todo lo que Pro incluye:
            </p>
            <table style="width:100%;border-collapse:collapse;margin-bottom:1.8rem;">
                <tr><td style="padding:8px 0;border-bottom:1px solid #F0F0F0;font-size:0.9rem;color:#444;">Locker Digital sin limite de almacenamiento</td></tr>
                <tr><td style="padding:8px 0;border-bottom:1px solid #F0F0F0;font-size:0.9rem;color:#444;">20 mensajes diarios con Hugo</td></tr>
                <tr><td style="padding:8px 0;font-size:0.9rem;color:#444;">Simulador estadistico ilimitado</td></tr>
            </table>
            <a href="{BASE_URL}" style="display:inline-block;background:#4A5D32;color:#fff;
                font-size:0.9rem;font-weight:600;padding:13px 32px;border-radius:8px;
                text-decoration:none;letter-spacing:0.01em;">
                Ir a mi cuenta
            </a>
            <p style="font-size:0.78rem;color:#999;margin-top:2rem;line-height:1.6;">
                Si tienes alguna duda, responde este correo.<br>— El equipo de Uniwebmx
            </p>
            </div>
        </div>
        """,
    )


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

# URL base de la app. En local usa localhost; en producción, define BASE_URL en tus secrets
# (ej. BASE_URL = "https://tuapp.streamlit.app") para que Stripe regrese al lugar correcto.
BASE_URL = st.secrets.get("BASE_URL", "http://localhost:8501")

# Duración del token de sesión (no del username) que viaja en la URL para los nav links.
SESSION_TOKEN_DIAS = 30

def crear_sesion_stripe(price_id, username, session_token):
    """Crea una Checkout Session de Stripe y devuelve la URL."""
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{BASE_URL}/?page=pago_exitoso&t={session_token}&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{BASE_URL}/?page=planes",
        metadata={"username": username},
        subscription_data={"metadata": {"username": username}},
    )
    # Guardamos el session_id como "pendiente": si el usuario cierra la
    # pestaña antes de volver por success_url, verificar_pago_pendiente()
    # lo revisará en su siguiente login (ver definición más abajo).
    try:
        supabase_client.table("usuarios").update(
            {"pending_stripe_session_id": session.id}
        ).eq("username", username).execute()
    except Exception:
        pass
    return session.url

def verificar_y_activar_pago(session_id, username_esperado):
    """
    Verifica directamente con Stripe (sin depender de un webhook) que la Checkout
    Session realmente se pagó, y si es así, activa el plan 'pro' en Supabase.
    Devuelve True si quedó activado, False si no se pudo verificar el pago.
    """
    if not session_id:
        return False
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception:
        return False

    pagado = getattr(session, "payment_status", None) == "paid" or getattr(session, "status", None) == "complete"
    _meta = getattr(session, "metadata", None) or {}
    username_sesion = _meta.get("username") if isinstance(_meta, dict) else getattr(_meta, "username", None)

    if pagado and username_sesion and username_sesion == username_esperado:
        subscription_id = getattr(session, "subscription", None)
        update_data = {"plan": "pro"}
        if subscription_id:
            update_data["stripe_subscription_id"] = subscription_id
        supabase_client.table("usuarios").update(update_data).eq("username", username_esperado).execute()
        return True
    return False

def verificar_pago_pendiente(username):
    """
    Red de seguridad para el caso en que el usuario pagó en Stripe pero
    cerró la pestaña (o perdió conexión) antes de que se completara el
    redirect a 'pago_exitoso', dejando su cuenta en 'gratis' a pesar de
    haber pagado. La revisamos en cada login: si hay un session_id
    pendiente guardado y el plan sigue en 'gratis', lo verificamos contra
    Stripe igual que en verificar_y_activar_pago(). Devuelve True si el
    plan quedó activado en esta llamada.
    Requiere en Supabase, tabla "usuarios": columna "pending_stripe_session_id" (text, nullable).
    """
    if not username:
        return False
    try:
        res = supabase_client.table("usuarios").select(
            "pending_stripe_session_id, plan"
        ).eq("username", username).execute()
    except Exception:
        return False
    if not res.data:
        return False

    pending_id = res.data[0].get("pending_stripe_session_id")
    plan_actual = res.data[0].get("plan")

    if not pending_id or plan_actual == "pro":
        if pending_id:
            # Ya no hace falta seguir cargando este campo
            try:
                supabase_client.table("usuarios").update(
                    {"pending_stripe_session_id": None}
                ).eq("username", username).execute()
            except Exception:
                pass
        return False

    activado = verificar_y_activar_pago(pending_id, username)
    try:
        supabase_client.table("usuarios").update(
            {"pending_stripe_session_id": None}
        ).eq("username", username).execute()
    except Exception:
        pass
    if activado and "_correo_pro_enviado" not in st.session_state:
        try:
            _res_email = supabase_client.table("usuarios").select("email").eq("username", username).execute()
            _email_pro = (_res_email.data[0].get("email") or "") if _res_email.data else ""
            if _email_pro:
                enviar_correo_bienvenida_pro(_email_pro)
            st.session_state["_correo_pro_enviado"] = True
        except Exception:
            pass
    return activado

def procesar_webhook_stripe(payload, sig_header):
    """
    Verifica y procesa el webhook de Stripe. NOTA: esta función queda lista para el
    día que se exponga un endpoint real (ej. con un servicio aparte tipo FastAPI/Cloud
    Function) que reciba los eventos de Stripe — Streamlit por sí solo no expone rutas
    HTTP para recibir webhooks, así que por ahora la activación real del plan ocurre
    en verificar_y_activar_pago() al momento del redirect de pago_exitoso.
    """
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, st.secrets["STRIPE_WEBHOOK_SECRET"]
        )
    except Exception:
        return False
    if event["type"] == "checkout.session.completed":
        username = event["data"]["object"]["metadata"].get("username")
        if username:
            supabase_client.table("usuarios").update({"plan": "pro"}).eq("username", username).execute()
    elif event["type"] in ("customer.subscription.deleted", "customer.subscription.paused"):
        # Cuando cancela o pausa, regresa a gratis
        subs = event["data"]["object"].get("metadata", {})
        username = subs.get("username")
        if username:
            supabase_client.table("usuarios").update({"plan": "gratis"}).eq("username", username).execute()
    return True

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

def save_user(username, password, email=""):
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    supabase_client.table("usuarios").upsert({
        "username": username,
        "password_hash": hashed,
        "email": email,
        "plan": "gratis"
    }).execute()

def verify_user(username, password):
    res = supabase_client.table("usuarios").select("password_hash").eq("username", username).execute()
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


def obtener_plan_usuario(username):
    """Devuelve 'gratis' o 'pro' según la columna plan en Supabase."""
    try:
        res = supabase_client.table("usuarios").select("plan").eq("username", username).execute()
        if res.data:
            return res.data[0].get("plan", "gratis")
    except Exception:
        pass
    return "gratis"

# Límites por plan
LIMITES = {
    "gratis": {"hugo_diario": 3,  "simulador_total": 1,  "locker_mb": 50},
    "pro":    {"hugo_diario": 20, "simulador_total": None, "locker_mb": None},
}

def get_plan():
    """Devuelve el plan activo del usuario en sesión."""
    return st.session_state.get("plan_usuario", "gratis")

def _banner_upgrade(mensaje):
    st.warning(f"⭐ {mensaje}  →  ve a **Planes** en el menú para mejorar tu cuenta.")


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
    datos = {
        "historial_chat": st.session_state.get("historial_chat", []),
        "contador_consultas": st.session_state.get("contador_consultas", 0),
        "fecha_contador": st.session_state.get("fecha_contador", ""),
        # Documentos académicos
        "kardex": st.session_state.get("kárdex", {"nombre": None, "contenido": ""}),
        "ensayo": st.session_state.get("ensayo", {"nombre": None, "contenido": ""}),
        "curriculum": st.session_state.get("curriculum", {"nombre": None, "contenido": ""}),
        "cartas": st.session_state.get("cartas", {"nombre": None, "contenido": ""}),
        "portafolio": st.session_state.get("portafolio", {"nombre": None, "contenido": ""}),
        # Documentos personales
        "acta": st.session_state.get("acta", {"nombre": None, "contenido": ""}),
        "curp": st.session_state.get("curp", {"nombre": None, "contenido": ""}),
        "identificacion": st.session_state.get("identificacion", {"nombre": None, "contenido": ""}),
        "foto": st.session_state.get("foto", {"nombre": None, "contenido": ""}),
        "comprobante": st.session_state.get("comprobante", {"nombre": None, "contenido": ""}),
        "resultados_simulador": st.session_state.get("resultados_simulador", None),
        "unis_seleccionadas": st.session_state.get("unis_seleccionadas", []),
        "correo_conectado": st.session_state.get("correo_conectado", ""),
        "proveedor_correo": st.session_state.get("proveedor_correo", ""),
        "perfil_completo": st.session_state.get("perfil_completo", False),
        "perfil_nombre": st.session_state.get("perfil_nombre", ""),
        "perfil_edad": st.session_state.get("perfil_edad", None),
        "perfil_carreras": st.session_state.get("perfil_carreras", []),
        "perfil_universidades_interes": st.session_state.get("perfil_universidades_interes", []),
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
    except Exception:
        pass


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
    st.session_state.simulador_usado = datos.get("simulador_usado", False)
    # Plan del usuario
    st.session_state.plan_usuario = obtener_plan_usuario(username)


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
       # Redirect de Stripe tras pago: preservar token y session_id en session_state
       # antes de limpiar la URL, porque Stripe no usa el formato ?nav=
       if _page_val == "pago_exitoso":
           _stripe_token = query_params.get("t", "")
           _stripe_sid   = query_params.get("session_id", "")
           if _stripe_token:
               _stripe_user = validar_sesion_token(_stripe_token)
               if _stripe_user:
                   st.session_state.logged_in = True
                   st.session_state.user = _stripe_user
                   st.session_state.session_token = _stripe_token
                   restaurar_sesion_usuario(_stripe_user)
           if _stripe_sid:
               st.session_state["_stripe_session_id"] = _stripe_sid
   else:
       st.session_state.page = "inicio"
   st.query_params.clear()


def cambiar_pagina(nombre_pagina):
   st.session_state.page = nombre_pagina
   st.rerun()


# --- PROCESAMIENTO DE IMÁGENES ---
def get_base64_image(image_path):
   if os.path.exists(image_path):
       with open(image_path, "rb") as img_file:
           return base64.b64encode(img_file.read()).decode()
   return None


logo_encoded = get_base64_image("logo.png")
logo_pro_encoded = get_base64_image("logo_pro.png")
fondo_inicio_encoded = get_base64_image("fondo_hero.png")
fondo_locker_encoded = get_base64_image("fondo_locker.png")
fondo_auth_encoded = get_base64_image("fondo_auth.png")


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
# Determinar si el usuario está dentro del Hub
es_hub = st.session_state.page in ["locker", "chat", "simulador", "mi_aplicacion", "mensajes"]


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
   {"[data-testid='stSidebar'] {display: none;}" if not es_hub else ""}
  
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
  
   /* --- CHAT IDENTICO A GEMINI --- */
   .gemini-chat-container {{
       max-width: 800px;
       margin: 0 auto;
       padding-top: 1rem;
       padding-bottom: 6rem;
   }}
   .gemini-row {{
       margin-bottom: 2.5rem;
       line-height: 1.7;
   }}
   .gemini-user-label {{
       font-weight: 700;
       font-size: 1rem;
       color: #1A1A1A;
       margin-bottom: 6px;
   }}
   .gemini-hugo-label {{
       font-weight: 700;
       font-size: 1rem;
       color: #4A5D32;
       margin-bottom: 6px;
   }}
   .gemini-text {{
       font-size: 1.05rem;
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
if not es_hub and st.session_state.page != "onboarding":
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
           <a href="/?page=planes" target="_self" style="font-size:0.9rem;font-weight:500;color:#1A1A1A;text-decoration:none;">Planes</a>
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
   _es_pro = st.session_state.get("plan_usuario", "gratis") == "pro"
   _logo_sb = logo_pro_encoded if (_es_pro and logo_pro_encoded) else logo_encoded
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
       return f'''<a href="/?nav={page_key}&t={_sesion_t}" target="_self" style="
           display:flex;align-items:center;gap:10px;
           padding:8px 10px;margin:1px 0;border-radius:6px;
           background:{bg};color:{color};
           font-family:Montserrat,sans-serif;font-size:0.85rem;font-weight:{fw};
           text-decoration:none;cursor:pointer;transition:background 0.1s;">
           <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;opacity:0.7;">
               {icon_path}
           </svg>{label}</a>'''

   _icon_locker = '<path d="M5 8a3 3 0 0 1 3-3h8a3 3 0 0 1 3 3v11a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1z"/><path d="M10 11h4M12 9v4"/>'
   _icon_chat   = '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>'
   _icon_sim    = '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>'
   _icon_app    = '<path d="M3 7l9-4 9 4-9 4-9-4z"/><path d="M3 7v10l9 4 9-4V7"/><path d="M12 11v10"/>'
   _icon_msg    = '<path d="M4 4h16v12H7l-3 3z"/><path d="M7 9h10M7 12h6"/>'
   _icon_planes = '<path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>'

   _label_style = "font-size:10px;letter-spacing:0.09em;text-transform:uppercase;color:#BBBBBB;padding:14px 10px 4px;margin:0;font-family:Montserrat,sans-serif;"

   with st.sidebar:
       st.markdown(f"""
       <div style="padding:20px 16px 14px;border-bottom:0.5px solid #EAEAEA;margin-bottom:6px;">{_logo_html}</div>
       <p style="{_label_style}">Tu espacio</p>
       <div style="padding:0 10px;">
           {_sb_item("Locker Digital", "locker", _icon_locker)}
           {_sb_item("Consultor IA",   "chat",   _icon_chat)}
           {_sb_item("Mi Aplicación",  "mi_aplicacion", _icon_app)}
           {_sb_item("Centro de Mensajes", "mensajes", _icon_msg)}
       </div>
       <p style="{_label_style}">Análisis</p>
       <div style="padding:0 10px;">
           {_sb_item("Simulador", "simulador", _icon_sim)}
       </div>
       <div style="border-top:0.5px solid #EAEAEA;margin:12px 16px 8px;"></div>
       <p style="{_label_style}">Cuenta</p>
       <div style="padding:0 10px;">
           {_sb_item("Planes", "planes", _icon_planes)}
       </div>
       <div style="border-top:0.5px solid #EAEAEA;margin:12px 16px 8px;"></div>
       """, unsafe_allow_html=True)

       # --- Perfil fijo al fondo de la sidebar (menú emergente hacia arriba) ---
       _plan_actual = st.session_state.get("plan_usuario", "gratis")
       _initials_sb = (_user[:2].upper()) if _user else "U"
       _badge_color = "#4A5D32" if _plan_actual == "pro" else "#AAAAAA"
       _badge_label = "PRO" if _plan_actual == "pro" else "GRATIS"
       _cancelar_url = "/?nav=__cancelar_sub__" if _plan_actual == "pro" else ""
       _cancel_item = f"""
           <div style="border-top:0.5px solid #EAEAEA;margin:4px 0;padding-top:4px;">
             <a href="/?nav=__cancelar_sub__" target="_self" style="display:flex;align-items:center;gap:8px;
                 padding:7px 10px;border-radius:6px;color:#C0392B;font-family:Montserrat,sans-serif;
                 font-size:0.82rem;font-weight:500;text-decoration:none;">
               <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                    stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                 <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
               </svg>Cancelar suscripción
             </a>
           </div>""" if _plan_actual == "pro" else ""

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
                 <span style="font-size:0.62rem;font-weight:700;background:{_badge_color};
                     color:#fff;padding:2px 9px;border-radius:20px;letter-spacing:0.06em;">{_badge_label}</span>
               </div>
               <a href="/?nav=__logout__" target="_self" style="display:flex;align-items:center;gap:9px;
                   padding:8px 14px;color:#555;font-family:Montserrat,sans-serif;
                   font-size:0.82rem;font-weight:400;text-decoration:none;">
                 <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                      stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                   <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                   <polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
                 </svg>Cerrar sesión
               </a>
               {_cancel_item}
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
                 <div style="font-size:0.65rem;color:#999;margin-top:1px;">{_badge_label}</div>
               </div>
               <svg class="profile-chevron" width="13" height="13" viewBox="0 0 24 24" fill="none"
                    stroke="#999" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                 <polyline points="18 15 12 9 6 15"/>
               </svg>
             </label>
           </div>
           """, unsafe_allow_html=True)

           # Manejo de cancelación (nav token)
           if st.query_params.get("nav") == "__cancelar_sub__":
               if "_cancelar_sub_procesado" not in st.session_state:
                   st.session_state["_confirmar_cancelacion"] = True
                   st.session_state["_cancelar_sub_procesado"] = True

           if st.session_state.get("_confirmar_cancelacion"):
               with st.sidebar:
                   st.markdown("""
                   <div style="margin:0 4px;padding:12px 14px;background:#FFF5F5;border:1px solid #FECACA;
                       border-radius:10px;font-family:Montserrat,sans-serif;">
                     <div style="font-size:0.82rem;font-weight:600;color:#C0392B;margin-bottom:6px;">
                       ¿Cancelar suscripción?
                     </div>
                     <div style="font-size:0.78rem;color:#666;line-height:1.5;">
                       Seguirás teniendo Pro hasta que termine el período que ya pagaste.
                     </div>
                   </div>
                   """, unsafe_allow_html=True)
                   st.markdown("""
                   <style>
                   div[data-testid="stSidebarContent"] .cancelar-btns a {{
                       display:block;text-align:center;font-family:Montserrat,sans-serif;
                       font-size:0.82rem;font-weight:600;border-radius:8px;
                       padding:9px 0;text-decoration:none;margin-bottom:6px;
                   }}
                   </style>
                   <div class="cancelar-btns" style="margin:8px 4px 0;">
                   """, unsafe_allow_html=True)
                   col_si, col_no = st.columns(2)
                   with col_si:
                       st.markdown("""<a href="/?nav=__ejecutar_cancelacion__" target="_self"
                           style="display:block;text-align:center;font-family:Montserrat,sans-serif;
                           font-size:0.8rem;font-weight:600;border-radius:8px;padding:9px 0;
                           text-decoration:none;background:#C0392B;color:#fff;">
                           Sí, cancelar</a>""", unsafe_allow_html=True)
                   with col_no:
                       st.markdown("""<a href="/?nav=locker" target="_self"
                           style="display:block;text-align:center;font-family:Montserrat,sans-serif;
                           font-size:0.8rem;font-weight:600;border-radius:8px;padding:9px 0;
                           text-decoration:none;background:#F5F5F3;color:#1A1A1A;border:1px solid #E0E0E0;">
                           Mantener</a>""", unsafe_allow_html=True)
                   st.markdown("</div>", unsafe_allow_html=True)

           if st.query_params.get("nav") == "__ejecutar_cancelacion__":
               if "_cancelacion_ejecutada" not in st.session_state:
                   try:
                       res = supabase_client.table("usuarios").select("stripe_subscription_id").eq("username", _user).execute()
                       sub_id = res.data[0].get("stripe_subscription_id") if res.data else None
                       if sub_id:
                           stripe.Subscription.modify(sub_id, cancel_at_period_end=True)
                           st.session_state["_cancelacion_ejecutada"] = True
                           st.session_state["_confirmar_cancelacion"] = False
                           with st.sidebar:
                               st.markdown("""<div style="margin:0 4px;padding:10px 14px;background:#F0FFF4;
                                   border:1px solid #C8D4B8;border-radius:10px;font-family:Montserrat,sans-serif;
                                   font-size:0.8rem;color:#4A5D32;font-weight:500;">
                                   ✓ Suscripción cancelada correctamente.</div>""", unsafe_allow_html=True)
                       else:
                           with st.sidebar:
                               st.markdown("""<div style="margin:0 4px;padding:10px 14px;background:#FFF5F5;
                                   border:1px solid #FECACA;border-radius:10px;font-family:Montserrat,sans-serif;
                                   font-size:0.8rem;color:#C0392B;">
                                   No encontramos tu suscripción. Escríbenos a hola@uniwebmx.com</div>""",
                                   unsafe_allow_html=True)
                   except Exception as e:
                       with st.sidebar:
                           st.error(f"Error: {e}")

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
  
   col_card1, col_card2, col_card3 = st.columns(3)
   with col_card1:
       st.markdown("""
       <div class="card-beneficio">
           <h3>Locker Digital</h3>
           <p style='color: #444444; line-height: 1.5; margin-bottom:0;'>Tus logros en un solo espacio seguro. Sube tu kárdex, ensayos previos, diplomas y proyectos extracurriculares. Mantén tu historial listo para cualquier convocatoria.</p>
       </div>
       """, unsafe_allow_html=True)
   with col_card2:
       st.markdown("""
       <div class="card-beneficio">
           <h3>Consultor de IA</h3>
           <p style='color: #444444; line-height: 1.5; margin-bottom:0;'>Retroalimentación experta en tiempo real. Un guía inteligente que analiza tus documentos, corrige la estructura de tus ensayos de motivos y te dice qué mejorar.</p>
       </div>
       """, unsafe_allow_html=True)
   with col_card3:
       st.markdown("""
       <div class="card-beneficio">
           <h3>Simulador Estadístico</h3>
           <p style='color: #444444; line-height: 1.5; margin-bottom:0;'>Visualiza tus probabilidades reales. Compara tu perfil académico actual con las tendencias históricas de aceptación de las mejores universidades del país.</p>
       </div>
       """, unsafe_allow_html=True)


   # --- SECCIÓN ADICIONAL: QUIÉNES SOMOS Y MISIÓN ---
   st.markdown('<div class="divider-olivo"></div>', unsafe_allow_html=True)
   col_qs, col_ms = st.columns(2, gap="large")
   with col_qs:
       st.markdown("<h2>Quiénes Somos</h2>", unsafe_allow_html=True)
       st.markdown("""
       <p style='color: #444444; line-height: 1.7; font-size: 1.05rem;'>
           Somos un equipo interdisciplinario apasionado por democratizar y optimizar el acceso a la educación superior en México.
           Creamos tecnología con un enfoque humano para dotar a los estudiantes de herramientas de análisis y edición que antes eran exclusivas de consultorías privadas.
       </p>
       """, unsafe_allow_html=True)
   with col_ms:
       st.markdown("<h2>Nuestra Misión</h2>", unsafe_allow_html=True)
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


# --- VISTA: PLANES ---
elif st.session_state.page == "planes":
    st.markdown("""
    <div style="max-width:900px;margin:0 auto;padding-top:2rem;text-align:center;">
        <p style="font-size:0.8rem;font-weight:600;letter-spacing:0.12em;text-transform:uppercase;color:#4A5D32;margin-bottom:0.5rem;">Precios</p>
        <h1 style="font-size:2.8rem;font-weight:700;color:#1A1A1A;letter-spacing:-0.03em;margin-bottom:0.5rem;">El plan correcto para tu etapa</h1>
        <p style="font-size:1.1rem;color:#666666;line-height:1.7;margin-bottom:3.5rem;max-width:580px;margin-left:auto;margin-right:auto;">Sin letra chica. Pago único anual. Empieza gratis hoy.</p>
    </div>
    """, unsafe_allow_html=True)

    col_p1, col_espaciado, col_p2 = st.columns([1, 0.15, 1], gap="large")

    plan_css_base = "border:1px solid #EAEAEA;border-radius:12px;padding:32px 24px;background:#FFFFFF;height:100%;"
    plan_css_pro  = "border:2px solid #4A5D32;border-radius:12px;padding:32px 24px;background:#FFFFFF;height:100%;position:relative;"

    def check(texto):
        return f'<div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:10px;"><span style="color:#4A5D32;font-weight:700;flex-shrink:0;">✓</span><span style="font-size:0.9rem;color:#444444;">{texto}</span></div>'

    def cross(texto):
        return f'<div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:10px;"><span style="color:#CCCCCC;flex-shrink:0;">✗</span><span style="font-size:0.9rem;color:#BBBBBB;">{texto}</span></div>'

    with col_p1:
        st.markdown(f"""
        <div style="{plan_css_base}">
            <p style="font-size:0.75rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#888;margin-bottom:8px;">Gratis</p>
            <div style="margin-bottom:6px;"><span style="font-size:2.4rem;font-weight:700;color:#1A1A1A;">$0</span></div>
            <p style="font-size:0.85rem;color:#888;margin-bottom:4px;">Para explorar la plataforma</p>
            <p style="font-size:0.78rem;color:#BBBBBB;margin-bottom:24px;">Sin tarjeta de crédito</p>
            <div style="border-top:1px solid #F0F0F0;padding-top:20px;">
                {check("Acceso al ranking de universidades")}
                {check("Blog completo de admisiones")}
                {check("Locker Digital — hasta 50 MB")}
                {check("Simulador estadístico — 1 simulación")}
                {check("Consultor Hugo IA — 3 mensajes diarios")}
                {cross("Locker Digital ilimitado")}
                {cross("Hugo IA — 20 mensajes diarios")}
                {cross("Simulador ilimitado")}
            </div>
            <a href="/?page=registro" target="_self" style="display:block;text-align:center;text-decoration:none;font-family:Montserrat,sans-serif;font-size:0.95rem;font-weight:600;color:#1A1A1A;padding:14px 20px;border:1.5px solid #D0D0D0;border-radius:8px;background:#fff;margin-top:24px;transition:background 0.15s,border-color 0.15s;">Comenzar gratis</a>
        </div>
        """, unsafe_allow_html=True)

    _logged = st.session_state.get("logged_in", False)
    _user_planes = st.session_state.get("user", "")
    _token_planes = st.session_state.get("session_token", "")
    if _logged and not _token_planes:
        # Sesión antigua sin token (p. ej. de antes de esta migración): genera uno ahora.
        _token_planes = crear_sesion_token(_user_planes)
        st.session_state.session_token = _token_planes
    if _logged:
        _url_mensual = crear_sesion_stripe(st.secrets["STRIPE_PRICE_MENSUAL"], _user_planes, _token_planes)
        _url_anual   = crear_sesion_stripe(st.secrets["STRIPE_PRICE_ANUAL"],   _user_planes, _token_planes)
    else:
        _url_mensual = "/?page=login"
        _url_anual   = "/?page=login"

    with col_p2:
        st.markdown(f"""
        <div style="{plan_css_pro}">
            <div style="position:absolute;top:-14px;left:50%;transform:translateX(-50%);background:#4A5D32;color:#FFF;font-size:0.72rem;font-weight:700;padding:4px 16px;border-radius:20px;white-space:nowrap;letter-spacing:.06em;">PRO</div>
            <p style="font-size:0.75rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#4A5D32;margin-bottom:8px;">Pro</p>
            <div style="margin-bottom:2px;">
                <div style="display:flex;align-items:flex-end;gap:6px;margin-bottom:4px;">
                    <span style="font-size:2.4rem;font-weight:700;color:#1A1A1A;">$79</span>
                    <span style="font-size:1rem;color:#888;padding-bottom:6px;">/ mes</span>
                </div>
                <div style="display:flex;align-items:flex-end;gap:6px;">
                    <span style="font-size:1.3rem;font-weight:600;color:#4A5D32;">$799</span>
                    <span style="font-size:0.85rem;color:#4A5D32;padding-bottom:3px;">/ año &nbsp;<span style="background:#EEF1E9;padding:2px 8px;border-radius:10px;font-size:0.72rem;">2 meses gratis</span></span>
                </div>
            </div>
            <p style="font-size:0.85rem;color:#888;margin-bottom:4px;">Para maximizar tu ingreso universitario</p>
            <p style="font-size:0.78rem;color:#BBBBBB;margin-bottom:24px;">Cancela cuando quieras</p>
            <div style="border-top:1px solid #F0F0F0;padding-top:20px;">
                {check("Todo lo del plan Gratis")}
                {check("Locker Digital ilimitado en la nube")}
                {check("Hugo IA — 20 mensajes diarios")}
                {check("Simulador estadístico ilimitado")}
                {check("Documentos disponibles desde cualquier dispositivo")}
                {check("Co-creación de ensayos y currículum con IA")}
            </div>
            <div style="display:flex;gap:10px;margin-top:24px;">
                <a href="{_url_mensual}" target="_self" style="flex:1;display:block;text-align:center;text-decoration:none;font-family:Montserrat,sans-serif;font-size:0.9rem;font-weight:600;color:#4A5D32;padding:13px 10px;border-radius:8px;background:#EEF1E9;transition:background 0.15s;">Mensual $79</a>
                <a href="{_url_anual}" target="_self" style="flex:1;display:block;text-align:center;text-decoration:none;font-family:Montserrat,sans-serif;font-size:0.9rem;font-weight:600;color:#FFFFFF;padding:13px 10px;border-radius:8px;background:#4A5D32;transition:background 0.15s;">Anual $799</a>
            </div>
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
        
        with st.form("form_registro"):
            reg_nombre = st.text_input("Usuario", placeholder="", key="reg_nom_input")
            reg_email  = st.text_input("Correo electrónico", placeholder="", key="reg_email_input")
            reg_pass   = st.text_input("Contraseña", type="password", placeholder="", key="reg_pass_input")
            _reg_clicked = st.form_submit_button("Crear cuenta", use_container_width=True)
        if _reg_clicked:
            import re as _re_email
            _email_val = reg_email.strip()
            _email_ok = bool(_re_email.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", _email_val))
            _pass_ok  = len(reg_pass) >= 8 and bool(_re_email.search(r"[A-Za-z]", reg_pass)) and bool(_re_email.search(r"\d", reg_pass))

            if not reg_nombre or not reg_pass or not _email_val:
                st.error("Por favor completa todos los campos (usuario, correo y contraseña).")
            elif not _email_ok:
                st.error("El correo electrónico no tiene un formato válido.")
            elif not _pass_ok:
                st.error("La contraseña debe tener al menos 8 caracteres, una letra y un número.")
            else:
                users = load_users()
                if reg_nombre in users:
                    st.error("El usuario ya existe, intenta con otro.")
                else:
                    # Verificar que el correo no esté ya registrado
                    _email_existente = supabase_client.table("usuarios").select("username").eq("email", _email_val).execute()
                    if _email_existente.data:
                        st.error("Ya existe una cuenta con ese correo electrónico.")
                    else:
                        save_user(reg_nombre, reg_pass, _email_val)
                        enviar_correo_bienvenida_registro(_email_val)
                        st.success("Cuenta creada exitosamente.")
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
                # Red de seguridad: si pagó pero cerró la pestaña antes de que
                # se confirmara el pago, lo verificamos aquí también.
                if verificar_pago_pendiente(_login_username):
                    st.session_state.plan_usuario = "pro"
                if st.session_state.get("perfil_completo"):
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

    _token_url = st.query_params.get("token", "")

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

# --- VISTA: PAGO EXITOSO ---
elif st.session_state.page == "pago_exitoso":
    # _user solo puede venir de session_state.user, que a este punto ya fue
    # poblado (en el bloque "Fallback" de arriba) mediante un token validado
    # contra Supabase — nunca se lee un username crudo desde la URL aquí.
    _user = st.session_state.get("user", "")
    _token_pago = st.session_state.get("session_token", "")
    _session_id = (st.query_params.get("session_id", "") or st.session_state.get("_stripe_session_id", ""))

    if _user:
        if "_pago_ya_verificado" not in st.session_state:
            with st.spinner("Confirmando tu pago con Stripe..."):
                activado = verificar_y_activar_pago(_session_id, _user)
            st.session_state["_pago_ya_verificado"] = True
            st.session_state["_pago_activado_ok"] = activado
            if activado:
                st.session_state.plan_usuario = "pro"
                if "_correo_pro_enviado" not in st.session_state:
                    _res_email = supabase_client.table("usuarios").select("email").eq("username", _user).execute()
                    _email_pro = (_res_email.data[0].get("email") or "") if _res_email.data else ""
                    if _email_pro:
                        enviar_correo_bienvenida_pro(_email_pro)
                    st.session_state["_correo_pro_enviado"] = True

    if st.session_state.get("_pago_activado_ok"):
        _logo_pro_html = (
            f'<img src="data:image/png;base64,{logo_pro_encoded}" style="width:100%;display:block;margin:0 auto 1.8rem;border-radius:8px;">'
            if logo_pro_encoded else (
                f'<img src="data:image/png;base64,{logo_encoded}" style="width:100%;display:block;margin:0 auto 1.8rem;border-radius:8px;">'
                if logo_encoded else
                '<div style="font-family:Montserrat,sans-serif;font-size:1.3rem;font-weight:700;letter-spacing:-0.03em;color:#4A5D32;margin-bottom:1.8rem;">uniwebmx <span style=\'font-size:0.7rem;font-weight:600;background:#4A5D32;color:#fff;padding:2px 9px;border-radius:20px;vertical-align:middle;letter-spacing:0.05em;\'>PRO</span></div>'
            )
        )
        st.markdown(f"""
        <div style="max-width:520px;margin:5rem auto;text-align:center;padding:3.5rem 3rem;border:1px solid #EAEAEA;border-radius:16px;background:#fff;">
            {_logo_pro_html}
            <h1 style="font-size:1.9rem;font-weight:700;color:#1A1A1A;margin-bottom:0.75rem;font-family:Montserrat,sans-serif;">¡Bienvenido a Pro!</h1>
            <p style="font-size:1rem;color:#666;line-height:1.75;margin-bottom:2.5rem;font-family:Montserrat,sans-serif;">
                Tu cuenta ya tiene acceso ilimitado al Locker Digital,<br>20 mensajes diarios con Hugo y el Simulador sin límites.
            </p>
            <a href="/?nav=locker&t={_token_pago}" target="_self" style="display:inline-block;background:#4A5D32;color:#fff;font-family:Montserrat,sans-serif;font-size:0.95rem;font-weight:600;padding:14px 40px;border-radius:8px;text-decoration:none;letter-spacing:0.01em;">
                Ir a mi cuenta →
            </a>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="max-width:520px;margin:5rem auto;text-align:center;padding:3.5rem 3rem;border:1px solid #EAEAEA;border-radius:16px;background:#fff;">
            <div style="width:48px;height:48px;background:#FEF3C7;border-radius:50%;display:flex;align-items:center;justify-content:center;margin:0 auto 1.5rem;font-size:1.3rem;">!</div>
            <h1 style="font-size:1.6rem;font-weight:700;color:#1A1A1A;margin-bottom:0.75rem;font-family:Montserrat,sans-serif;">No pudimos confirmar tu pago todavía</h1>
            <p style="font-size:0.95rem;color:#666;line-height:1.75;margin-bottom:2.5rem;font-family:Montserrat,sans-serif;">
                Si Stripe ya te cobró, espera un momento e intenta de nuevo,<br>o contáctanos con tu correo de confirmación.
            </p>
        </div>
        """, unsafe_allow_html=True)
        col_rv1, col_rv2, col_rv3 = st.columns([1, 1, 1])
        with col_rv2:
            st.markdown('<div class="btn-form-submit">', unsafe_allow_html=True)
            if st.button("Reintentar verificación", key="reintentar_pago", use_container_width=True):
                st.session_state.pop("_pago_ya_verificado", None)
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('<div class="btn-link-highlight" style="text-align:center;margin-top:0.75rem;">', unsafe_allow_html=True)
            if st.button("Volver a Planes", key="volver_planes_pago"):
                st.session_state.pop("_pago_ya_verificado", None)
                cambiar_pagina("planes")
            st.markdown('</div>', unsafe_allow_html=True)

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
               # Verificar límite de tamaño para plan gratis
               _limite_mb = LIMITES[get_plan()]["locker_mb"]
               if _limite_mb is not None and len(archivo.getvalue()) > _limite_mb * 1024 * 1024:
                   _banner_upgrade(f"Este archivo supera el límite de {_limite_mb}MB del plan gratis. Mejora a Pro para subir archivos sin límite.")
               else:
                   with st.spinner("Guardando..."):
                       guardar_archivo_original(_user, key, archivo.name, archivo.getvalue())
                       texto = extraer_texto_archivo(archivo) if archivo.type in ["application/pdf","text/plain"] else ""
                       st.session_state[sk] = {"nombre": archivo.name, "contenido": texto}
                       guardar_datos_usuario(_user)
                   st.toast(f"'{archivo.name}' guardado.")
                   st.rerun()

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

    _plan_chat = get_plan()
    LIMITE_DIARIO = LIMITES[_plan_chat]["hugo_diario"]

    st.markdown('<div class="gemini-chat-container">', unsafe_allow_html=True)
  
    if "historial_chat" not in st.session_state:
        st.session_state.historial_chat = [
            {"role": "assistant", "content": "¡Hola! Soy Hugo, tu consultor de admisión. ¿En qué puedo ayudarte hoy?"}
        ]
  
    for msg in st.session_state.historial_chat:
        rol_label = "Tú" if msg["role"] == "user" else "Hugo"
        clase = "gemini-user-label" if msg["role"] == "user" else "gemini-hugo-label"
        st.markdown(f"""
        <div class="gemini-row">
            <div class="{clase}">{rol_label}</div>
            <div class="gemini-text">{msg["content"]}</div>
        </div>
        """, unsafe_allow_html=True)
          
    st.markdown('</div>', unsafe_allow_html=True)
  
    prompt_chat = st.chat_input("Pregúntale a Hugo...", key="chat_gemini_input_real")
    
    if prompt_chat:
        # VERIFICACIÓN DE LÍMITE
        if st.session_state.contador_consultas >= LIMITE_DIARIO:
            if get_plan() == "gratis":
                _banner_upgrade(f"Alcanzaste tu límite de {LIMITE_DIARIO} mensajes diarios con Hugo. Mejora a Pro para obtener 20 mensajes diarios.")
            else:
                st.warning("Has alcanzado tu límite diario de 20 consultas con Hugo. Intenta mañana.")
        else:
            st.session_state.historial_chat.append({"role": "user", "content": prompt_chat})
            
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
                            "verificado, en vez de inventar cifras."
                        ),
                    )
                    chat = model.start_chat(history=historial_gemini)
                    respuesta = chat.send_message(prompt_chat + info_doc)
                    texto_hugo = respuesta.text
                    
                    # INCREMENTAR CONTADOR SOLO SI LA LLAMADA ES EXITOSA
                    st.session_state.contador_consultas += 1
                    
                    st.session_state.historial_chat.append({"role": "assistant", "content": texto_hugo})

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

    # --- Control de uso del simulador según plan ---
    _plan_sim = get_plan()
    _sim_usado = st.session_state.get("simulador_usado", False)
    if _plan_sim == "gratis" and _sim_usado:
        _banner_upgrade("Ya usaste tu simulación gratuita. Mejora a Pro para simulaciones ilimitadas.")
        st.stop()

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
                if get_plan() == "gratis":
                    st.session_state.simulador_usado = True
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
# PIE DE PÁGINA (SOLO PÚBLICO)
# =================================================================
if not es_hub:
   st.markdown('<div style="margin-top: 5rem;"></div>', unsafe_allow_html=True)
   col_foot1, col_foot2, col_foot3 = st.columns([3, 3, 2])
   with col_foot1:
       st.markdown("<p style='color: #666666; font-size: 0.85rem;'>© 2026 Uniwebmx. Todos los derechos reservados.</p>", unsafe_allow_html=True)
   with col_foot2:
       st.markdown("<p style='color: #666666; font-size: 0.85rem; text-align: center;'>Aviso de Privacidad | Términos y Condiciones</p>", unsafe_allow_html=True)
   with col_foot3:
       st.markdown("<p style='font-size: 0.85rem; text-align: right;'><a href='https://www.instagram.com/uniwebmx/' target='_blank' style='color:#4A5D32;font-weight:bold;text-decoration:none;'>Instagram</a> | <span style='color:#BBBBBB;'>LinkedIn</span> | <span style='color:#BBBBBB;'>TikTok</span></p>", unsafe_allow_html=True)