import bcrypt
from datetime import datetime, timedelta, timezone
from core.database import supabase_client
from core.config import SESSION_TOKEN_DIAS, MAX_INTENTOS_LOGIN, BLOQUEO_MINUTOS

def verify_user(username, password):
    """Verifies user credentials against the Supabase hash."""
    try:
        res = supabase_client.table("usuarios").select("password_hash").eq("username", username).execute()
    except Exception:
        return False
    if res.data:
        stored_hash = res.data[0]["password_hash"].encode('utf-8')
        return bcrypt.checkpw(password.encode('utf-8'), stored_hash)
    return False

def cuenta_bloqueada(username):
    """Checks if an account is temporarily locked due to failed attempts."""
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
    """Increments failed login attempts and locks account if limit reached."""
    if not username:
        return
    try:
        res = supabase_client.table("usuarios").select("failed_attempts").eq("username", username).execute()
        if not res.data:
            return
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
    """Resets failed attempts after successful login."""
    if not username:
        return
    try:
        supabase_client.table("usuarios").update(
            {"failed_attempts": 0, "locked_until": None}
        ).eq("username", username).execute()
    except Exception:
        pass

def crear_sesion_token(username):
    """Generates a secure session token for URL-based navigation."""
    import secrets as _secrets_sesion
    token = _secrets_sesion.token_urlsafe(32)
    expiry = (datetime.now(timezone.utc) + timedelta(days=SESSION_TOKEN_DIAS)).isoformat()
    supabase_client.table("usuarios").update({
        "session_token": token,
        "session_token_expiry": expiry,
    }).eq("username", username).execute()
    return token

def validar_sesion_token(token):
    """Validates session token and returns username if valid."""
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
    """Revokes current session token (Logout)."""
    if not username:
        return
    try:
        supabase_client.table("usuarios").update({
            "session_token": None,
            "session_token_expiry": None,
        }).eq("username", username).execute()
    except Exception:
        pass

def rol_usuario_actual(username):
    """Fetches the role of the user."""
    res = supabase_client.table("usuarios").select("rol").eq("username", username).execute()
    if res.data:
        return res.data[0].get("rol", "alumno")
    return "alumno"

def es_admin(username):
    return rol_usuario_actual(username) == "admin"

def es_universidad(username):
    return rol_usuario_actual(username) == "universidad"

def puede_ver_panel(username):
    return rol_usuario_actual(username) in ("admin", "universidad")
