from __future__ import annotations

import csv
import statistics
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "phase5_results" / "platform_trials.csv"
OUT_PATH = ROOT / "ShadowPost_IEEE_Paper.pdf"
CHART_PATH = ROOT / "phase7_results" / "success_rate_per_platform.png"


def load_rows() -> list[dict[str, str]]:
    with CSV_PATH.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def metrics(rows: list[dict[str, str]]) -> dict[str, tuple[int, int, float]]:
    result = {}
    for platform in sorted({row["platform"] for row in rows}):
        group = [row for row in rows if row["platform"] == platform]
        successes = sum(row["success"] == "True" for row in group)
        bers = [float(row["ber"]) for row in group if row["ber"]]
        result[platform] = (len(group), successes, statistics.mean(bers) if bers else 0.0)
    return result


def page_number(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(letter[0] / 2, 0.35 * inch, str(doc.page))
    canvas.restoreState()


def build_styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("PaperTitle", parent=base["Title"], fontName="Helvetica-Bold", fontSize=16, leading=19, alignment=TA_CENTER, spaceAfter=5),
        "authors": ParagraphStyle("Authors", parent=base["Normal"], fontSize=8.5, leading=10, alignment=TA_CENTER, spaceAfter=8),
        "abstract": ParagraphStyle("Abstract", parent=base["Normal"], fontSize=8.2, leading=9.7, alignment=TA_JUSTIFY, spaceAfter=4),
        "heading": ParagraphStyle("Heading", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=9.4, leading=11, spaceBefore=5, spaceAfter=2),
        "subheading": ParagraphStyle("Subheading", parent=base["Heading3"], fontName="Helvetica-BoldOblique", fontSize=8.5, leading=10, spaceBefore=3, spaceAfter=1),
        "body": ParagraphStyle("Body", parent=base["BodyText"], fontName="Helvetica", fontSize=8.2, leading=9.7, alignment=TA_JUSTIFY, spaceAfter=3),
        "small": ParagraphStyle("Small", parent=base["BodyText"], fontSize=7.1, leading=8.2, alignment=TA_JUSTIFY, spaceAfter=2),
        "reference": ParagraphStyle("Reference", parent=base["BodyText"], fontSize=7.1, leading=8.3, leftIndent=8, firstLineIndent=-8, spaceAfter=2),
        "caption": ParagraphStyle("Caption", parent=base["Normal"], fontSize=7.2, leading=8.5, alignment=TA_CENTER, spaceBefore=2, spaceAfter=4),
    }


def P(text: str, style):
    return Paragraph(text, style)


