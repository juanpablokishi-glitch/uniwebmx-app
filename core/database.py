import streamlit as st
from datetime import datetime
from supabase import create_client, Client
from core.config import BUCKET

@st.cache_resource
def get_supabase() -> Client:
    """Initialize and return the Supabase client."""
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase_client = get_supabase()

def load_users():
    """Returns dict {username: hash} from Supabase."""
    res = supabase_client.table("usuarios").select("username, password_hash").execute()
    return {row["username"]: row["password_hash"] for row in (res.data or [])}

def save_user(username, password, email="", edad=None, es_menor_edad=False,
              tutor_nombre="", tutor_email="", tutor_consentimiento=False,
              tutor_confirm_token=None, tutor_confirm_token_expiry=None,
              consentimiento_hugo=False, consentimiento_universidades=False,
              consentimiento_promocional=False, consentimientos_fecha=None):
    """Saves a new user to Supabase. Returns True if successful."""
    import bcrypt
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
    try:
        supabase_client.table("usuarios").insert(datos_usuario).execute()
        return True
    except Exception as e:
        if "usuarios_username_key" in str(e) or "23505" in str(e):
            return False
        # Notification will be handled by the service layer calling this function
        raise e

def cargar_datos_usuario(username):
    """Loads user-specific data dictionary from Supabase."""
    res = supabase_client.table("datos_usuario").select("datos").eq("username", username).execute()
    if res.data:
        return res.data[0]["datos"]
    return {}

def guardar_datos_usuario(username, datos):
    """Persists user data dictionary to Supabase."""
    if not username:
        return
    try:
        res = supabase_client.table("datos_usuario").update({
            "datos": datos,
            "updated_at": datetime.now().isoformat()
        }).eq("username", username).execute()

        if not res.data:
            supabase_client.table("datos_usuario").insert({
                "username": username,
                "datos": datos,
                "updated_at": datetime.now().isoformat()
            }).execute()
    except Exception as e:
        raise e

def restaurar_sesion_usuario(username):
    """Helper to fetch user account metadata for session initialization."""
    res = supabase_client.table("usuarios").select(
        "es_menor_edad, tutor_confirmado, tutor_nombre, tutor_email, "
        "consentimiento_hugo, consentimiento_universidades, consentimiento_promocional, "
        "rol, universidad_asignada"
    ).eq("username", username).execute()

    if res.data:
        return res.data[0]
    return None

def guardar_conversacion_entrenamiento(username, mensaje_usuario, respuesta_hugo):
    """Saves a chat exchange for AI training if consented."""
    try:
        supabase_client.table("hugo_entrenamiento").insert({
            "username": username,
            "mensaje_usuario": mensaje_usuario,
            "respuesta_hugo": respuesta_hugo,
        }).execute()
    except Exception as e:
        print(f"[hugo_entrenamiento ERROR] {e}")

def log_evento(username, tipo_evento, detalle=None):
    """
    Guarda un evento con fecha/hora en la tabla 'eventos_uso'.
    No debe tumbar la app si falla.
    """
    try:
        supabase_client.table("eventos_uso").insert({
            "username": username,
            "tipo_evento": tipo_evento,
            "detalle": detalle or {},
        }).execute()
    except Exception:
        pass
