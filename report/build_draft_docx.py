"""Build draft Word document for Stage 3 (Front matter, Chapter 1, Chapter 2).

Output: report/draft_stage3.docx
Format rules:
- Page size: US Letter (8.5 x 11 in)
- Margins: 1.25 in left, 1.0 in right, top, bottom
- Times New Roman 12 pt, 1.5 line spacing
- Chapter titles: 14 pt bold, centred, capitals
- Headings & sub-headings bold
- Table caption ABOVE table (12 pt bold)
- Figure caption BELOW figure (12 pt bold)
- Section 1: Front matter (lowerRoman page numbers in footer)
- Section 2: Body Chapters 1 & 2 (decimal page numbers starting at 1)
"""

import os
from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Set inner cell padding in twips."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('w:top', top), ('w:bottom', bottom), ('w:left', left), ('w:right', right)]:
        node = OxmlElement(m)
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def set_cell_shading(cell, color_hex):
    """Set cell background color."""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
    tcPr.append(shd)

def set_table_borders(table, color="D3D3D3", sz="4", val="single"):
    """Set clean subtle borders on table."""
    tblPr = table._tbl.tblPr
    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'  <w:top w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'  <w:bottom w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'  <w:insideH w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'  <w:insideV w:val="none"/>'
        f'  <w:left w:val="none"/>'
        f'  <w:right w:val="none"/>'
        f'</w:tblBorders>'
    )
    tblPr.append(borders)

def add_page_number_to_section(section, start_num=None, num_format="decimal"):
    """Configure footer page numbering for a document section."""
    sectPr = section._sectPr
    pgNumType = OxmlElement('w:pgNumType')
    pgNumType.set(qn('w:fmt'), num_format)
    if start_num is not None:
        pgNumType.set(qn('w:start'), str(start_num))
    sectPr.append(pgNumType)

    footer = section.footer
    footer.is_linked_to_previous = False
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.0

    # Add page number field
    run = p.add_run()
    run.font.name = "Times New Roman"
    run.font.size = Pt(11)
    fldSimple = OxmlElement('w:fldSimple')
    fldSimple.set(qn('w:instr'), 'PAGE')
    run._r.append(fldSimple)

def apply_base_page_layout(section):
    """Set 21.5 cm x 28 cm (US Letter) page size and required margins."""
    section.page_width = Inches(8.5)
    section.page_height = Inches(11.0)
    section.left_margin = Inches(1.25)
    section.right_margin = Inches(1.0)
    section.top_margin = Inches(1.0)
    section.bottom_margin = Inches(1.0)

