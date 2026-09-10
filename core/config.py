import streamlit as st
import google.generativeai as genai
from datetime import datetime

# --- API Configuration ---
# Use st.secrets for security in Streamlit Cloud
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=GEMINI_API_KEY)

# Model used for all AI interactions
GEMINI_MODEL = "gemini-2.5-flash"

# Max previous messages to send as context to Gemini (User + Assistant)
MAX_HISTORIAL_GEMINI = 12

# Session Token duration
SESSION_TOKEN_DIAS = 30

# Login Rate Limiting
MAX_INTENTOS_LOGIN = 5
BLOQUEO_MINUTOS = 15

# Supabase Storage Bucket
BUCKET = "locker-archivos"
SUPABASE_URL = st.secrets["SUPABASE_URL"]
PUBLIC_STORAGE_URL = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}"

# Carousel images in the public bucket
carrusel_locker_url = f"{PUBLIC_STORAGE_URL}/fondo_carrusel_locker.png"
carrusel_consultor_url = f"{PUBLIC_STORAGE_URL}/fondo_carrusel_consultor.png"
carrusel_simulador_url = f"{PUBLIC_STORAGE_URL}/fondo_carrusel_simulador.png"
carrusel_orientacion_url = f"{PUBLIC_STORAGE_URL}/fondo_carrusel_orientacion.png"

# Admin Panel Pages
PANEL_ADMIN_PAGES = [
    "panel_admin", "panel_chat", "panel_simulador",
    "panel_carreras", "panel_perfiles", "panel_carreras_perfiles", "panel_consultor", "panel_usuarios",
]

# --- Static Data ---

PROVEEDORES_IMAP = {
    "Gmail": "imap.gmail.com",
    "Outlook / Hotmail": "outlook.office365.com",
    "Yahoo": "imap.mail.yahoo.com",
    "iCloud": "imap.mail.me.com",
    "Otro (servidor personalizado)": None,
}

UNIV_DOMINIOS = {
    "Tec de Monterrey": ["tec.mx", "itesm.mx"],
    "UdeG": ["udg.mx"],
    "UP": ["up.edu.mx"],
    "ITESO": ["iteso.mx"],
    "UNAM": ["unam.mx"],
    "UAG": ["uag.mx"],
}

