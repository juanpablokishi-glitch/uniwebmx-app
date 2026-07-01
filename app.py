import streamlit as st
import pandas as pd
import numpy as np
import base64
import os
import google.generativeai as genai  # <-- IMPORTANTE: Ponlo aquí, libre de comillas
import pypdf
import json
import os
import bcrypt
import PyPDF2 # Asegúrate de tener esta librería instalada

# --- CONFIGURACIÓN DE LA API DE GEMINI ---
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

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

USER_FILE = "users.json"

def load_users():
    if not os.path.exists(USER_FILE):
        return {}
    with open(USER_FILE, "r") as f:
        return json.load(f)

def save_user(username, password):
    users = load_users()
    # Hasheamos la contraseña
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    users[username] = hashed.decode('utf-8')
    with open(USER_FILE, "w") as f:
        json.dump(users, f)

def verify_user(username, password):
    users = load_users()
    if username in users:
        stored_hash = users[username].encode('utf-8')
        return bcrypt.checkpw(password.encode('utf-8'), stored_hash)
    return False


# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
   page_title="Uniwebmx - Admisiones Inteligentes",
   page_icon="🎓",
   layout="wide",
   initial_sidebar_state="expanded"
)
# --- CAPTURA DE NAVEGACIÓN VIA URL ---
# Solo leemos el query param la PRIMERA VEZ que carga la app (cuando aún
# no existe session_state.page). Después de eso, la navegación interna
# (cambiar_pagina) tiene prioridad absoluta y la URL ya no puede pisarla.
query_params = st.query_params
if "page" not in st.session_state:
   if "page" in query_params:
       st.session_state.page = query_params["page"]
   else:
       st.session_state.page = "inicio"
   # Limpiamos el query param para que no se quede "pegado" en la URL
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
if not st.session_state.logged_in and st.session_state.page in ["locker", "chat", "simulador"]:
    st.session_state.page = "login"
# Determinar si el usuario está dentro del Hub
es_hub = st.session_state.page in ["locker", "chat", "simulador"]


# --- INYECCIÓN CSS INTERNA ---
st.markdown(f"""
<style>
   @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght=400;500;600;700&display=swap');


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
   .locker-text-desc {{
       color: #666666;
       font-size: 0.95rem;
       line-height: 1.5;
       margin-bottom: 1.8rem !important;
   }}
   .stFileUploader label {{
       display: none !important;
   }}
   .stFileUploader button {{
       background-color: #FBFBFA !important;
       color: #1A1A1A !important;
       border: 1px solid #EAEAEA !important;
       border-radius: 4px !important;
       padding: 10px 24px !important;
       font-weight: 600 !important;
   }}


   /* --- SOLUCIÓN INTEGRAL AL CORTE DE BORDES EN INPUTS --- */
   .stTextInput input {{
       border-radius: 24px !important;
       border: 1px solid #777777 !important;
       height: 48px !important;
       padding: 10px 20px !important;
       background-color: #FFFFFF !important;
       box-shadow: none !important;
   }}
   /* Previene que la estructura interna de la celda mutile el borde inferior */
   .stTextInput div[data-baseweb="input"] {{
       background-color: transparent !important;
       border: none !important;
       padding-bottom: 6px !important;
   }}
   .stTextInput label {{
       font-weight: 500 !important;
       color: #1A1A1A !important;
       font-size: 1.1rem !important;
       margin-bottom: 8px !important;
   }}
  
   .btn-form-submit button {{
       background-color: #4A5D32 !important;
       color: white !important;
       width: 100% !important;
       height: 48px !important;
       border-radius: 4px !important;
       font-size: 1rem !important;
       font-weight: 600 !important;
       margin-top: 1.5rem !important;
       border: none !important;
   }}
   .auth-redirect-text {{
       font-size: 1.1rem;
       color: #444444;
       margin-top: 2rem !important;
       text-align: center;
   }}
   .btn-link-highlight button {{
       background: none !important;
       border: none !important;
       padding: 0 !important;
       color: #1A1A1A !important;
       font-weight: 700 !important;
       text-decoration: underline !important;
       font-size: 1.2rem !important;
       display: block !important;
       margin: 0 auto !important;
   }}


   /* --- BARRA LATERAL TIPO GEMINI CENTRADA --- */
   [data-testid="stSidebar"] {{
       background-color: #F0F4F9 !important;
       border-right: none !important;
   }}
   .sidebar-logo-container {{
       text-align: center;
       padding: 2.5rem 1rem 2.5rem 1rem;
   }}
   .sidebar-logo-container img {{
       max-height: 42px;
       margin: 0 auto;
   }}
  
   /* Contenedor y Centrado perfecto de los Botones en la Barra Lateral */
   .sidebar-btn, .sidebar-btn-active {{
       padding: 0 16px !important;
   }}
   .sidebar-btn button, .sidebar-btn-active button {{
       width: 100% !important;
       background-color: transparent !important;
       border: none !important;
       text-align: center !important; /* Centrado del texto */
       font-family: 'Montserrat', sans-serif !important;
       font-weight: 500 !important;
       font-size: 0.95rem !important;
       padding: 12px 14px !important;
       color: #1A1A1A !important;
       border-radius: 24px !important;
       margin-bottom: 0.5rem !important;
       display: flex !important;
       justify-content: center !important; /* Centrado horizontal del contenido flex */
       align-items: center !important;
       transition: background-color 0.15s ease;
   }}
   .sidebar-btn-active button {{
       background-color: #D3E3FD !important;
       font-weight: 600 !important;
       color: #041E49 !important;
   }}
   .sidebar-btn button:hover {{
       background-color: #E1E5EA !important;
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
   }}
   div[data-testid="stChatInput"] textarea {{
       border-radius: 24px !important;
       border: 1px solid #777777 !important;
       background-color: #FFFFFF !important;
   }}
</style>
""", unsafe_allow_html=True)




