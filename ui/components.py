import streamlit as st
import streamlit.components.v1 as components
import base64
import json
from core.config import BASE_URL

def inject_pwa_and_seo(logo_path="logo_chrome.png"):
    """Injects PWA manifest and SEO meta tags into the page head via JS."""
    def _pwa_encode_image(path):
        try:
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode()
        except FileNotFoundError:
            return None

    logo_b64 = _pwa_encode_image(logo_path)
    if not logo_b64:
        return

    # PWA Manifest
    pwa_manifest = {
        "name": "Uniwebmx - Admisiones Inteligentes",
        "short_name": "uniwebmx",
        "start_url": ".",
        "display": "standalone",
        "background_color": "#FFFFFF",
        "theme_color": "#4A5D32",
        "icons": [
            {"src": f"data:image/png;base64,{logo_b64}", "sizes": "192x192", "type": "image/png"},
            {"src": f"data:image/png;base64,{logo_b64}", "sizes": "512x512", "type": "image/png"},
        ],
    }
    pwa_manifest_json = json.dumps(pwa_manifest)

    # SEO Meta Tags
    seo_titulo = "Uniwebmx - Admisiones Inteligentes con IA"
    seo_descripcion = (
        "Organiza tus documentos, platica con Hugo (tu asesor de admisiones con IA) "
        "y simula tus probabilidades de ingreso por universidad. Empieza gratis."
    )
    seo_url = "https://uniwebmx.com"

    components.html(f"""
    <script>
    (function() {{
        var doc = window.parent.document;

        // --- PWA ---
        if (doc.getElementById('uniwebmx-manifest')) {{}} else {{
            var manifestStr = {json.dumps(pwa_manifest_json)};
            var blob = new Blob([manifestStr], {{type: 'application/manifest+json'}});
            var manifestUrl = URL.createObjectURL(blob);
            var link = doc.createElement('link');
            link.id = 'uniwebmx-manifest';
            link.rel = 'manifest';
            link.href = manifestUrl;
            doc.head.appendChild(link);

            var icon = doc.createElement('link');
            icon.rel = 'apple-touch-icon';
            icon.href = 'data:image/png;base64,{logo_b64}';
            doc.head.appendChild(icon);

            var themeColor = doc.createElement('meta');
            themeColor.name = 'theme-color';
            themeColor.content = '#4A5D32';
            doc.head.appendChild(themeColor);

            var appleCapable = doc.createElement('meta');
            appleCapable.name = 'apple-mobile-web-app-capable';
            appleCapable.content = 'yes';
            doc.head.appendChild(appleCapable);

            var appleStatusBar = doc.createElement('meta');
            appleStatusBar.name = 'apple-mobile-web-app-status-bar-style';
            appleStatusBar.content = 'default';
            doc.head.appendChild(appleStatusBar);

            var appleTitle = doc.createElement('meta');
            appleTitle.name = 'apple-mobile-web-app-title';
            appleTitle.content = 'uniwebmx';
            doc.head.appendChild(appleTitle);
        }}

        // --- SEO ---
        if (doc.getElementById('uniwebmx-seo')) return;
        doc.title = {json.dumps(seo_titulo)};

        function setMeta(attr, key, content) {{
            var el = doc.querySelector('meta[' + attr + '="' + key + '"]');
            if (!el) {{
                el = doc.createElement('meta');
                el.setAttribute(attr, key);
                doc.head.appendChild(el);
            }}
            el.setAttribute('content', content);
        }}
        setMeta('name', 'description', {json.dumps(seo_descripcion)});
        setMeta('property', 'og:title', {json.dumps(seo_titulo)});
        setMeta('property', 'og:description', {json.dumps(seo_descripcion)});
        setMeta('property', 'og:type', 'website');
        setMeta('property', 'og:url', {json.dumps(seo_url)});
        setMeta('property', 'og:image', 'data:image/png;base64,{logo_b64}');
        setMeta('name', 'twitter:card', 'summary');
        setMeta('name', 'twitter:title', {json.dumps(seo_titulo)});
        setMeta('name', 'twitter:description', {json.dumps(seo_descripcion)});

        var favicon = doc.querySelector('link[rel="icon"]') || doc.createElement('link');
        favicon.rel = 'icon';
        favicon.href = 'data:image/png;base64,{logo_b64}';
        if (!favicon.parentNode) doc.head.appendChild(favicon);

        var marcador = doc.createElement('meta');
        marcador.id = 'uniwebmx-seo';
        marcador.name = 'uniwebmx-seo';
        doc.head.appendChild(marcador);
    }})();
    </script>
    """, height=0, width=0)