# University reference data for the simulator and Hugo
UNIVERSIDADES_DATA = {
    "Tec de Monterrey": {
        "promedio_min": 8.5,
        "examen_min": 82,
        "tasa_historica": 25,
        "confianza": "oficial",
        "fuente": "Promedio mínimo 8.5 y PAA mínimo ~1,320/1,600 pts; tasa de aceptación ~25%.",
        "documentos": ["kardex", "ensayo", "curriculum", "cartas", "acta", "curp", "identificacion", "foto", "comprobante"],
        "documentos_extra": ["Ficha de inscripción pagada", "Resultado oficial del PAA/examen de admisión"],
        "proceso": [
            "Crear solicitud en solicitud.tec.mx",
            "Pagar cuota de admisión (~$1,300 MXN)",
            "Presentar examen PAA (o entregar SAT/ACT convertido a escala PAA)",
            "Llenar currículo y ensayo (pesan en la decisión final, no son trámite)",
            "Recibir resultado en ~15 días por correo y portal",
        ],
        "fechas_clave": "Para becas de talento académico, el PAA debe presentarse antes del 17 de enero 2026 (Medicina: 13 dic 2025). Resultados de becas: 26 feb 2026.",
        "costos": {
            "examen_admision": "$1,300 MXN (cuota de admisión)",
            "reserva_de_lugar": "$7,000–$9,000 MXN según si hay beca",
            "colegiatura": "Variable por campus/carrera — usar cotizador oficial del Tec",
        },
        "becas": ["Beca al Talento Académico (requiere PAA alto, varía por tipo)", "Becas socioeconómicas con préstamo educativo complementario"],
        "notas_hugo": "El 'puntaje PAA mínimo' no es un corte único de admisión — los rangos de 1,000-1,360 que existen son requisitos de BECA, no de entrada. No los presentes como si fueran el mínimo para ser acept도.",
    },
    "UdeG": {
        "promedio_min": 8.0,
        "examen_min": 70,
        "tasa_historica": 33.5,
        "confianza": "parcial",
        "fuente": "Tasa de aceptación oficial 2026-A: 56,202 admitidos de 167,690 aspirantes (~33.5%). El puntaje mínimo real varía por carrera y centro universitario, no es un número fijo.",
        "documentos": ["kardex", "acta", "curp", "identificacion", "foto", "comprobante"],
        "documentos_extra": ["Ficha PRECOSECH / pago de derechos", "Certificado de bachillerato (no solo kárdex)"],
        "proceso": [
            "Registro PRECOSECH y pago de derechos",
            "Presentar PAA del College Board (la sección de inglés no cuenta para el puntaje final)",
            "Puntaje total = resultado PAA + promedio de bachillerato",
            "Publicación de dictamen (varía según calendario, ~1 semana antes de inicio de clases)",
            "Si no fue admitido: solicitar cambio a carrera con cupo disponible en los días inmediatos al dictamen",
        ],
        "fechas_clave": "Calendario 2026-A: dictamen publicado 12 enero 2026; inicio de clases 19 enero 2026.",
        "costos": {
            "examen_admision": "Costo de trámite PRECOSECH, varía por calendario — confirmar monto vigente",
            "colegiatura": "Universidad pública, cuotas simbólicas comparadas con privadas",
        },
        "becas": ["Becas SEP / gobierno federal para alumnos de universidad pública (sujetas a convocatoria aparte)"],
        "notas_hugo": "El puntaje mínimo por carrera es DINÁMICO: lo define el último aspirante admitidocada ciclo. Nunca lo presentes como una cifra fija año con año — habla de rangos históricos como referencia, no como garantía.",
    },
    "UP": {
        "promedio_min": 8.0,
        "examen_min": 50,
        "tasa_historica": 78,
        "confianza": "estimado",
        "fuente": "No hay tasa de aceptación pública. Estimado a partir de fuentes que describen el ingreso como poco competitivo (excepto Medicina).",
        "documentos": ["kardex", "ensayo", "curriculum", "acta", "curp", "identificacion", "foto", "comprobante"],
        "documentos_extra": ["Entrevista de admisión agendada"],
        "proceso": [
            "Solicitud en línea (mkt.up.edu.mx)",
            "Examen PAA del College Board",
            "Examen psicométrico (día siguiente al PAA)",
            "Entrevista con un miembro de la comunidad académica",
            "Entrega de resultados",
        ],
        "fechas_clave": "Sujeto a calendario oficial de la UP.",
        "costos": {
            "examen_admision": "Consultar portal de admisiones",
            "colegiatura": "Consultar cotizador oficial de la UP",
        },
        "becas": ["Becas internas basadas en mérito académico y socioeconómico"],
        "notas_hugo": "La UP valora mucho el perfil humano y la entrevista, no solo el puntaje del PAA.",
    },
}

# URL base of the app
BASE_URL = st.secrets.get("BASE_URL", "http://localhost:8501")

# --- Orientation Test Constants ---

RIASEC_LABELS = {
    "R": "Realista",
    "I": "Investigador",
    "A": "Artístico",
    "S": "Social",
    "E": "Emprendedor",
    "C": "Convencional",
}

RIASEC_DESCRIPCIONES = {
    "R": "Te gusta trabajar con las manos, herramientas, máquinas o el aire libre.",
    "I": "Te gusta investigar, resolver problemas y entender cómo funcionan las cosas.",
    "A": "Te gusta crear, expresarte y trabajar en cosas originales o artísticas.",
    "S": "Te gusta ayudar, enseñar, cuidar o trabajar directamente con personas.",
    "E": "Te gusta liderar, vender, negociar y emprender proyectos o negocios.",
    "C": "Te gusta el orden, los datos precisos y seguir procesos claros.",
}

