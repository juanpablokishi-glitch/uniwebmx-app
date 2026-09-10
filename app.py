import streamlit as st
from ui import components
from ui.pages import (
    public,
    auth,
    auth_recovery,
    onboarding,
    locker,
    chat,
    mi_aplicacion,
    mensajes,
    orientacion
)
from core import auth as auth_core
from core.database import restaurar_sesion_usuario, supabase_client
from core.config import PANEL_ADMIN_PAGES

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
   page_title="Uniwebmx - Admisiones Inteligentes",
   page_icon="logo_chrome.png",
   layout="wide",
   initial_sidebar_state="expanded"
)

# --- PWA, SEO & CSS ---
components.inject_pwa_and_seo()

# Inyectar fondos personalizados para los Heroes
# Estos se cargan desde el disco y se pasan al CSS
from ui.components import get_base64_image
bg_inicio = get_base64_image("fondo_hero.png")
bg_locker = get_base64_image("fondo_locker.png")

# Formatear fondos para CSS si existen, sino usar fallback
bg_inicio_css = f"linear-gradient(rgba(255, 255, 255, 0.75), rgba(255, 255, 255, 0.75)), url('data:image/png;base64,{bg_inicio}')" if bg_inicio else "linear-gradient(rgba(243, 239, 234, 0.95), rgba(243, 239, 234, 0.95))"
bg_locker_css = f"linear-gradient(rgba(255, 255, 255, 0.75), rgba(255, 255, 255, 0.75)), url('data:image/png;base64,{bg_locker}')" if bg_locker else "linear-gradient(rgba(238, 240, 236, 0.95), rgba(238, 240, 236, 0.95))"

components.apply_custom_css(bg_inicio=bg_inicio_css, bg_locker=bg_locker_css)

# --- CAPTURA DE NAVEGACIÓN VIA URL ---

# 1. Interceptor de navegación interna via ?nav=X&t=TOKEN
if "nav" in st.query_params:
   _nav_target = st.query_params.get("nav")
   _nav_token  = st.query_params.get("t", "")
   st.query_params.clear()

   if _nav_target == "__logout__":
       auth_core.invalidar_sesion_token(st.session_state.get("user"))
       st.session_state.logged_in = False
       st.session_state.pop("user", None)
       st.session_state.pop("session_token", None)
       st.session_state.page = "inicio"
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
       _usuario_validado = auth_core.validar_sesion_token(_nav_token)
       if _usuario_validado:
           st.session_state.logged_in = True
           st.session_state.user = _usuario_validado
           st.session_state.session_token = _nav_token
           restaurar_sesion_usuario(_usuario_validado)
           st.session_state.page = _nav_target
       else:
           st.session_state.logged_in = False
           st.session_state.pop("user", None)
           st.session_state.page = "login"

# 2. Fallback: primera carga normal sin parámetros nav
if "page" not in st.session_state:
   query_params = st.query_params
   if "page" in query_params:
       _page_val = query_params["page"]
       st.session_state.page = _page_val
       if _page_val in ("confirmar_tutor", "reset_contrasena"):
           st.session_state["_token_url_pendiente"] = query_params.get("token", "")
   else:
       st.session_state.page = "inicio"
   st.query_params.clear()

def cambiar_pagina(nombre_pagina):
   st.session_state.page = nombre_pagina
   st.rerun()

# --- ESTADO DE SESIÓN Y SEGURIDAD ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# Filtro de seguridad: Si no está logueado, prohibir acceso al Hub
if not st.session_state.logged_in and st.session_state.page in ["locker", "chat", "simulador", "mi_aplicacion", "mensajes", "onboarding", "orientacion"]:
    st.session_state.page = "login"

# Filtro de seguridad: Panel admin/universidades
if not st.session_state.logged_in and st.session_state.page in PANEL_ADMIN_PAGES:
    st.session_state.page = "login"
elif st.session_state.logged_in and st.session_state.page in PANEL_ADMIN_PAGES and not auth_core.puede_ver_panel(st.session_state.get("user")):
    st.session_state.page = "locker" if st.session_state.get("perfil_completo") else "onboarding"
elif st.session_state.page == "panel_usuarios" and not auth_core.es_admin(st.session_state.get("user")):
    st.session_state.page = "panel_admin"
elif st.session_state.page == "panel_chat" and auth_core.es_universidad(st.session_state.get("user")):
    st.session_state.page = "panel_admin"

# Determinar visibilidad de sidebar
es_hub = st.session_state.page in ["locker", "chat", "simulador", "mi_aplicacion", "mensajes", "orientacion"]
es_panel = st.session_state.page in PANEL_ADMIN_PAGES

# Aplicar visibilidad de sidebar via CSS dinámico (inyectando la regla específica)
if not es_hub and not es_panel:
    st.markdown("[data-testid='stSidebar'] {display: none;}")

# --- BUCLE DE RUTEO PRINCIPAL ---
page = st.session_state.page

if page == "inicio":
    public.render_inicio()
elif page == "ranking":
    public.render_ranking()
elif page == "blog":
    public.render_blog()
elif page == "login":
    auth.render_login()
elif page == "registro":
    auth.render_registro()
elif page == "olvide_contrasena":
    auth_recovery.render_olvide_contrasena()
elif page == "reset_contrasena":
    auth_recovery.render_reset_contrasena()
elif page == "onboarding":
    onboarding.render_onboarding()
elif page == "locker":
    locker.render_locker()
elif page == "chat":
    chat.render_chat()
elif page == "simulador":
    # Simulador logic was in app.py, let's ensure it's moved or implement a placeholder
    # Since it's a pending task in the summary, I'll call a render if it exists.
    try:
        from ui.pages import simulador
        simulador.render_simulador()
    except ImportError:
        st.error("La página del simulador aún no ha sido modularizada.")
elif page == "mi_aplicacion":
    mi_aplicacion.render_mi_aplicacion()
elif page == "mensajes":
    mensajes.render_mensajes()
elif page == "orientacion":
    orientacion.render_orientacion()
elif page in PANEL_ADMIN_PAGES:
    # Admin views would be handled here
    st.warning(f"La vista {page} está en desarrollo en el módulo de administración.")
else:
    # Fallback
    st.session_state.page = "inicio"
    st.rerun()