def make_pdf() -> None:
    rows = load_rows()
    stats = metrics(rows)
    total = len(rows)
    successes = sum(row["success"] == "True" for row in rows)
    recorded_bers = [float(row["ber"]) for row in rows if row["ber"]]
    mean_all = statistics.mean(recorded_bers)
    styles = build_styles()

    margin = 0.58 * inch
    gutter = 0.22 * inch
    top = 0.55 * inch
    bottom = 0.52 * inch
    column_width = (letter[0] - 2 * margin - gutter) / 2
    column_height = letter[1] - top - bottom
    left = Frame(margin, bottom, column_width, column_height, id="left", leftPadding=0, rightPadding=5, topPadding=0, bottomPadding=0)
    right = Frame(margin + column_width + gutter, bottom, column_width, column_height, id="right", leftPadding=5, rightPadding=0, topPadding=0, bottomPadding=0)

    doc = BaseDocTemplate(str(OUT_PATH), pagesize=letter, leftMargin=margin, rightMargin=margin, topMargin=top, bottomMargin=bottom)
    doc.addPageTemplates([PageTemplate(id="TwoColumn", frames=[left, right], onPage=page_number)])

    story = [
        P("ShadowPost: Measuring Native-JPEG DCT Steganography Survival Across Messaging and Social Platforms", styles["title"]),
        P("ShadowPost Research Team<br/>Priyadarshini College of Engineering, Nagpur, India", styles["authors"]),
        P("<b>Abstract</b> - Platform image processing can invalidate a steganographic payload even when the embedding algorithm is correct. This paper presents ShadowPost, a native-JPEG DCT system that encrypts a message with AES-256-GCM, protects it with RS(48,32) error correction, and encodes bits through relative ordering of mid-frequency luminance coefficient pairs. The evaluation contains 270 delivery trials across Discord, Telegram, WhatsApp document and image modes, Twitter/X, and Instagram. The structured cohort uses 15 covers and three payload classes for three delivery modes; the feed/media cohort uses 45 fixed 100-byte trials for each of three additional modes. Exact recovery was 100% for Discord and WhatsApp documents, 80% for Telegram, and 0% for Twitter/X, Instagram, and standard WhatsApp images. The results show that file-preserving channels can retain native-DCT payloads, while feed-oriented recompression and spatial scaling destroy the original block-grid relationship.", styles["abstract"]),
        P("<b>Index Terms</b> - image steganography, JPEG DCT, Reed-Solomon, AES-GCM, platform recompression, survivability benchmark", styles["abstract"]),
        P("I. INTRODUCTION", styles["heading"]),
        P("A JPEG stego image is not delivered unchanged by many modern services. Upload pipelines may decode pixels, resize the image, quantize frequency coefficients, and encode a new JPEG. These operations are particularly damaging to methods that assume a stable 8 by 8 block grid. A useful system therefore needs both a robust embedding representation and measurements taken after real delivery.", styles["body"]),
        P("ShadowPost addresses this problem as an end-to-end pipeline. The message is authenticated and encrypted before embedding; an error-correcting code provides bounded correction; and the hidden bits are represented by ordering pairs of native JPEG DCT coefficients. This study focuses on the delivery layer: how much of the encoded message remains recoverable after transmission through six practical channels.", styles["body"]),
        P("II. SYSTEM DESIGN", styles["heading"]),
        P("<b>A. Security and framing.</b> A plaintext message is encrypted with AES-256-GCM using a scrypt-derived key. The resulting container includes a two-byte length, a 12-byte nonce, ciphertext, and a 16-byte authentication tag. The framed bytes are split into 32-byte data blocks and encoded with RS(48,32), adding 16 parity bytes per codeword.", styles["body"]),
        P("<b>B. Native-DCT embedding.</b> ShadowPost reads and writes JPEG coefficient arrays directly. In the luminance channel, each bit is represented by the relative magnitude ordering of two coefficient pairs: positions (1,3) versus (2,2), and (1,4) versus (4,1). Extraction uses a deterministic tie rule, |A| >= |B|, so the decoder remains reproducible at zero or equal coefficients.", styles["body"]),
        P("<b>C. Decode pipeline.</b> The receiver extracts the coefficient-order bits, groups them into RS codewords, corrects errors when possible, reconstructs the encrypted container, and authenticates it with AES-GCM. A message is counted as recovered only when the complete plaintext matches exactly.", styles["body"]),
        P("III. EVALUATION METHOD", styles["heading"]),
        P("<b>A. Trial cohorts.</b> The canonical CSV contains 270 rows. Telegram, Discord, and WhatsApp Document use the structured 15-cover matrix with 10-byte, 100-byte, and image-specific near-capacity payloads. Twitter/X, Instagram, and WhatsApp Image each contain 45 fixed 100-byte trials. This distinction is retained because the source datasets do not have identical payload distributions.", styles["body"]),
        P("<b>B. Metrics.</b> We report exact recovery rate and bit error rate (BER). BER is computed from rows with a recorded bit comparison; trials rejected before delivery have no BER and are excluded from the corresponding mean. Delivery behavior is interpreted from the returned JPEG dimensions, extraction outcome, and failure reason stored in the platform CSVs.", styles["body"]),
        P("IV. RESULTS", styles["heading"]),
    ]

    table_data = [[P("Mode", styles["small"]), P("N", styles["small"]), P("Exact", styles["small"]), P("Rate", styles["small"]), P("BER", styles["small"])]]
    order = ["discord", "whatsapp_document", "telegram", "twitter", "instagram", "whatsapp_image"]
    labels = {"discord": "Discord", "whatsapp_document": "WA doc", "telegram": "Telegram", "twitter": "X", "instagram": "Instagram", "whatsapp_image": "WA image"}
    for platform in order:
        n, ok, ber = stats[platform]
        table_data.append([P(labels[platform], styles["small"]), str(n), str(ok), f"{100 * ok / n:.1f}%", f"{ber:.4f}"])
    table_data.append([P("Overall", styles["small"]), str(total), str(successes), f"{100 * successes / total:.1f}%", f"{mean_all:.4f}"])
    result_table = Table(table_data, colWidths=[0.92 * inch, 0.28 * inch, 0.42 * inch, 0.48 * inch, 0.48 * inch], repeatRows=1)
    result_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf3")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story += [result_table, P("TABLE I. EXACT RECOVERY RESULTS FROM THE CANONICAL DATASET", styles["caption"])]
    if CHART_PATH.exists():
        story += [Image(str(CHART_PATH), width=3.25 * inch, height=2.15 * inch), P("Fig. 1. Exact recovery rate by delivery mode.", styles["caption"])]
    story += [
        P("Discord and WhatsApp Document achieved 45/45 exact recoveries with zero recorded BER, consistent with byte-preserving file transfer. Telegram recovered 36/45 messages. Its failures are concentrated in cases where platform resizing changes the DCT block registration or where the requested near-capacity payload exceeds the delivered image capacity. Twitter/X, Instagram, and WhatsApp Image recorded 0/45 exact recoveries each and BER 1.0 for every recorded row.", styles["body"]),
        P("V. DISCUSSION", styles["heading"]),
        P("The results separate two properties that are often conflated: payload robustness and channel preservation. RS parity can correct bounded coefficient errors, but it cannot reconstruct a payload when the receiver loses block-grid alignment or when the platform has replaced the JPEG with a substantially different spatial representation. The 100% document results therefore reflect preservation of the original file structure, whereas the 0% feed results show that the current native-grid decoder is not invariant to arbitrary rescaling.", styles["body"]),
        P("Telegram occupies an intermediate regime. Some images remain decodable, while high-resolution or rescaled images fail structurally. A deployment policy should therefore inspect delivered dimensions and reserve capacity below the smallest expected grid, rather than treating all JPEG upload paths as equivalent.", styles["body"]),
        P("VI. LIMITATIONS", styles["heading"]),
        P("The benchmark is a platform snapshot rather than a universal guarantee. Platform encoders, account settings, client versions, and image policies can change. The three feed/media datasets use fixed 100-byte payloads and are not directly equivalent to the structured three-payload cohort. The study also measures exact recovery, not visual quality, detectability, or resistance to an active steganalyst. These dimensions are appropriate follow-up evaluations.", styles["body"]),
        P("VII. CONCLUSION", styles["heading"]),
        P("ShadowPost combines native-JPEG DCT embedding, authenticated encryption, and Reed-Solomon coding in a measurable delivery pipeline. Across 270 recorded trials, exact recovery was 46.7% overall, with complete recovery on byte-preserving Discord and WhatsApp document channels, partial recovery on Telegram, and no recovery on the tested Twitter/X, Instagram, or standard WhatsApp image paths. The central engineering conclusion is direct: error correction helps only while the platform preserves enough of the original DCT coordinate system for extraction to remain meaningful.", styles["body"]),
        P("REFERENCES", styles["heading"]),
        P("[1] W. Bender, D. Gruhl, N. Morimoto, and A. Lu, \"Techniques for data hiding,\" IBM Systems Journal, vol. 35, no. 3-4, pp. 313-336, 1996.", styles["reference"]),
        P("[2] J. Fridrich, Steganography in Digital Media: Principles, Algorithms, and Applications. Cambridge, U.K.: Cambridge University Press, 2009.", styles["reference"]),
        P("[3] National Institute of Standards and Technology, Advanced Encryption Standard (AES), FIPS PUB 197, 2001.", styles["reference"]),
        P("[4] International Telecommunication Union, Information Technology - Digital Compression and Coding of Continuous-Tone Still Images - Requirements and Guidelines, Recommendation T.81, 1992.", styles["reference"]),
        P("[5] I. S. Reed and G. Solomon, \"Polynomial codes over certain finite fields,\" Journal of the Society for Industrial and Applied Mathematics, vol. 8, no. 2, pp. 300-304, 1960.", styles["reference"]),
        P("[6] ShadowPost Research Team, \"ShadowPost platform trial datasets,\" project artifact, 2026.", styles["reference"]),
    ]
    doc.build(story)
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    make_pdf()
