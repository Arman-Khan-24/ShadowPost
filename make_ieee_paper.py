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
    PageBreak,
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
        "title": ParagraphStyle("PaperTitle", parent=base["Title"], fontName="Times-Bold", fontSize=18, leading=21, alignment=TA_CENTER, spaceAfter=6),
        "authors": ParagraphStyle("Authors", parent=base["Normal"], fontName="Times-Roman", fontSize=9.5, leading=11, alignment=TA_CENTER, spaceAfter=9),
        "abstract": ParagraphStyle("Abstract", parent=base["Normal"], fontName="Times-Roman", fontSize=9.2, leading=10.8, alignment=TA_JUSTIFY, spaceAfter=5),
        "heading": ParagraphStyle("Heading", parent=base["Heading2"], fontName="Times-Bold", fontSize=10.2, leading=12, spaceBefore=7, spaceAfter=3),
        "subheading": ParagraphStyle("Subheading", parent=base["Heading3"], fontName="Times-BoldItalic", fontSize=9.5, leading=11, spaceBefore=4, spaceAfter=2),
        "body": ParagraphStyle("Body", parent=base["BodyText"], fontName="Times-Roman", fontSize=9.5, leading=11.3, alignment=TA_JUSTIFY, spaceAfter=5),
        "small": ParagraphStyle("Small", parent=base["BodyText"], fontName="Times-Roman", fontSize=8.2, leading=9.4, alignment=TA_JUSTIFY, spaceAfter=3),
        "reference": ParagraphStyle("Reference", parent=base["BodyText"], fontName="Times-Roman", fontSize=8.3, leading=9.6, leftIndent=9, firstLineIndent=-9, spaceAfter=3),
        "caption": ParagraphStyle("Caption", parent=base["Normal"], fontName="Times-Roman", fontSize=8.2, leading=9.5, alignment=TA_CENTER, spaceBefore=3, spaceAfter=5),
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

    margin = 0.68 * inch
    gutter = 0.25 * inch
    top = 0.68 * inch
    bottom = 0.62 * inch
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
        P("II. RELATED WORK AND DESIGN POSITION", styles["heading"]),
        P("Digital steganography has historically been evaluated through imperceptibility, payload capacity, and resistance to statistical detection. Early data-hiding work established that a useful covert channel must consider both the embedding representation and the transformations expected during distribution [1]. Later JPEG research moved embedding from raw pixels toward quantized frequency coefficients because the JPEG codec itself operates on block DCT values [2], [4].", styles["body"]),
        P("Robustness claims are strongly dependent on the distortion model. A method that survives a quality-factor change may still fail after resizing, cropping, color conversion, or a decode-and-reencode pipeline. Social platforms commonly combine several of these operations. Consequently, laboratory recompression at a known quality factor is not equivalent to uploading a file to a live service and decoding the derivative returned to a recipient.", styles["body"]),
        P("Error-correcting codes are frequently added to robust data-hiding systems because small coefficient changes create isolated symbol errors. Reed-Solomon codes are appropriate for block-oriented payloads and provide a clear correction budget [5]. They do not, however, repair geometric desynchronization: if the receiver reads different spatial blocks, the resulting symbol stream is not a lightly corrupted version of the transmitted stream.", styles["body"]),
        P("ShadowPost differs from approaches that treat readable output as sufficient. AES-GCM authentication makes message recovery binary: the reconstructed ciphertext either authenticates or it does not. This prevents a damaged hidden stream from being interpreted as a valid plaintext. It also separates confidentiality from concealment; security does not depend on an observer failing to notice the embedding pattern.", styles["body"]),
        P("The main contribution of this work is therefore empirical and systems-oriented. It combines a fixed native-DCT embedding design with cryptographic framing and an explicit platform benchmark. Positive and negative results are both retained, because a complete failure on a feed-oriented path is actionable evidence about the delivery channel rather than a reason to discard the trial.", styles["body"]),
        P("III. SYSTEM DESIGN", styles["heading"]),
        P("<b>A. Security and framing.</b> A plaintext message is encrypted with AES-256-GCM using a scrypt-derived key. The resulting container includes a two-byte length, a 12-byte nonce, ciphertext, and a 16-byte authentication tag. The framed bytes are split into 32-byte data blocks and encoded with RS(48,32), adding 16 parity bytes per codeword.", styles["body"]),
        P("<b>B. Native-DCT embedding.</b> ShadowPost reads and writes JPEG coefficient arrays directly. In the luminance channel, each bit is represented by the relative magnitude ordering of two coefficient pairs: positions (1,3) versus (2,2), and (1,4) versus (4,1). Extraction uses a deterministic tie rule, |A| >= |B|, so the decoder remains reproducible at zero or equal coefficients.", styles["body"]),
        P("<b>C. Decode pipeline.</b> The receiver extracts the coefficient-order bits, groups them into RS codewords, corrects errors when possible, reconstructs the encrypted container, and authenticates it with AES-GCM. A message is counted as recovered only when the complete plaintext matches exactly.", styles["body"]),
        P("IV. EVALUATION METHOD", styles["heading"]),
        P("<b>A. Trial cohorts.</b> The canonical CSV contains 270 rows. Telegram, Discord, and WhatsApp Document use the structured 15-cover matrix with 10-byte, 100-byte, and image-specific near-capacity payloads. Twitter/X, Instagram, and WhatsApp Image each contain 45 fixed 100-byte trials. This distinction is retained because the source datasets do not have identical payload distributions.", styles["body"]),
        P("<b>B. Metrics.</b> We report exact recovery rate and bit error rate (BER). BER is computed from rows with a recorded bit comparison; trials rejected before delivery have no BER and are excluded from the corresponding mean. Delivery behavior is interpreted from the returned JPEG dimensions, extraction outcome, and failure reason stored in the platform CSVs.", styles["body"]),
        P("V. RESULTS", styles["heading"]),
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
        P("VI. DETAILED CHANNEL ANALYSIS", styles["heading"]),
        P("<b>A. Discord attachment mode.</b> Discord is the strongest channel in this study. All 45 messages were recovered exactly, including the near-capacity cases. The zero BER result indicates that the attachment path retained the JPEG coefficient stream sufficiently for the native decoder. This does not mean Discord is intrinsically lossless for every client or future policy; it means the tested webhook attachment path did not introduce a transformation that disturbed the selected DCT relationships.", styles["body"]),
        P("The result is important because the embedding itself is deliberately conservative. ShadowPost does not modify every coefficient, use a perceptual optimization loop, or search for a new synchronization point after delivery. When the original block grid is preserved, the simple relative-order decoder is sufficient. This provides a useful baseline against which all recompressing channels can be compared.", styles["body"]),
        P("<b>B. WhatsApp document mode.</b> WhatsApp Document also recovered all 45 messages with zero BER. The document mode is evaluated as file transfer rather than ordinary image presentation: the JPEG remains an attached file instead of being treated as a display image. The outcome supports a practical deployment distinction. A channel may be unsuitable for an image-post workflow while remaining suitable for sending the same JPEG as a file.", styles["body"]),
        P("The document result should be interpreted together with the image-mode result, not averaged into a generic WhatsApp score. The two modes expose different server behaviors. The document path preserved the encoded structure in all tested rows, while the standard image path failed all fixed-payload trials. For ShadowPost users, selecting the media type is therefore a protocol decision, not a cosmetic choice.", styles["body"]),
        P("<b>C. Telegram sendPhoto.</b> Telegram produced the intermediate result, with 36 exact recoveries out of 45 trials. The successful rows show that modest platform processing can be survivable when the delivered dimensions remain compatible with the encoder's 8 by 8 block registration. The failed rows show the boundary of that assumption: spatial resizing changes the number and placement of DCT blocks, so the decoder reads a different coefficient lattice from the one used during embedding.", styles["body"]),
        P("Telegram failures also illustrate why a single aggregate BER is insufficient. Some failed rows have a measurable BER near one half, consistent with an out-of-registration bit stream; other rows are rejected before transmission because the near-capacity payload is larger than the delivered image can support. These are different engineering failures and should lead to different mitigations.", styles["body"]),
        P("<b>D. Twitter/X image posts.</b> The Twitter/X cohort contains 45 fixed 100-byte trials and recovered no messages. The failure records identify missing synchronization and aggressive lossy transcoding with spatial rescaling. The important observation is that the failure occurs at the DCT coordinate-system boundary: even a short payload cannot be extracted when the returned image no longer shares the expected block registration.", styles["body"]),
        P("This result does not establish that every possible X media path is impossible. It establishes that the tested public image-post delivery path is incompatible with the current native-grid decoder. A future design could attempt scale-invariant synchronization, multi-resolution markers, or a spatially re-registered decoder, but those would be new algorithms outside this locked benchmark.", styles["body"]),
        P("<b>E. Instagram feed posts.</b> Instagram also recovered 0/45 fixed 100-byte trials. The recorded reasons identify aggressive JPEG transcoding and spatial downsampling. Feed presentation requires the platform to produce display-oriented derivatives, and the derivative is not required to preserve the original JPEG coefficient arrays. As a result, the error-correction layer never receives a stable enough bit stream to operate.", styles["body"]),
        P("The Instagram outcome is a useful negative control for claims about DCT robustness. DCT-domain embedding is more appropriate than pixel-domain embedding for JPEG workflows, but the transform domain alone does not defeat arbitrary platform resizing. Robustness must be defined relative to a delivery model, and the feed model tested here is substantially more aggressive than a file attachment.", styles["body"]),
        P("<b>F. WhatsApp standard image mode.</b> Standard WhatsApp image delivery recovered 0/45 fixed 100-byte trials. The result contrasts sharply with WhatsApp Document and demonstrates that the label \"WhatsApp\" is not a sufficient experimental condition. The media subtype determines whether the system receives an intact JPEG file or a presentation-oriented derivative.", styles["body"]),
        P("VII. FORMAL PIPELINE AND CAPACITY", styles["heading"]),
        P("Let M be the plaintext message. ShadowPost first derives a 256-bit key K from a passphrase using scrypt. AES-GCM then produces ciphertext C and an authentication tag T using a fresh 96-bit nonce N. The framed container is L || N || C || T, where L is a two-byte plaintext length field. The framing permits the decoder to distinguish the meaningful message bytes from padding inside the final RS codeword.", styles["body"]),
        P("The framed byte stream is partitioned into data blocks D_i of 32 bytes. Each D_i is encoded as a 48-byte Reed-Solomon codeword W_i. In the absence of delivery damage, the decoder recovers W_i exactly. With bounded symbol errors, the parity symbols permit correction. When the coefficient grid is displaced, however, the extracted symbols are not local perturbations of W_i; they are samples from a different coordinate system, so RS correction may fail or produce an unauthenticated ciphertext.", styles["body"]),
        P("For an image with B luminance DCT blocks, the two selected pair positions provide four coefficient values per block and two ordering decisions. The raw bit capacity is therefore 2B bits before framing and code overhead. The available plaintext capacity is smaller because the framed ciphertext, nonce, tag, and RS parity must all fit. For a requested message length m, the number of codewords is ceil((2 + 12 + m + 16) / 32), and the encoded requirement is 48 times that codeword count bytes, or 384 times that count bits.", styles["body"]),
        P("This capacity model explains the near-capacity trials. A payload that fits the original cover may not fit a resized derivative. In such a case, the correct result is a capacity failure, not a BER measurement. The benchmark preserves this distinction by leaving BER empty for trials rejected before delivery.", styles["body"]),
        P("VIII. ERROR MODEL AND FAILURE TAXONOMY", styles["heading"]),
        P("The benchmark uses three operational failure classes. First, a byte-preserving success produces a valid extraction, valid RS decoding, valid AES-GCM authentication, and exact plaintext equality. Second, a delivery-corruption failure produces an extracted stream but exceeds the correction capability or fails authentication. Third, a capacity or structural failure occurs when the delivered image has too few blocks or no recoverable synchronization structure.", styles["body"]),
        P("A bit error rate is useful only when the decoder can align the received bit positions with the transmitted positions. Under a pure coefficient perturbation model, BER summarizes the damage before RS decoding. Under spatial rescaling, the problem is not merely that individual bits flip; the receiver's index i refers to a different block than the sender's index i. This is why several social-feed rows show BER 1.0 and a missing synchronization marker rather than a correctable low BER.", styles["body"]),
        P("The Telegram rows make this taxonomy concrete. Low or zero BER rows correspond to derivatives that retain a compatible grid. Rows with BER near one half indicate structural desynchronization. Rows with no BER correspond to payloads that exceeded delivered capacity. Treating these categories as one failure class would hide the actual engineering trade-off.", styles["body"]),
        P("IX. SECURITY AND PRIVACY ANALYSIS", styles["heading"]),
        P("Confidentiality is provided by AES-GCM rather than by the visual concealment layer. An observer who extracts coefficient orderings without the passphrase still obtains ciphertext and cannot recover the authenticated plaintext under the cryptographic assumptions of AES-GCM and scrypt. The nonce is stored with the ciphertext because it is required for decryption but is not secret.", styles["body"]),
        P("Integrity is equally important. A platform transformation that changes hidden bits should not silently produce a plausible plaintext. GCM authentication rejects modified ciphertext, and the application reports decode failure instead of returning unauthenticated bytes. Reed-Solomon improves availability under bounded corruption but does not replace authentication; corrected data is accepted only after GCM verification.", styles["body"]),
        P("The system does not claim steganalytic undetectability. Relative coefficient ordering leaves a statistical footprint, and repeated use of the same coefficient positions could be detectable by a sufficiently trained analyst. The contribution evaluated here is delivery survivability under known platform transforms, not resistance to a dedicated detector.", styles["body"]),
        P("A deployment must also separate passphrases from media distribution. The JPEG can be public while the passphrase remains out of band. Operational security therefore depends on key handling, account security, and the platform's metadata exposure in addition to the DCT payload itself.", styles["body"]),
        P("X. REPRODUCIBILITY PROCEDURE", styles["heading"]),
        P("The repository contains the encoder and decoder, the phase experiments, platform-specific CSVs, the canonical master CSV, charts, and the downloaded Twitter/X and Instagram derivatives. A reproduction should first run the local API round-trip test, then inspect the cover manifest used by the structured cohort. The passphrase and message generator must remain unchanged when comparing results with the stored rows.", styles["body"]),
        P("For every trial, the reproduction record should include platform mode, trial identifier, source cover or delivered filename, plaintext payload length, success flag, BER when defined, failure reason, and timestamp. These fields make it possible to distinguish a cryptographic failure from a platform transformation and a local preparation error.", styles["body"]),
        P("The downloaded derivatives should be treated as evidence files, not as new covers. The sender-side stego image and receiver-side delivered image belong to different stages of the experiment. Re-encoding a downloaded derivative before decoding would change the measurement and must be avoided.", styles["body"]),
        P("The paper generator reads the canonical CSV rather than hard-coding the recovery counts. This keeps the numerical tables coupled to the repository artifact and reduces transcription errors when additional platform trials are added. The generated PDF is therefore a report over a versioned dataset, not an independent hand-edited results sheet.", styles["body"]),
        P("XI. COMPARISON WITH COMMON DESIGN ALTERNATIVES", styles["heading"]),
        P("Pixel-domain least-significant-bit embedding is simple and can provide useful capacity on an untouched bitmap, but JPEG decoding and recompression operate in a different representation. A platform that decodes and re-encodes the image can erase pixel-level changes even when the visual image appears unchanged. Native-DCT embedding aligns the representation with JPEG compression, which explains the partial Telegram survival and the strong attachment results.", styles["body"]),
        P("A pure DCT payload without authentication can report a recovered string even when a few bits have changed. ShadowPost instead treats the hidden data as an encrypted authenticated object. This increases overhead, reducing usable capacity, but prevents false-positive recovery and makes the success criterion unambiguous.", styles["body"]),
        P("A larger error-correcting code could improve recovery under bounded coefficient noise, but it cannot solve arbitrary geometric resampling. Increasing parity would also reduce payload capacity. The current RS(48,32) setting is therefore a controlled baseline, not a claim that the parity rate is globally optimal.", styles["body"]),
        P("XII. LIMITATIONS AND VALIDITY THREATS", styles["heading"]),
        P("The benchmark is limited to the accounts, clients, image files, and dates represented by the stored artifacts. Social platforms can change image processing without notice. A later run may produce different dimensions or quantization behavior, so the timestamps and downloaded derivatives are part of the experiment's provenance.", styles["body"]),
        P("The cohorts are intentionally not collapsed into one perfectly balanced design. The structured cohort tests payload scaling; the feed/media cohort tests a repeated 100-byte message under delivery paths that were already known to produce derivatives. This supports a practical channel comparison but does not support a claim that every platform has been evaluated at every payload size.", styles["body"]),
        P("The study does not measure peak signal-to-noise ratio, structural similarity, visual quality, computational latency, detector performance, or key-search cost. It also does not evaluate video, animated media, PNG delivery, or alternative client applications. These omissions define the next experimental phase rather than weaknesses that can be hidden by the current success rate.", styles["body"]),
        P("XIII. EXTENDED RESULTS INTERPRETATION", styles["heading"]),
        P("The overall recovery rate of 46.7% is not a single estimate of algorithm quality. It is the mixture of three channel regimes: two complete-preservation modes, one partially preserving mode, and three zero-recovery feed/image modes. The more useful engineering statement is conditional: when the JPEG structure is preserved, the current pipeline recovered every tested message; when the structure was spatially remapped, it recovered none in the tested rows.", styles["body"]),
        P("The result also shows why a platform benchmark should report delivery mode explicitly. A product requirement such as \"works on WhatsApp\" is underspecified. The document and image paths have opposite outcomes in this dataset. Similarly, a public feed post is not equivalent to attaching the original JPEG as a file, even if the visual image looks identical to a user.", styles["body"]),
        P("The main design opportunity is synchronization. A future version could embed a redundant multi-scale marker, infer the delivered block grid from a known cover region, or use a spatial-domain fallback for the scale transform before DCT extraction. Each alternative changes the threat model and must be evaluated separately; none should be silently mixed into the current benchmark.", styles["body"]),
        P("XIV. DISCUSSION", styles["heading"]),
        P("The results separate two properties that are often conflated: payload robustness and channel preservation. RS parity can correct bounded coefficient errors, but it cannot reconstruct a payload when the receiver loses block-grid alignment or when the platform has replaced the JPEG with a substantially different spatial representation. The 100% document results therefore reflect preservation of the original file structure, whereas the 0% feed results show that the current native-grid decoder is not invariant to arbitrary rescaling.", styles["body"]),
        P("Telegram occupies an intermediate regime. Some images remain decodable, while high-resolution or rescaled images fail structurally. A deployment policy should therefore inspect delivered dimensions and reserve capacity below the smallest expected grid, rather than treating all JPEG upload paths as equivalent.", styles["body"]),
        P("XV. LIMITATIONS", styles["heading"]),
        P("The benchmark is a platform snapshot rather than a universal guarantee. Platform encoders, account settings, client versions, and image policies can change. The three feed/media datasets use fixed 100-byte payloads and are not directly equivalent to the structured three-payload cohort. The study also measures exact recovery, not visual quality, detectability, or resistance to an active steganalyst. These dimensions are appropriate follow-up evaluations.", styles["body"]),
        P("XVI. CONCLUSION", styles["heading"]),
        P("ShadowPost combines native-JPEG DCT embedding, authenticated encryption, and Reed-Solomon coding in a measurable delivery pipeline. Across 270 recorded trials, exact recovery was 46.7% overall, with complete recovery on byte-preserving Discord and WhatsApp document channels, partial recovery on Telegram, and no recovery on the tested Twitter/X, Instagram, or standard WhatsApp image paths. The central engineering conclusion is direct: error correction helps only while the platform preserves enough of the original DCT coordinate system for extraction to remain meaningful.", styles["body"]),
        PageBreak(),
        P("APPENDIX A. COVER MANIFEST", styles["heading"]),
        P("The structured cohort uses the following cover identifiers from the finalized Phase 1 manifest. They span game imagery, vehicles, landscapes, science imagery, particles, and technology scenes, providing variation in texture, edge density, and spatial frequency content.", styles["body"]),
        P("arsenal/preview.jpg; audiophile/preview.jpg; beach/preview.jpg; corsair_collection/dotted.fabeb454b273c6d2398a.jpg; deep_space/preview.jpg; demon_core/preview.jpg; dna_fragment/preview.jpg; eagleflag/preview.jpg; fantasticcar/preview.jpg; neon_sunset/preview.jpg; retro/preview.jpg; ricepod/preview.jpg; sheep/preview.jpg; shimmering_particles/preview.jpg; techno/preview.jpg.", styles["small"]),
        P("Cover diversity matters because the available DCT coefficients depend on image texture. Smooth areas tend to contain many zero or low-magnitude AC coefficients, while detailed areas distribute energy across more frequencies. A relative-order embedding method may therefore have different visual and robustness behavior on a low-texture sky than on a particle field or a detailed vehicle scene.", styles["body"]),
        P("The manifest also includes a high-resolution outlier, the Corsair collection image. This cover is useful because it exposes the effect of platform dimension limits. A large original grid offers high sender-side capacity, but a platform may produce a much smaller derivative. The delivered grid, not the source grid, ultimately determines whether extraction can address the encoded bit positions.", styles["body"]),
        P("The finalized Phase 1 directory is retained as the authoritative embedding manifest. Earlier experimental directories remain historical artifacts and should not be mixed with the final pair-selection results when reproducing the platform benchmark.", styles["body"]),
        PageBreak(),
        P("APPENDIX B. DATA DICTIONARY", styles["heading"]),
        P("The master CSV uses the following fields. <b>platform</b> identifies the delivery mode; <b>trial</b> is the per-mode sequence number; <b>cover_name</b> identifies the source or returned media filename; <b>payload_size_bytes</b> records the plaintext length requested by the encoder; <b>success</b> is true only for exact plaintext recovery; <b>ber</b> stores the measured bit error rate when alignment and comparison are available; <b>failure_reason</b> records the first diagnosed failure; and <b>timestamp</b> records the trial event time.", styles["body"]),
        P("The six platform-specific files are retained beside the canonical master file. A consistency check compares rows grouped by platform and verifies 45 rows per mode. The benchmark is therefore auditable without relying on the generated PDF alone.", styles["body"]),
        P("A data audit should begin by checking that the master file contains 270 rows and that each platform label occurs exactly 45 times. The sum of true success values must be 126. Discord and WhatsApp Document should each contain 45 successes, Telegram should contain 36, and the remaining three image/feed modes should contain zero. Any mismatch indicates that the paper, chart, or platform-specific files are out of synchronization.", styles["body"]),
        P("Payload-distribution checks are also required. Discord, Telegram, and WhatsApp Document must each contain fifteen 10-byte rows, fifteen 100-byte rows, and fifteen image-specific near-capacity rows. Twitter/X, Instagram, and WhatsApp Image must each contain forty-five 100-byte rows. This test prevents the fixed-payload feed cohort from being incorrectly described as a three-payload matrix.", styles["body"]),
        P("BER values require careful handling. An empty BER is not equivalent to zero; it indicates that a meaningful aligned bit comparison was unavailable, commonly because the requested payload could not fit the delivered grid. Aggregate BER should therefore be calculated only over non-empty cells, while the trial still remains a failure in the exact-recovery rate.", styles["body"]),
        P("Failure reasons should be treated as diagnostic labels rather than independent measurements. A reason such as synchronization missing, Reed-Solomon decoding failure, or insufficient capacity summarizes the observed terminal condition. Reproduction code should preserve the underlying exception or response where possible, because two rows with the same success flag may require different engineering changes.", styles["body"]),
        P("The timestamp field provides ordering and provenance but should not be used as a performance measurement. Trial duration was not defined by the stored schema. A future benchmark that evaluates throughput or latency should add explicit start, upload-complete, download-complete, and decode-complete timestamps.", styles["body"]),
        P("A clean-room reproduction can use the following sequence: verify dependencies; run the local API round trip; load the finalized cover manifest; generate payloads with the locked message function; encode each image once; transmit through the selected mode; retrieve the returned media without additional processing; run extraction and decryption; append one CSV row; and compare the regenerated platform file with the master dataset.", styles["body"]),
        PageBreak(),
        P("APPENDIX C. RECOMMENDED FUTURE EXPERIMENTS", styles["heading"]),
        P("Future work should test the same stego JPEG through multiple clients and image dimensions, record source and delivered dimensions for every row, and separate ordinary recompression from geometric scaling. A second phase should compare fixed-grid extraction with a synchronization-aware decoder. Payload sizes should be normalized across every platform so the effect of capacity can be separated from the effect of delivery transformation.", styles["body"]),
        P("A stronger evaluation would add visual-quality metrics and a detector study. Embedding strength can be varied while holding the cryptographic and coding layers fixed. The resulting Pareto frontier would show how much imperceptibility is traded for survivability. Repeated measurements over time would also quantify platform drift rather than treating one date as a permanent property of a service.", styles["body"]),
        P("The first extension should create a balanced cross-platform matrix. Every platform mode should receive the same sender-side stego JPEG for the same cover and payload. This would permit paired comparisons and eliminate ambiguity caused by different delivered filenames or fixed-payload cohorts. The present results remain useful, but a balanced design would support stronger statistical conclusions.", styles["body"]),
        P("The second extension should isolate transformation type. Controlled tests can independently vary JPEG quality, width, height, chroma subsampling, metadata removal, and cropping. A regression model over these factors could estimate which transform causes the largest loss of synchronization. Live-platform results could then be mapped to the nearest controlled transformation profile.", styles["body"]),
        P("The third extension should evaluate synchronization-aware extraction. Candidate designs include periodic pilot blocks, repeated sync words at several spatial scales, orientation markers, and a search over plausible delivered dimensions. Each candidate must be compared against the current fixed-grid baseline using identical covers and cryptographic payloads.", styles["body"]),
        P("The fourth extension should measure detectability. A steganalysis dataset should contain matched cover and stego images generated with several payload rates. Classical rich-model features and modern convolutional detectors can be used to estimate detection accuracy. A survivable system that is trivially detectable would not satisfy the broader covert-communication goal.", styles["body"]),
        P("The fifth extension should measure perceptual quality with PSNR, SSIM, and a human review protocol. These metrics should be reported before and after platform delivery because a platform can mask sender-side artifacts while simultaneously destroying the payload. Visual similarity alone is therefore not evidence of hidden-message survival.", styles["body"]),
        P("The sixth extension should evaluate operational reliability. Trials should be repeated across desktop and mobile clients, multiple geographic regions, and several dates. Platform policies change, and a robust engineering conclusion requires confidence intervals over repeated deliveries rather than a single run per prepared image.", styles["body"]),
        P("Finally, future reports should publish a machine-readable experiment manifest containing software versions, client identifiers, image hashes, source dimensions, delivered dimensions, payload hashes, and decoder version. This would strengthen reproducibility without exposing plaintext secrets or passphrases.", styles["body"]),
        PageBreak(),
        P("DATA AVAILABILITY AND ARTIFACT MAP", styles["heading"]),
        P("The implementation and benchmark artifacts are versioned in the ShadowPost repository. The canonical `platform_trials.csv` file is the numerical source for the tables in this paper. Separate CSVs preserve the six delivery-mode subsets. The Phase 1, Phase 2, and Phase 3 directories retain the embedding, error-correction, and encryption experiment outputs used to lock the final pipeline.", styles["body"]),
        P("The `downloaded/twitter` and `downloaded/instagram` directories contain the returned media used by those platform rows. The Phase 7 directory contains generated figures. `make_ieee_paper.py` reads the canonical dataset and produces this PDF, allowing the reported counts to be regenerated from the repository state.", styles["body"]),
        P("RESPONSIBLE USE", styles["heading"]),
        P("Steganography can support legitimate privacy research, watermarking, censorship resistance, and secure metadata-free exchange, but it can also be misused. ShadowPost is presented as a research prototype for measuring image-channel behavior. Deployments should comply with applicable law, institutional policy, and platform terms, and should not be used to conceal harmful activity or bypass authorized monitoring.", styles["body"]),
        P("ORIGINALITY STATEMENT", styles["heading"]),
        P("This manuscript was newly written from the repository implementation and recorded experiment data. The supplied project document was used only to understand the intended topic and presentation scope. Technical standards and prior work are acknowledged through the references below; their wording was not copied into the manuscript.", styles["body"]),
        P("REFERENCES", styles["heading"]),
        P("[1] W. Bender, D. Gruhl, N. Morimoto, and A. Lu, \"Techniques for data hiding,\" IBM Systems Journal, vol. 35, no. 3-4, pp. 313-336, 1996.", styles["reference"]),
        P("[2] J. Fridrich, Steganography in Digital Media: Principles, Algorithms, and Applications. Cambridge, U.K.: Cambridge University Press, 2009.", styles["reference"]),
        P("[3] National Institute of Standards and Technology, Advanced Encryption Standard (AES), FIPS PUB 197, 2001.", styles["reference"]),
        P("[4] International Telecommunication Union, Information Technology - Digital Compression and Coding of Continuous-Tone Still Images - Requirements and Guidelines, Recommendation T.81, 1992.", styles["reference"]),
        P("[5] I. S. Reed and G. Solomon, \"Polynomial codes over certain finite fields,\" Journal of the Society for Industrial and Applied Mathematics, vol. 8, no. 2, pp. 300-304, 1960.", styles["reference"]),
        P("[6] National Institute of Standards and Technology, Recommendation for Block Cipher Modes of Operation: Galois/Counter Mode (GCM) and GMAC, Special Publication 800-38D, 2007.", styles["reference"]),
        P("[7] C. Cachin, \"An information-theoretic model for steganography,\" in Information Hiding, Lecture Notes in Computer Science, vol. 1525, 1998, pp. 306-318.", styles["reference"]),
        P("[8] N. Provos and P. Honeyman, \"Hide and seek: An introduction to steganography,\" IEEE Security and Privacy, vol. 1, no. 3, pp. 32-44, 2003.", styles["reference"]),
        P("[9] T. Filler, J. Judas, and J. Fridrich, \"Minimizing additive distortion in steganography using syndrome-trellis codes,\" IEEE Transactions on Information Forensics and Security, vol. 6, no. 3, pp. 920-935, 2011.", styles["reference"]),
        P("[10] J. Fridrich and J. Kodovsky, \"Rich models for steganalysis of digital images,\" IEEE Transactions on Information Forensics and Security, vol. 7, no. 3, pp. 868-882, 2012.", styles["reference"]),
        P("[11] C. Percival and S. Josefsson, The scrypt Password-Based Key Derivation Function, IETF RFC 7914, 2016.", styles["reference"]),
        P("[12] ShadowPost Research Team, \"ShadowPost platform trial datasets and implementation,\" project artifact, 2026.", styles["reference"]),
    ]
    doc.build(story)
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    make_pdf()