# =================================================================
# NAV BAR SUPERIOR (SOLO PÚBLICO)
# =================================================================
if not es_hub:
   col_nav_left, col_nav_right = st.columns([5.5, 2.5])
   with col_nav_left:
       logo_html = f'<img src="data:image/png;base64,{logo_encoded}">' if logo_encoded else "uniwebmx"
       st.markdown(f"""
       <div class="navbar-custom">
           <div class="menu-items-container">
               <a href="/?page=inicio" target="_self" class="nav-logo-link">{logo_html}</a>
               <a href="#" class="menu-item-link" style="pointer-events: none; opacity: 0.6;">Ranking de Universidades</a>
               <a href="#" class="menu-item-link" style="pointer-events: none; opacity: 0.6;">Comunidad</a>
               <a href="#" class="menu-item-link" style="pointer-events: none; opacity: 0.6;">Blog</a>
               <a href="#" class="menu-item-link" style="pointer-events: none; opacity: 0.6;">Planes y Comparativa</a>
           </div>
       </div>
       """, unsafe_allow_html=True)


   with col_nav_right:
       col_b1, col_b2 = st.columns(2)
       with col_b1:
           st.markdown('<div class="nav-right btn-login">', unsafe_allow_html=True)
           if st.button("Iniciar Sesión", key="btn_login"):
               cambiar_pagina("login")
           st.markdown('</div>', unsafe_allow_html=True)
       with col_b2:
           st.markdown('<div class="nav-right btn-register">', unsafe_allow_html=True)
           if st.button("Registrarse", key="btn_register"):
               cambiar_pagina("registro")
           st.markdown('</div>', unsafe_allow_html=True)




# =================================================================
# BARRA LATERAL TIPO GEMINI CENTRADA (SIN EMOJIS)
# =================================================================
if es_hub:
   with st.sidebar:
       if logo_encoded:
           st.markdown(f'<div class="sidebar-logo-container"><img src="data:image/png;base64,{logo_encoded}"></div>', unsafe_allow_html=True)
       else:
           st.markdown('<div class="sidebar-logo-container" style="font-weight:700; font-size:1.3rem; color:#1A1A1A;">uniwebmx</div>', unsafe_allow_html=True)
      
       st.markdown(f'<div class="{"sidebar-btn-active" if st.session_state.page == "locker" else "sidebar-btn"}">', unsafe_allow_html=True)
       if st.button("Locker Digital", key="side_lock"):
           cambiar_pagina("locker")
       st.markdown('</div>', unsafe_allow_html=True)
      
       st.markdown(f'<div class="{"sidebar-btn-active" if st.session_state.page == "chat" else "sidebar-btn"}">', unsafe_allow_html=True)
       if st.button("Consultor IA", key="side_chat"):
           cambiar_pagina("chat")
       st.markdown('</div>', unsafe_allow_html=True)
      
       st.markdown(f'<div class="{"sidebar-btn-active" if st.session_state.page == "simulador" else "sidebar-btn"}">', unsafe_allow_html=True)
       if st.button("Simulador", key="side_sim"):
           cambiar_pagina("simulador")
       st.markdown('</div>', unsafe_allow_html=True)
      
       st.markdown('<hr style="border-top: 1px solid rgba(0,0,0,0.08); margin: 2rem 0;">', unsafe_allow_html=True)
      
       st.markdown('<div class="sidebar-btn">', unsafe_allow_html=True)
       if st.button("Cerrar Sesión", key="side_logout"):
           st.session_state.logged_in = False
           st.session_state.pop("user", None)
           cambiar_pagina("inicio")
       st.markdown('</div>', unsafe_allow_html=True)




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


