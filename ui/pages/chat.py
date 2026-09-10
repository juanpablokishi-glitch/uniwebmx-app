import streamlit as st
from services.ai_hugo import get_hugo_response_stream, construir_contexto_universidades, detectar_necesidad_busqueda_tiempo_real, buscar_info_actualizada_universidad
from core.database import guardar_datos_usuario, cargar_datos_usuario, guardar_conversacion_entrenamiento
from core.config import MAX_HISTORIAL_GEMINI

def render_chat():
    username = st.session_state.user
    st.markdown(f'<div class="hero-section-locker"> <h1 style="color:white; font-size:3rem;">Chat con Hugo</h1> <p style="color:rgba(255,255,255,0.9); font-size:1.2rem;">Tu asesor de admisiones con IA</p> </div>', unsafe_allow_html=True)

    # Setup chat history
    if "historial_chat" not in st.session_state:
        st.session_state.historial_chat = [{"role": "assistant", "content": "¡Hola! Soy Hugo, tu consultor de admisión. ¿En qué puedo ayudarte hoy?"}]

    # Render chat container
    st.markdown('<div class="gemini-chat-container">', unsafe_allow_html=True)
    for msg in st.session_state.historial_chat:
        role_class = "gemini-row-user" if msg["role"] == "user" else "gemini-row-hugo"
        label = "Tú" if msg["role"] == "user" else "Hugo"
        bubble_class = "gemini-bubble-user" if msg["role"] == "user" else "gemini-bubble-hugo"

        st.markdown(f"""
        <div class="gemini-row {role_class}">
            <div class="gemini-bubble">
                <div class="{'gemini-user-label' if msg['role'] == 'user' else 'gemini-hugo-label'}">{label}</div>
                <div class="gemini-text">{msg['content']}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Chat input
    if prompt := st.chat_input("Pregunta a Hugo..."):
        # Add user message to history
        st.session_state.historial_chat.append({"role": "user", "content": prompt})

        # logic for real-time grounding
        unis_interes = st.session_state.get("perfil_universidades_interes", [])
        uni_to_search = detectar_necesidad_busqueda_tiempo_real(prompt, unis_interes)

        context_extra = ""
        if uni_to_search:
            with st.spinner(f"Hugo está buscando info actualizada de {uni_to_search}..."):
                info = buscar_info_actualizada_universidad(uni_to_search, prompt)
                if info:
                    context_extra = f"\n\nINFORMACIÓN ACTUALIZADA DE {uni_to_search}:\n{info}"

        # Build full prompt
        full_prompt = prompt
        if context_extra:
            full_prompt = f"{prompt}\n\n{context_extra}"

        # System instruction including university knowledge base
        system_instr = (
            "Eres Hugo, un asesor experto en admisiones universitarias en México. "
            "Tu objetivo es ayudar al alumno a organizar su perfil y maximizar sus posibilidades. "
            "Sé profesional, empático y preciso.\n\n"
            f"BASE DE CONOCIMIENTO VERIFICADA:\n{construir_contexto_universidades(unis_interes)}"
        )

        # AI Streaming Response
        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_response = ""
            # We use the streaming helper from ai_hugo.py
            for chunk in get_hugo_response_stream(full_prompt, st.session_state.historial_chat, system_instruction=system_instr):
                full_response += chunk
                placeholder.markdown(f"""
                <div class="gemini-row gemini-row-hugo">
                    <div class="gemini-bubble">
                        <div class="gemini-hugo-label">Hugo</div>
                        <div class="gemini-text">{full_response}▌</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            placeholder.markdown(f"""
                <div class="gemini-row gemini-row-hugo">
                    <div class="gemini-bubble">
                        <div class="gemini-hugo-label">Hugo</div>
                        <div class="gemini-text">{full_response}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # Save to history and DB
        st.session_state.historial_chat.append({"role": "assistant", "content": full_response})

        # Persist to Supabase
        guardar_datos_usuario(username, st.session_state.__dict__) # simplified for now

        # Training consent check
        if st.session_state.get("consentimiento_hugo_actual"):
            guardar_conversacion_entrenamiento(username, prompt, full_response)

        st.rerun()
