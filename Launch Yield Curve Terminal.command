#!/bin/bash
# ============================================================
# Yield Curve Terminal — launcher a doppio click (macOS)
# Fai doppio click su questo file nel Finder per avviare l'app.
# Si apre da solo nel browser.
# Per FERMARE l'app: chiudi questa finestra del Terminale.
# ============================================================

# Vai nella cartella di questo script (funziona da qualsiasi posizione)
cd "$(dirname "$0")" || exit 1

# Trova streamlit: prima nel PATH, poi nelle posizioni comuni di Anaconda
if command -v streamlit >/dev/null 2>&1; then
  STREAMLIT="streamlit"
elif [ -x "/opt/anaconda3/bin/streamlit" ]; then
  STREAMLIT="/opt/anaconda3/bin/streamlit"
elif [ -x "$HOME/anaconda3/bin/streamlit" ]; then
  STREAMLIT="$HOME/anaconda3/bin/streamlit"
else
  echo "❌ Streamlit non trovato."
  echo "   Installalo con:  pip install streamlit"
  echo ""
  read -n 1 -s -r -p "Premi un tasto per chiudere..."
  exit 1
fi

# Salta la richiesta email di Streamlit al primo avvio (crea il file se manca)
if [ ! -f "$HOME/.streamlit/credentials.toml" ]; then
  mkdir -p "$HOME/.streamlit"
  printf '[general]\nemail = ""\n' > "$HOME/.streamlit/credentials.toml"
fi

# Ferma un'eventuale istanza precedente di questa app (così la porta è libera)
pkill -f "streamlit run app.py --server.port 8544" 2>/dev/null
sleep 1

echo "▶  Avvio Yield Curve Terminal..."
echo "   Si aprirà nel browser tra pochi secondi."
echo "   Il primo caricamento scarica i dati da FRED/BCE (qualche secondo)."
echo "   Per fermare l'app: chiudi questa finestra del Terminale."
echo ""

# Avvia il server (apre il browser da solo, non-headless)
exec "$STREAMLIT" run app.py --server.port 8544
