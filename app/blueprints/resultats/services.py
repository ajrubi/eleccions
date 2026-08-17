"""View-specific shaping of data already fetched from the Resultats API.

Nothing here performs I/O: resultats_client.py already did the HTTP call
and the (convocatòria, partit) aggregation. This module only reshapes that
result for the template (bar-chart widths, grouping by tipus) and builds
the on-the-fly CSV/PDF exports, generated in memory and streamed straight
back in the response — never written to disk.
"""
from __future__ import annotations

import csv
import io
import math
from typing import Any, Optional

# LOREG art. 180.1.a: en l'àmbit municipal, només entren al repartiment
# d'escons les candidatures amb, com a mínim, aquest % dels vots vàlids
# emesos al municipi.
MUNICIPAL_DHONDT_THRESHOLD_PCT = 5.0


def dhondt_regidors(
    candidatures: list[dict[str, Any]],
    total_seats: int,
    vots_valids: float,
    threshold_pct: float = MUNICIPAL_DHONDT_THRESHOLD_PCT,
) -> dict[Any, int]:
    """Reparteix `total_seats` escons entre `candidatures` per Llei D'Hondt.

    Àmbit municipal (LOREG art. 180): primer es descarten les candidatures
    que no arriben al `threshold_pct` dels vots vàlids; després, cada escó
    es dona, un per un, a qui tingui el quocient vots / (escons_ja_obtinguts
    + 1) més alt — l'algorisme clàssic de la mitjana més alta. Els empats de
    quocient es resolen a favor de qui tingui més vots (la llei preveu
    sorteig; aquí es fa determinista).
    """
    seats = {c["codi"]: 0 for c in candidatures}
    if total_seats <= 0 or vots_valids <= 0:
        return seats

    eligibles = [c for c in candidatures if (c["vots"] / vots_valids * 100) >= threshold_pct]
    if not eligibles:
        return seats

    for _ in range(total_seats):
        winner = max(eligibles, key=lambda c: (c["vots"] / (seats[c["codi"]] + 1), c["vots"]))
        seats[winner["codi"]] += 1
    return seats


