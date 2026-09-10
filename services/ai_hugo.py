import streamlit as st
import google.generativeai as genai
import json
import re as _re_hugo
from core.config import GEMINI_MODEL, MAX_HISTORIAL_GEMINI, UNIVERSIDADES_DATA
from core.database import guardar_conversacion_entrenamiento

# --- AI Helpers ---

def _quitar_emojis(texto):
    """Removes emojis from text to prevent rendering issues in some environments."""
    if not texto:
        return texto
    _EMOJI_PATTERN = _re_hugo.compile(
        "["
        "\U0001F300-\U0001FAFF"
        "\U00002600-\U000027BF"
        "\U0001F1E6-\U0001F1FF"
        "\U00002B00-\U00002BFF"
        "\U0001F900-\U0001F9FF"
        "\U0000FE00-\U0000FE0F"
        "\U0000200D"
        "]+",
        flags=_re_hugo.UNICODE,
    )
    return _EMOJI_PATTERN.sub("", texto).strip()

# --- Core AI Logic ---

def _interpretar_conversacion_orientacion(historial_qna):
    """
    Analyzes a conversation to estimate RIASEC and IPIP scores.
    Returns dict {"riasec": {...}, "ipip": {...}} or None.
    """
    transcript = "\n\n".join(f"P: {qa['pregunta']}\nR: {qa['respuesta']}" for qa in historial_qna)
    prompt_sistema = (
        "Eres un psicólogo vocacional experto en el modelo RIASEC de Holland y en el modelo de "
        "personalidad Big Five (IPIP). Vas a leer una conversación breve con un estudiante de "
        "preparatoria y vas a ESTIMAR sus puntajes, basándote en el contenido y tono de sus "
        "respuestas (no en contar palabras literalmente).\n\n"
        "Responde ÚNICAMENTE con un objeto JSON válido, sin texto antes ni después, sin backticks, "
        "exactamente con esta forma:\n"
        '{"riasec": {"R": 0, "I": 0, "A": 0, "S": 0, "E": 0, "C": 0}, '
        '"ipip": {"extraversion": 3.0, "amabilidad": 3.0, "responsabilidad": 3.0, '
        '"estabilidad": 3.0, "apertura": 3.0}}\n\n'
        "Cada valor de 'riasec' es un entero de 0 a 10 (qué tanto encaja ese interés con lo que "
        "describió). Cada valor de 'ipip' es un número de 1.0 a 5.0 (qué tan presente parece estar "
        "ese rasgo de personalidad)."
    )
    try:
        model_interp = genai.GenerativeModel(GEMINI_MODEL, system_instruction=prompt_sistema)
        respuesta_interp = model_interp.generate_content(transcript)
        texto_interp = respuesta_interp.text.strip().replace("```json", "").replace("```", "").strip()
        data = json.loads(texto_interp)
        if "riasec" not in data or "ipip" not in data:
            return None
        return data
    except Exception:
        return None