# --- VISTA: REGISTRO ---
elif st.session_state.page == "registro":
    col_img, col_form = st.columns([1.1, 0.9], gap="large")
    with col_img:
        if fondo_auth_encoded:
            st.markdown(f'<div style="width: 100%; height: 680px; background-image: url(\'data:image/png;base64,{fondo_auth_encoded}\'); background-size: cover; background-position: center; border-radius: 4px;"></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="width: 100%; height: 680px; background-color: #EFEFEF; border-radius: 4px;"></div>', unsafe_allow_html=True)
    with col_form:
        st.markdown("<div style='padding-top: 40px;'></div>", unsafe_allow_html=True)
        st.markdown("<h1 style='font-size: 3.5rem; font-weight: 400; color: #333333; margin-bottom: 2.5rem;'>Registro</h1>", unsafe_allow_html=True)
        
        reg_nombre = st.text_input("Usuario", placeholder="", key="reg_nom_input")
        reg_email = st.text_input("Correo electrónico", placeholder="", key="reg_email_input")
        reg_pass = st.text_input("Contraseña", type="password", placeholder="", key="reg_pass_input")
        
        st.markdown('<div class="btn-form-submit">', unsafe_allow_html=True)
        if st.button("Crear cuenta", key="submit_registro"):
            if not reg_nombre or not reg_pass:
                st.error("Por favor completa los campos obligatorios.")
            else:
                users = load_users()
                if reg_nombre in users:
                    st.error("El usuario ya existe, intenta con otro.")
                else:
                    # AQUÍ ESTÁ EL CAMBIO: Usamos nuestra función segura
                    save_user(reg_nombre, reg_pass)
                    st.success("Cuenta creada exitosamente.")
                    st.info("Ahora puedes iniciar sesión.")
                    
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown("<p class='auth-redirect-text'>¿Ya tienes cuenta?</p>", unsafe_allow_html=True)
        st.markdown('<div class="btn-link-highlight">', unsafe_allow_html=True)
        if st.button("Inicia sesión aquí", key="go_to_login"):
            cambiar_pagina("login")
        st.markdown('</div>', unsafe_allow_html=True)

# --- VISTA: LOGIN ---
elif st.session_state.page == "login":
    col_img, col_form = st.columns([1.1, 0.9], gap="large")
    with col_img:
        if fondo_auth_encoded:
            st.markdown(f'<div style="width: 100%; height: 680px; background-image: url(\'data:image/png;base64,{fondo_auth_encoded}\'); background-size: cover; background-position: center; border-radius: 4px;"></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="width: 100%; height: 680px; background-color: #EFEFEF; border-radius: 4px;"></div>', unsafe_allow_html=True)
            
    with col_form:
        st.markdown("<div style='padding-top: 60px;'></div>", unsafe_allow_html=True)
        st.markdown("<h1 style='font-size: 3.5rem; font-weight: 400; color: #333333; margin-bottom: 3rem;'>Inicio de sesión</h1>", unsafe_allow_html=True)
        
        login_email = st.text_input("Usuario", placeholder="", key="login_email_input")
        login_pass = st.text_input("Contraseña", type="password", placeholder="", key="login_pass_input")
        
        st.markdown('<div class="btn-form-submit">', unsafe_allow_html=True)
        if st.button("Iniciar sesión", key="submit_login"):
            # AQUÍ USAMOS LA FUNCIÓN SEGURA
            if verify_user(login_email, login_pass):
                st.session_state.logged_in = True
                st.session_state.user = login_email
                cambiar_pagina("locker")
            else:
                st.error("Usuario o contraseña incorrectos")
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown("<p class='auth-redirect-text'>¿No tienes cuenta?</p>", unsafe_allow_html=True)
        st.markdown('<div class="btn-link-highlight">', unsafe_allow_html=True)
        if st.button("Registro", key="go_to_reg"):
            cambiar_pagina("registro")
        st.markdown('</div>', unsafe_allow_html=True)