def apply_custom_css(bg_inicio, bg_locker):
    """Injects the comprehensive CSS styles into the app."""
    st.markdown(f"""
    <style>
       @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght=400;500;600;700&display=swap');
       @import url('https://cdnjs.cloudflare.com/ajax/libs/tabler-icons/2.47.0/tabler-icons.min.css');

       [data-testid="stIconMaterial"] {{ display: none !important; }}
       #MainMenu {{ visibility: hidden !important; display: none !important; }}
       header[data-testid="stHeader"] {{ background: transparent !important; height: 3rem !important; }}
       [data-testid="stToolbar"] {{ display: none !important; }}
       [data-testid="stDecoration"] {{ display: none !important; }}
       footer {{ visibility: hidden !important; display: none !important; }}

       /* Mobile Sidebar Button (FAB style) */
       [data-testid="collapsedControl"] {{
           display: flex !important;
           visibility: visible !important;
           opacity: 1 !important;
           z-index: 999999 !important;
           background: #4A5D32 !important;
           border-radius: 50% !important;
           width: 40px !important;
           height: 40px !important;
           justify-content: center !important;
           align-items: center !important;
           box-shadow: 0 4px 12px rgba(0,0,0,0.2) !important;
       }}
       [data-testid="collapsedControl"] button {{
           color: white !important;
       }}

       .stApp {{ margin-top: 0 !important; }}
       [data-testid="stAppViewContainer"] {{ padding-top: 0 !important; }}
       .stApp, button, p, span, a, h1, h2, h3, [data-testid="stSidebar"] {{ font-family: 'Montserrat', sans-serif !important; }}
       .stApp {{ background-color: #FFFFFF; }}
       .block-container {{ padding-top: 1rem !important; padding-bottom: 5rem !important; }}
       [data-testid="stSidebar"] {{ background-color: #FFFFFF !important; border-right: 0.5px solid #EAEAEA !important; }}
       [data-testid="stSidebar"] section[data-testid="stSidebarContent"] > div {{ padding: 0 !important; gap: 0 !important; }}
       [data-testid="stSidebar"] a:hover {{ background: #F5F5F3 !important; color: #1A1A1A !important; }}
       h1 {{ font-weight: 700; color: #1A1A1A !important; letter-spacing: -0.03em; }}
       h2 {{ font-weight: 700; color: #1A1A1A !important; }}
       h3 {{ font-weight: 600; color: #4A5D32 !important; margin-bottom: 12px !important; margin-top: 0px !important; }}

       .navbar-custom {{ display: flex; align-items: center; justify-content: space-between; padding: 10px 0; margin-bottom: 1rem; }}
       .nav-logo-link {{ font-weight: 700; color: #374337 !important; font-size: 1.8rem; letter-spacing: -0.04em; text-transform: lowercase; text-decoration: none !important; }}
       .nav-logo-link img {{ max-height: 45px; }}
       .menu-items-container {{ display: flex; gap: 28px; align-items: center; margin-top: 12px; }}
       .menu-item-link {{ font-weight: 500; color: #1A1A1A !important; font-size: 0.95rem; text-decoration: none !important; }}
       .nav-right div.stButton button {{ border-radius: 4px !important; font-weight: 600 !important; height: 40px !important; padding: 0 22px !important; margin-top: 10px !important; font-size: 0.9rem !important; }}
       .btn-login div.stButton button {{ background-color: transparent !important; color: #1A1A1A !important; border: 1px solid #EAEAEA !important; }}
       .btn-register div.stButton button {{ background-color: #4A5D32 !important; color: white !important; border: none !important; }}

       .hero-section-inicio {{ background-image: {bg_inicio}; background-size: cover; background-position: center; padding: 7rem 4rem 8rem 4rem; text-align: center; margin-left: -5rem !important; margin-right: -5rem !important; margin-top: 0.5rem; margin-bottom: 4rem; width: calc(100% + 10rem); }}
       .hero-section-locker {{ background-image: {bg_locker}; background-size: cover; background-position: center; padding: 6rem 4rem; text-align: center; margin-left: -5rem !important; margin-right: -5rem !important; margin-top: -1.6rem !important; margin-bottom: 4rem; width: calc(100% + 10rem); }}
       .hero-green-btn {{ display: inline-block; background-color: #4A5D32 !important; color: white !important; font-weight: 600; font-size: 1rem; padding: 14px 38px; border-radius: 4px; text-decoration: none !important; margin-top: 2.5rem; }}
       .card-beneficio {{ background-color: #FFFFFF; padding: 2.5rem 2rem; border-radius: 6px; border: 1px solid #EAEAEA; height: 100%; }}

       .uw-carrusel-viewport {{ overflow: hidden; background-color: #FAFAF8; border-radius: 10px; padding: 2rem 0; -webkit-mask-image: linear-gradient(90deg, transparent, #000 6%, #000 94%, transparent); mask-image: linear-gradient(90deg, transparent, #000 6%, #000 94%, transparent); }}
       .uw-carrusel-track {{ display: flex; gap: 18px; width: max-content; animation: uw-scroll 42s linear infinite; }}
       .uw-carrusel-track:hover {{ animation-play-state: paused; }}
       @keyframes uw-scroll {{ from {{ transform: translateX(0); }} to {{ transform: translateX(-50%); }} }}
       .uw-slide {{ flex-shrink: 0; width: 320px; height: 220px; border-radius: 10px; overflow: hidden; position: relative; background-size: cover; background-position: center; }}
       .uw-slide-overlay {{ position: absolute; inset: 0; background: linear-gradient(0deg, rgba(20,24,14,0.75) 0%, rgba(20,24,14,0.15) 55%, rgba(20,24,14,0) 75%); }}
       .uw-slide-text {{ position: absolute; left: 0; right: 0; bottom: 0; padding: 18px 20px; }}
       .uw-somos-icon {{ width: 34px; height: 34px; border-radius: 8px; background: #EEF1E9; display: flex; align-items: center; justify-content: center; margin-bottom: 12px; }}

       @media (max-width: 768px) {{
           .hero-section-inicio, .hero-section-locker {{ margin-left: -1rem !important; margin-right: -1rem !important; width: calc(100% + 2rem) !important; padding: 3rem 1.25rem !important; }}
           h1 {{ font-size: 1.9rem !important; line-height: 1.3 !important; }}
           .hero-section-inicio p, .hero-section-locker p {{ font-size: 1rem !important; line-height: 1.55 !important; }}
           .hero-green-btn {{ padding: 12px 26px !important; font-size: 0.9rem !important; }}
           .uw-slide {{ width: 220px !important; height: 160px !important; }}
           .uw-carrusel-viewport {{ padding: 1rem 0 !important; }}
           .card-beneficio {{ padding: 1.5rem 1.25rem !important; }}
           .locker-box-clean {{ padding: 1.5rem !important; }}
           [data-testid="stVerticalBlockBorderWrapper"] {{ padding: 1.25rem 1.25rem !important; }}
           .sidebar-bottom-bar {{ width: 100% !important; }}
           .profile-menu {{ width: min(85vw, 320px) !important; }}
           [data-testid="collapsedControl"] {{ top: 10px !important; left: 10px !important; }}
       }}
       @media (max-width: 480px) {{
           h1 {{ font-size: 1.6rem !important; }}
           .hero-section-inicio, .hero-section-locker {{ padding: 2.25rem 1rem !important; }}
           .uw-slide {{ width: 190px !important; height: 140px !important; }}
       }}

       .locker-box-clean {{ background-color: #FFFFFF !important; border: 1px solid #EAEAEA !important; border-radius: 8px !important; padding: 2.5rem !important; margin-bottom: 1.5rem !important; }}
       [data-testid="stVerticalBlockBorderWrapper"] {{ background-color: #FFFFFF !important; border: 1px solid #EAEAEA !important; border-radius: 8px !important; margin-bottom: 1.5rem !important; padding: 2rem 2.2rem !important; min-height: 220px !important; }}
       [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stHorizontalBlock"] {{ align-items: flex-start !important; }}
       .quitar-link button {{ all: unset !important; cursor: pointer !important; font-family: Montserrat, sans-serif !important; font-size: 0.78rem !important; color: #AAAAAA !important; text-decoration: underline !important; padding: 0 !important; margin-top: 6px !important; display: inline !important; }}
       .quitar-link button:hover {{ color: #CC3333 !important; }}
       .locker-text-desc {{ color: #666666; font-size: 0.95rem; line-height: 1.5; margin-bottom: 1.8rem !important; }}
       .stFileUploader label {{ display: none !important; }}
       [data-testid="stFileUploaderDropzone"] {{ display: flex !important; flex-direction: column !important; align-items: center !important; justify-content: center !important; gap: 10px !important; padding: 1.5rem 1rem !important; background-color: #FBFBFA !important; border: 1px dashed #D9D9D3 !important; border-radius: 8px !important; }}
       [data-testid="stFileUploaderDropzoneInstructions"] {{ text-align: center !important; white-space: normal !important; overflow: visible !important; }}
       [data-testid="stFileUploaderDropzoneInstructions"] span, [data-testid="stFileUploaderDropzoneInstructions"] small {{ display: block !important; white-space: normal !important; word-break: break-word !important; }}
       .stFileUploader button {{ background-color: #1A1A1A !important; color: #FFFFFF !important; border: none !important; border-radius: 8px !important; padding: 9px 24px !important; font-weight: 600 !important; font-size: 0.85rem !important; font-family: Montserrat, sans-serif !important; white-space: nowrap !important; transition: background 0.15s !important; letter-spacing: 0.01em !important; }}
       .stFileUploader button:hover {{ background-color: #333333 !important; }}
       [data-testid="stFileUploaderDropzone"] {{ border: 1.5px dashed #D0D0D0 !important; border-radius: 10px !important; background: #FAFAF9 !important; padding: 1.8rem 1rem !important; }}
       [data-testid="stFileUploaderFile"] {{ display: flex !important; align-items: center !important; gap: 8px !important; overflow: hidden !important; }}
       [data-testid="stFileUploaderFileName"] {{ white-space: nowrap !important; overflow: hidden !important; text-overflow: ellipsis !important; }}
       .stTextInput input, .stTextInput input:focus {{ border-radius: 24px !important; border: 1px solid #777777 !important; height: 48px !important; padding: 10px 20px !important; background-color: #FFFFFF !important; box-shadow: none !important; outline: none !important; }}
       .stTextInput div[data-baseweb="input"] {{ background-color: transparent !important; border: none !important; padding: 0 !important; overflow: visible !important; }}
       .stTextInput > div {{ overflow: visible !important; padding-bottom: 2px !important; }}
       .stTextInput label {{ font-weight: 500 !important; color: #1A1A1A !important; font-size: 1.1rem !important; margin-bottom: 8px !important; }}
       div[data-baseweb="base-input"], div[data-baseweb="input"], div[data-baseweb="textarea"], div[data-testid="stChatInput"], div[data-testid="stChatInput"] textarea, .stTextInput div[data-baseweb="input"], .stTextArea textarea {{ box-shadow: none !important; }}
       div[data-baseweb="base-input"]:focus-within, div[data-baseweb="input"]:focus-within, div[data-baseweb="textarea"]:focus-within, div[data-testid="stChatInput"]:focus-within, div[data-testid="stChatInput"] textarea:focus, .stTextArea textarea:focus {{ border-color: #4A5D32 !important; box-shadow: 0 0 0 1px rgba(74, 93, 50, 0.35) !important; outline: none !important; }}
       [data-testid="stTextInputRootElement"], [data-testid="stForm"] [data-baseweb="base-input"], [data-testid="stForm"] [data-baseweb="input"] {{ border-color: #777777 !important; }}
       [data-testid="stTextInputRootElement"]:focus-within, [data-testid="stForm"] [data-baseweb="base-input"]:focus-within, [data-testid="stForm"] [data-baseweb="input"]:focus-within {{ border-color: #4A5D32 !important; box-shadow: 0 0 0 1px rgba(74, 93, 50, 0.35) !important; outline: none !important; }}
       button:focus, button:focus-visible, .stButton button:focus, .stButton button:focus-visible, .stFormSubmitButton button:focus, .stFormSubmitButton button:focus-visible {{ outline: none !important; box-shadow: 0 0 0 2px rgba(74, 93, 50, 0.35) !important; }}
       .stButton > button {{ border-radius: 8px !important; font-family: Montserrat, sans-serif !important; font-weight: 600 !important; font-size: 0.9rem !important; border: 1px solid #D0D0D0 !important; background: #FFFFFF !important; color: #1A1A1A !important; padding: 10px 20px !important; transition: background 0.15s, border-color 0.15s !important; }}
       .stButton > button:hover {{ background: #F5F5F3 !important; border-color: #999 !important; }}
       [data-testid="stForm"] {{ border: none !important; padding: 0 !important; background: transparent !important; }}
       [data-testid="stFormSubmitButton"] > button {{ background-color: #4A5D32 !important; color: #FFFFFF !important; border: none !important; width: 100% !important; height: 52px !important; margin-top: 1.2rem !important; font-size: 1rem !important; font-weight: 600 !important; font-family: Montserrat, sans-serif !important; letter-spacing: 0.01em !important; border-radius: 8px !important; }}
       [data-testid="stFormSubmitButton"] > button:hover {{ background-color: #3a4a27 !important; }}
       .auth-redirect-text {{ font-size: 0.9rem; color: #999999; margin-top: 2rem !important; margin-bottom: 0.5rem !important; text-align: center; font-family: Montserrat, sans-serif; }}
       [data-testid="stSidebar"] {{ background-color: #FFFFFF !important; border-right: 0.5px solid #EAEAEA !important; }}
       [data-testid="stSidebar"] section[data-testid="stSidebarContent"] > div {{ padding: 0 !important; gap: 0 !important; }}
       [data-testid="stSidebar"] a:hover {{ background: #F5F5F3 !important; color: #1A1A1A !important; }}
       .auth-img-box {{ width: 100%; min-height: 560px; height: 100%; background-size: cover; background-position: center; border-radius: 8px; }}
       .gemini-chat-container {{ max-width: 760px; margin: 0 auto 1.25rem; padding: 0.5rem 0.25rem; border: none; background: transparent; box-shadow: none; outline: none !important; -webkit-tap-highlight-color: transparent; }}
       .gemini-row {{ display: flex; margin-bottom: 1.1rem; outline: none !important; -webkit-tap-highlight-color: transparent; }}
       .gemini-row.gemini-row-user {{ justify-content: flex-end; }}
       .gemini-row.gemini-row-hugo {{ justify-content: flex-start; }}
       .gemini-bubble {{ max-width: 80%; outline: none !important; -webkit-tap-highlight-color: transparent; }}
       .gemini-bubble-user {{ background: #EEF1E9; border-radius: 16px 16px 4px 16px; padding: 8px 14px; }}
       .gemini-bubble-hugo {{ max-width: 100%; }}
       .gemini-user-label {{ font-weight: 600; font-size: 0.72rem; color: #666666; margin-bottom: 3px; text-align: right; }}
       .gemini-hugo-label {{ font-weight: 700; font-size: 0.78rem; color: #4A5D32; margin-bottom: 3px; }}
       .gemini-text {{ font-size: 0.88rem; line-height: 1.45; color: #202124; white-space: pre-line; outline: none !important; -webkit-tap-highlight-color: transparent; }}
       .gemini-chat-container ::selection {{ background: rgba(74, 93, 50, 0.25) !important; color: #1A1A1A !important; }}
       .gemini-chat-container ::-moz-selection {{ background: rgba(74, 93, 50, 0.25) !important; color: #1A1A1A !important; }}
       .gemini-chat-container, .gemini-chat-container * {{ outline: none !important; -webkit-tap-highlight-color: transparent !important; }}
       .gemini-chat-container *:focus, .gemini-chat-container *:focus-visible, .gemini-chat-container *:active {{ outline: none !important; box-shadow: none !important; }}
       [data-testid="stTabs"] [data-baseweb="tab-list"] {{ position: sticky !important; top: 3.5rem !important; background: #FFFFFF !important; z-index: 100 !important; }}
       div[data-testid="stChatInput"] {{ background-color: transparent !important; border: none !important; padding: 0 !important; overflow: visible !important; }}
       div[data-testid="stChatInput"] textarea {{ border-radius: 24px !important; }}

       /* Custom Loading Animation */
       .loading-circle {{
           width: 40px; height: 40px;
           border: 4px solid #f3f3f3;
           border-top: 4px solid #4A5D32;
           border-radius: 50%;
           animation: spin 1s linear infinite;
           margin: 20px auto;
       }}
       @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
    """, unsafe_allow_html=True)
 !important; color: #1A1A1A !important; }}
       .gemini-chat-container ::-moz-selection {{ background: rgba(74, 93, 50, 0.25) !important; color: #1A1A1A !important; }}
       .gemini-chat-container, .gemini-chat-container * {{ outline: none !important; -webkit-tap-highlight-color: transparent !important; }}
       .gemini-chat-container *:focus, .gemini-chat-container *:focus-visible, .gemini-chat-container *:active {{ outline: none !important; box-shadow: none !important; }}
       [data-testid="stTabs"] [data-baseweb="tab-list"] {{ position: sticky !important; top: 3.5rem !important; background: #FFFFFF !important; z-index: 100 !important; }}
       div[data-testid="stChatInput"] {{ background-color: transparent !important; border: none !important; padding: 0 !important; overflow: visible !important; }}
       div[data-testid="stChatInput"] textarea {{ border-radius: 24px !important; }}
    """, unsafe_allow_html=True)
