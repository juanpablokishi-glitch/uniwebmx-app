import streamlit as st
import io
import zipfile
import PyPDF2
from core.database import supabase_client
from core.config import BUCKET

def extraer_texto_archivo(archivo):
    """
    Reads PDF or TXT files and returns the text as a string.
    """
    texto = ""
    if archivo.type == "application/pdf":
        try:
            lector = PyPDF2.PdfReader(archivo)
            for pagina in lector.pages:
                texto += pagina.extract_text() or ""
        except Exception as e:
            st.error(f"Error al leer el PDF: {e}")
    elif archivo.type == "text/plain":
        texto = archivo.read().decode("utf-8")
    return texto

def _nombre_seguro(username):
    """Creates a safe filename for Supabase Storage."""
    return "".join(c for c in (username or "usuario") if c.isalnum() or c in ("_", "-")) or "usuario"

def guardar_archivo_original(username, tipo_documento, nombre_archivo, datos_bytes):
    """Uploads a file to Supabase Storage, replacing the previous one of the same type."""
    eliminar_archivo_original(username, tipo_documento)
    carpeta = _nombre_seguro(username)
    path = f"{carpeta}/{tipo_documento}__{nombre_archivo}"
    supabase_client.storage.from_(BUCKET).upload(
        path, datos_bytes,
        {"content-type": "application/octet-stream", "upsert": "true"}
    )
    return path

def obtener_archivo_original(username, tipo_documento):
    """Returns (bytes, original_name) of the stored file, or (None, None)."""
    carpeta = _nombre_seguro(username)
    try:
        archivos = supabase_client.storage.from_(BUCKET).list(carpeta)
    except Exception:
        return None, None
    for archivo in (archivos or []):
        if archivo["name"].startswith(f"{tipo_documento}__"):
            nombre_original = archivo["name"].split("__", 1)[1]
            try:
                datos = supabase_client.storage.from_(BUCKET).download(
                    f"{carpeta}/{archivo['name']}"
                )
            except Exception:
                return None, None
            return datos, nombre_original
    return None, None

def eliminar_archivo_original(username, tipo_documento):
    """Deletes a file of a specific type from the user's locker."""
    carpeta = _nombre_seguro(username)
    try:
        archivos = supabase_client.storage.from_(BUCKET).list(carpeta)
    except Exception:
        return
    for archivo in (archivos or []):
        if archivo["name"].startswith(f"{tipo_documento}__"):
            supabase_client.storage.from_(BUCKET).remove(
                [f"{carpeta}/{archivo['name']}"]
            )

def generar_zip_carpeta(username, tipos_documento):
    """Bundles multiple documents into a ZIP in memory."""
    buffer = io.BytesIO()
    incluidos = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for tipo_documento in tipos_documento:
            datos_bytes, nombre_original = obtener_archivo_original(username, tipo_documento)
            if datos_bytes and nombre_original:
                nombre_en_zip = f"{tipo_documento}__{nombre_original}"
                zf.writestr(nombre_en_zip, datos_bytes)
                incluidos += 1
    buffer.seek(0)
    return buffer.getvalue(), incluidos

def get_signed_url_for_pdf(username, tipo_documento):
    """
    Generates a signed URL for a PDF to allow direct iframe rendering.
    This replaces the inefficient base64 encoding.
    """
    carpeta = _nombre_seguro(username)
    try:
        archivos = supabase_client.storage.from_(BUCKET).list(carpeta)
    except Exception:
        return None

    for archivo in (archivos or []):
        if archivo["name"].startswith(f"{tipo_documento}__"):
            path = f"{carpeta}/{archivo['name']}"
            # Create a signed URL valid for 1 hour
            res = supabase_client.storage.from_(BUCKET).create_signed_url(path, expires_in=3600)
            return res if isinstance(res, str) else res.get("signedURL")
    return None