# --- VISTA: LOCKER DIGITAL ---
elif st.session_state.page == "locker":
   st.markdown("""
   <div class="hero-section-locker">
       <h1 style='font-size: 3.5rem; margin-bottom: 1.5rem; max-width: 900px; margin-left: auto; margin-right: auto;'>Tu Locker Digital</h1>
       <p style='font-size: 1.35rem; color: #1A1A1A; max-width: 850px; margin: 0 auto; line-height: 1.6; font-weight: 400; opacity: 0.9;'>
           Centraliza tus documentos fundamentales. Al cargar un archivo, la inteligencia artificial lo leerá automáticamente para alimentar tu perfil de postulación.
       </p>
   </div>
   """, unsafe_allow_html=True)
  
   col_row1_left, col_row1_right = st.columns(2)
   col_row2_left, col_row2_right = st.columns(2)
  
   with col_row1_left:
       st.markdown('<div class="locker-box-clean">', unsafe_allow_html=True)
       st.markdown("<h3>Kárdex</h3>", unsafe_allow_html=True)
       st.markdown('<p class="locker-text-desc">Sube las versiones o borradores de tus cartas personales y declaraciones de propósito (PDF o TXT).</p>', unsafe_allow_html=True)
      
       # --- LÓGICA DE FUNCIONALIDAD SIN TOCAR EL DISEÑO ---
      
       # 1. Inicializar el almacén de documentos en la sesión si no existe
       if "kárdex" not in st.session_state:
           st.session_state.kárdex = {"nombre": None, "contenido": ""}


       # 2. Tu cargador de archivos pero con clave funcional
       archivo_kárdex = st.file_uploader(
           "",
           type=["pdf", "txt"],
           key="up_kárdex_funcional" # Clave única y funcional
       )


       # 3. Procesamiento silencioso al subir el archivo
       if archivo_kárdex is not None:
           # Si es un archivo nuevo que no hemos procesado
           if st.session_state.kárdex["nombre"] != archivo_kárdex.name:
               with st.spinner("Preparando documento para Hugo..."):
                   # Usamos la función del Paso 2
                   texto_extraido = extraer_texto_archivo(archivo_kárdex)
                  
                   # Guardamos el documento en la memoria de la sesión
                   st.session_state.kárdex= {
                       "nombre": archivo_kárdex.name,
                       "contenido": texto_extraido
                   }
               st.toast(f"✅ '{archivo_kárdex.name}' listo para Hugo.")
      
       st.markdown('</div>', unsafe_allow_html=True) # Cierre del contenedor visual
   # =================================================================
