import google.generativeai as genai
import json
from core.config import GEMINI_MODEL, UNIVERSIDADES_DATA

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

def get_ia_adjustment(unis_para_simular, contenido_kardex, contenido_ensayo):
    """
    Requests a qualitative adjustment from Hugo based on the student's profile.
    Returns a dict with adjustments and justifications.
    """
    if not contenido_kardex and not contenido_ensayo:
        return {}

    try:
        lista_unis_txt = ", ".join(unis_para_simular)
        prompt_ajuste = (
            f"Eres Hugo, consultor de admisiones. Con base en este kárdex y/o ensayo del "
            f"alumno, da un AJUSTE cualitativo (entero, entre -8 y 8) a la probabilidad base "
            f"de aceptación para cada una de estas universidades: {lista_unis_txt}. "
            f"Un ajuste positivo significa que el perfil cualitativo (logros, narrativa del "
            f"ensayo, actividades) suma a favor del alumno; negativo si hay señales débiles. "
            f"Responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional, sin markdown, con "
            f"este formato exacto, usando exactamente estos nombres de universidad como claves: "
            f'{{"{unis_para_simular[0]}": {{"ajuste": 0, "justificacion": "..."}}, ...}}. '
            f"La justificación debe ser de máximo 15 palabras.\n\n"
            f"KÁRDEX: {contenido_kardex}\n\nENSAYO: {contenido_ensayo}"
        )
        model_ajuste = genai.GenerativeModel(GEMINI_MODEL)
        respuesta_ajuste = model_ajuste.generate_content(prompt_ajuste)
        texto_limpio = respuesta_ajuste.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(texto_limpio)
    except Exception:
        return {}