def _annotate_regidors(results: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    """Afegeix `regidors` a cada candidatura quan la convocatòria ho permet.

    Només té sentit per a eleccions municipals i sobre el resultat de tot el
    municipi: els districtes/seccions/meses són subdivisions de recompte,
    no circumscripcions pròpies, així que amb un filtre de zona actiu no es
    calcula el repartiment.
    """
    candidatures = results["candidatures"]
    es_municipals = results.get("tipus") == "Municipals"
    zona_filtrada = bool(results.get("districte") or results.get("seccio") or results.get("mesa"))
    te_regidors = es_municipals and not zona_filtrada and results.get("total_regidors", 0) > 0
    if not te_regidors:
        return candidatures, False

    regidors_per_codi = dhondt_regidors(candidatures, results["total_regidors"], results["vots_valids"])
    return [{**c, "regidors": regidors_per_codi[c["codi"]]} for c in candidatures], True


# Geometria del gràfic d'arc (mig donut) de repartiment de regidors, en
# unitats del viewBox SVG. cy queda arran de la base perquè l'arc s'obre
# cap amunt, com un "hemicicle" de premsa (vegeu REGIDORES.png).
_ARC_CX = 200
_ARC_CY = 190
_ARC_OUTER_R = 180
_ARC_INNER_R = 104


def _arc_text_color(hex_color: str) -> str:
    """Blanc o gris fosc segons la lluminositat del color de fons, per llegibilitat."""
    hex_color = (hex_color or "").lstrip("#")
    if len(hex_color) != 6:
        return "#ffffff"
    try:
        r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return "#ffffff"
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#262223" if luminance > 0.6 else "#ffffff"


def build_regidors_arc(candidatures: list[dict[str, Any]], total_seats: int) -> Optional[dict[str, Any]]:
    """Dades per dibuixar el repartiment de regidors com un arc (mig donut).

    Cada candidatura amb escons ocupa una porció de l'arc proporcional al
    seu nombre de REGIDORS (no als vots), d'esquerra a dreta de més a menys
    escons — l'estil habitual d'"hemicicle" a premsa. Els partits sense
    escons no hi surten (no ocupen cap porció).
    """
    amb_escons = sorted(
        (c for c in candidatures if c.get("regidors", 0) > 0),
        key=lambda c: (-c["regidors"], -c["vots"]),
    )
    if not amb_escons or total_seats <= 0:
        return None

    def punt(theta: float, radi: float) -> tuple[float, float]:
        return (_ARC_CX + radi * math.cos(theta), _ARC_CY - radi * math.sin(theta))

    segments = []
    acumulat = 0
    for c in amb_escons:
        theta_start = math.pi - (acumulat / total_seats) * math.pi
        acumulat += c["regidors"]
        theta_end = math.pi - (acumulat / total_seats) * math.pi

        x1o, y1o = punt(theta_start, _ARC_OUTER_R)
        x2o, y2o = punt(theta_end, _ARC_OUTER_R)
        x2i, y2i = punt(theta_end, _ARC_INNER_R)
        x1i, y1i = punt(theta_start, _ARC_INNER_R)
        # Arc exterior en sentit horari (theta decreixent) i interior en
        # sentit antihorari de tornada: junts tanquen la porció de donut.
        path = (
            f"M {x1o:.2f} {y1o:.2f} "
            f"A {_ARC_OUTER_R} {_ARC_OUTER_R} 0 0 1 {x2o:.2f} {y2o:.2f} "
            f"L {x2i:.2f} {y2i:.2f} "
            f"A {_ARC_INNER_R} {_ARC_INNER_R} 0 0 0 {x1i:.2f} {y1i:.2f} Z"
        )

        label_x, label_y = punt((theta_start + theta_end) / 2, (_ARC_OUTER_R + _ARC_INNER_R) / 2)
        segments.append({
            "nom": c["nom"],
            "siglas": c["siglas"] or c["nom"],
            "color": c["color"],
            "regidors": c["regidors"],
            "path": path,
            "label_x": round(label_x, 2),
            "label_y": round(label_y, 2),
            "text_color": _arc_text_color(c["color"]),
        })

    return {
        "segments": segments,
        "total_regidors": total_seats,
        "majoria_absoluta": total_seats // 2 + 1,
        "view_box": f"0 0 {_ARC_CX * 2} {_ARC_CY + 20}",
    }


def build_view_model(results: dict[str, Any]) -> dict[str, Any]:
    candidatures, te_regidors = _annotate_regidors(results)
    max_vots = max((c["vots"] for c in candidatures), default=0)
    chart_rows = [
        {**c, "bar_pct": round((c["vots"] / max_vots) * 100, 1) if max_vots > 0 else 0}
        for c in candidatures
    ]
    regidors_arc = build_regidors_arc(candidatures, results.get("total_regidors", 0)) if te_regidors else None
    return {
        **results,
        "candidatures": candidatures,
        "chart_rows": chart_rows,
        "te_dades": bool(candidatures),
        "te_regidors": te_regidors,
        "regidors_arc": regidors_arc,
    }


def unique_tipus(convocatories: list[dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    for c in convocatories:
        if c["tipus"] not in seen:
            seen.append(c["tipus"])
    return seen


def unique_districtes(combos: list[dict[str, str]]) -> list[str]:
    seen: list[str] = []
    for c in combos:
        if c["districte"] not in seen:
            seen.append(c["districte"])
    return seen


def seccions_for_districte(combos: list[dict[str, str]], districte: str) -> list[str]:
    if not districte:
        return []
    seen: list[str] = []
    for c in combos:
        if c["districte"] == districte and c["seccio"] not in seen:
            seen.append(c["seccio"])
    return seen


def meses_for_districte_seccio(combos: list[dict[str, str]], districte: str, seccio: str) -> list[str]:
    if not districte or not seccio:
        return []
    seen: list[str] = []
    for c in combos:
        if c["districte"] == districte and c["seccio"] == seccio and c["mesa"] not in seen:
            seen.append(c["mesa"])
    return seen


def _pct_text(value):
    return f"{value}%" if value is not None else "N/D"


def _zona_text(results: dict[str, Any]) -> Optional[str]:
    if not (results.get("districte") or results.get("seccio") or results.get("mesa")):
        return None
    parts = []
    if results.get("districte"):
        parts.append(f"Districte {results['districte']}")
    if results.get("seccio"):
        parts.append(f"Secció {results['seccio']}")
    if results.get("mesa"):
        parts.append(f"Mesa {results['mesa']}")
    return " · ".join(parts)


def results_to_csv(results: dict[str, Any]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Convocatòria", results["nom"]])
    writer.writerow(["Data", results["data"]])
    zona = _zona_text(results)
    if zona:
        writer.writerow(["Zona", zona])
    writer.writerow(["Cens electoral", results["cens_total"]])
    writer.writerow(["Participació", _pct_text(results["participacio_pct"])])
    writer.writerow(["Abstenció", _pct_text(results["abstencio_pct"])])
    writer.writerow(["Vots nuls", results["vots_nuls"]])
    writer.writerow(["Vots en blanc", results["vots_blancs"]])
    writer.writerow(["Vots a candidatures", results["vots_candidatures"]])
    writer.writerow(["Vots vàlids (candidatures + blancs, base del %)", results["vots_valids"]])
    writer.writerow(["Total de vots", results["participants_total"]])
    candidatures, te_regidors = _annotate_regidors(results)
    writer.writerow([])
    header = ["Candidatura", "Sigles", "Vots", "%"]
    if te_regidors:
        header.append("Regidors")
    writer.writerow(header)
    for c in candidatures:
        row = [c["nom"], c["siglas"], c["vots"], c["pct"]]
        if te_regidors:
            row.append(c["regidors"])
        writer.writerow(row)
    if te_regidors:
        writer.writerow([])
        writer.writerow([
            f"Regidors calculats per Llei D'Hondt (LOREG art. 180): "
            f"llindar del {MUNICIPAL_DHONDT_THRESHOLD_PCT:g}% dels vots vàlids, "
            f"{results['total_regidors']} escons a repartir."
        ])
    return buffer.getvalue()


def results_to_pdf(results: dict[str, Any]) -> bytes:
    from xml.sax.saxutils import escape as xml_escape

    from reportlab.lib import colors as rl_colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    # Every table cell below is a Paragraph, never a raw string: plain
    # strings in a reportlab Table are drawn on a single line and, if
    # longer than the column, spill into the neighbouring cell instead of
    # wrapping. Paragraph cells wrap onto extra lines and grow the row
    # height instead, which is what keeps long candidatura names (this
    # dataset has names past 45 characters) from overlapping the next
    # column.
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=f"Resultats {results['nom']}",
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()

    label_style = ParagraphStyle("label", parent=styles["Normal"], fontSize=9, leading=12, textColor=rl_colors.white, fontName="Helvetica-Bold")
    value_style = ParagraphStyle("value", parent=styles["Normal"], fontSize=9, leading=12)
    header_style = ParagraphStyle("partyHeader", parent=styles["Normal"], fontSize=9, leading=11, textColor=rl_colors.white, fontName="Helvetica-Bold")
    header_style_right = ParagraphStyle("partyHeaderRight", parent=header_style, alignment=TA_RIGHT)
    party_style = ParagraphStyle("party", parent=styles["Normal"], fontSize=8, leading=10)
    num_style = ParagraphStyle("num", parent=party_style, alignment=TA_RIGHT)

    story = [
        Paragraph(xml_escape(f"Resultats oficials — {results['nom']}"), styles["Title"]),
        Paragraph("Ajuntament de Rubí — Dades Obertes", styles["Normal"]),
    ]
    zona = _zona_text(results)
    if zona:
        story.append(Paragraph(xml_escape(zona), styles["Normal"]))
    story.append(Spacer(1, 0.5 * cm))

    resum_rows = [
        ("Cens electoral", str(results["cens_total"])),
        ("Participació", _pct_text(results["participacio_pct"])),
        ("Abstenció", _pct_text(results["abstencio_pct"])),
        ("Vots nuls", str(results["vots_nuls"])),
        ("Vots en blanc", str(results["vots_blancs"])),
        ("Vots a candidatures", str(results["vots_candidatures"])),
        ("Vots vàlids (base del %)", str(results["vots_valids"])),
        ("Total de vots", str(results["participants_total"])),
    ]
    resum_data = [
        [Paragraph(label, label_style), Paragraph(value, value_style)]
        for label, value in resum_rows
    ]
    resum_table = Table(resum_data, colWidths=[6 * cm, 6 * cm])
    resum_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), rl_colors.HexColor("#901b13")),
        ("GRID", (0, 0), (-1, -1), 0.5, rl_colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(resum_table)
    story.append(Spacer(1, 0.7 * cm))

    candidatures, te_regidors = _annotate_regidors(results)
    header_row = [
        Paragraph("Candidatura", header_style),
        Paragraph("Sigles", header_style),
        Paragraph("Vots", header_style_right),
        Paragraph("%", header_style_right),
    ]
    col_widths = [8 * cm, 3 * cm, 3 * cm, 3 * cm]
    if te_regidors:
        header_row.append(Paragraph("Regidors", header_style_right))
        col_widths = [7 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm]
    partit_data = [header_row]
    for c in candidatures:
        row = [
            Paragraph(xml_escape(c["nom"]), party_style),
            Paragraph(xml_escape(c["siglas"]), party_style),
            Paragraph("{:,}".format(c["vots"]).replace(",", "."), num_style),
            Paragraph(f"{c['pct']}%", num_style),
        ]
        if te_regidors:
            row.append(Paragraph(str(c["regidors"]), num_style))
        partit_data.append(row)
    partit_table = Table(partit_data, colWidths=col_widths, repeatRows=1)
    partit_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor("#da291c")),
        ("GRID", (0, 0), (-1, -1), 0.5, rl_colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor("#fbe4e1")]),
    ]))
    story.append(partit_table)

    if te_regidors:
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph(
            xml_escape(
                f"Regidors calculats per Llei D'Hondt (LOREG art. 180): llindar del "
                f"{MUNICIPAL_DHONDT_THRESHOLD_PCT:g}% dels vots vàlids, "
                f"{results['total_regidors']} escons a repartir."
            ),
            styles["Normal"],
        ))

    doc.build(story)
    return buffer.getvalue()