# BUSCA ESTE BLOQUE EN TU CÓDIGO Y REEMPLÁZALO:
# =================================================================
   with col_row1_right:
       st.markdown('<div class="locker-box-clean">', unsafe_allow_html=True)
       st.markdown("<h3>Ensayo de Motivos</h3>", unsafe_allow_html=True)
       st.markdown('<p class="locker-text-desc">Sube las versiones o borradores de tus cartas personales y declaraciones de propósito (PDF o TXT).</p>', unsafe_allow_html=True)
      
       # --- LÓGICA DE FUNCIONALIDAD SIN TOCAR EL DISEÑO ---
      
       # 1. Inicializar el almacén de documentos en la sesión si no existe
       # 1. Inicializar el almacén de documentos en la sesión si no existe
       if "ensayo" not in st.session_state:
           st.session_state.ensayo = {"nombre": None, "contenido": ""}
       
       # 2. Tu cargador de archivos pero con clave funcional
       archivo_ensayo = st.file_uploader(
           "",
           type=["pdf", "txt"],
           key="up_ensayo_funcional" # Clave única y funcional
       )


       # 3. Procesamiento silencioso al subir el archivo
       if archivo_ensayo is not None:
           # Si es un archivo nuevo que no hemos procesado
           if st.session_state.ensayo["nombre"] != archivo_ensayo.name:
               with st.spinner("Preparando documento para Hugo..."):
                   # Usamos la función del Paso 2
                   texto_extraido = extraer_texto_archivo(archivo_ensayo)
                  
                   # Guardamos el documento en la memoria de la sesión
                   st.session_state.ensayo = {
                       "nombre": archivo_ensayo.name,
                       "contenido": texto_extraido
                   }
               st.toast(f"✅ '{archivo_ensayo.name}' listo para Hugo.")
      
       st.markdown('</div>', unsafe_allow_html=True) # Cierre del contenedor visual
   with col_row2_left:
       st.markdown('<div class="locker-box-clean">', unsafe_allow_html=True)
       st.markdown("<h3>Cartas de Recomendación</h3>", unsafe_allow_html=True)
       st.markdown('<p class="locker-text-desc">Adjunta las cartas expedidas por tus profesores, directores o tutores académicos.</p>', unsafe_allow_html=True)
       st.file_uploader("", type=["pdf", "docx"], key="up_cartas")
       st.markdown('</div>', unsafe_allow_html=True)
   with col_row2_right:
       st.markdown('<div class="locker-box-clean">', unsafe_allow_html=True)
       st.markdown("<h3>Portafolio y Extracurriculares</h3>", unsafe_allow_html=True)
       st.markdown('<p class="locker-text-desc">Sube tus reconocimientos, diplomas de idiomas, proyectos de diseño o voluntariados relevantes.</p>', unsafe_allow_html=True)
       st.file_uploader("", type=["pdf", "zip", "jpg", "png"], key="up_proyectos")
       st.markdown('</div>', unsafe_allow_html=True)


# --- VISTA: CONSULTOR IA ---
# --- VISTA: CONSULTOR IA ---
elif st.session_state.page == "chat":
    # --- CONFIGURACIÓN DEL LÍMITE ---
    if "contador_consultas" not in st.session_state:
        st.session_state.contador_consultas = 0
    LIMITE_DIARIO = 20  # Ajusta este número según prefieras
    # ---------------------------------

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
            st.warning("⚠️ Has alcanzado tu límite diario de consultas con Hugo. Por favor, intenta mañana.")
        else:
            st.session_state.historial_chat.append({"role": "user", "content": prompt_chat})
            
            with st.spinner("Hugo está revisando..."):
                try:
                    info_doc = ""
                    if "kárdex" in st.session_state and "ensayo" in st.session_state:
                        info_doc = f"\nContexto: {st.session_state.kárdex.get('contenido', '')}"

                    model = genai.GenerativeModel("gemini-1.5-flash")
                    chat = model.start_chat(history=[])
                    respuesta = chat.send_message(prompt_chat + info_doc)
                    texto_hugo = respuesta.text
                    
                    # INCREMENTAR CONTADOR SOLO SI LA LLAMADA ES EXITOSA
                    st.session_state.contador_consultas += 1
                    
                    st.session_state.historial_chat.append({"role": "assistant", "content": texto_hugo})
                    
                    # ... [TU LÓGICA DE EXTRACCIÓN DE DATOS JSON SIGUE IGUAL] ...
                    import json
                    import re
                    match = re.search(r'\{.*"UNAM".*\}', texto_hugo)
                    if match:
                        datos = json.loads(match.group())
                        st.session_state.prob_unam = datos.get("UNAM", 75)
                        st.session_state.prob_itesm = datos.get("ITESM", 85)
                        st.session_state.prob_udg = datos.get("UDG", 90)
                        st.session_state.prob_uam = datos.get("UAM", 80)
                        st.session_state.hay_datos = True
                    
                except Exception as e:
                    if "429" in str(e):
                        msg_error = "🤖 **Hugo está tomando un descanso.** Has alcanzado el límite de velocidad de la API. Intenta en un momento."
                    else:
                        msg_error = "Lo siento, hubo un problema al conectar con Hugo. Inténtalo de nuevo."
                    st.session_state.historial_chat.append({"role": "assistant", "content": msg_error})
            
            st.rerun()
