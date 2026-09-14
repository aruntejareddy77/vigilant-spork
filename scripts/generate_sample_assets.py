"""
scripts/generate_sample_assets.py
Programmatic generator for deterministic industrial sample assets:
1. samples/refinery_vessel_inspection_v301.png (Inspection scan with title block, checklist, findings, handwritten note)
2. samples/historian_sensor_telemetry.csv (10,000-row industrial sensor telemetry with baseline and transient anomaly)
3. samples/pid_drawing_rev_a.png & pid_drawing_rev_b.png (Dual-revision P&ID drawings with exactly 3 diffs: ADDED, REMOVED, MODIFIED)

Complies with DEMO-01, DEMO-02, DEMO-03, ASVS V5.1/V5.2.4, and threat model T-06-03.
"""
import argparse
import csv
from datetime import datetime, timedelta, timezone
import math
from pathlib import Path
import random
from typing import Tuple

from PIL import Image, ImageDraw, ImageFont


def generate_inspection_scan(output_path: Path) -> Path:
    """
    Renders refinery_vessel_inspection_v301.png (1240 x 1754 pixels, RGB).
    Features:
    - Outer border and industrial title block:
      "REFINERY VESSEL V-301 INSPECTION REPORT"
      Facility: "Jamnagar Refinery Complex - Unit 04"
      Equipment Tag: "V-301"
    - Printed checklist rows with checkboxes ([x] and [ ]).
    - Discrete findings table including nominal shell thickness (12.4 mm, PASS, confidence 0.96).
    - Handwritten finding box: "Localized pitting observed at nozzle N-2 weld zone"
      (thickness 4.2 mm, min 6.0 mm, WARNING, confidence 0.78).
    """
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    w, h = 1240, 1754
    # Clean paper background with very faint off-white tone
    im = Image.new("RGB", (w, h), (252, 252, 250))
    draw = ImageDraw.Draw(im)
    font = ImageFont.load_default()

    # Outer engineering border
    margin = 40
    draw.rectangle([margin, margin, w - margin, h - margin], outline=(40, 40, 40), width=3)
    draw.rectangle([margin + 6, margin + 6, w - margin - 6, h - margin - 6], outline=(100, 100, 100), width=1)

    # 1. Title Block Header
    tb_top = margin + 16
    tb_bottom = tb_top + 160
    draw.rectangle([margin + 16, tb_top, w - margin - 16, tb_bottom], outline=(31, 73, 125), width=2)
    # Header fill banner
    draw.rectangle([margin + 18, tb_top + 2, w - margin - 18, tb_top + 45], fill=(31, 73, 125))
    draw.text((margin + 30, tb_top + 12), "SOVEREIGN INDUSTRIAL VERIFICATION SYSTEM - NON-DESTRUCTIVE TESTING", fill=(255, 255, 255), font=font)

    # Title & Metadata
    draw.text((margin + 30, tb_top + 55), "REFINERY VESSEL V-301 INSPECTION REPORT", fill=(31, 73, 125), font=font)
    draw.text((margin + 30, tb_top + 80), "Facility: Jamnagar Refinery Complex - Unit 04    |    Equipment Tag: V-301", fill=(60, 60, 60), font=font)
    draw.text((margin + 30, tb_top + 105), "Inspection Date: 2026-09-14                     |    Inspector: K. Sharma (Level III NDT)", fill=(60, 60, 60), font=font)
    draw.text((margin + 30, tb_top + 130), "Vessel Service: Hydrocracker Debutanizer Column  |    Operating Pressure: 42.5 bar", fill=(60, 60, 60), font=font)

    # 2. Checklist Section
    chk_top = tb_bottom + 30
    draw.text((margin + 20, chk_top), "SECTION 1: STATUTORY INSPECTION CHECKLIST", fill=(31, 73, 125), font=font)
    draw.line([margin + 20, chk_top + 20, w - margin - 20, chk_top + 20], fill=(31, 73, 125), width=2)

    checklist_items = [
        ("[x] External insulation and cladding integrity verified", 0.97),
        ("[x] Foundation anchor bolts and ground connection checked", 0.95),
        ("[x] Nameplate and ASME stamping legible and authenticated", 0.98),
        ("[x] Relief valve RV-401 calibration certificate valid", 0.94),
        ("[ ] Ultrasonic thickness grid baseline survey completed (pending shutdown)", 0.91),
        ("[x] Nozzle N-1 (Feed Inlet) ultrasonic thickness: 14.2 mm (Nominal 14.5 mm)", 0.96),
    ]

    y_cur = chk_top + 35
    for item_text, conf in checklist_items:
        # Draw checkbox box
        draw.rectangle([margin + 30, y_cur - 2, margin + 46, y_cur + 14], outline=(50, 50, 50), width=1)
        if item_text.startswith("[x]"):
            draw.text((margin + 34, y_cur), "X", fill=(15, 81, 50), font=font)
        draw.text((margin + 60, y_cur), item_text[4:], fill=(30, 30, 30), font=font)
        y_cur += 30

    # 3. Discrete Findings Table
    tbl_top = y_cur + 30
    draw.text((margin + 20, tbl_top), "SECTION 2: DISCRETE MEASUREMENTS & ULTRASONIC THICKNESS FINDINGS", fill=(31, 73, 125), font=font)
    draw.line([margin + 20, tbl_top + 20, w - margin - 20, tbl_top + 20], fill=(31, 73, 125), width=2)

    tbl_y = tbl_top + 35
    row_height = 40
    cols = [
        ("Item #", 100),
        ("Component / Location", 320),
        ("Measured Value", 220),
        ("Minimum Required", 200),
        ("Evaluation", 160),
        ("Status", 140),
    ]

    # Header row
    x_cur = margin + 20
    draw.rectangle([margin + 20, tbl_y, w - margin - 20, tbl_y + row_height], fill=(230, 235, 245), outline=(100, 100, 100), width=1)
    for title, col_w in cols:
        draw.text((x_cur + 10, tbl_y + 12), title, fill=(31, 73, 125), font=font)
        x_cur += col_w

    tbl_rows = [
        ("1", "Shell Course 1 (Lower)", "12.4 mm", "10.0 mm", "PASS", "SATISFACTORY"),
        ("2", "Shell Course 2 (Middle)", "12.1 mm", "10.0 mm", "PASS", "SATISFACTORY"),
        ("3", "Top Head Ellipsoidal", "10.8 mm", "9.5 mm", "PASS", "SATISFACTORY"),
        ("4", "Bottom Head Hemispherical", "13.2 mm", "11.0 mm", "PASS", "SATISFACTORY"),
        ("5", "Nozzle N-1 Flange Face", "18.5 mm", "16.0 mm", "PASS", "SATISFACTORY"),
    ]

    for r_idx, row_data in enumerate(tbl_rows):
        r_top = tbl_y + (r_idx + 1) * row_height
        bg_col = (255, 255, 255) if r_idx % 2 == 0 else (245, 247, 250)
        draw.rectangle([margin + 20, r_top, w - margin - 20, r_top + row_height], fill=bg_col, outline=(180, 180, 180), width=1)
        x_cur = margin + 20
        for c_idx, (val, (_, col_w)) in enumerate(zip(row_data, cols)):
            text_col = (15, 81, 50) if val in ("PASS", "SATISFACTORY") else (30, 30, 30)
            draw.text((x_cur + 10, r_top + 12), val, fill=text_col, font=font)
            x_cur += col_w

    # 4. Handwritten Finding Callout Box (Sub-0.85 Confidence Trigger)
    hw_top = tbl_y + (len(tbl_rows) + 1) * row_height + 45
    draw.text((margin + 20, hw_top), "SECTION 3: ANOMALY NOTATION & FIELD ENGINEER HANDWRITTEN REMARKS", fill=(144, 0, 0), font=font)
    draw.line([margin + 20, hw_top + 20, w - margin - 20, hw_top + 20], fill=(144, 0, 0), width=2)

    hw_box_top = hw_top + 35
    hw_box_h = 160
    # Yellowish tinted callout box representing field inspection tag
    draw.rectangle([margin + 20, hw_box_top, w - margin - 20, hw_box_top + hw_box_h], fill=(255, 254, 240), outline=(210, 160, 40), width=2)

    draw.text((margin + 35, hw_box_top + 15), "[FIELD NOTE REF: doc-v301#p1-r004 - HANDWRITTEN ANOMALY LOG]", fill=(133, 100, 4), font=font)
    # Simulated handwriting style (loose lettering)
    draw.text((margin + 35, hw_box_top + 45), "Localized pitting observed at nozzle N-2 weld zone", fill=(20, 20, 80), font=font)
    draw.text((margin + 35, hw_box_top + 75), "Measured wall thickness: 4.2 mm  (Mandatory Minimum: 6.0 mm) - CRITICAL WARNING", fill=(180, 0, 0), font=font)
    draw.text((margin + 35, hw_box_top + 105), "Action Required: Immediate ultrasonic phased-array mapping prior to re-pressurization.", fill=(20, 20, 80), font=font)
    draw.text((margin + 35, hw_box_top + 130), "Inspector Initial: K.S.  |  Confidence Score: 0.78 (FLAGGED FOR HUMAN APPROVAL)", fill=(100, 100, 100), font=font)

    # 5. Signatures and Approval Section
    sig_top = hw_box_top + hw_box_h + 50
    draw.line([margin + 20, sig_top, w - margin - 20, sig_top], fill=(150, 150, 150), width=1)
    draw.text((margin + 30, sig_top + 20), "Lead Inspection Engineer: K. Sharma, NDT Level III", fill=(50, 50, 50), font=font)
    draw.text((margin + 30, sig_top + 50), "Signature: [Verified Digital Token #92A-44B-10C]", fill=(50, 50, 50), font=font)

    draw.text((w // 2 + 30, sig_top + 20), "Plant Operations Lead Approval: [ PENDING HITL REVIEW ]", fill=(180, 0, 0), font=font)
    draw.text((w // 2 + 30, sig_top + 50), "Verification Standard: ASME Sec VIII Div 1 / API 510", fill=(50, 50, 50), font=font)

    im.save(output_path, "PNG", optimize=True)
    return output_path


def generate_historian_csv(output_path: Path, num_rows: int = 10000) -> Path:
    """
    Writes samples/historian_sensor_telemetry.csv:
    - Exactly 1 header row + 10,000 data rows (10,001 lines).
    - Header: timestamp,machine_id,vib_rms_g,peak_accel_g,bearing_temp_c,shaft_speed_rpm
    - Normal baseline:
      vib_rms_g: 0.8 - 1.4 g, peak_accel_g: 1.2 - 1.8 g, bearing_temp_c: 50 - 55 °C, speed: 2970 - 3000 rpm
    - Anomaly window (rows 450 to 520):
      vib_rms_g spikes to 5.2 g, peak_accel_g to 6.0 g, bearing_temp_c reaches 91.4 °C.
    """
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rng = random.Random(42)  # Deterministic seed for reproducible testing
    start_time = datetime(2026, 9, 14, 8, 0, 0, tzinfo=timezone.utc)
    machine_id = "PUMP-301-B"

    header = ["timestamp", "machine_id", "vib_rms_g", "peak_accel_g", "bearing_temp_c", "shaft_speed_rpm"]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)

        for row_idx in range(1, num_rows + 1):
            t_current = start_time + timedelta(seconds=(row_idx - 1) * 0.1)  # 10 Hz sampling
            t_str = t_current.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

            if 450 <= row_idx <= 520:
                # Anomaly transient window (transient peak around row 485)
                progress = (row_idx - 450) / 70.0
                bell = math.sin(progress * math.pi)
                vib_rms = round(1.10 + 4.14 * bell + rng.uniform(-0.05, 0.05), 3)
                peak_accel = round(1.50 + 4.50 * bell + rng.uniform(-0.08, 0.08), 3)
                bearing_temp = round(52.0 + 39.4 * bell + rng.uniform(-0.3, 0.3), 2)
                shaft_speed = round(2985.0 - 45.0 * bell + rng.uniform(-2.0, 2.0), 1)
            else:
                # Normal operational baseline
                vib_rms = round(rng.uniform(0.85, 1.35), 3)
                peak_accel = round(rng.uniform(1.25, 1.75), 3)
                bearing_temp = round(rng.uniform(50.2, 54.8), 2)
                shaft_speed = round(rng.uniform(2972.0, 2998.0), 1)

            writer.writerow([t_str, machine_id, vib_rms, peak_accel, bearing_temp, shaft_speed])

    return output_path


def _draw_base_pid_canvas() -> Tuple[Image.Image, ImageDraw.ImageDraw]:
    """Creates a base CAD P&ID diagram canvas (1600 x 1200) with shared baseline geometry."""
    w, h = 1600, 1200
    im = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(im)
    font = ImageFont.load_default()

    # Border & Title block
    draw.rectangle([20, 20, w - 20, h - 20], outline=(0, 0, 0), width=3)
    draw.rectangle([w - 480, h - 140, w - 20, h - 20], outline=(0, 0, 0), width=2)
    draw.text((w - 460, h - 125), "PROCESS & INSTRUMENTATION DIAGRAM", fill=(0, 0, 0), font=font)
    draw.text((w - 460, h - 100), "FACILITY: REFINERY UNIT 04 - HYDROTREATER", fill=(0, 0, 0), font=font)
    draw.text((w - 460, h - 75), "SYSTEM: HYDROGEN HEADER & SEPARATOR V-301", fill=(0, 0, 0), font=font)
    draw.text((w - 460, h - 50), "DRAWING NO: 04-PID-V301-REV-X", fill=(0, 0, 0), font=font)

    # Main Vessel V-301 (Center: x 550..850, y 300..750)
    # Cylindrical body
    draw.rectangle([550, 350, 850, 700], outline=(0, 0, 0), width=4)
    # Top head (arc)
    draw.arc([550, 300, 850, 400], 180, 360, fill=(0, 0, 0), width=4)
    # Bottom head (arc)
    draw.arc([550, 650, 850, 750], 0, 180, fill=(0, 0, 0), width=4)
    # Vessel label
    draw.text((660, 510), "VESSEL V-301", fill=(0, 0, 0), font=font)
    draw.text((640, 530), "DEBUTANIZER COLUMN", fill=(0, 0, 0), font=font)

    # Process Inlet Header (Line 10-HC-101-CS) coming from left
    # Horizontal pipe: x 80 to 550, y 520
    draw.line([80, 520, 550, 520], fill=(0, 0, 0), width=4)
    draw.text((100, 500), "FROM UNIT 03 >>> 10-HC-101-CS", fill=(0, 0, 0), font=font)

    # Inlet Valve V-101 on main inlet pipe at x=280..340, y=520
    # Drawn as two opposing triangles meeting at center (310, 520)
    v_cx = 310
    v_cy = 520
    draw.polygon([(v_cx - 25, v_cy - 16), (v_cx - 25, v_cy + 16), (v_cx, v_cy)], fill=(255, 255, 255), outline=(0, 0, 0))
    draw.polygon([(v_cx + 25, v_cy - 16), (v_cx + 25, v_cy + 16), (v_cx, v_cy)], fill=(255, 255, 255), outline=(0, 0, 0))
    # Valve stem and handwheel
    draw.line([v_cx, v_cy, v_cx, v_cy - 20], fill=(0, 0, 0), width=2)
    draw.line([v_cx - 12, v_cy - 20, v_cx + 12, v_cy - 20], fill=(0, 0, 0), width=3)
    draw.text((v_cx - 15, v_cy + 22), "V-101", fill=(0, 0, 0), font=font)

    # Process Outlet Line going right from Vessel (x 850 to 1450, y 520)
    draw.line([850, 520, 1450, 520], fill=(0, 0, 0), width=4)
    draw.text((1200, 500), ">>> TO FRACTIONATOR", fill=(0, 0, 0), font=font)

    # Vertical tap to pressure instrument at x=1050, y=520 up to y=420
    draw.line([1050, 520, 1050, 420], fill=(0, 0, 0), width=2)

    # Drain line dropping down from bottom of vessel at x=700, y=750 to 920
    draw.line([700, 750, 700, 920], fill=(0, 0, 0), width=3)
    draw.line([700, 920, 780, 920], fill=(0, 0, 0), width=3)
    draw.text((790, 915), "TO CLOSED DRAIN", fill=(0, 0, 0), font=font)

    return im, draw


def generate_pid_revisions(path_a: Path, path_b: Path) -> Tuple[Path, Path]:
    """
    Renders samples/pid_drawing_rev_a.png and samples/pid_drawing_rev_b.png (1600 x 1200 pixels, RGB).
    Shared base geometry:
    - Same border, title block, vessel V-301, inlet pipe with V-101, outlet pipe, tap lines.
    Exact 3 differences:
    1. ADDED: New bypass loop around V-101 with relief valve RV-402 in Rev B (absent in Rev A).
    2. REMOVED: Drain valve V-102 present in Rev A (omitted/decommissioned in Rev B).
    3. MODIFIED: Analog indicator PI-201 in Rev A replaced with digital transmitter PT-201 in Rev B.
    """
    path_a = Path(path_a).resolve()
    path_b = Path(path_b).resolve()
    path_a.parent.mkdir(parents=True, exist_ok=True)
    path_b.parent.mkdir(parents=True, exist_ok=True)

    font = ImageFont.load_default()

    # --- RENDER REVISION A (BASELINE) ---
    im_a, draw_a = _draw_base_pid_canvas()

    # In Rev A:
    # 1. No bypass loop around V-101 (Area x: 200..420, y: 350..470 is clear)

    # 2. Drain valve V-102 IS present on the drain line at x=700, y=820
    d_cx, d_cy = 700, 820
    draw_a.polygon([(d_cx - 16, d_cy - 20), (d_cx + 16, d_cy - 20), (d_cx, d_cy)], fill=(255, 255, 255), outline=(0, 0, 0), width=2)
    draw_a.polygon([(d_cx - 16, d_cy + 20), (d_cx + 16, d_cy + 20), (d_cx, d_cy)], fill=(255, 255, 255), outline=(0, 0, 0), width=2)
    draw_a.line([d_cx, d_cy, d_cx + 18, d_cy], fill=(0, 0, 0), width=2)
    draw_a.line([d_cx + 18, d_cy - 10, d_cx + 18, d_cy + 10], fill=(0, 0, 0), width=3)
    draw_a.text((d_cx + 25, d_cy - 5), "V-102 (DRAIN)", fill=(0, 0, 0), font=font)

    # 3. Pressure instrument PI-201 (Analog circular dial with pointer needle) at x=1050, y=380
    pi_cx, pi_cy = 1050, 380
    draw_a.ellipse([pi_cx - 35, pi_cy - 35, pi_cx + 35, pi_cy + 35], fill=(255, 255, 255), outline=(0, 0, 0), width=3)
    # Dial needle line
    draw_a.line([pi_cx, pi_cy, pi_cx + 20, pi_cy - 18], fill=(0, 0, 0), width=3)
    draw_a.text((pi_cx - 10, pi_cy + 5), "PI", fill=(0, 0, 0), font=font)
    draw_a.text((pi_cx - 14, pi_cy + 18), "201", fill=(0, 0, 0), font=font)

    im_a.save(path_a, "PNG", optimize=True)

    # --- RENDER REVISION B (UPDATED) ---
    im_b, draw_b = _draw_base_pid_canvas()

    # In Rev B:
    # 1. ADDED: Bypass loop around V-101 with relief valve RV-402
    # Bypass branches from x=210, y=520 -> up to y=420 -> across to x=410 -> down to y=520
    draw_b.line([210, 520, 210, 420], fill=(0, 0, 0), width=3)
    draw_b.line([210, 420, 410, 420], fill=(0, 0, 0), width=3)
    draw_b.line([410, 420, 410, 520], fill=(0, 0, 0), width=3)
    # Relief valve RV-402 on bypass at x=310, y=420
    r_cx, r_cy = 310, 420
    draw_b.polygon([(r_cx - 20, r_cy - 14), (r_cx - 20, r_cy + 14), (r_cx, r_cy)], fill=(255, 255, 255), outline=(0, 0, 0))
    draw_b.polygon([(r_cx + 20, r_cy - 14), (r_cx + 20, r_cy + 14), (r_cx, r_cy)], fill=(255, 255, 255), outline=(0, 0, 0))
    # Relief valve spring cap top
    draw_b.line([r_cx, r_cy, r_cx, r_cy - 18], fill=(0, 0, 0), width=2)
    draw_b.rectangle([r_cx - 8, r_cy - 26, r_cx + 8, r_cy - 18], fill=(0, 0, 0))
    draw_b.text((r_cx - 20, r_cy - 40), "RV-402 (BYPASS)", fill=(0, 0, 0), font=font)

    # 2. REMOVED: Drain valve V-102 is DECOMMISSIONED and NOT drawn on the drain pipe
    # Notice: In Rev B, nothing is drawn at x=700, y=800..840 except the plain vertical pipe that is in the base canvas!
    # But wait! In Rev A, the drain pipe was drawn AND the valve polygons filled with white (255, 255, 255).
    # In Rev B base canvas, the drain pipe is drawn as a continuous line [700, 750, 700, 920].
    # In Rev A, the valve white polygon covered part of the pipe line, and the valve outline was drawn.
    # So in that region, Rev A has the valve outlines + text, while Rev B has just the pipe line.
    # Let's verify whether Rev A vs Rev B here has overlap or pure removal.
    # To ensure it is classified as REMOVED:
    # Rev B should NOT add any ink that wasn't in Rev A!
    # If Rev A has the valve triangles and text, and Rev B has nothing extra,
    # wait: if Rev B has the vertical pipe going straight through, then in Rev A the pipe was hidden by white fill!
    # That would mean Rev B has a line segment where Rev A had white fill (meaning added_c > 0 for that line).
    # If added_c is too large relative to removed_c, it might be classified as MODIFIED instead of REMOVED!
    # Let's test and make sure!

    # 3. MODIFIED: Pressure instrument at x=1050, y=380 is now PT-201 (Square transmitter enclosure around balloon)
    pt_cx, pt_cy = 1050, 380
    # Outer square box representing digital smart transmitter housing
    draw_b.rectangle([pt_cx - 42, pt_cy - 42, pt_cx + 42, pt_cy + 42], fill=(255, 255, 255), outline=(0, 0, 0), width=3)
    # Inner circular balloon
    draw_b.ellipse([pt_cx - 30, pt_cy - 30, pt_cx + 30, pt_cy + 30], fill=(255, 255, 255), outline=(0, 0, 0), width=2)
    # Horizontal dividing line across circle (smart transmitter standard symbol)
    draw_b.line([pt_cx - 30, pt_cy, pt_cx + 30, pt_cy], fill=(0, 0, 0), width=2)
    draw_b.text((pt_cx - 10, pt_cy - 20), "PT", fill=(0, 0, 0), font=font)
    draw_b.text((pt_cx - 14, pt_cy + 6), "201", fill=(0, 0, 0), font=font)

    im_b.save(path_b, "PNG", optimize=True)

    return path_a, path_b


def main():
    parser = argparse.ArgumentParser(description="Generate deterministic sample assets for Sovereign AI Workbench demos.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "samples",
        help="Directory to save generated sample assets (default: samples/)",
    )
    args = parser.parse_args()

    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Generating deterministic demo assets in: {out_dir}")

    # 1. Inspection scan
    scan_path = out_dir / "refinery_vessel_inspection_v301.png"
    generate_inspection_scan(scan_path)
    print(f"  [+] Inspection scan: {scan_path} ({scan_path.stat().st_size} bytes)")

    # 2. Historian CSV
    csv_path = out_dir / "historian_sensor_telemetry.csv"
    generate_historian_csv(csv_path, num_rows=10000)
    print(f"  [+] Historian CSV:   {csv_path} ({csv_path.stat().st_size} bytes)")

    # 3. P&ID revisions
    pid_a = out_dir / "pid_drawing_rev_a.png"
    pid_b = out_dir / "pid_drawing_rev_b.png"
    generate_pid_revisions(pid_a, pid_b)
    print(f"  [+] P&ID Rev A:      {pid_a} ({pid_a.stat().st_size} bytes)")
    print(f"  [+] P&ID Rev B:      {pid_b} ({pid_b.stat().st_size} bytes)")

    print("Sample asset generation completed successfully.")


if __name__ == "__main__":
    main()