RIASEC_ITEMS = [
    {"texto": "Construir gabinetes de cocina", "cat": "R"},
    {"texto": "Colocar ladrillo o azulejo", "cat": "R"},
    {"texto": "Reparar electrodomésticos", "cat": "R"},
    {"texto": "Criar peces en un criadero", "cat": "R"},
    {"texto": "Ensamblar piezas electrónicas", "cat": "R"},
    {"texto": "Manejar un camión para repartir paquetes a oficinas y casas", "cat": "R"},
    {"texto": "Probar la calidad de piezas antes de enviarlas", "cat": "R"},
    {"texto": "Reparar e instalar cerraduras", "cat": "R"},
    {"texto": "Instalar y operar máquinas para fabricar productos", "cat": "R"},
    {"texto": "Apagar incendios forestales", "cat": "R"},
    {"texto": "Desarrollar un nuevo medicamento", "cat": "I"},
    {"texto": "Estudiar formas de reducir la contaminación del agua", "cat": "I"},
    {"texto": "Realizar experimentos químicos", "cat": "I"},
    {"texto": "Estudiar el movimiento de los planetas", "cat": "I"},
    {"texto": "Examinar muestras de sangre con un microscopio", "cat": "I"},
    {"texto": "Investigar la causa de un incendio", "cat": "I"},
    {"texto": "Desarrollar una forma de predecir mejor el clima", "cat": "I"},
    {"texto": "Trabajar en un laboratorio de biología", "cat": "I"},
    {"texto": "Inventar un sustituto del azúcar", "cat": "I"},
    {"texto": "Hacer pruebas de laboratorio para identificar enfermedades", "cat": "I"},
    {"texto": "Escribir libros u obras de teatro", "cat": "A"},
    {"texto": "Pintar escenografías para obras de teatro", "cat": "A"},
    {"texto": "Tocar un instrumento musical", "cat": "A"},
    {"texto": "Escribir guiones para películas o series de televisión", "cat": "A"},
    {"texto": "Componer o arreglar música", "cat": "A"},
    {"texto": "Bailar jazz o tap", "cat": "A"},
    {"texto": "Dibujar", "cat": "A"},
    {"texto": "Cantar en una banda", "cat": "A"},
    {"texto": "Crear efectos especiales para películas", "cat": "A"},
    {"texto": "Editar películas", "cat": "A"},
    {"texto": "Enseñarle a alguien una rutina de ejercicio", "cat": "S"},
    {"texto": "Enseñar a niños a practicar deportes", "cat": "S"},
    {"texto": "Ayudar a personas con problemas personales o emocionales", "cat": "S"},
    {"texto": "Enseñar lenguaje de señas a personas sordas o con dificultad auditiva", "cat": "S"},
    {"texto": "Dar orientación vocacional a las personas", "cat": "S"},
    {"texto": "Ayudar a dirigir una sesión de terapia grupal", "cat": "S"},
    {"texto": "Dar terapia de rehabilitación", "cat": "S"},
    {"texto": "Cuidar niños en una guardería", "cat": "S"},
    {"texto": "Hacer trabajo voluntario en una organización sin fines de lucro", "cat": "S"},
    {"texto": "Dar clases en preparatoria", "cat": "S"},
    {"texto": "Comprar y vender acciones y bonos", "cat": "E"},
    {"texto": "Negociar contratos de negocios", "cat": "E"},
    {"texto": "Administrar una tienda", "cat": "E"},
    {"texto": "Representar a un cliente en un juicio", "cat": "E"},
    {"texto": "Operar un salón de belleza o barbería", "cat": "E"},
    {"texto": "Comercializar una nueva línea de ropa", "cat": "E"},
    {"texto": "Administrar un departamento dentro de una empresa grande", "cat": "E"},
    {"texto": "Vender mercancía en una tienda departamental", "cat": "E"},
    {"texto": "Iniciar tu propio negocio", "cat": "E"},
    {"texto": "Administrar una tienda de ropa", "cat": "E"},
    {"texto": "Crear una hoja de cálculo con software de computadora", "cat": "C"},
    {"texto": "Calcular el salario de empleados", "cat": "C"},
    {"texto": "Revisar registros o formularios en busca de errores", "cat": "C"},
    {"texto": "Inventariar suministros con una computadora portátil", "cat": "C"},
    {"texto": "Instalar software en varias computadoras de una red grande", "cat": "C"},
    {"texto": "Registrar pagos de renta", "cat": "C"},
    {"texto": "Usar una calculadora", "cat": "C"},
    {"texto": "Llevar el control de inventarios", "cat": "C"},
    {"texto": "Llevar registros de envíos y recepciones", "cat": "C"},
    {"texto": "Sellar, clasificar y repartir correspondencia en una organización", "cat": "C"},
]

IPIP_LABELS = {
    "extraversion": "Extraversión",
    "amabilidad": "Amabilidad",
    "responsabilidad": "Responsabilidad",
    "estabilidad": "Estabilidad emocional",
    "apertura": "Apertura a la experiencia",
}