# --- VISTA: SIMULADOR ESTADÍSTICO ---
# --- VISTA: SIMULADOR ESTADÍSTICO ---
# --- VISTA: SIMULADOR ESTADÍSTICO ---
elif st.session_state.page == "simulador":
    st.markdown("""
    <div class="hero-section-locker">
        <h1 style='font-size: 3.5rem; margin-bottom: 1.5rem; max-width: 900px; margin-left: auto; margin-right: auto;'>Simulador Estadístico</h1>
        <p style='font-size: 1.35rem; color: #1A1A1A; max-width: 850px; margin: 0 auto; line-height: 1.6; font-weight: 400; opacity: 0.9;'>
            Calcula tus probabilidades de ingreso en base a tus calificaciones, perfiles históricos y tendencias de admisión de las universidades.
        </p>
    </div>
    """, unsafe_allow_html=True)

    if "hay_datos" in st.session_state:
        # Preparación de datos
        data = {
            "Universidad": ["UNAM", "ITESM", "UDG", "UAM"],
            "Probabilidad": [st.session_state.prob_unam, st.session_state.prob_itesm, st.session_state.prob_udg, st.session_state.prob_uam]
        }
        df = pd.DataFrame(data)
        
        st.subheader("Curva de Probabilidad por Institución")
        st.bar_chart(df.set_index("Universidad"))
        
        st.subheader("Porcentajes de Aceptación Estimados")
        st.table(df)
    else:
        st.info("💡 Ve al Consultor IA y pregúntale por tus probabilidades para ver tu gráfica personalizada.")

# --- FIN DE VISTAS -----
# --- CONEXIÓN CON EL LOCKER ---
# Revisamos si el alumno ya subió un documento para personalizar el análisis
# --- VISTA: SIMULADOR ESTADÍSTICO ---
elif st.session_state.page == "simulador":
    st.markdown("""
    <div class="hero-section-locker">
        <h1 style='font-size: 3.5rem; margin-bottom: 1.5rem; max-width: 900px; margin-left: auto; margin-right: auto;'>Simulador Estadístico</h1>
    </div>
    """, unsafe_allow_html=True)
    
    if "hay_datos" in st.session_state:
        # Variables
        prob_unam = st.session_state.get("prob_unam", 0)
        prob_itesm = st.session_state.get("prob_itesm", 0)
        prob_udg = st.session_state.get("prob_udg", 0)
        prob_uam = st.session_state.get("prob_uam", 0)

        # Lógica del ensayo
        tiene_ensayo = ("ensayo" in st.session_state and st.session_state.ensayo.get("nombre"))
        texto_adicional_locker = ""
        if tiene_ensayo:
            texto_adicional_locker = f" El ensayo detectado en tu Locker (<strong>{st.session_state.ensayo['nombre']}</strong>) fue considerado."

        # Gráfica
        df_grafica = pd.DataFrame({
            'Universidad': ['UNAM', 'ITESM', 'UDG', 'UAM'],
            'Probabilidad (%)': [prob_unam, prob_itesm, prob_udg, prob_uam]
        })
        
        import altair as alt
        chart = alt.Chart(df_grafica).mark_line(point=True, color='#4A5D32', strokeWidth=3).encode(
            x=alt.X('Universidad:N', sort=['UNAM', 'ITESM', 'UDG', 'UAM']),
            y=alt.Y('Probabilidad (%):Q', scale=alt.Scale(domain=[0, 100]))
        ).properties(height=300)
        
        st.subheader("Curva de Probabilidad por Institución")
        st.altair_chart(chart, use_container_width=True)
        
        # Tabla y Análisis
        col_tabla, col_explicacion = st.columns([1.2, 0.8], gap="large")
        with col_tabla:
            st.subheader("Porcentajes de Aceptación Estimados")
            st.table(df_grafica)
        with col_explicacion:
            st.subheader("Análisis de Resultados")
            st.info(f"Tus probabilidades cruzan tu kárdex y el ensayo.{texto_adicional_locker}")

    else:
        st.info("💡 Ve al Consultor IA y pregúntale por tus probabilidades para ver tu gráfica personalizada.")
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
       st.markdown("<p style='color: #4A5D32; font-size: 0.85rem; text-align: right; font-weight: bold;'>Instagram | LinkedIn | TikTok</p>", unsafe_allow_html=True)
