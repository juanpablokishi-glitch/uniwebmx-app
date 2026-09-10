import streamlit as st
import pandas as pd
import altair as alt
from core.config import UNIVERSIDADES_DATA
from core.database import guardar_datos_usuario, log_evento
from services.simulador import calcular_probabilidad_base, get_ia_adjustment

def render_simulador():
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

                # --- AJUSTE CUALITATIVO DE HUGO ---
                contenido_kardex = st.session_state.get("kárdex", {}).get("contenido", "")
                contenido_ensayo = st.session_state.get("ensayo", {}).get("contenido", "")

                datos_ia = get_ia_adjustment(unis_para_simular, contenido_kardex, contenido_ensayo)

                for nombre_uni in resultados:
                    if nombre_uni in datos_ia:
                        ajuste = max(-8, min(8, int(datos_ia[nombre_uni].get("ajuste", 0))))
                        resultados[nombre_uni]["ajuste_ia"] = ajuste
                        resultados[nombre_uni]["justificacion_ia"] = datos_ia[nombre_uni].get("justificacion", "")

                for nombre_uni, r in resultados.items():
                    r["prob_final"] = max(5, min(98, round(r["prob_base"] + r["ajuste_ia"], 1)))

                st.session_state.resultados_simulador = resultados
                st.session_state.simulador_usado = True
                log_evento(st.session_state.get("user"), "simulador_usado", {"universidades": list(resultados.keys())})
                guardar_datos_usuario(st.session_state.get("user"), st.session_state.__dict__)
                st.rerun()

    if "resultados_simulador" in st.session_state:
        resultados = st.session_state.resultados_simulador

        df_grafica = pd.DataFrame({
            "Universidad": list(resultados.keys()),
            "Probabilidad (%)": [r["prob_final"] for r in resultados.values()],
        })

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
