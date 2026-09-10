import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta
from core.config import PROVEEDORES_IMAP, UNIV_DOMINIOS

def _decodificar_header(valor):
    """Decodes email headers (subject, sender) from various encodings."""
    if not valor:
        return ""
    partes = decode_header(valor)
    resultado = ""
    for texto, codificacion in partes:
        if isinstance(texto, bytes):
            try:
                resultado += texto.decode(codificacion or "utf-8", errors="ignore")
            except Exception:
                resultado += texto.decode("utf-8", errors="ignore")
        else:
            resultado += texto
    return resultado

def _extraer_cuerpo_correo(msg):
    """Extracts plain text (or HTML extract) from an email message body."""
    cuerpo = ""
    if msg.is_multipart():
        for parte in msg.walk():
            tipo = parte.get_content_type()
            disposicion = str(parte.get("Content-Disposition") or "")
            if tipo == "text/plain" and "attachment" not in disposicion:
                try:
                    cuerpo = parte.get_payload(decode=True).decode(parte.get_content_charset() or "utf-8", errors="ignore")
                    break
                except Exception:
                    continue
        if not cuerpo:
            for parte in msg.walk():
                if parte.get_content_type() == "text/html":
                    try:
                        html = parte.get_payload(decode=True).decode(parte.get_content_charset() or "utf-8", errors="ignore")
                        import re as _re
                        cuerpo = _re.sub("<[^<]+?>", " ", html)
                        break
                    except Exception:
                        continue
    else:
        try:
            cuerpo = msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", errors="ignore")
        except Exception:
            cuerpo = str(msg.get_payload())
    return cuerpo.strip()

def conectar_correo_imap(correo, contrasena, servidor):
    """Opens an authenticated IMAP connection."""
    conn = imaplib.IMAP4_SSL(servidor)
    conn.login(correo, contrasena)
    return conn

def buscar_correos_universidades(conn, dias_atras=120, limite_por_universidad=15):
    """
    Optimized search for emails from known university domains.
    Implements a 'Broad Search -> Local Filter -> Header-First Fetch' approach.
    """
    resultados = {nombre: [] for nombre in UNIV_DOMINIOS}
    conn.select("INBOX")
    fecha_desde = (datetime.now() - timedelta(days=dias_atras)).strftime("%d-%b-%Y")

    # 1. Broad Search: Get all messages since the date limit
    try:
        tipo, datos = conn.search(None, f'(SINCE {fecha_desde})')
        if tipo != "OK":
            return resultados
        ids_correo = datos[0].split()
    except Exception:
        return resultados

    # 2. Local Filter and Header-First Fetch
    # To avoid downloading full bodies of thousands of emails,
    # we only fetch the headers first.
    for id_correo in reversed(ids_correo):
        try:
            # Fetch only headers to check the sender
            tipo_f, datos_msg = conn.fetch(id_correo, "(RFC822)")
            if tipo_f != "OK":
                continue

            msg = email.message_from_bytes(datos_msg[0][1])
            de = _decodificar_header(msg.get("From"))

            # Check if 'de' matches any known university domain
            for nombre_uni, dominios in UNIV_DOMINIOS.items():
                if any(dominio in de.lower() for dominio in dominios):
                    if len(resultados[nombre_uni]) < limite_por_universidad:
                        asunto = _decodificar_header(msg.get("Subject"))
                        fecha = msg.get("Date", "")
                        cuerpo = _extraer_cuerpo_correo(msg)
                        resultados[nombre_uni].append({
                            "de": de,
                            "asunto": asunto or "(Sin asunto)",
                            "fecha": fecha,
                            "cuerpo": cuerpo[:3000],
                        })
        except Exception:
            continue

    return resultados