def main():
    doc = Document()
    base_dir = Path(__file__).resolve().parent
    assets_dir = base_dir / "assets"
    output_docx = base_dir / "draft_stage3.docx"

    # Base Normal Style setup
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Times New Roman'
    font.size = Pt(12)
    font.color.rgb = RGBColor(0x22, 0x22, 0x22)
    style.paragraph_format.line_spacing = 1.5
    style.paragraph_format.space_after = Pt(6)

    # Section 1: Front Matter
    sec1 = doc.sections[0]
    apply_base_page_layout(sec1)
    add_page_number_to_section(sec1, num_format="lowerRoman")

    # -------------------------------------------------------------
    # 1. FRONT PAGE
    # -------------------------------------------------------------
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(36)
    p.paragraph_format.space_after = Pt(18)
    run = p.add_run("CITY-WIDE AI ENGINE FOR MULTI-CAMERA ANPR TRAJECTORY TRACKING AND URBAN TRAFFIC ANALYTICS")
    run.font.size = Pt(16)
    run.font.bold = True
    run.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(18)
    run = p.add_run("A Project Report Submitted in Partial Fulfilment of the Requirements\nfor the Award of the Degree of")
    run.font.size = Pt(12)
    run.font.italic = True

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(24)
    run = p.add_run("BACHELOR OF TECHNOLOGY\nin\nCOMPUTER SCIENCE AND ENGINEERING")
    run.font.size = Pt(14)
    run.font.bold = True

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(12)
    run = p.add_run("by")
    run.font.italic = True

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(24)
    run = p.add_run("[TEAM MEMBERS AND REG. NOS.]")
    run.font.size = Pt(13)
    run.font.bold = True

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(36)
    run = p.add_run("Under the Guidance of\n[GUIDE NAME AND DESIGNATION]")
    run.font.size = Pt(12)
    run.font.bold = True

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(24)
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run("DEPARTMENT OF COMPUTER SCIENCE AND ENGINEERING\n[INSTITUTION / UNIVERSITY NAME]\n[MONTH YEAR]")
    run.font.size = Pt(12)
    run.font.bold = True

    doc.add_page_break()

    # -------------------------------------------------------------
    # 2. CERTIFICATE
    # -------------------------------------------------------------
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(6)
    run = p.add_run("DEPARTMENT OF COMPUTER SCIENCE AND ENGINEERING\n[INSTITUTION / UNIVERSITY NAME]")
    run.font.size = Pt(13)
    run.font.bold = True

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(18)
    p.paragraph_format.space_after = Pt(24)
    run = p.add_run("CERTIFICATE")
    run.font.size = Pt(14)
    run.font.bold = True

    p = doc.add_paragraph(
        "This is to certify that the project report entitled \"City-Wide AI Engine for Multi-Camera ANPR Trajectory "
        "Tracking and Urban Traffic Analytics\" is a bonafide record of the work carried out by [TEAM MEMBERS AND REG. NOS.] "
        "in partial fulfilment of the requirements for the award of the degree of Bachelor of Technology in Computer Science "
        "and Engineering from [INSTITUTION / UNIVERSITY NAME] during the academic year 2026–2027."
    )
    p.paragraph_format.space_after = Pt(14)
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    p = doc.add_paragraph(
        "The results embodied in this report have not been submitted to any other university or institute for the award "
        "of any degree or diploma."
    )
    p.paragraph_format.space_after = Pt(48)
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # Signature Block Table
    sig_table = doc.add_table(rows=1, cols=2)
    sig_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    sig_table.autofit = False
    sig_table.columns[0].width = Inches(3.0)
    sig_table.columns[1].width = Inches(3.0)

    cell_left = sig_table.cell(0, 0)
    p_l = cell_left.paragraphs[0]
    p_l.paragraph_format.line_spacing = 1.2
    run_l = p_l.add_run("[GUIDE NAME AND DESIGNATION]\nProject Guide\nDepartment of Computer Science & Engineering")
    run_l.font.size = Pt(11)
    run_l.font.bold = True

    cell_right = sig_table.cell(0, 1)
    p_r = cell_right.paragraphs[0]
    p_r.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_r.paragraph_format.line_spacing = 1.2
    run_r = p_r.add_run("[HOD NAME]\nHead of the Department\nDepartment of Computer Science & Engineering")
    run_r.font.size = Pt(11)
    run_r.font.bold = True

    p_space = doc.add_paragraph()
    p_space.paragraph_format.space_before = Pt(60)

    p_exam = doc.add_paragraph()
    p_exam.paragraph_format.line_spacing = 1.2
    p_exam.add_run("Internal Examiner: _______________________          External Examiner: _______________________").font.bold = True

    doc.add_page_break()

    # -------------------------------------------------------------
    # 3. ACKNOWLEDGEMENT
    # -------------------------------------------------------------
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(18)
    run = p.add_run("ACKNOWLEDGEMENT")
    run.font.size = Pt(14)
    run.font.bold = True

    ack_texts = [
        "We express our sincere gratitude to [INSTITUTION / UNIVERSITY NAME] for providing the academic infrastructure, computing facilities, and research environment required to carry out this final-year B.Tech project.",
        "We convey our profound gratitude and respect to our project guide, [GUIDE NAME AND DESIGNATION], Department of Computer Science and Engineering, for continuous technical guidance, constructive critique, and encouragement throughout the design, software implementation, and experimental evaluation of this system.",
        "We express our heartfelt gratitude to [HOD NAME], Head of the Department of Computer Science and Engineering, for providing administrative support and academic facilities.",
        "We thank our project review coordinators and all faculty members of the Department of Computer Science and Engineering for their valuable reviews and suggestions during internal milestone presentations.",
        "Finally, we thank our parents, family members, and friends for their continuous patience, understanding, and encouragement throughout this work."
    ]
    for text in ack_texts:
        p = doc.add_paragraph(text)
        p.paragraph_format.space_after = Pt(12)
        p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    p_sig = doc.add_paragraph()
    p_sig.paragraph_format.space_before = Pt(30)
    p_sig.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_sig.add_run("[TEAM MEMBERS AND REG. NOS.]\nFinal-Year B.Tech Students").font.bold = True

    doc.add_page_break()

    # -------------------------------------------------------------
    # 4. ABSTRACT
    # -------------------------------------------------------------
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(18)
    run = p.add_run("ABSTRACT")
    run.font.size = Pt(14)
    run.font.bold = True

    abstract_p1 = (
        "Urban traffic surveillance networks generate millions of video frames daily across distributed roadside cameras. "
        "However, municipal traffic management centres struggle to convert disjoint camera observations into continuous spatial journeys, "
        "actionable congestion intelligence, and automated surveillance alerts without intensive manual intervention. "
        "In this work, we design and implement an end-to-end city-wide artificial intelligence engine that connects automated "
        "number-plate recognition (ANPR), multi-camera trajectory tracking, and real-time surveillance analytics."
    )
    p = doc.add_paragraph(abstract_p1)
    p.paragraph_format.line_spacing = 2.0  # Double spacing required for Abstract
    p.paragraph_format.space_after = Pt(12)
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    abstract_p2 = (
        "The system operates on a dual-pathway architecture. On real video sequences and held-out photographs, an Ultralytics YOLOv8s "
        "detector localises license plates with 98.3% precision, 98.1% recall, and 84.3% mAP50-95. A Compact Convolutional Transformer "
        "(CCT-s-v2) optical character recogniser, fine-tuned on real Indian plate crops, attains 95.7% character-level accuracy and "
        "76.9% full-plate exact match accuracy. When deployed across multi-frame video clips with ByteTrack and positional confidence-weighted "
        "voting, consensus accuracy reaches 90.00% (18 of 20 test sequences), while an automated quality assurance rule flags low-confidence "
        "readings (OCR confidence or vote margin below 0.80) for human operator review."
    )
    p = doc.add_paragraph(abstract_p2)
    p.paragraph_format.line_spacing = 2.0
    p.paragraph_format.space_after = Pt(12)
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    abstract_p3 = (
        "On a simulated road network of Bangalore (5 km radius, 40 camera nodes, 5,000 vehicles), the spatial database ingests 31,244 "
        "noisy sightings (5% miss rate, 8% confusable character error). A graph-theoretic trajectory reconstruction engine with canonical "
        "3-partition fuzzy indexing achieves 99.95% precision, 96.35% recall, and 97.91% F1-score with 15.82 ms average query latency. "
        "A multi-rule surveillance engine detects 100% (5 of 5) of injected cloned-plate anomalies through shortest-path speed feasibility "
        "analysis (>120 km/h) and achieves 100% precision with 93.6% recall on vehicle blacklist matching. Furthermore, an AI City Challenge "
        "vehicle counting prototype demonstrates that calibrating directional ingress/egress centroids improves test movement counting F1-score "
        "from 17.9% to 65.1%. All capabilities are served through a unified FastAPI gateway and interactive web dashboard."
    )
    p = doc.add_paragraph(abstract_p3)
    p.paragraph_format.line_spacing = 2.0
    p.paragraph_format.space_after = Pt(18)
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    p_kw = doc.add_paragraph()
    p_kw.paragraph_format.line_spacing = 1.5
    run_kwt = p_kw.add_run("Keywords: ")
    run_kwt.font.bold = True
    p_kw.add_run("Automated Number-Plate Recognition, Trajectory Reconstruction, Graph Routing, ByteTrack, Multi-Frame Consensus Voting, Urban Traffic Analytics, Surveillance Alerting.")

    doc.add_page_break()

    # -------------------------------------------------------------
    # 5. TABLE OF CONTENTS
    # -------------------------------------------------------------
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(18)
    run = p.add_run("TABLE OF CONTENTS")
    run.font.size = Pt(14)
    run.font.bold = True

    toc_entries = [
        ("Certificate", "ii", True),
        ("Acknowledgement", "iii", True),
        ("Abstract", "iv", True),
        ("List of Tables", "vii", True),
        ("List of Figures", "viii", True),
        ("List of Symbols and Abbreviations", "ix", True),
        ("1. INTRODUCTION", "1", True),
        ("   1.1 Introduction", "1", False),
        ("   1.2 Major Challenges", "2", False),
        ("      1.2.1 Real-World License Plate Optical Character Recognition", "2", False),
        ("      1.2.2 Tracking and Identity Preservation Across Cameras", "3", False),
        ("      1.2.3 Privacy Considerations and Operator Data Protection", "4", False),
        ("      1.2.4 Absence of Labelled City-Scale ANPR Trajectory Data", "4", False),
        ("   1.3 Proposed Solutions and Key Contributions", "5", False),
        ("   1.4 Background and Motivation", "6", False),
        ("   1.5 Overview of the Proposed System", "8", False),
        ("   1.6 Objective of the Work", "9", False),
        ("   1.7 Organization of the Report", "10", False),
        ("2. RELATED WORK AND THEORETICAL STUDY", "11", True),
        ("   2.1 License Plate Detection and OCR Techniques", "11", False),
        ("   2.2 Multi-Object and Multi-Camera Vehicle Tracking", "13", False),
        ("   2.3 City-Scale Trajectory Reconstruction Datasets", "15", False),
        ("   2.4 Urban Traffic Flow Analytics and Anomaly Alert Systems", "16", False),
        ("   2.5 Vehicle Movement Counting Benchmarks", "18", False),
        ("   2.6 Theoretical Foundations and Metric Formulations", "19", False),
        ("      2.6.1 Precision, Recall, and F1-Score", "19", False),
        ("      2.6.2 Mean Average Precision (mAP)", "20", False),
        ("      2.6.3 Character-Level and Full-Plate Exact Match Accuracies", "21", False),
        ("      2.6.4 Wilson Score Confidence Interval Formulation", "22", False),
        ("      2.6.5 Temporal Event Matching Metric", "23", False),
        ("   2.7 Research Gap and Comparative Analysis", "24", False),
        ("3. EXPERIMENTAL STUDY", "26", True),
        ("4. RESULTS AND DISCUSSIONS", "48", True),
        ("5. CONCLUSIONS AND FUTURE SCOPE", "65", True),
        ("APPENDICES", "69", True),
        ("REFERENCES", "80", True),
        ("LIST OF PUBLICATIONS", "82", True),
    ]

    for title, pg, is_bold in toc_entries:
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.15
        p.paragraph_format.space_after = Pt(2)
        run_t = p.add_run(title)
        run_t.font.bold = is_bold
        run_t.font.size = Pt(11)
        # Dot leader to page number
        dots_len = max(2, 68 - len(title) - len(pg))
        run_dots = p.add_run(" " + "." * dots_len + " ")
        run_dots.font.color.rgb = RGBColor(0x88, 0x88, 0x88)
        run_p = p.add_run(pg)
        run_p.font.bold = is_bold
        run_p.font.size = Pt(11)

    doc.add_page_break()

    # -------------------------------------------------------------
    # 6. LIST OF TABLES
    # -------------------------------------------------------------
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(18)
    run = p.add_run("LIST OF TABLES")
    run.font.size = Pt(14)
    run.font.bold = True

    table_entries = [
        ("Table 2.1: Comparative Analysis of Base Papers with the Proposed System", "25"),
        ("Table 3.1: System Requirements and Engineering Acceptance Benchmarks", "27"),
        ("Table 3.2: Computational Hardware and Software Execution Environment", "28"),
        ("Table 3.3: Image and Video Datasets Utilised Across System Modules", "31"),
        ("Table 3.4: Relational SQLite Schema Architecture (data/city_anpr.db)", "39"),
        ("Table 3.5: RESTful API Endpoints and WebSocket Streaming Interface", "44"),
        ("Table 3.6: Surveillance Alert Engine Rules, Parameters, and Trigger Thresholds", "43"),
        ("Table 3.7: Fixed Hyperparameters for the Vehicle Movement Counting Pipeline", "45"),
        ("Table 4.1: YOLOv8s License Plate Detector Performance on Test Split (N=184) [REAL]", "49"),
        ("Table 4.2: License Plate Optical Character Recognition Progression Across Regimes [REAL]", "50"),
        ("Table 4.3: End-to-End System Evaluation on Held-Out Indian Test Photographs (N=167) [REAL]", "51"),
        ("Table 4.4: Video Plate Voting Performance Across Real Sequences and Synthetic Clips", "53"),
        ("Table 4.5: Qualitative Breakdown of Failed Plate Reads in Video Evaluation [REAL]", "54"),
        ("Table 4.6: Trajectory Reconstruction Engine Accuracy and Latency Benchmarks [SIMULATED]", "55"),
        ("Table 4.7: Surveillance Alert Engine Empirical Evaluation and False Alarm Audit [SIMULATED]", "57"),
        ("Table 4.8: Movement Counting Performance on Test Split (frames >= 300) (v1 vs. v2) [REAL]", "60"),
        ("Table 4.9: Comprehensive Requirements vs. Achieved Performance Audit", "61"),
    ]

    for title, pg in table_entries:
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.15
        p.paragraph_format.space_after = Pt(3)
        run_t = p.add_run(title)
        run_t.font.size = Pt(11)
        dots_len = max(2, 70 - len(title) - len(pg))
        run_dots = p.add_run(" " + "." * dots_len + " ")
        run_dots.font.color.rgb = RGBColor(0x88, 0x88, 0x88)
        run_p = p.add_run(pg)
        run_p.font.size = Pt(11)

    doc.add_page_break()

    # -------------------------------------------------------------
    # 7. LIST OF FIGURES
    # -------------------------------------------------------------
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(18)
    run = p.add_run("LIST OF FIGURES")
    run.font.size = Pt(14)
    run.font.bold = True

    figure_entries = [
        ("Figure 1.1: City-Wide ANPR System Architecture (Block Diagram)", "8"),
        ("Figure 1.2: End-to-End System Data Flow Diagram (DFD)", "9"),
        ("Figure 3.1: Video Perception & Plate Recognition Pipeline", "34"),
        ("Figure 3.2: Multi-Frame Consensus Voting and Quality Assurance Logic", "35"),
        ("Figure 3.3: City-Scale ANPR Simulator Architecture & Event Generation", "37"),
        ("Figure 3.4: Relational Entity-Relationship Diagram (SQLite Database Schema)", "40"),
        ("Figure 3.5: Cross-Camera Trajectory Reconstruction & Fuzzy Search Engine", "41"),
        ("Figure 3.6: Multi-Rule Surveillance Alert Engine Evaluation Pipeline", "43"),
        ("Figure 3.7: REST API and WebSocket Surveillance Streaming Sequence", "44"),
        ("Figure 3.8: Unified Traffic Intelligence Dashboard Interface Layout", "45"),
        ("Figure 3.9: AI City Challenge Vehicle Counting & Trajectory Assignment", "46"),
        ("Figure 3.10: Schematic Coordinate Map of Camera 5 ROI and 12 Directional Movements", "47"),
        ("Figure 3.11: Project Repository Hierarchy and Deployment Architecture", "48"),
        ("Figure 3.12: Project Implementation Methodology and Milestone Timeline", "48"),
        ("Figure 4.1: License Plate Recognition (OCR) Progression Across Training Regimes [REAL]", "50"),
        ("Figure 4.2: YOLOv8s License Plate Detector Quantitative Evaluation [REAL]", "49"),
        ("Figure 4.3: End-to-End Plate Recognition Benchmark on Held-Out Test Photos [REAL]", "52"),
        ("Figure 4.4: Temporal Consensus Voting Accuracy Across Real & Synthetic Sequences", "53"),
        ("Figure 4.5: Surveillance Alert Engine Incident Classification & Severity Breakdown [SIMULATED]", "58"),
        ("Figure 4.6: Cross-Camera Trajectory Reconstruction Performance & Latency Benchmarks [SIMULATED]", "55"),
        ("Figure 4.7: Vehicle Movement Counting Performance (v1 Visual vs. v2 Calibrated) [REAL]", "60"),
    ]

    for title, pg in figure_entries:
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.15
        p.paragraph_format.space_after = Pt(3)
        run_t = p.add_run(title)
        run_t.font.size = Pt(11)
        dots_len = max(2, 70 - len(title) - len(pg))
        run_dots = p.add_run(" " + "." * dots_len + " ")
        run_dots.font.color.rgb = RGBColor(0x88, 0x88, 0x88)
        run_p = p.add_run(pg)
        run_p.font.size = Pt(11)

    doc.add_page_break()

    # -------------------------------------------------------------
    # 8. LIST OF SYMBOLS AND ABBREVIATIONS
    # -------------------------------------------------------------
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(18)
    run = p.add_run("LIST OF SYMBOLS AND ABBREVIATIONS")
    run.font.size = Pt(14)
    run.font.bold = True

    abbr_data = [
        ("AICity", "AI City Challenge (IEEE Smart World Congress Benchmark)"),
        ("ANPR", "Automated Number-Plate Recognition"),
        ("API", "Application Programming Interface"),
        ("ByteTrack", "Multi-Object Tracking by Associating Every Detection Box"),
        ("CCT", "Compact Convolutional Transformer"),
        ("CI", "Confidence Interval (Wilson score formulation at 95% confidence level)"),
        ("COCO", "Common Objects in Context Benchmark"),
        ("Dijkstra", "Dijkstra's Single-Source Shortest-Path Graph Algorithm"),
        ("ER", "Entity-Relationship (Database Schema)"),
        ("F1", "Harmonic Mean of Precision and Recall (2 * P * R / (P + R))"),
        ("FastAPI", "Modern Asynchronous Web Framework for Building RESTful APIs in Python"),
        ("FN / FP / TP", "False Negative / False Positive / True Positive"),
        ("HSRP", "High-Security Registration Plate"),
        ("IoU", "Intersection over Union (Jaccard Index between bounding boxes)"),
        ("Levenshtein", "Edit Distance Metric for String Character Insertions, Deletions, Substitutions"),
        ("LOS", "Level of Service (Urban Road Traffic Condition Rating)"),
        ("LPRNet", "License Plate Recognition Deep Neural Network Architecture"),
        ("mAP", "Mean Average Precision across object detection classes"),
        ("mAP@50", "Mean Average Precision at an Intersection-over-Union threshold of 0.50"),
        ("mAP@50-95", "Mean Average Precision averaged from IoU 0.50 to 0.95 with step size 0.05"),
        ("MTMC", "Multi-Target Multi-Camera Vehicle Tracking"),
        ("OCR", "Optical Character Recognition"),
        ("OD", "Origin-Destination Traffic Matrix"),
        ("ONNX", "Open Neural Network Exchange Runtime Format"),
        ("OSM / OSMnx", "OpenStreetMap / Python Street Network Modeling Library"),
        ("P95", "95th Percentile Query Execution Latency"),
        ("Re-ID", "Vehicle Re-Identification Across Disjoint Camera Views"),
        ("REST", "Representational State Transfer Architectural Style"),
        ("REVIEW", "Low-Confidence Optical Character Recognition Operator Audit Flag"),
        ("ROI", "Region of Interest Polygon Boundary"),
        ("SQLite", "Embedded Self-Contained Serverless Relational Database Engine"),
        ("WebSocket", "Full-Duplex Bidirectional Persistent Network Communication Protocol"),
        ("Wilson", "Wilson Score Interval for Binomial Confidence Proportions"),
        ("YOLO", "You Only Look Once (Real-Time Object Detection Framework)"),
    ]

    abbr_table = doc.add_table(rows=len(abbr_data), cols=2)
    abbr_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    abbr_table.autofit = False
    abbr_table.columns[0].width = Inches(2.0)
    abbr_table.columns[1].width = Inches(4.25)
    set_table_borders(abbr_table, color="EEEEEE")

    for i, (sym, desc) in enumerate(abbr_data):
        c0 = abbr_table.cell(i, 0)
        c1 = abbr_table.cell(i, 1)
        set_cell_margins(c0, top=60, bottom=60, left=80, right=80)
        set_cell_margins(c1, top=60, bottom=60, left=80, right=80)
        p0 = c0.paragraphs[0]
        p0.paragraph_format.line_spacing = 1.15
        p0.paragraph_format.space_after = Pt(2)
        r0 = p0.add_run(sym)
        r0.font.bold = True
        r0.font.size = Pt(10.5)

        p1 = c1.paragraphs[0]
        p1.paragraph_format.line_spacing = 1.15
        p1.paragraph_format.space_after = Pt(2)
        r1 = p1.add_run(desc)
        r1.font.size = Pt(10.5)

    doc.add_page_break()

    # =============================================================
    # Section 2: Body Chapters (Arabic numerals starting at 1)
    # =============================================================
    sec2 = doc.add_section()
    apply_base_page_layout(sec2)
    add_page_number_to_section(sec2, start_num=1, num_format="decimal")

    # -------------------------------------------------------------
    # CHAPTER 1: INTRODUCTION
    # -------------------------------------------------------------
    p_ch1 = doc.add_paragraph()
    p_ch1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_ch1.paragraph_format.space_before = Pt(18)
    p_ch1.paragraph_format.space_after = Pt(24)
    run_ch1 = p_ch1.add_run("1. INTRODUCTION")
    run_ch1.font.size = Pt(14)
    run_ch1.font.bold = True
    run_ch1.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)

    # 1.1 Introduction
    p = doc.add_paragraph()
    p.add_run("1.1 Introduction").font.bold = True
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(6)

    intro_paras = [
        "Urban transportation networks in modern metropolitan centres handle millions of vehicular trips every day. Rapid vehicular expansion strains existing arterial road corridors, resulting in severe traffic congestion, elevated carbon emissions, transit delays, and elevated road accident rates. Effective metropolitan traffic governance demands real-time situational awareness across dozens or hundreds of distributed monitoring locations. Municipal authorities increasingly deploy automated number-plate recognition (ANPR) camera networks across key intersections, toll barriers, arterial entry corridors, and expressway flyovers to track traffic density, identify stolen or wanted vehicles, and support incident investigations.",
        "Traditional ANPR deployments operate primarily as isolated, point-based optical sensors. A standalone camera captures passing vehicles, runs an onboard character recognition algorithm, and logs single-point sightings into a siloed database. While single-point logging confirms that a specific vehicle passed an isolated checkpoint at a given timestamp, it cannot reconstruct the vehicle's spatial journey across the wider urban road network. Isolated cameras fail to reveal route progression, average transit velocities across intermediate road segments, or systemic congestion bottlenecks that develop between sensors. Furthermore, municipal operators face an unmanageable volume of raw plate sightings, making manual cross-camera correlation impractical during urgent law-enforcement investigations or city-scale traffic planning.",
        "In this project, we design, build, and evaluate an integrated city-wide artificial intelligence engine that bridges the gap between single-camera computer vision and macroscopic urban traffic intelligence. The system couples deep-learning visual perception with graph-theoretic trajectory reconstruction, high-throughput spatial storage, automated multi-rule surveillance alerting, and interactive web visualization. By unifying edge perception with central graph analytics, the platform converts discrete, noisy sensor sightings into coherent vehicular journeys, computes empirical traffic flow metrics, and automatically detects high-priority security anomalies in real time."
    ]
    for text in intro_paras:
        p = doc.add_paragraph(text)
        p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # 1.2 Major Challenges
    p = doc.add_paragraph()
    p.add_run("1.2 Major Challenges").font.bold = True
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(6)

    doc.add_paragraph(
        "Developing an end-to-end city-wide ANPR intelligence system presents substantial theoretical and engineering "
        "hurdles across computer vision, distributed data engineering, and spatial graph algorithms."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # 1.2.1
    p = doc.add_paragraph()
    p.add_run("1.2.1 Real-World License Plate Optical Character Recognition").font.bold = True
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)

    doc.add_paragraph(
        "Accurate optical character recognition (OCR) of vehicle registration plates under real-world traffic conditions "
        "remains notoriously difficult. In developing countries such as India, vehicle license plates exhibit high structural variability. "
        "While the central government mandates standardised High-Security Registration Plates (HSRP) conforming to regular alphanumeric regex patterns, "
        "millions of vehicles still carry older or non-standard plates. These display non-standard typefaces, non-uniform character kerning, regional state prefixes, "
        "trade certificate (TC) dealer notations, and custom decorative styling."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.add_paragraph(
        "Furthermore, outdoor roadside cameras capture moving vehicles across diverse illumination regimes, ranging from harsh midday glare to deep nighttime shadows. "
        "Optical sensors encounter severe perspective distortion due to camera mounting angles, motion blur from high-speed travel, lens dirt, rain precipitation, "
        "and partial occlusions by vehicle bodywork or tow bars. As our empirical benchmarks demonstrate, standard off-the-shelf OCR engines achieve less than 38% "
        "exact plate match accuracy on real Indian road crops without domain-specific training. A single misread character invalidates the entire registration string, "
        "breaking cross-camera identification."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # 1.2.2
    p = doc.add_paragraph()
    p.add_run("1.2.2 Tracking and Identity Preservation Across Cameras").font.bold = True
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)

    doc.add_paragraph(
        "Maintaining vehicle identity across non-overlapping, distributed camera views represents a core research challenge in intelligent transportation systems. "
        "Multi-target multi-camera (MTMC) tracking typically relies on visual vehicle re-identification (Re-ID) algorithms that extract deep appearance embeddings from vehicle bodywork. "
        "However, urban vehicle fleets exhibit immense intra-class visual similarity: thousands of commercial hatchbacks and sedans share identical paint codes, chassis silhouettes, "
        "and trim packages. Visual appearance alone cannot reliably distinguish two silver hatchbacks traversing parallel arterial corridors."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.add_paragraph(
        "License plate text provides the single definitive unique identifier for motor vehicles. Nevertheless, because cameras are spaced hundreds of metres or several kilometres apart, "
        "continuous video tracking is impossible between camera blind spots. When OCR engines generate noisy or corrupted plate strings, simple exact-match SQL queries fail to reconnect sightings "
        "belonging to the same journey. Resolving identity across disjoint cameras demands fault-tolerant fuzzy string matching coupled with physical velocity validation across the underlying road network graph."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # 1.2.3
    p = doc.add_paragraph()
    p.add_run("1.2.3 Privacy Considerations and Operator Data Protection").font.bold = True
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)

    doc.add_paragraph(
        "Automated vehicle tracking across urban road networks raises significant civil liberty, personal privacy, and data protection concerns. Continuous vehicular trajectory logging creates a "
        "detailed record of private citizens' daily movements, dwelling locations, places of work, and personal habits. Compromise of an unencrypted central ANPR repository could expose sensitive citizen "
        "travel histories to unauthorised surveillance or commercial exploitation."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.add_paragraph(
        "To maintain ethical compliance and alignment with emerging data protection regulations, an intelligent ANPR platform must incorporate strict privacy-by-design safeguards. Visual vehicle photographs "
        "must restrict operator access to cropped plate regions rather than full cabin views, driver faces must be obscured, and automated journey searches must enforce role-based access control. Furthermore, public data "
        "releases and evaluation benchmarks must anonymise personal registration strings, and system export functions must sanitise data outputs to prevent formula injection attacks against municipal spreadsheet applications."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # 1.2.4
    p = doc.add_paragraph()
    p.add_run("1.2.4 Absence of Labelled City-Scale ANPR Trajectory Data").font.bold = True
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)

    doc.add_paragraph(
        "Supervised machine learning algorithms require large, accurately annotated training datasets. While isolated benchmarks exist for single-image vehicle plate detection (such as the CCPD or Indian Number Plate datasets), "
        "no publicly available, fully labelled dataset provides ground-truth vehicle trajectories linked to optical camera video feeds across a complete metropolitan street network. Real municipal ANPR feeds are strictly restricted "
        "due to statutory privacy laws and national security constraints."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.add_paragraph(
        "Existing open urban trajectory benchmarks, such as the Jinan city dataset published by Yu et al. in 2023 [1], capture macroscopic vehicle trips across thousands of road network nodes. However, these datasets strip license plate strings, "
        "omit raw camera imagery, and obscure calendar dates to protect driver privacy. Conversely, computer vision benchmarks, such as the IEEE AI City Challenge [8], offer rich multi-camera video streams but restrict evaluation to localised "
        "intersection zones without city-scale trajectory ground truth. Developing and verifying an integrated city-wide ANPR engine therefore requires constructing a rigorous, synthetic road network simulator that models realistic vehicle "
        "mobility, camera placements, and sensor noise while validating visual perception components against real-world video footage."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # 1.3 Proposed Solutions and Key Contributions
    p = doc.add_paragraph()
    p.add_run("1.3 Proposed Solutions and Key Contributions").font.bold = True
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(6)

    contributions = [
        ("Dual-Pathway Perception and Simulation Architecture: ", "We implement a modular architecture where real-world video feeds and synthetic city-scale mobility streams converge into a unified spatial database (data/city_anpr.db). This allows municipal operators to run identical trajectory reconstruction, flow analytics, and surveillance alerting engines over both physical camera streams and simulated urban fleets."),
        ("Deep-Learning Perception Pipeline with Quality Assurance Review: ", "We train and deploy a custom YOLOv8s license plate detector alongside an ONNX-optimized Compact Convolutional Transformer (CCT-s-v2) optical character recogniser. We implement a multi-frame temporal voting module that aggregates ByteTrack tracking sequences using character-position weighted consensus. To prevent automated misclassification from corrupting municipal records, we introduce an automated REVIEW flag that isolates any plate read where OCR confidence or vote margin falls below 0.80."),
        ("High-Throughput Fuzzy Trajectory Reconstruction Engine: ", "We develop a graph-theoretic journey router that queries OpenStreetMap road networks extracted via OSMnx. To overcome optical character corruptions, we build a canonical 3-partition fuzzy string index that searches plates within a weighted Levenshtein distance of 1.0 (with 0.3 penalty for confusable character substitutions like O/0 and B/8). The engine filters temporal duplicates, splits journeys exceeding 30 minutes of inactivity, and validates implied hop velocity against shortest-path road geometry."),
        ("Real-Time Multi-Rule Surveillance Alert Engine: ", "We design an event-driven surveillance engine that evaluates incoming sightings against multiple concurrent security rules, including exact and fuzzy blacklist matching, speed-feasibility cloned-plate anomaly detection (>120 km/h), prohibited vehicle curfew zones, and overspeeding. A 10-minute sliding window suppresses redundant alarms, delivering zero false alarms on verified fleet movements."),
        ("Calibrated Vehicle Movement Counting Prototype: ", "We construct a standalone vehicle counting module benchmarked against the IEEE AI City Challenge 2021 Track 1 dataset. We demonstrate that visual movement estimation yields severe spatial mismatch, whereas empirical trajectory calibration on the initial segment of a video improves directional counting F1-score from 17.9% to 65.1% on held-out test frames."),
        ("Unified Web Application and Streaming Interface: ", "We deploy all backend analytical services behind an asynchronous FastAPI server. The system exposes RESTful endpoints, streaming WebSockets, and an interactive HTML5/Leaflet dashboard supporting live map exploration, trajectory polylines, congestion heatmaps, and direct single-image inference.")
    ]
    for label, desc in contributions:
        p = doc.add_paragraph()
        p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_after = Pt(6)
        r_lbl = p.add_run(label)
        r_lbl.font.bold = True
        p.add_run(desc)

    # 1.4 Background and Motivation
    p = doc.add_paragraph()
    p.add_run("1.4 Background and Motivation").font.bold = True
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(6)

    doc.add_paragraph(
        "The motivation for this project stems from the operational realities of municipal Traffic Management Centres (TMC) in rapidly expanding metropolitan areas. "
        "In cities such as Bangalore, traffic police command centres manage feeds from hundreds of roadside CCTV cameras. Operators face two primary operational bottlenecks: "
        "fragmented surveillance workflows and lagging macroscopic traffic intelligence."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.add_paragraph(
        "In typical surveillance scenarios—such as tracking a stolen vehicle, identifying a hit-and-run suspect, or tracing an abducted child's vehicle—investigators must manually "
        "inspect recorded footage camera by camera. Operators manually note vehicle timestamps, estimate possible travel corridors, and telephone neighbouring control rooms to check downstream camera logs. "
        "This fragmented process introduces critical delays during golden-hour emergency responses. If a roadside camera misreads an '8' as a 'B' or an 'O' as a '0', standard database lookup queries return zero records, "
        "and the vehicle's trail goes cold. An automated trajectory engine capable of fuzzy character resolution, topological graph routing, and instant impossible-speed clone detection provides immediate operational "
        "value to law-enforcement personnel."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.add_paragraph(
        "Concurrently, urban planners require macroscopic traffic flow metrics to design signal timing schedules, implement congestion pricing, and identify bottleneck corridors. Traditional loop detectors and pneumatic "
        "road tubes are expensive to install, vulnerable to asphalt resurfacing damage, and incapable of identifying vehicular origin-destination (OD) patterns. Because ANPR cameras capture unique vehicular identifiers across "
        "space and time, an aggregated ANPR stream naturally yields comprehensive OD matrices, link travel times, and intersection level-of-service (LOS) metrics without extra road hardware. Connecting computer vision directly "
        "to urban graph analytics creates a cost-effective, dual-use platform serving both law enforcement and municipal urban planning."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # 1.5 Overview of the Proposed System
    p = doc.add_paragraph()
    p.add_run("1.5 Overview of the Proposed System").font.bold = True
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(6)

    doc.add_paragraph(
        "The proposed system comprises nine modular subsystems organised into visual perception, spatial persistence, graph analytics, and web presentation. "
        "Figure 1.1 illustrates the comprehensive block diagram of the system architecture, detailing the convergence of the real perception pathway and the simulated "
        "city pathway into the shared spatial database."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # Embed Figure 1.1
    fig1_path = assets_dir / "fig_system_block.png"
    if fig1_path.exists():
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.space_before = Pt(6)
        p_img.paragraph_format.space_after = Pt(4)
        run_img = p_img.add_run()
        run_img.add_picture(str(fig1_path), width=Inches(6.0))

        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_before = Pt(2)
        p_cap.paragraph_format.space_after = Pt(12)
        r_cap = p_cap.add_run("Figure 1.1: City-Wide ANPR System Architecture (Block Diagram)")
        r_cap.font.bold = True
        r_cap.font.size = Pt(11)

    doc.add_paragraph(
        "As illustrated in Figure 1.1, the platform executes two concurrent pipelines: the Real Perception Pathway and the Simulated City Pathway. "
        "The real perception path ingests video footage (such as the 20 test sequences in video_images) or isolated photos. Bounding boxes detected by YOLOv8s "
        "(at conf ≥ 0.25) receive 5% boundary expansion to protect edge characters before passing to ByteTrack for multi-object identity persistence. "
        "The fine-tuned CCT-s-v2 ONNX transformer transcribes character tokens, which are synthesized across frames using positional weighted voting. "
        "Readings exhibiting OCR confidence or vote margin below 0.80 receive the REVIEW flag before database entry (source='video')."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.add_paragraph(
        "In the simulated pathway, an OpenStreetMap road network of Bangalore (5 km radius) is parsed via OSMnx into a directed MultiDiGraph G. "
        "Forty cameras are positioned at major arterial junctions (spacing ≥ 300 m). A synthetic fleet of 5,000 vehicles generates 31,244 trips under diurnal morning and evening congestion. "
        "Simulated ANPR sensor noise (5% miss rate, 8% confusable character error) and security scenarios (10 blacklist plates, 5 cloned plate teleportation pairs) are applied. "
        "These records populate the database with source='sim'."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.add_paragraph(
        "Figure 1.2 details the corresponding end-to-end data flow diagram (DFD), illustrating how incoming sensor streams transition through validation, persistence, and analytical modeling."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # Embed Figure 1.2
    fig2_path = assets_dir / "fig_data_flow.png"
    if fig2_path.exists():
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.space_before = Pt(6)
        p_img.paragraph_format.space_after = Pt(4)
        run_img = p_img.add_run()
        run_img.add_picture(str(fig2_path), width=Inches(6.0))

        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_before = Pt(2)
        p_cap.paragraph_format.space_after = Pt(12)
        r_cap = p_cap.add_run("Figure 1.2: End-to-End System Data Flow Diagram (DFD)")
        r_cap.font.bold = True
        r_cap.font.size = Pt(11)

    doc.add_paragraph(
        "Both streams converge in data/city_anpr.db (SQLite). The Trajectory Reconstruction Engine executes shortest-path Dijkstra traversal over precomputed camera paths, "
        "using a canonical 3-partition fuzzy plate search to link noisy sightings. The Traffic Analytics Engine computes rolling speed distributions, congestion severity scores, "
        "segment densities, and a 64-zone OD matrix. The Alert Engine scans sightings against security watchlists and spatial rules, pushing live JSON notifications over a WebSocket stream (/ws/live). "
        "An interactive dashboard presents map overlays, trajectory polylines, congestion heatmaps, and single-image inference."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # 1.6 Objective of the work (Exact sub-heading required)
    p = doc.add_paragraph()
    p.add_run("1.6 Objective of the work").font.bold = True
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(6)

    objectives = [
        "1. Train and optimize a YOLOv8s license plate detector on real Indian road scenes, achieving greater than 95.0% precision, recall, and mAP@50 on held-out test splits.",
        "2. Fine-tune a lightweight Compact Convolutional Transformer (CCT-s-v2) on real Indian plate crops, targeting greater than 95.0% character-level accuracy and evaluating full-plate exact match performance under single-frame and multi-frame video voting regimes.",
        "3. Implement a confidence-weighted voting module using ByteTrack multi-object tracking to improve video plate recognition accuracy over single-frame baseline reads, coupled with an empirical quality assurance threshold (REVIEW_CONFIDENCE_THRESHOLD = 0.80) to isolate low-confidence predictions.",
        "4. Construct a realistic urban traffic simulator on Bangalore's road network using OSMnx, modeling 40 cameras, 5,000 vehicles, realistic diurnal traffic flow, optical sensor noise, and injected security scenarios (stolen vehicles, cloned plates, curfew violations).",
        "5. Develop a spatial trajectory reconstruction engine that tolerates OCR character corruptions via weighted Levenshtein matching, validates hop speed feasibility (>120 km/h) to isolate cloned plates, and delivers sub-50 ms query response times with F1-score exceeding 90.0%.",
        "6. Implement a multi-rule surveillance engine capable of processing over 1,000 sightings per second, achieving 100% precision on blacklist alerts with zero false alarms after sliding-window de-duplication.",
        "7. Prototype an intersection vehicle counting algorithm on the IEEE AI City Challenge 2021 Track 1 benchmark, establishing an empirical calibration methodology to assign vehicle trajectories to 12 distinct directional movement paths.",
        "8. Expose all analytical models through a unified FastAPI REST and WebSocket gateway, providing municipal operators with a responsive HTML5/Leaflet web dashboard."
    ]
    for obj in objectives:
        p = doc.add_paragraph(obj)
        p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_after = Pt(4)

    # 1.7 Organization of the report (Exact sub-heading required)
    p = doc.add_paragraph()
    p.add_run("1.7 Organization of the report").font.bold = True
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(6)

    org_text = [
        "The remainder of this report is organized as follows:",
        "Chapter 2 (Related Work and Theoretical Study) surveys existing literature across license plate detection and OCR, multi-object and cross-camera vehicle tracking, macroscopic trajectory datasets, urban traffic analytics, and vehicle counting benchmarks. It formulates the formal mathematical equations governing detection, recognition, confidence intervals, and graph routing, concluding with a research gap analysis and comparative matrix (Table 2.1).",
        "Chapter 3 (Experimental Study) details the complete engineering design, system specifications, hardware/software environments, and dataset curation procedures. It describes the perception pipeline, simulation mechanics, SQLite database schema, trajectory router, alert engine, REST/WebSocket API endpoints, and AI City counting pipeline. It concludes with evaluation protocols and automated testing strategies.",
        "Chapter 4 (Results and Discussions) presents comprehensive empirical findings across all modules using concrete, number-backed results labeled REAL, SIMULATED, or SYNTHETIC. It examines detector metrics, OCR training progression, end-to-end photo recognition, multi-frame video voting, trajectory reconstruction accuracy, surveillance alert performance, and AI City movement counting (v1 vs. v2). It provides an honest appraisal of the 90% target, error analysis of misread video sequences, requirements traceability, and system limitations.",
        "Chapter 5 (Conclusions and Future Scope) synthesises project achievements, outlines key engineering constraints, and highlights directions for future research.",
        "Appendices 1 through 4 provide installation instructions, API endpoint specifications, core code excerpts, and test suite execution logs, followed by IEEE-style references and publication declarations."
    ]
    for t in org_text:
        doc.add_paragraph(t).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.add_page_break()

    # -------------------------------------------------------------
    # CHAPTER 2: RELATED WORK AND THEORETICAL STUDY
    # -------------------------------------------------------------
    p_ch2 = doc.add_paragraph()
    p_ch2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_ch2.paragraph_format.space_before = Pt(18)
    p_ch2.paragraph_format.space_after = Pt(24)
    run_ch2 = p_ch2.add_run("2. RELATED WORK AND THEORETICAL STUDY")
    run_ch2.font.size = Pt(14)
    run_ch2.font.bold = True
    run_ch2.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)

    # 2.1 License Plate Detection and OCR Techniques
    p = doc.add_paragraph()
    p.add_run("2.1 License Plate Detection and OCR Techniques").font.bold = True
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(6)

    doc.add_paragraph(
        "Automated number-plate recognition (ANPR) systems traditionally follow a two-stage computer vision pipeline: first localising the license plate bounding box within a camera frame, "
        "and second transcribing the alphanumeric character sequence from the cropped region. Early detection systems relied on handcrafted visual features, including vertical edge density, "
        "morphological gradients, colour saliency filters, and Haar-like wavelets classified via AdaBoost or Support Vector Machines. While computationally lightweight, these classical techniques "
        "degrade severely under non-uniform illumination, perspective tilt, complex vehicle bodywork, and shadowed backgrounds."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.add_paragraph(
        "The introduction of convolutional neural networks (CNN) fundamentally transformed object detection. The You Only Look Once (YOLO) framework introduced by Redmon et al. [5] "
        "reframed detection as a single-stage spatial regression problem, predicting bounding box coordinates and class probabilities directly from full images in a single forward pass. "
        "Subsequent iterations optimized feature pyramid networks, path aggregation, and anchor-free regression heads. In a recent 2025 study published in Scientific Reports [2], "
        "researchers proposed an improved YOLOv5s architecture coupled with an LPRNet recognition backbone for multi-scene license plate detection and transcription, reporting superior localization "
        "accuracy on Chinese and international benchmarks. Concurrently, Ultralytics YOLOv8 [9] introduced an anchor-free split-head architecture with decoupled classification and regression branches, "
        "providing state-of-the-art detection accuracy and sub-millisecond edge latency on embedded GPUs and modern multi-core CPUs."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.add_paragraph(
        "For optical character recognition, early deep architectures employed Connectionist Temporal Classification (CTC) over recurrent neural networks (RNN) or LPRNet [6]. LPRNet eliminates recurrent layers "
        "in favour of spatial inception blocks, outputting character probability distributions directly to CTC loss without requiring individual character segmentation. More recently, vision transformers have "
        "demonstrated superior character sequence modeling. The Compact Convolutional Transformer (CCT) architecture implemented in fast-plate-ocr [10] combines convolutional tokenization with multi-head self-attention mechanisms. "
        "By avoiding heavy recurrent gates, CCT models achieve sub-10 ms CPU inference per crop while maintaining robustness against character rotation, dirt smudges, and non-standard typography common in developing countries."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # 2.2 Multi-Object and Multi-Camera Vehicle Tracking
    p = doc.add_paragraph()
    p.add_run("2.2 Multi-Object and Multi-Camera Vehicle Tracking").font.bold = True
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(6)

    doc.add_paragraph(
        "Tracking detected vehicles across consecutive frames is essential for aggregating multi-frame visual information and suppressing transient misclassifications. Single-camera Multi-Object Tracking (MOT) algorithms "
        "typically adopt the tracking-by-detection paradigm. Classical approaches, such as SORT and DeepSORT, utilise Kalman filtering to propagate spatial bounding box state vectors across time, associating current detections "
        "with existing tracklets using the Hungarian algorithm based on spatial Intersection over Union (IoU) and deep visual appearance embeddings."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.add_paragraph(
        "However, standard MOT algorithms frequently drop valid tracks during brief vehicle occlusions or when detection confidence scores dip due to motion blur. To resolve this, Zhang et al. [4] introduced ByteTrack, "
        "which associates almost every detection box regardless of confidence. Instead of discarding low-scoring detections, ByteTrack partitions detections into high-confidence and low-confidence pools. High-confidence detections "
        "are matched first; unmatched tracks are then associated with low-confidence boxes, preserving track continuity through partial occlusions and camera noise without requiring heavy deep Re-ID feature extraction."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.add_paragraph(
        "Across multi-camera networks (Multi-Target Multi-Camera, or MTMC tracking), spatial continuity breaks down because cameras are non-overlapping. Tran et al. [3] investigated cross-camera tracking by fusing visual Re-ID "
        "embeddings with spatial-temporal transition matrices across highway camera networks. However, in dense urban street grids with identical vehicle models, deep appearance vectors exhibit significant ambiguity. "
        "In our work, we prioritize definitive alphanumeric license plate identity over visual Re-ID, using physical road network routing and travel-time bounds to validate vehicle transitions across camera networks."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # 2.3 City-Scale Trajectory Reconstruction Datasets
    p = doc.add_paragraph()
    p.add_run("2.3 City-Scale Trajectory Reconstruction Datasets").font.bold = True
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(6)

    doc.add_paragraph(
        "Research in urban traffic flow modeling and intelligent transportation systems relies heavily on large-scale trajectory benchmarks. In 2023, Yu et al. [1] published a landmark benchmark in Scientific Data "
        "providing city-scale vehicle trajectories collected from Jinan, China. The Jinan dataset documents over 1.18 million vehicle trips and 963,125 unique vehicles traversing a topological road network comprising 8,908 street nodes, "
        "of which 1,651 nodes feature surveillance camera sensors."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.add_paragraph(
        "While the Jinan benchmark provides unprecedented macroscopic scale for urban mobility modeling, it suffers from two major operational constraints for ANPR engineering: "
        "(1) Omission of alphanumeric identifiers: to comply with national privacy regulations, all license plate strings were stripped and replaced with arbitrary synthetic integer identifiers; and "
        "(2) Absence of raw camera imagery: the dataset provides spatial-temporal event tuples but includes no video or image feeds, preventing researchers from studying the coupling between optical vision errors and graph trajectory reconstruction."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.add_paragraph(
        "To model road network topology programmatically, Boeing [7] developed OSMnx, a Python framework that downloads, constructs, and visualises complex street networks directly from OpenStreetMap (OSM). "
        "OSMnx models intersections as graph nodes and road segments as directed edges carrying geographic length, lane counts, and speed limit attributes. In this project, we exploit OSMnx to construct a 5 km radius road network graph of Bangalore, "
        "enabling realistic vehicular mobility modeling and Dijkstra-based shortest-path travel time precomputation."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # 2.4 Urban Traffic Flow Analytics and Anomaly Alert Systems
    p = doc.add_paragraph()
    p.add_run("2.4 Urban Traffic Flow Analytics and Anomaly Alert Systems").font.bold = True
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(6)

    doc.add_paragraph(
        "Urban traffic management centres utilize camera observations to compute macroscopic flow parameters defined by the Highway Capacity Manual. Key indicators include segment flow volume (q, vehicles per hour), "
        "mean transit velocity (v, km/h), vehicular density (k, vehicles per km), and Level of Service (LOS) ratings ranging from free-flow (LOS A) to severe breakdown (LOS F). Traditional municipal systems compute these metrics from "
        "inductive loop sensors embedded in roadway asphalt. However, physical loops cannot track vehicle identities across space, making them incapable of measuring true Origin-Destination (OD) trip distributions."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.add_paragraph(
        "Surveillance alert systems in intelligent transportation platforms enforce traffic compliance and assist law enforcement. Automated alert rules commonly monitor: "
        "(1) Watchlists/Blacklists: real-time flagging of stolen vehicles, wanted suspects, or unregistered vehicles against criminal databases; "
        "(2) Cloned plate anomalies: detecting two physical sightings of the same license plate at distant geographic locations within an impossibly short time interval, indicating that one or both vehicles are operating with forged plates; "
        "(3) Access restrictions: enforcing commercial truck curfews in dense residential corridors during night-time hours; and "
        "(4) Speed enforcement: identifying vehicles exceeding posted corridor speed limits."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.add_paragraph(
        "Conventional rule engines frequently suffer from high false alarm rates. In high-throughput streaming environments, transient OCR misreads produce spurious plate collisions that mimic cloned vehicles or trigger false blacklist hits. "
        "Robust surveillance systems must incorporate sliding-window incident de-duplication, fuzzy string thresholds, and shortest-path road distance verification to prevent operator notification fatigue."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # 2.5 Vehicle Movement Counting Benchmarks
    p = doc.add_paragraph()
    p.add_run("2.5 Vehicle Movement Counting Benchmarks").font.bold = True
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(6)

    doc.add_paragraph(
        "Automated vehicle counting at urban road intersections is critical for optimizing traffic signal cycles and evaluating junction capacity. The IEEE AI City Challenge, organized annually by Naphade et al. [8], "
        "established Track 1 as the international standard benchmark for multi-class multi-movement vehicle counting from fixed roadside video streams."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.add_paragraph(
        "In the AI City Challenge Track 1 benchmark, an intersection is defined by a Region of Interest (ROI) polygon and a set of predefined directional movement trajectories (such as through-movements, left turns, and right turns). "
        "Participating systems must count the cumulative number of vehicles completing each specific movement, categorized by vehicle class (cars, trucks, and buses). Vehicles that park, loiter, or enter and exit via the same roadway branch "
        "without completing a valid turn must be filtered out."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.add_paragraph(
        "Most existing literature approaches vehicle counting by manually defining virtual tripwire lines across lane boundaries. However, roadside cameras experience perspective foreshortening, lens distortion, and optical occlusions, "
        "causing rigid tripwires to miscount vehicles that deviate slightly from lane centres. In this work, we implement a trajectory assignment algorithm that evaluates the complete vehicle tracklet against calibrated directional movement vectors, "
        "demonstrating the vital necessity of empirical centroid calibration."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # 2.6 Theoretical Foundations and Metric Formulations
    p = doc.add_paragraph()
    p.add_run("2.6 Theoretical Foundations and Metric Formulations").font.bold = True
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(6)

    doc.add_paragraph(
        "To ensure rigorous quantitative evaluation, we establish formal mathematical definitions for all computer vision, statistical confidence, and graph routing metrics utilized throughout this report."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # 2.6.1
    p = doc.add_paragraph()
    p.add_run("2.6.1 Precision, Recall, and F1-Score").font.bold = True
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)

    doc.add_paragraph(
        "Binary classification performance across object detection, trajectory matching, and surveillance alerting is evaluated using True Positives (TP), False Positives (FP), and False Negatives (FN):"
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # Equation 2.1
    p_eq = doc.add_paragraph()
    p_eq.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_eq.paragraph_format.line_spacing = 1.2
    p_eq.paragraph_format.space_after = Pt(4)
    p_eq.add_run("Precision = TP / (TP + FP)                                                            (2.1)").font.italic = True

    # Equation 2.2
    p_eq = doc.add_paragraph()
    p_eq.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_eq.paragraph_format.line_spacing = 1.2
    p_eq.paragraph_format.space_after = Pt(4)
    p_eq.add_run("Recall = TP / (TP + FN)                                                                  (2.2)").font.italic = True

    # Equation 2.3
    p_eq = doc.add_paragraph()
    p_eq.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_eq.paragraph_format.line_spacing = 1.2
    p_eq.paragraph_format.space_after = Pt(8)
    p_eq.add_run("F1 = 2 * (Precision * Recall) / (Precision + Recall) = 2*TP / (2*TP + FP + FN)        (2.3)").font.italic = True

    # 2.6.2
    p = doc.add_paragraph()
    p.add_run("2.6.2 Mean Average Precision (mAP)").font.bold = True
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)

    doc.add_paragraph(
        "Object detection localisation accuracy is evaluated using Mean Average Precision across Intersection over Union (IoU) thresholds. "
        "Given a predicted bounding box B_p and a ground-truth box B_gt, spatial overlap is computed via the Jaccard index:"
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # Equation 2.4
    p_eq = doc.add_paragraph()
    p_eq.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_eq.paragraph_format.line_spacing = 1.2
    p_eq.paragraph_format.space_after = Pt(4)
    p_eq.add_run("IoU(B_p, B_gt) = Area(B_p ∩ B_gt) / Area(B_p ∪ B_gt)                                  (2.4)").font.italic = True

    doc.add_paragraph(
        "A detection is counted as a True Positive if IoU(B_p, B_gt) ≥ τ, where τ = 0.50 for standard mAP@50. "
        "The Average Precision (AP) corresponds to the area under the interpolated precision-recall curve p(r):"
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # Equation 2.5
    p_eq = doc.add_paragraph()
    p_eq.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_eq.paragraph_format.line_spacing = 1.2
    p_eq.paragraph_format.space_after = Pt(8)
    p_eq.add_run("AP = ∫[0 to 1] p(r) dr                                                                  (2.5)").font.italic = True

    doc.add_paragraph(
        "The metric mAP@50-95 averages AP scores across 10 evenly spaced IoU thresholds from τ = 0.50 to τ = 0.95 with step size Δτ = 0.05."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # 2.6.3
    p = doc.add_paragraph()
    p.add_run("2.6.3 Character-Level and Full-Plate Exact Match Accuracies").font.bold = True
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)

    doc.add_paragraph(
        "Optical character recognition performance is evaluated at both the macroscopic string level and the microscopic character level. "
        "Full-plate exact match accuracy measures the percentage of plates where the predicted string S_hat identically matches the ground truth string S:"
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # Equation 2.6
    p_eq = doc.add_paragraph()
    p_eq.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_eq.paragraph_format.line_spacing = 1.2
    p_eq.paragraph_format.space_after = Pt(4)
    p_eq.add_run("Acc_plate = (1 / N) * Σ[i=1..N] I(S_hat_i == S_i)                                      (2.6)").font.italic = True

    doc.add_paragraph(
        "where I(·) is the indicator function returning 1 if strings are identical and 0 otherwise. "
        "Character-level accuracy measures transcription fidelity using the Levenshtein edit distance L(S_hat, S), "
        "defined as the minimum number of single-character insertions, deletions, or substitutions required to transform S_hat into S:"
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # Equation 2.7
    p_eq = doc.add_paragraph()
    p_eq.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_eq.paragraph_format.line_spacing = 1.2
    p_eq.paragraph_format.space_after = Pt(8)
    p_eq.add_run("Acc_char = (1 / N) * Σ[i=1..N] max(0, 1 - L(S_hat_i, S_i) / max(|S_i|, |S_hat_i|))       (2.7)").font.italic = True

    # 2.6.4
    p = doc.add_paragraph()
    p.add_run("2.6.4 Wilson Score Confidence Interval Formulation").font.bold = True
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)

    doc.add_paragraph(
        "When evaluating accuracy over small empirical test sets (such as N = 20 video sequences or N = 57 counting events), "
        "sample proportions p_hat = k/N carry significant statistical uncertainty. Standard normal approximation intervals fail near boundary proportions. "
        "We therefore compute asymmetric two-sided 95% confidence intervals using the Wilson score interval:"
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # Equation 2.8
    p_eq = doc.add_paragraph()
    p_eq.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_eq.paragraph_format.line_spacing = 1.2
    p_eq.paragraph_format.space_after = Pt(8)
    p_eq.add_run("CI_95% = [p_hat + z^2/(2N) ± z * sqrt(p_hat*(1 - p_hat)/N + z^2/(4N^2))] / [1 + z^2/N]    (2.8)").font.italic = True

    doc.add_paragraph(
        "where z = 1.95996 corresponds to the standard normal quantile for α = 0.05. For 18 successes out of 20 trials (p_hat = 0.90), "
        "Equation (2.8) yields an asymmetric interval of [69.9%, 97.2%], rigorously capturing the ±13 percentage point uncertainty inherent in small-sample evaluations."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # 2.6.5
    p = doc.add_paragraph()
    p.add_run("2.6.5 Temporal Event Matching Metric").font.bold = True
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)

    doc.add_paragraph(
        "In vehicle movement counting evaluation, predicted counting events e_p = (t_p, m_p, c_p) are matched against ground-truth events e_gt = (t_gt, m_gt, c_gt), "
        "where t denotes video frame index, m denotes movement identifier, and c denotes vehicle class. A predicted event is an eligible match for a ground-truth event "
        "if they share identical movement and class assignments, and their temporal frame discrepancy falls within a maximum tolerance window Δt_max = 20 frames:"
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # Equation 2.9
    p_eq = doc.add_paragraph()
    p_eq.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_eq.paragraph_format.line_spacing = 1.2
    p_eq.paragraph_format.space_after = Pt(8)
    p_eq.add_run("Match(e_p, e_gt) = I(m_p == m_gt) * I(c_p == c_gt) * I(|t_p - t_gt| ≤ Δt_max)          (2.9)").font.italic = True

    doc.add_paragraph(
        "Eligible pairs are greedily matched in order of minimum absolute frame difference |t_p - t_gt|, with each ground truth and predicted event matched at most once."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # 2.7 Research Gap and Comparative Analysis
    p = doc.add_paragraph()
    p.add_run("2.7 Research Gap and Comparative Analysis").font.bold = True
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(6)

    doc.add_paragraph(
        "Existing literature in intelligent transportation systems exhibits a persistent bifurcation: computer vision researchers focus on visual detection and tracking over isolated intersection videos without modeling city-wide graph dynamics, "
        "while transportation network researchers analyze macroscopic trajectory graphs while treating vehicle identification as a synthetic, error-free abstraction."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.add_paragraph(
        "Table 2.1 provides a structured comparative analysis contrasting our proposed system against the three foundational base papers identified in the literature review: "
        "Yu et al. (2023) [1], Scientific Reports (2025) [2], and Tran et al. (2022) [3]."
    ).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # Table 2.1 Caption (ABOVE table, 12pt bold)
    p_tc = doc.add_paragraph()
    p_tc.paragraph_format.space_before = Pt(12)
    p_tc.paragraph_format.space_after = Pt(4)
    r_tc = p_tc.add_run("Table 2.1: Comparative Analysis of Base Papers with the Proposed System")
    r_tc.font.bold = True
    r_tc.font.size = Pt(12)

    # Table 2.1 Data
    table_headers = ["Evaluation Dimension", "Yu et al. (2023) [1]", "Scientific Reports (2025) [2]", "Tran et al. (2022) [3]", "Proposed System (This Work)"]
    table_rows = [
        ["Primary Domain", "Macroscopic Trajectory Mining", "Optical Plate Detection & OCR", "Multi-Camera Vehicle Tracking", "Integrated End-to-End ANPR Engine"],
        ["Perception Input", "None (Tabular Sensor Tuples)", "Static Multi-Scene Photographs", "Multi-Camera Video Streams", "Full Frames, Videos & Synthetic City"],
        ["Detection Backbone", "Not Applicable", "Improved YOLOv5s", "Mask R-CNN / ResNet", "Ultralytics YOLOv8s (Anchor-Free)"],
        ["OCR Architecture", "Not Applicable", "LPRNet (CNN + CTC Loss)", "None (Visual Appearance Only)", "Compact Conv Transformer (CCT-s-v2)"],
        ["Tracking Paradigm", "Spatial Node Traversal", "None (Single-Image Only)", "Deep Appearance Re-ID (MTMC)", "ByteTrack + Positional Consensus Voting"],
        ["Noise Tolerance", "Assumes Clean Sensor IDs", "Evaluated on Static Images", "Visual Lighting / Skew Robust", "Weighted Levenshtein (Fuzzy Distance 1.0)"],
        ["Graph Routing", "Empirical Node Sequences", "None", "Transition Probability Matrix", "OpenStreetMap Dijkstra Shortest Paths"],
        ["Surveillance Alerting", "None", "None", "Stolen Vehicle Flagging", "Multi-Rule Engine (Blacklist, Clones, Curfew)"],
        ["Vehicle Counting", "Macroscopic Link Volumes", "None", "Highway Tripwire Counts", "Calibrated Directional Movement Assignment"],
        ["User Interface", "Offline Data Archive", "Standalone Evaluation Scripts", "Offline Research Benchmark", "Interactive Web Dashboard (FastAPI/Leaflet)"],
        ["Data Realism", "REAL (Jinan, 1.18M Trips)", "REAL (Static Plate Datasets)", "REAL (Highway CCTV Footage)", "REAL (Vision/Counting) + SIMULATED (City)"],
    ]

    t21 = doc.add_table(rows=len(table_rows) + 1, cols=5)
    t21.alignment = WD_TABLE_ALIGNMENT.CENTER
    t21.autofit = False
    set_table_borders(t21, color="B0C4DE", sz="4")

    # Column widths
    col_widths = [Inches(1.5), Inches(1.2), Inches(1.2), Inches(1.2), Inches(1.4)]
    for row in t21.rows:
        for idx, width in enumerate(col_widths):
            row.cells[idx].width = width

    # Format Header Row
    hdr_cells = t21.rows[0].cells
    for c_idx, h_text in enumerate(table_headers):
        hdr_cells[c_idx].text = h_text
        set_cell_shading(hdr_cells[c_idx], "1B365D")
        set_cell_margins(hdr_cells[c_idx], top=80, bottom=80, left=80, right=80)
        p = hdr_cells[c_idx].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.line_spacing = 1.1
        p.paragraph_format.space_after = Pt(0)
        r = p.runs[0]
        r.font.bold = True
        r.font.size = Pt(9.5)
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    # Format Data Rows
    for r_idx, r_data in enumerate(table_rows):
        row_cells = t21.rows[r_idx + 1].cells
        bg_col = "F8F9FA" if r_idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate(r_data):
            row_cells[c_idx].text = val
            set_cell_shading(row_cells[c_idx], bg_col)
            set_cell_margins(row_cells[c_idx], top=60, bottom=60, left=70, right=70)
            p = row_cells[c_idx].paragraphs[0]
            p.paragraph_format.line_spacing = 1.15
            p.paragraph_format.space_after = Pt(0)
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if c_idx == 0 else WD_ALIGN_PARAGRAPH.CENTER
            r = p.runs[0]
            r.font.size = Pt(9.0)
            if c_idx == 0:
                r.font.bold = True
            if c_idx == 4:
                r.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)

    p_after = doc.add_paragraph()
    p_after.paragraph_format.space_before = Pt(8)
    p_after.add_run(
        "As established in Table 2.1, our work bridges these disparate domains into a unified, operational intelligence engine. "
        "By integrating real-world visual perception, noise-tolerant fuzzy graph routing, empirical movement calibration, and real-time streaming surveillance into a single architecture, "
        "this project provides a reproducible blueprint for metropolitan intelligent transportation governance."
    ).font.size = Pt(12)
    p_after.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # Save draft document
    doc.save(str(output_docx))
    print(f"Successfully generated draft Word report: {output_docx}")

if __name__ == "__main__":
    main()