def construir_contexto_universidades(universidades_interes=None):
    """
    Builds a text block with verified info from UNIVERSIDADES_DATA to inject into Hugo's context.
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

# --- Real-time Grounding ---

_PATRON_FECHA_PROCESO = _re_hugo.compile(
    r"\b(fecha|fechas|cu[aá]ndo|calendario|plazo|plazos|vence|vencimiento|"
    r"l[ií]mite|inscripci[oó]n|inscribirse|registro|convocatoria|"
    r"proceso de admisi[oó]n|cu[aá]nto tiempo|este (a[ñn]o|ciclo|semestre)|"
    r"20(2[5-9]|3\d))\b",
    _re_hugo.IGNORECASE,
)

def detectar_necesidad_busqueda_tiempo_real(texto_alumno, universidades_interes=None):
    """Determines if the message warrants a real-time Google search."""
    if not texto_alumno or not _PATRON_FECHA_PROCESO.search(texto_alumno):
        return None

    texto_low = texto_alumno.lower()
    for nombre in UNIVERSIDADES_DATA.keys():
        if nombre.lower() in texto_low:
            return nombre

    universidades_interes = universidades_interes or []
    if len(universidades_interes) == 1:
        return universidades_interes[0]

    return None

def buscar_info_actualizada_universidad(universidad, pregunta_alumno):
    """Performs a real-time search using Gemini Grounding with Google Search."""
    try:
        from google import genai as genai_nuevo
        from google.genai import types as genai_types

        cliente_busqueda = genai_nuevo.Client(api_key=st.secrets["GEMINI_API_KEY"])
        herramienta_busqueda = genai_types.Tool(google_search=genai_types.GoogleSearch())

        prompt_busqueda = (
            f"Busca información oficial y actualizada (2025-2026) sobre el "
            f"proceso de admisión de '{universidad}' en México, en relación "
            f"con esta pregunta de un aspirante a licenciatura: "
            f"\"{pregunta_alumno}\"\n\n"
            f"Enfócate en fechas, plazos, calendario o requisitos de "
            f"proceso. Responde en español, en 3-5 líneas, mencionando de "
            f"qué fuente sale cada dato (nombre del sitio, no la URL "
            f"completa). Si no encuentras el dato exacto, dilo explícitamente "
            f"en vez de inventarlo."
        )

        respuesta = cliente_busqueda.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt_busqueda,
            config=genai_types.GenerateContentConfig(
                tools=[herramienta_busqueda],
                temperature=1.0,
            ),
        )
        texto = (respuesta.text or "").strip()
        return texto or None
    except Exception:
        return None

# --- Chat Interaction & Streaming ---

def get_hugo_response_stream(prompt, historial, system_instruction=None, stream=True):
    """
    Generates a response from Hugo.
    If stream=True, returns a generator for st.write_stream.
    """
    model = genai.GenerativeModel(
        GEMINI_MODEL,
        system_instruction=system_instruction
    )

    # Convert Streamlit history format to Gemini format
    gemini_history = [
        {"role": ("user" if m["role"] == "user" else "model"), "parts": [m["content"]]}
        for m in historial[-MAX_HISTORIAL_GEMINI:]
    ]

    chat = model.start_chat(history=gemini_history[:-1])

    if stream:
        response = chat.send_message(prompt, stream=True)
        for chunk in response:
            yield _quitar_emojis(chunk.text)
    else:
        response = chat.send_message(prompt)
        return _quitar_emojis(response.text)

def generar_analisis_perfil_universidad(nombre_uni, sub_df):
    """Generates an aggregated profile analysis for a university's interested students."""
    if sub_df.empty:
        return "Todavía no hay suficientes alumnos interesados en esta universidad para generar un análisis."

    edades = [e for e in sub_df["perfil_edad"].tolist() if isinstance(e, (int, float))]

    # Helper functions for frequencies (to be implemented or passed as args)
    # For now, we assume the calling UI handles the frequency counting and passes a summary
    # or we implement them here. Let's implement a simple version:
    def _count_freq(series):
        if series.empty: return {}
        return series.value_counts().to_dict()

    carreras_contador = _count_freq(sub_df["perfil_carreras"])
    top_carreras = ", ".join(f"{c} ({n})" for c, n in list(carreras_contador.items())[:8]) or "no especificadas"
    prepas_contador = _count_freq(sub_df["perfil_preparatoria"])
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
            GEMINI_MODEL,
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

def responder_consultor_panel(pregunta, df, historial):
    """Handles the 'Consultant Hugo' chat for the admin/university panel."""
    # Simplified frequency count for the prompt
    def _count_freq(series):
        if series.empty: return {}
        return series.value_counts().to_dict()

    top_carreras = _count_freq(df["perfil_carreras"])
    top_unis = _count_freq(df["universidades_interes"]) # Assuming it's a series of strings or similar

    total_mensajes = sum(
        1 for h in df["historial_chat"] for m in (h or []) if m.get("role") == "user"
    )

    # The actual role check should happen in the UI layer before calling this
    # but we include the context here for the prompt.
    contexto = (
        f"Total de alumnos en este alcance: {len(df)}\n"
        f"Perfil completo: {int(df['perfil_completo'].sum())}\n"
        f"Usaron el simulador: {int(df['simulador_usado'].sum())}\n"
        f"Mensajes totales enviados a Hugo: {total_mensajes}\n"
        f"Top carreras de interés: {list(top_carreras.items())[:10]}\n"
        f"Top universidades de interés: {list(top_unis.items())[:10]}\n"
    )

    system_instruction = (
        "Eres Hugo, pero ahora en modo 'consultor de datos' para el equipo interno de "
        "Uniwebmx o para una universidad socia. Te dan estadísticas agregadas y anónimas "
        "de uso de la plataforma; tu trabajo es ayudar a interpretarlas, encontrar patrones "
        "y sugerir acciones. Responde en español, de forma concisa y concreta. Si te "
        "preguntan algo que no puedes saber con estos datos (por ejemplo información "
        "individual de un alumno específico), dilo claramente en vez de inventar. No uses "
        "emojis en tus respuestas.\n\n"
        f"[DATOS DISPONIBLES]\n{contexto}"
    )

    return get_hugo_response_stream(
        prompt=pregunta,
        historial=historial,
        system_instruction=system_instruction,
        stream=False # Panel usually uses static responses, but can be switched to True
    )
