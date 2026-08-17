"""View-specific shaping for "Resultats per mesa electoral".

Nothing here performs I/O: app.services.api_clients.mesa_client already
fetched and cleaned every mesa row. This module only builds the tipus/
convocatòria/districte/secció/mesa filter options (same pattern as
resultats/services.py) and applies the extra oberta/comunicada filters and
the summary cards, none of which the client should know about.

"% escrutini" oficial: el Ministeri de l'Interior i la Junta Electoral
Central el calculen com a mesas comunicades sobre el total, sense que hi
intervinguin els vots (vegeu el docstring de mesa_client.py).
build_summary() calcula exactament això.
"""
from __future__ import annotations

import csv
import io
from typing import Any


def unique_tipus(convocatories: list[dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    for c in convocatories:
        if c["tipus"] not in seen:
            seen.append(c["tipus"])
    return seen


def unique_districtes(rows: list[dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    for r in rows:
        if r["districte"] not in seen:
            seen.append(r["districte"])
    return seen


def seccions_for_districte(rows: list[dict[str, Any]], districte: str) -> list[str]:
    if not districte:
        return []
    seen: list[str] = []
    for r in rows:
        if r["districte"] == districte and r["seccio"] not in seen:
            seen.append(r["seccio"])
    return seen


def meses_for_districte_seccio(rows: list[dict[str, Any]], districte: str, seccio: str) -> list[str]:
    if not districte or not seccio:
        return []
    seen: list[str] = []
    for r in rows:
        if r["districte"] == districte and r["seccio"] == seccio and r["mesa"] not in seen:
            seen.append(r["mesa"])
    return seen


def filter_by_zona(rows: list[dict[str, Any]], districte: str = "", seccio: str = "", mesa: str = "") -> list[dict[str, Any]]:
    result = rows
    if districte:
        result = [r for r in result if r["districte"] == districte]
    if seccio:
        result = [r for r in result if r["seccio"] == seccio]
    if mesa:
        result = [r for r in result if r["mesa"] == mesa]
    return result


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Resum de tota la convocatòria (abans de cap filtre de la taula).

    "Comunicada" és el camp que marca una mesa com a escrutinada; la resta
    queda pendent, tant si està oberta com si encara no s'ha obert. El %
    de meses escrutades es calcula directament com comunicades/total (no
    com una mitjana del % de vots escrutats de cada mesa, que és una
    magnitud diferent): així, quan pendents arriba a 0, comunicades==total
    i el % surt exactament 100, mai una xifra arrodonida per sota.
    """
    total = len(rows)
    comunicades = sum(1 for r in rows if r["comunicada"])
    obertes = sum(1 for r in rows if r["oberta"])
    pendents = total - comunicades
    pct_escrutades = round((comunicades / total) * 100, 2) if total > 0 else None
    pct_pendents = round((pendents / total) * 100, 2) if total > 0 else None
    return {
        "total": total,
        "obertes": obertes,
        "comunicades": comunicades,
        "pendents": pendents,
        "pct_escrutades": pct_escrutades,
        "pct_pendents": pct_pendents,
    }


def filter_meses(
    rows: list[dict[str, Any]],
    oberta: str = "",
    comunicada: str = "",
) -> list[dict[str, Any]]:
    result = rows
    if oberta == "SI":
        result = [r for r in result if r["oberta"]]
    elif oberta == "NO":
        result = [r for r in result if not r["oberta"]]
    if comunicada == "SI":
        result = [r for r in result if r["comunicada"]]
    elif comunicada == "NO":
        result = [r for r in result if not r["comunicada"]]
    return result


def build_export_meta(convocatories: list[dict[str, Any]], codi: str, args: Any) -> dict[str, Any]:
    """Capçalera (nom/data/zona) pels exports CSV/PDF, a partir dels mateixos
    paràmetres de zona que ja viatgen a la query string de la vista."""
    conv = next((c for c in convocatories if c["codi"] == codi), None)
    parts = []
    districte = args.get("districte") or ""
    seccio = args.get("seccio") or ""
    mesa = args.get("mesa") or ""
    if districte:
        parts.append(f"Districte {districte}")
    if seccio:
        parts.append(f"Secció {seccio}")
    if mesa:
        parts.append(f"Mesa {mesa}")
    return {
        "nom": conv["nom"] if conv else codi,
        "data": conv["data"] if conv else "",
        "zona": " · ".join(parts) or None,
    }


def rows_to_csv(rows: list[dict[str, Any]], meta: dict[str, Any]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Convocatòria", meta.get("nom", "")])
    writer.writerow(["Data", meta.get("data", "")])
    if meta.get("zona"):
        writer.writerow(["Zona", meta["zona"]])
    writer.writerow([])
    writer.writerow([
        "Districte", "Secció", "Mesa", "Cens", "Oberta", "Comunicada", "Hora comunicada",
        "Avanç 1", "Avanç 2", "Avanç 3", "Vots a partits", "Nuls", "Blancs", "Total vots",
    ])
    for r in rows:
        writer.writerow([
            r["districte"], r["seccio"], r["mesa"], r["cens_mesa"],
            "Sí" if r["oberta"] else "No", "Sí" if r["comunicada"] else "No",
            r["hora_comunicada"] or "",
            r["avan1_mesa"], r["avan2_mesa"], r["avan3_mesa"],
            r["vots_partits_mesa"], r["nuls_mesa"], r["blancs_mesa"], r["totals_vots_mesa"],
        ])
    return buffer.getvalue()


def rows_to_pdf(rows: list[dict[str, Any]], meta: dict[str, Any]) -> bytes:
    from xml.sax.saxutils import escape as xml_escape

    from reportlab.lib import colors as rl_colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    # Landscape, no vertical (com resultats/services.py::results_to_pdf):
    # aquesta taula té 14 columnes i no hi cap en orientació vertical sense
    # que el text es comprimeixi il·legible.
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        title=f"Resultats per mesa — {meta.get('nom', '')}",
        leftMargin=1.2 * cm, rightMargin=1.2 * cm, topMargin=1.2 * cm, bottomMargin=1.2 * cm,
    )
    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        "mesaHeader", parent=styles["Normal"], fontSize=8, leading=10,
        textColor=rl_colors.white, fontName="Helvetica-Bold", alignment=TA_CENTER,
    )
    cell_style = ParagraphStyle("mesaCell", parent=styles["Normal"], fontSize=7.5, leading=9, alignment=TA_CENTER)

    story = [
        Paragraph(xml_escape(f"Resultats per mesa electoral — {meta.get('nom', '')}"), styles["Title"]),
        Paragraph("Ajuntament de Rubí — Dades Obertes", styles["Normal"]),
    ]
    if meta.get("zona"):
        story.append(Paragraph(xml_escape(meta["zona"]), styles["Normal"]))
    story.append(Spacer(1, 0.4 * cm))

    headers = ["Districte", "Secció", "Mesa", "Cens", "Oberta", "Comunicada", "Hora", "Av.1", "Av.2", "Av.3", "Partits", "Nuls", "Blancs", "Total"]
    data = [[Paragraph(h, header_style) for h in headers]]
    for r in rows:
        data.append([
            Paragraph(str(r["districte"]), cell_style),
            Paragraph(str(r["seccio"]), cell_style),
            Paragraph(str(r["mesa"]), cell_style),
            Paragraph("{:,}".format(r["cens_mesa"]).replace(",", "."), cell_style),
            Paragraph("Sí" if r["oberta"] else "No", cell_style),
            Paragraph("Sí" if r["comunicada"] else "No", cell_style),
            Paragraph(r["hora_comunicada"] or "—", cell_style),
            Paragraph("{:,}".format(r["avan1_mesa"]).replace(",", "."), cell_style),
            Paragraph("{:,}".format(r["avan2_mesa"]).replace(",", "."), cell_style),
            Paragraph("{:,}".format(r["avan3_mesa"]).replace(",", "."), cell_style),
            Paragraph("{:,}".format(r["vots_partits_mesa"]).replace(",", "."), cell_style),
            Paragraph("{:,}".format(r["nuls_mesa"]).replace(",", "."), cell_style),
            Paragraph("{:,}".format(r["blancs_mesa"]).replace(",", "."), cell_style),
            Paragraph("{:,}".format(r["totals_vots_mesa"]).replace(",", "."), cell_style),
        ])

    col_widths = [
        1.8 * cm, 1.8 * cm, 1.5 * cm, 2.1 * cm, 1.8 * cm, 2.2 * cm, 1.8 * cm,
        1.6 * cm, 1.6 * cm, 1.6 * cm, 2.2 * cm, 1.7 * cm, 1.7 * cm, 2.1 * cm,
    ]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor("#da291c")),
        ("GRID", (0, 0), (-1, -1), 0.4, rl_colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor("#fbe4e1")]),
    ]))
    story.append(table)

    doc.build(story)
    return buffer.getvalue()
