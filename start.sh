#!/usr/bin/env bash
set -e

# Este script traduce las variables de entorno que configures en el
# dashboard de Render a un archivo .streamlit/secrets.toml, que es el
# formato que espera st.secrets dentro de app.py. Así no hay que tocar
# nada del código de la app.

mkdir -p .streamlit

cat > .streamlit/secrets.toml <<EOF
GEMINI_API_KEY = "${GEMINI_API_KEY}"
SUPABASE_URL = "${SUPABASE_URL}"
SUPABASE_KEY = "${SUPABASE_KEY}"
RESEND_API_KEY = "${RESEND_API_KEY}"
ADMIN_EMAIL = "${ADMIN_EMAIL}"
BASE_URL = "${BASE_URL}"
EOF

streamlit run app.py \
  --server.port="${PORT}" \
  --server.address=0.0.0.0 \
  --server.headless=true \
  --browser.gatherUsageStats=false
