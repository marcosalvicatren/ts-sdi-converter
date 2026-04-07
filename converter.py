#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
converter.py — Logica di conversione TS → SDI
Usato sia dall'app Streamlit che da riga di comando.

Correzioni attive:
  1. Nota di credito  → TipoDocumento = TD04 se parola chiave in <Descrizione>
  2. Fattura a zero   → DatiRiepilogo con Natura=N4 anche se importo = 0.00
  3. IVA calcolata    → Imposta = Imponibile × Aliquota / 100
  4. Fattura mista    → un blocco DatiRiepilogo per ogni coppia (AliquotaIVA, Natura)
  5. Namespace        → prefisso 'p:' e namespace originali preservati nell'output
"""

import xml.etree.ElementTree as ET
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------
KEYWORDS_NOTA_CREDITO = [
    "storno totale fattura",
    "nota di accredito",
    "storno fattura",
    "nota credito",
]

# ---------------------------------------------------------------------------
# Utility numeriche
# ---------------------------------------------------------------------------
def _d(x) -> Decimal:
    try:
        return Decimal(str(x).replace(",", ".").strip())
    except Exception:
        return Decimal("0.00")

def _fmt(x: Decimal) -> str:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP).to_eng_string()

# ---------------------------------------------------------------------------
# Utility XML
# ---------------------------------------------------------------------------
def _localname(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag

def _first(parent, name: str):
    for el in parent.iter():
        if el is parent:
            continue
        if _localname(el.tag) == name:
            return el
    return None

def _children(parent, name: str):
    return [el for el in parent if _localname(el.tag) == name]

def _text(el) -> str:
    return el.text.strip() if el is not None and el.text else ""

def _register_ns(path: str):
    """Registra i namespace originali del file in ET (preserva prefisso p:)."""
    for event, elem in ET.iterparse(path, events=["start-ns"]):
        ET.register_namespace(elem[0], elem[1])

# ---------------------------------------------------------------------------
# Rilevazione nota di credito
# ---------------------------------------------------------------------------
def _is_nota_credito(righe) -> bool:
    for r in righe:
        desc = _text(_first(r, "Descrizione")).lower()
        if any(kw in desc for kw in KEYWORDS_NOTA_CREDITO):
            return True
    return False

# ---------------------------------------------------------------------------
# Conversione singolo file (path → path)
# ---------------------------------------------------------------------------
def convert_file(input_path: str | Path, output_path: str | Path) -> dict:
    """
    Converte un singolo XML TS in XML SDI.

    Ritorna un dict con:
      - numero        : numero documento
      - data          : data documento
      - tipo_originale: TipoDocumento nel file TS
      - tipo_output   : TipoDocumento nel file SDI prodotto
      - importo       : ImportoTotaleDocumento calcolato
      - note          : lista di stringhe descrittive delle trasformazioni applicate
      - errore        : stringa di errore oppure None
    """
    result = {
        "file": Path(input_path).name,
        "numero": "",
        "data": "",
        "tipo_originale": "",
        "tipo_output": "",
        "importo": "",
        "note": [],
        "errore": None,
    }

    try:
        input_path  = str(input_path)
        output_path = str(output_path)

        _register_ns(input_path)
        tree = ET.parse(input_path)
        root = tree.getroot()

        body = _first(root, "FatturaElettronicaBody")
        if body is None:
            raise RuntimeError("Manca FatturaElettronicaBody")

        dgd_parent = _first(body, "DatiGenerali")
        dgd        = _first(dgd_parent, "DatiGeneraliDocumento") if dgd_parent else None
        if dgd is None:
            raise RuntimeError("Manca DatiGeneraliDocumento")

        dbs = _first(body, "DatiBeniServizi")
        if dbs is None:
            raise RuntimeError("Manca DatiBeniServizi")

        righe = _children(dbs, "DettaglioLinee")
        if not righe:
            raise RuntimeError("Nessuna riga DettaglioLinee")

        # Info documento per il report
        result["numero"] = _text(_first(dgd, "Numero"))
        result["data"]   = _text(_first(dgd, "Data"))
        tipo_el          = _first(dgd, "TipoDocumento")
        result["tipo_originale"] = _text(tipo_el)

        # -----------------------------------------------------------------
        # FIX 1 — Nota di credito
        # -----------------------------------------------------------------
        if tipo_el is not None and _is_nota_credito(righe):
            tipo_el.text = "TD04"
            result["note"].append("TipoDocumento → TD04 (nota di credito rilevata)")

        result["tipo_output"] = _text(tipo_el)

        # -----------------------------------------------------------------
        # Analisi righe
        # -----------------------------------------------------------------
        gruppi: dict[tuple, Decimal] = defaultdict(Decimal)
        totale_righe = Decimal("0.00")
        tutte_zero   = True

        for r in righe:
            prezzo  = _d(_text(_first(r, "PrezzoTotale")))
            aliq    = _text(_first(r, "AliquotaIVA")) or "0.00"
            natura  = _text(_first(r, "Natura"))
            if prezzo != Decimal("0.00"):
                tutte_zero = False
            gruppi[(aliq, natura)] += prezzo
            totale_righe           += prezzo

        # -----------------------------------------------------------------
        # FIX 2 — Fattura a zero: forza Natura N4 se non già presente
        # -----------------------------------------------------------------
        if tutte_zero:
            ha_natura = any(nat for (_, nat) in gruppi)
            if not ha_natura:
                gruppi = defaultdict(Decimal)
                gruppi[("0.00", "N4")] = Decimal("0.00")
                result["note"].append("Fattura a zero: Natura=N4 aggiunta automaticamente")

        # -----------------------------------------------------------------
        # Rimuovi DatiRiepilogo placeholder
        # -----------------------------------------------------------------
        for child in list(dbs):
            if _localname(child.tag) == "DatiRiepilogo":
                dbs.remove(child)

        # -----------------------------------------------------------------
        # FIX 3 + 4 — Ricostruzione DatiRiepilogo con IVA calcolata
        # -----------------------------------------------------------------
        totale_documento = Decimal("0.00")

        for (aliq, natura), imponibile in gruppi.items():
            aliq_dec = _d(aliq)
            if aliq_dec > Decimal("0.00"):
                imposta = (imponibile * aliq_dec / Decimal("100")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                result["note"].append(
                    f"IVA {aliq}% calcolata: imponibile {_fmt(imponibile)}€ → imposta {_fmt(imposta)}€"
                )
            else:
                imposta = Decimal("0.00")

            totale_documento += imponibile + imposta

            dr = ET.SubElement(dbs, "DatiRiepilogo")
            ET.SubElement(dr, "AliquotaIVA").text = _fmt(aliq_dec)
            if natura:
                ET.SubElement(dr, "Natura").text = natura
            ET.SubElement(dr, "ImponibileImporto").text = _fmt(imponibile)
            ET.SubElement(dr, "Imposta").text            = _fmt(imposta)
            if (natura or "").upper() == "N4":
                ET.SubElement(dr, "RiferimentoNormativo").text = "Art. 10 DPR 633/72"

        # -----------------------------------------------------------------
        # ImportoTotaleDocumento
        # -----------------------------------------------------------------
        itot = _first(dgd, "ImportoTotaleDocumento")
        if itot is None:
            itot = ET.SubElement(dgd, "ImportoTotaleDocumento")
        itot.text = _fmt(totale_documento)

        result["importo"] = _fmt(totale_documento)

        tree.write(output_path, encoding="utf-8", xml_declaration=True)

    except Exception as e:
        result["errore"] = str(e)

    return result


# ---------------------------------------------------------------------------
# Entry point CLI (compatibilità con vecchio uso)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print('Uso: python converter.py "input.xml" "output.xml"')
        sys.exit(1)
    r = convert_file(sys.argv[1], sys.argv[2])
    if r["errore"]:
        print("ERRORE:", r["errore"], file=sys.stderr)
        sys.exit(1)
    print("OK:", sys.argv[2])
    for nota in r["note"]:
        print(" •", nota)
