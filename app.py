#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py — Interfaccia Streamlit per la conversione TS → SDI
Carica uno ZIP con XML TS, converte, scarica ZIP SDI + report CSV.
"""

import csv
import io
import zipfile
from pathlib import Path

import streamlit as st

from converter import convert_file

# ---------------------------------------------------------------------------
# Configurazione pagina
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Conversione TS → SDI",
    page_icon="🧾",
    layout="centered",
)

# ---------------------------------------------------------------------------
# CSS minimale per rendere l'app più gradevole
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .success-box  { background:#d4edda; border-left:4px solid #28a745;
                    padding:10px 14px; border-radius:4px; margin-bottom:8px; }
    .warning-box  { background:#fff3cd; border-left:4px solid #ffc107;
                    padding:10px 14px; border-radius:4px; margin-bottom:8px; }
    .error-box    { background:#f8d7da; border-left:4px solid #dc3545;
                    padding:10px 14px; border-radius:4px; margin-bottom:8px; }
    .info-box     { background:#d1ecf1; border-left:4px solid #17a2b8;
                    padding:10px 14px; border-radius:4px; margin-bottom:8px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Titolo
# ---------------------------------------------------------------------------
st.title("🧾 Conversione fatture TS → SDI")
st.caption(
    "Carica il file ZIP contenente le fatture XML Tessera Sanitaria. "
    "Lo strumento le converte in formato XML SDI (FatturaPA) e produce "
    "un archivio ZIP scaricabile con il report CSV."
)

st.divider()

# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------
uploaded = st.file_uploader(
    "📂 Carica il file ZIP con le fatture TS",
    type=["zip"],
    help="Il file ZIP deve contenere file XML nel formato FatturaPA Tessera Sanitaria.",
)

if uploaded is None:
    st.info("Carica un file ZIP per iniziare.")
    st.stop()

# ---------------------------------------------------------------------------
# Avvio conversione
# ---------------------------------------------------------------------------
st.divider()
st.subheader("⚙️ Conversione in corso…")

results    = []   # lista dict per il report
xml_output = {}   # nome_file → bytes XML convertito

zip_bytes = uploaded.read()

with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zin:
    xml_names = [n for n in zin.namelist() if n.lower().endswith(".xml")]

if not xml_names:
    st.error("Il file ZIP non contiene alcun file XML.")
    st.stop()

progress_bar = st.progress(0, text="Inizio conversione…")
log_area     = st.empty()
log_lines    = []

with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zin:
    total = len(xml_names)

    for i, name in enumerate(sorted(xml_names), start=1):
        # Aggiorna progress
        pct  = int(i * 100 / total)
        fname = Path(name).name
        progress_bar.progress(pct, text=f"Conversione {i}/{total}: {fname}")

        # Scrivi input su buffer in memoria (via BytesIO + file temporaneo virtuale)
        raw_in = zin.read(name)

        # Usiamo file temporanei reali (in /tmp) per compatibilità con ET.parse
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp_in:
            tmp_in.write(raw_in)
            tmp_in_path = tmp_in.name

        tmp_out_path = tmp_in_path.replace(".xml", "_out.xml")

        result = convert_file(tmp_in_path, tmp_out_path)
        result["file"] = fname  # usa nome originale

        # Leggi output
        if result["errore"] is None and Path(tmp_out_path).exists():
            xml_output[fname] = Path(tmp_out_path).read_bytes()
        
        # Pulizia file temporanei
        try:
            os.unlink(tmp_in_path)
            if Path(tmp_out_path).exists():
                os.unlink(tmp_out_path)
        except Exception:
            pass

        results.append(result)

        # Log inline
        if result["errore"]:
            log_lines.append(f"❌ {fname} — ERRORE: {result['errore']}")
        else:
            note_str = " | ".join(result["note"]) if result["note"] else "nessuna trasformazione speciale"
            log_lines.append(f"✅ {fname} — {note_str}")

        log_area.text("\n".join(log_lines))

progress_bar.progress(100, text="Conversione completata.")

# ---------------------------------------------------------------------------
# Riepilogo
# ---------------------------------------------------------------------------
st.divider()
st.subheader("📊 Riepilogo")

n_ok  = sum(1 for r in results if r["errore"] is None)
n_err = sum(1 for r in results if r["errore"] is not None)

col1, col2, col3 = st.columns(3)
col1.metric("File elaborati", len(results))
col2.metric("✅ Convertiti",  n_ok)
col3.metric("❌ Errori",      n_err)

if n_err > 0:
    st.warning(
        f"{n_err} file non convertiti. Controlla il log e il report CSV per i dettagli."
    )

# ---------------------------------------------------------------------------
# Tabella risultati
# ---------------------------------------------------------------------------
with st.expander("📋 Dettaglio conversioni", expanded=True):
    for r in results:
        if r["errore"]:
            st.markdown(
                f'<div class="error-box">❌ <b>{r["file"]}</b> — {r["errore"]}</div>',
                unsafe_allow_html=True,
            )
        else:
            trasf = ", ".join(r["note"]) if r["note"] else "—"
            tipo_badge = "🔵 TD04" if r["tipo_output"] == "TD04" else "🟢 TD01"
            st.markdown(
                f'<div class="success-box">'
                f'✅ <b>{r["file"]}</b> &nbsp;|&nbsp; '
                f'N. {r["numero"]} &nbsp;|&nbsp; '
                f'{r["data"]} &nbsp;|&nbsp; '
                f'{tipo_badge} &nbsp;|&nbsp; '
                f'Totale: <b>{r["importo"]} €</b><br>'
                f'<small>Trasformazioni: {trasf}</small>'
                f'</div>',
                unsafe_allow_html=True,
            )

# ---------------------------------------------------------------------------
# Costruzione ZIP output + CSV report
# ---------------------------------------------------------------------------
st.divider()
st.subheader("⬇️ Download")

# -- CSV report --
csv_buffer = io.StringIO()
writer = csv.DictWriter(
    csv_buffer,
    fieldnames=["file", "numero", "data", "tipo_originale", "tipo_output", "importo", "note", "errore"],
    extrasaction="ignore",
)
writer.writeheader()
for r in results:
    r_csv = dict(r)
    r_csv["note"] = " | ".join(r["note"])
    writer.writerow(r_csv)

csv_bytes = csv_buffer.getvalue().encode("utf-8-sig")  # utf-8-sig = compatibile Excel

# -- ZIP output --
zip_out_buffer = io.BytesIO()
with zipfile.ZipFile(zip_out_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zout:
    for fname, content in xml_output.items():
        zout.writestr(fname, content)
    zout.writestr("report_conversione.csv", csv_bytes)

zip_out_bytes = zip_out_buffer.getvalue()

col_zip, col_csv = st.columns(2)

with col_zip:
    st.download_button(
        label="📦 Scarica ZIP (XML SDI + CSV)",
        data=zip_out_bytes,
        file_name="fatture_SDI_convertite.zip",
        mime="application/zip",
        use_container_width=True,
    )

with col_csv:
    st.download_button(
        label="📄 Scarica solo il report CSV",
        data=csv_bytes,
        file_name="report_conversione.csv",
        mime="text/csv",
        use_container_width=True,
    )

st.caption(
    "Lo ZIP contiene tutti i file XML SDI convertiti correttamente "
    "e il file `report_conversione.csv` con il dettaglio di ogni conversione."
)
