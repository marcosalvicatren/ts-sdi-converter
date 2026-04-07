# 🧾 Convertitore Fatture TS → SDI

Tool per convertire fatture XML Tessera Sanitaria (TS) in fatture XML SDI (FatturaPA) compatibili con il Sistema di Interscambio dell'Agenzia delle Entrate.

---

## ✅ Funzionalità

| Caso | Comportamento |
|------|---------------|
| **Nota di credito** | Se la `<Descrizione>` contiene "storno totale fattura", "nota di accredito", "storno fattura" o "nota credito" → `TipoDocumento` impostato a **TD04** |
| **Fattura a zero (omaggio)** | `DatiRiepilogo` compilato con `Natura=N4` e `ImponibileImporto=0.00` |
| **Fattura con IVA** | `Imposta` calcolata correttamente: `Imponibile × Aliquota / 100` |
| **Fattura mista** | Un blocco `DatiRiepilogo` per ogni coppia `(AliquotaIVA, Natura)` |
| **Namespace** | Prefisso `p:` originale preservato nell'output |

---

## 🚀 Utilizzo su Streamlit Cloud (consigliato per i collaboratori)

1. Vai all'indirizzo dell'app (fornito dall'amministratore)
2. Carica il file **ZIP** contenente le fatture XML TS
3. Attendi il completamento della conversione
4. Scarica il **ZIP** con i file SDI convertiti e il **report CSV**

---

## 🛠️ Deploy su Streamlit Cloud (una tantum, solo per l'amministratore)

### 1. Fork / push su GitHub

```bash
git clone https://github.com/TUO-USERNAME/ts-sdi-converter.git
cd ts-sdi-converter
# copia i file del progetto qui
git add .
git commit -m "Primo deploy"
git push
```

### 2. Deploy su Streamlit Cloud

1. Vai su [share.streamlit.io](https://share.streamlit.io) e accedi con GitHub
2. Clicca **"New app"**
3. Seleziona il repository e imposta:
   - **Branch:** `main`
   - **Main file path:** `app.py`
4. Clicca **"Deploy"**

L'app sarà disponibile a un link pubblico condivisibile con tutti i collaboratori.

---

## 💻 Esecuzione in locale (opzionale)

```bash
# Clona il repository
git clone https://github.com/TUO-USERNAME/ts-sdi-converter.git
cd ts-sdi-converter

# Installa le dipendenze
pip install -r requirements.txt

# Avvia l'app
streamlit run app.py
```

L'app si aprirà automaticamente nel browser su `http://localhost:8501`.

---

## 📁 Struttura del progetto

```
ts-sdi-converter/
├── app.py              # Interfaccia Streamlit
├── converter.py        # Logica di conversione XML
├── requirements.txt    # Dipendenze Python
└── README.md           # Questo file
```

---

## 📄 Output

Lo ZIP scaricabile contiene:
- Tutti i file **XML SDI** convertiti (stesso nome del file originale)
- Il file `report_conversione.csv` con per ogni fattura:
  - Nome file, Numero, Data, TipoDocumento originale e output, Importo totale, Trasformazioni applicate, Eventuali errori

---

## ⚙️ Uso da riga di comando (avanzato)

```bash
python converter.py input_TS.xml output_SDI.xml
```
