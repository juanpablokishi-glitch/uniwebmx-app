import streamlit as st
import pandas as pd
from datetime import datetime
from core.config import (
    RIASEC_LABELS, RIASEC_DESCRIPCIONES, RIASEC_ITEMS,
    IPIP_LABELS, IPIP_ITEMS, ORIENTACION_CONV_PREGUNTAS
)
from core.database import guardar_datos_usuario
from services.orientacion import calcular_riasec, calcular_ipip, carreras_sugeridas_por_codigo
from services.ai_hugo import _interpretar_conversacion_orientacion

def render_orientacion():
    st.markdown("""
    <div class="hero-section-locker">
        <h1 style='font-size: 3.5rem; margin-bottom: 1.5rem; max-width: 900px; margin-left: auto; margin-right: auto;'>Orientación Vocacional</h1>
        <p style='font-size: 1.35rem; color: #1A1A1A; max-width: 850px; margin: 0 auto; line-height: 1.6; font-weight: 400; opacity: 0.9;'>
            Un test de intereses (RIASEC) y de personalidad (IPIP) para ayudarte a descubrir qué carreras encajan mejor contigo.
        </p>
    </div>
    """, unsafe_allow_html=True)

    if "orientacion_paso" not in st.session_state:
        st.session_state.orientacion_paso = 0

    _paso = st.session_state.orientacion_paso
    _categorias_orden = ["R", "I", "A", "S", "E", "C"]

    # --- Paso 0: intro ---
    if _paso == 0:
        _resultado_previo = st.session_state.get("resultados_orientacion")
        if _resultado_previo:
            _tipo_previo = _resultado_previo.get("tipo", "completo")
            _etiqueta_tipo = "mini-test conversacional (estimado)" if _tipo_previo == "conversacional" else "test completo"
            st.success(f"Ya tienes un resultado guardado ({_etiqueta_tipo}): tu código Holland es **{_resultado_previo.get('codigo_top3', '')}**.")
            col_ver, col_repetir = st.columns(2)
            with col_ver:
                if st.button("Ver mi resultado", use_container_width=True):
                    st.session_state.orientacion_paso = 8
                    st.rerun()
            with col_repetir:
                if st.button("Volver a hacer el test", use_container_width=True):
                    st.session_state.orientacion_paso = 0
                    st.session_state.pop("resultados_orientacion", None)
                    st.rerun()
        else:
            st.markdown("""
            <div style="background:#F5F5F3;border-radius:12px;padding:20px 24px;margin-bottom:1.2rem;">
                <p style="margin:0 0 10px;font-weight:600;">Elige cómo hacerlo</p>
                <ul style="margin:0;padding-left:18px;line-height:1.7;color:#333;">
                    <li><b>Test completo (RIASEC + IPIP):</b> 60 actividades de intereses + 20 frases de personalidad. Toma 20-25 minutos y da el resultado más preciso.</li>
                    <li><b>Mini-test conversacional con Hugo:</b> una plática de 8 preguntas abiertas, ~5 minutos. Hugo estima tu perfil a partir de lo que le cuentes — es más rápido pero menos exacto.</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
            st.caption("Basado en el O*NET Interest Profiler (U.S. Department of Labor, licencia CC BY 4.0) y el Mini-IPIP (Donnellan et al., 2006), ambos de uso libre.")
            col_completo, col_conv = st.columns(2)
            with col_completo:
                if st.button("Test completo", type="primary", use_container_width=True):
                    st.session_state.orientacion_paso = 1
                    st.rerun()
            with col_conv:
                if st.button("Mini-test con Hugo", use_container_width=True):
                    st.session_state.orientacion_conv_qna = []
                    st.session_state.orientacion_conv_indice = 0
                    st.session_state.orientacion_paso = 9
                    st.rerun()

    # --- Pasos 1-6: RIASEC ---
    elif 1 <= _paso <= 6:
        _cat = _categorias_orden[_paso - 1]
        st.progress(_paso / 8, text=f"Parte 1 de 2 — Intereses ({_paso}/6)")
        st.markdown(f"##### {RIASEC_LABELS[_cat]}")
        st.caption("Marca las actividades que te gustaría hacer. No pienses en el sueldo ni en cuánto estudio necesitan, solo en si te gustaría hacerlas.")
        with st.form(f"form_riasec_{_cat}"):
            _indices_cat = [i for i, item in enumerate(RIASEC_ITEMS) if item["cat"] == _cat]
            for i in _indices_cat:
                st.checkbox(RIASEC_ITEMS[i]["texto"], key=f"riasec_{i}")
            _texto_boton = "Siguiente" if _paso < 6 else "Continuar a personalidad"
            _avanzar = st.form_submit_button(_texto_boton, type="primary", use_container_width=True)
        if _paso > 1:
            if st.button("← Atrás", key=f"atras_riasec_{_cat}"):
                st.session_state.orientacion_paso -= 1
                st.rerun()
        if _avanzar:
            st.session_state.orientacion_paso += 1
            st.rerun()

    # --- Paso 7: IPIP ---
    elif _paso == 7:
        st.progress(7 / 8, text="Parte 2 de 2 — Personalidad")
        st.markdown("##### ¿Qué tan bien te describe cada frase?")
        st.caption("1 = Muy en desacuerdo · 5 = Muy de acuerdo")
        with st.form("form_ipip"):
            for i, item in enumerate(IPIP_ITEMS):
                st.select_slider(
                    item["texto"],
                    options=[1, 2, 3, 4, 5],
                    value=st.session_state.get(f"ipip_{i}", 3),
                    key=f"ipip_{i}",
                )
            _finalizar = st.form_submit_button("Ver mis resultados", type="primary", use_container_width=True)
        if st.button("← Atrás", key="atras_ipip"):
            st.session_state.orientacion_paso -= 1
            st.rerun()
        if _finalizar:
            _resp_riasec = {i: st.session_state.get(f"riasec_{i}", False) for i in range(len(RIASEC_ITEMS))}
            _resp_ipip = {i: st.session_state.get(f"ipip_{i}", 3) for i in range(len(IPIP_ITEMS))}
            _puntajes_riasec, _codigo_top3 = calcular_riasec(_resp_riasec)
            _perfil_ipip = calcular_ipip(_resp_ipip)
            st.session_state.resultados_orientacion = {
                "riasec_puntajes": _puntajes_riasec,
                "codigo_top3": _codigo_top3,
                "ipip": _perfil_ipip,
                "fecha": datetime.now().isoformat(),
                "tipo": "completo",
            }
            guardar_datos_usuario(st.session_state.get("user"), st.session_state.__dict__)
            st.session_state.orientacion_paso = 8
            st.rerun()

    # --- Paso 8: resultados ---
    elif _paso == 8:
        _resultado = st.session_state.get("resultados_orientacion")
        if not _resultado:
            st.warning("Todavía no tienes un resultado. Empieza el test primero.")
            if st.button("Ir al inicio del test"):
                st.session_state.orientacion_paso = 0
                st.rerun()
        else:
            _puntajes = _resultado["riasec_puntajes"]
            _codigo = _resultado["codigo_top3"]
            _ipip = _resultado["ipip"]
            _tipo_resultado = _resultado.get("tipo", "completo")

            if _tipo_resultado == "conversacional":
                st.info("Este es un resultado **estimado** por Hugo a partir de tu mini-test conversacional. Si quieres algo más preciso, puedes hacer el test completo cuando quieras.")

            st.markdown(f"### Tu código Holland: {_codigo}")
            st.caption("Las 3 letras representan, en orden, tus intereses vocacionales más fuertes.")
            for letra in _codigo:
                st.markdown(f"**{letra} — {RIASEC_LABELS[letra]}:** {RIASEC_DESCRIPCIONES[letra]}")

            st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)
            st.markdown("##### Tu perfil de intereses (RIASEC)")
            _df_riasec = pd.DataFrame(
                [(RIASEC_LABELS[c], _puntajes[c]) for c in _categorias_orden],
                columns=["Categoría", "Puntaje (de 10)"],
            ).set_index("Categoría")
            st.bar_chart(_df_riasec)

            st.markdown("##### Tu perfil de personalidad (IPIP)")
            _df_ipip = pd.DataFrame(
                [(IPIP_LABELS[r], _ipip[r]) for r in IPIP_LABELS],
                columns=["Rasgo", "Puntaje (1-5)"],
            ).set_index("Rasgo")
            st.bar_chart(_df_ipip)

            st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)
            st.markdown("##### Carreras que podrían encajar contigo")
            _sugerencias = carreras_sugeridas_por_codigo(_codigo)
            if _sugerencias:
                for _carrera, _puntaje in _sugerencias:
                    st.markdown(f"- **{_carrera}**")
            else:
                st.caption("No encontramos coincidencias fuertes todavía — puedes explorar el Ranking de universidades para ver más opciones.")

            st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)
            col_repetir_r, col_otro_modo = st.columns(2)
            with col_repetir_r:
                if st.button("Volver a hacer este mismo test", use_container_width=True):
                    for i in range(len(RIASEC_ITEMS)):
                        st.session_state.pop(f"riasec_{i}", None)
                    for i in range(len(IPIP_ITEMS)):
                        st.session_state.pop(f"ipip_{i}", None)
                    st.session_state.pop("resultados_orientacion", None)
                    st.session_state.orientacion_paso = 1 if _tipo_resultado == "completo" else 0
                    st.rerun()
            with col_otro_modo:
                if _tipo_resultado == "conversacional":
                    if st.button("Mejor hacer el test completo", type="primary", use_container_width=True):
                        st.session_state.orientacion_paso = 1
                        st.rerun()
                else:
                    if st.button("Probar el mini-test con Hugo", use_container_width=True):
                        st.session_state.orientacion_conv_qna = []
                        st.session_state.orientacion_conv_indice = 0
                        st.session_state.orientacion_paso = 9
                        st.rerun()

    # --- Paso 9: mini-test conversacional con Hugo ---
    elif _paso == 9:
        st.markdown("##### Mini-test con Hugo")
        st.caption("Responde con tus propias palabras, no hay respuestas correctas o incorrectas.")

        if "orientacion_conv_qna" not in st.session_state:
            st.session_state.orientacion_conv_qna = []
        if "orientacion_conv_indice" not in st.session_state:
            st.session_state.orientacion_conv_indice = 0

        _indice_conv = st.session_state.orientacion_conv_indice
        _total_preguntas_conv = len(ORIENTACION_CONV_PREGUNTAS)

        for _qa in st.session_state.orientacion_conv_qna:
            with st.chat_message("assistant"):
                st.write(_qa["pregunta"])
            with st.chat_message("user"):
                st.write(_qa["respuesta"])

        if _indice_conv < _total_preguntas_conv:
            _pregunta_actual = ORIENTACION_CONV_PREGUNTAS[_indice_conv]
            with st.chat_message("assistant"):
                st.write(_pregunta_actual)
            st.progress((_indice_conv) / _total_preguntas_conv, text=f"Pregunta {_indice_conv + 1} de {_total_preguntas_conv}")
            _respuesta_conv = st.chat_input("Escribe tu respuesta...")
            if _respuesta_conv:
                st.session_state.orientacion_conv_qna.append({"pregunta": _pregunta_actual, "respuesta": _respuesta_conv})
                st.session_state.orientacion_conv_indice += 1
                st.rerun()
            if st.button("← Cancelar y volver"):
                st.session_state.orientacion_paso = 0
                st.rerun()
        else:
            with st.spinner("Hugo está pensando en tu perfil..."):
                _interpretacion = _interpretar_conversacion_orientacion(st.session_state.orientacion_conv_qna)
            if not _interpretacion:
                st.error("No pudimos generar tu resultado en este momento. Intenta de nuevo en un momento, o haz el test completo para un resultado garantizado.")
                col_reintentar, col_ir_completo = st.columns(2)
                with col_reintentar:
                    if st.button("Reintentar", use_container_width=True):
                        st.rerun()
                with col_ir_completo:
                    if st.button("Hacer el test completo", use_container_width=True):
                        st.session_state.orientacion_paso = 1
                        st.rerun()
            else:
                _riasec_est = _interpretacion["riasec"]
                _orden_desempate_conv = ["R", "I", "A", "S", "E", "C"]
                _ranking_conv = sorted(_riasec_est.keys(), key=lambda c: (-_riasec_est.get(c, 0), _orden_desempate_conv.index(c) if c in _orden_desempate_conv else 99))
                _codigo_conv = "".join(_ranking_conv[:3])
                st.session_state.resultados_orientacion = {
                    "riasec_puntajes": {c: _riasec_est.get(c, 0) for c in _orden_desempate_conv},
                    "codigo_top3": _codigo_conv,
                    "ipip": _interpretacion["ipip"],
                    "fecha": datetime.now().isoformat(),
                    "tipo": "conversacional",
                }
                guardar_datos_usuario(st.session_state.get("user"), st.session_state.__dict__)
                st.session_state.orientacion_paso = 8
                st.rerun()
