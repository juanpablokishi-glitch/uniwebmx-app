import streamlit as st
from core.config import carrusel_locker_url, carrusel_consultor_url, carrusel_simulador_url, carrusel_orientacion_url

def render_inicio():
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

    _carrusel_slides = [
        ("Locker digital", "Kárdex, ensayos y diplomas en un solo lugar.", carrusel_locker_url, "linear-gradient(135deg,#5C6B4A,#7C8A6A)"),
        ("Consultor IA", "Retroalimentación en tiempo real de Hugo.", carrusel_consultor_url, "linear-gradient(135deg,#6B5D3F,#8C7B54)"),
        ("Simulador estadístico", "Tus probabilidades reales de aceptación.", carrusel_simulador_url, "linear-gradient(135deg,#4A5A5C,#6B8083)"),
        ("Orientación vocacional", "Descubre tu perfil profesional con IA.", carrusel_orientacion_url, "linear-gradient(135deg,#4A5D32,#7C8A6A)"),
    ]

    def _uw_slide_html(titulo, desc, img_url, fallback_bg):
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

    _uw_slides_html = "".join(_uw_slide_html(*s) for s in _carrusel_slides) * 2
    st.markdown(
        f'<div class="uw-carrusel-viewport"><div class="uw-carrusel-track">{_uw_slides_html}</div></div>'
        f'<div style="text-align:center;font-size:11px;color:#999;margin-top:14px;">pasa el mouse encima para pausar</div>',
        unsafe_allow_html=True,
    )

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

def render_ranking():
    st.markdown("""
    <div style="max-width:900px;margin:0 auto;padding-top:2rem;">
        <p style="font-size:0.8rem;font-weight:600;letter-spacing:0.12em;text-transform:uppercase;color:#4A5D32;margin-bottom:0.5rem;">Ranking 2026</p>
        <h1 style="font-size:2.8rem;font-weight:700;color:#1A1A1A;letter-spacing:-0.03em;margin-bottom:0.5rem;">Las mejores universidades de México</h1>
        <p style="font-size:1.1rem;color:#666666;line-height:1.7;margin-bottom:3rem;">Basado en el QS World University Rankings 2027, colegiaturas reales 2026 y tasas de aceptación verificadas.</p>
    </div>
    """, unsafe_allow_html=True)

    universidades_ranking = [
        {"pos": 1, "nombre": "UNAM", "tipo": "Pública", "qs": "#145 mundial", "aceptacion": "~9%", "colegiatura": "Gratuita (cuota simbólica)", "examen": "Propio UNAM — 120 reactivos, 3 hrs", "fortalezas": "Medicina · Derecho · Ciencias · Humanidades", "color": "#1A3A5C"},
        {"pos": 2, "nombre": "Tec de Monterrey", "tipo": "Privada", "qs": "#188 mundial", "aceptacion": "~25%", "colegiatura": "$155k–$189k / semestre", "examen": "PAA (College Board) — mín. 1,320 pts", "fortalezas": "Negocios · Ingeniería · Arquitectura · Medicina", "color": "#003057"},
        {"pos": 3, "nombre": "UAG", "tipo": "Privada", "qs": "#1201–1400 mundial", "aceptacion": "~80%", "colegiatura": "$27k–$69k / semestre", "examen": "PAA (College Board) + autobiografía", "fortalezas": "Medicina · Odontología · Negocios · Arquitectura", "color": "#2C2C2C"},
        {"pos": 4, "nombre": "UP", "tipo": "Privada", "qs": "Top México", "aceptacion": "~78%", "colegiatura": "$177k / semestre", "examen": "Examen propio + entrevista", "fortalezas": "Derecho · Filosofía · Medicina · Negocios", "color": "#5A1A1A"},
        {"pos": 5, "nombre": "UdeG", "tipo": "Pública", "qs": "#1001–1200 mundial", "aceptacion": "~34.5%", "colegiatura": "Gratuita (cuota mínima)", "examen": "CUAAD / examen propio por centro universitario", "fortalezas": "Ciencias de la Salud · Exactas · Sociales · Artes", "color": "#1B4D3E"},
        {"pos": 6, "nombre": "ITESO", "tipo": "Privada", "qs": "#1201–1400 mundial", "aceptacion": "~75%", "colegiatura": "$90k–$130k / semestre", "examen": "Examen propio + ficha de admisión", "fortalezas": "Ingeniería · Negocios · Diseño · Comunicación", "color": "#1A3A5C"},
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

def render_blog():
    st.markdown("""
    <div style="max-width:860px;margin:0 auto;padding-top:2rem;">
        <p style="font-size:0.8rem;font-weight:600;letter-spacing:0.12em;text-transform:uppercase;color:#4A5D32;margin-bottom:0.5rem;">Recursos</p>
        <h1 style="font-size:2.8rem;font-weight:700;color:#1A1A1A;letter-spacing:-0.03em;margin-bottom:0.5rem;">Blog de Admisiones</h1>
        <p style="font-size:1.1rem;color:#666666;line-height:1.7;margin-bottom:3rem;">Estamos preparando contenido valioso para ayudarte en tu camino. ¡Vuelve pronto!</p>
    </div>
    """, unsafe_allow_html=True)