IPIP_ITEMS = [
    {"texto": "Soy el alma de la fiesta", "rasgo": "extraversion", "signo": 1},
    {"texto": "Hablo con mucha gente distinta en las fiestas", "rasgo": "extraversion", "signo": 1},
    {"texto": "No hablo mucho", "rasgo": "extraversion", "signo": -1},
    {"texto": "Prefiero quedarme en un segundo plano", "rasgo": "extraversion", "signo": -1},
    {"texto": "Me identifico con los sentimientos de los demás", "rasgo": "amabilidad", "signo": 1},
    {"texto": "Siento las emociones de otras personas", "rasgo": "amabilidad", "signo": 1},
    {"texto": "En realidad no me interesan los demás", "rasgo": "amabilidad", "signo": -1},
    {"texto": "No me interesan los problemas de otras personas", "rasgo": "amabilidad", "signo": -1},
    {"texto": "Hago mis pendientes de inmediato", "rasgo": "responsabilidad", "signo": 1},
    {"texto": "Me gusta el orden", "rasgo": "responsabilidad", "signo": 1},
    {"texto": "Frecuentemente olvido poner las cosas en su lugar", "rasgo": "responsabilidad", "signo": -1},
    {"texto": "Dejo las cosas hechas un desastre", "rasgo": "responsabilidad", "signo": -1},
    {"texto": "Tengo cambios de humor frecuentes", "rasgo": "estabilidad", "signo": -1},
    {"texto": "Me altero con facilidad", "rasgo": "estabilidad", "signo": -1},
    {"texto": "Estoy tranquilo(a) la mayor parte del tiempo", "rasgo": "estabilidad", "signo": 1},
    {"texto": "Casi nunca me siento triste", "rasgo": "estabilidad", "signo": 1},
    {"texto": "Tengo una imaginación muy vívida", "rasgo": "apertura", "signo": 1},
    {"texto": "Se me dificulta entender ideas abstractas", "rasgo": "apertura", "signo": -1},
    {"texto": "No me interesan las ideas abstractas", "rasgo": "apertura", "signo": -1},
    {"texto": "No tengo mucha imaginación", "rasgo": "apertura", "signo": -1},
]

CARRERAS_RIASEC = {
    "Administración": "EC",
    "Arquitectura": "AIR",
    "Comunicación": "ASE",
    "Contaduría": "CE",
    "Derecho": "ES",
    "Diseño": "AR",
    "Economía": "ICE",
    "Enfermería": "SI",
    "Filosofía": "IA",
    "Gastronomía": "RA",
    "Ingeniería en Sistemas / Software": "IRC",
    "Ingeniería Industrial": "RIC",
    "Ingeniería Mecatrónica": "RI",
    "Ingeniería Civil": "RI",
    "Marketing / Mercadotecnia": "EAS",
    "Medicina": "IS",
    "Negocios Internacionales": "ECS",
    "Psicología": "SIA",
    "Relaciones Internacionales": "SEI",
    "Veterinaria y Zootecnia": "IRS",
}

ORIENTACION_CONV_PREGUNTAS = [
    "Si tuvieras una tarde totalmente libre, sin pendientes ni tarea, ¿qué te gustaría hacer?",
    "Piensa en la última vez que resolviste algo que te dio mucha satisfacción. ¿Qué tipo de problema era?",
    "¿Prefieres trabajar solo, en equipo, o depende de la situación? Cuéntame por qué.",
    "¿Qué tema o materia podrías estudiar por horas sin aburrirte?",
    "Cuando algo no te sale como esperabas, ¿cómo reaccionas normalmente?",
    "¿Te imaginas más liderando tu propio proyecto o negocio, o en un rol de apoyo muy especializado en algo?",
    "¿Qué tan importante es para ti el orden y tener todo bien organizado en tu día a día?",
    "Si pudieras ayudar a resolver un problema del mundo, ¿cuál elegirías y por qué?",
]

# Re-adding DOCUMENTOS_LOCKER_INFO (Academic only)
DOCUMENTOS_LOCKER_INFO = {
    "kardex":         {"label": "Kárdex / Certificado",          "tipo": "académico"},
    "ensayo":         {"label": "Ensayo / Carta de motivos",     "tipo": "académico"},
    "curriculum":     {"label": "Currículum académico",          "tipo": "académico"},
    "cartas":         {"label": "Cartas de recomendación",       "tipo": "académico"},
    "portafolio":     {"label": "Portafolio / Extracurriculares","tipo": "académico"},
}

# URL base of the app
BASE_URL = st.secrets.get("BASE_URL", "http://localhost:8501")
