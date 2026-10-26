"""Read scanned CMS-1500 style paper bills into reviewable line records.

Local only: pages are rendered with PyMuPDF and read with the Tesseract CLI.
Nothing here decides anything; it returns the raw text it read for each field
so a reviewer can compare it with the page image.
"""
import re
import subprocess

import cv2
import numpy as np
import pymupdf

DPI = 300
# Form geometry at 300 dpi, measured from the top ruled line of the form box.
SECTION = 94          # height of each header band (1/1A, 2/3/4, 10A/14/26, 21)
TABLE_HEADER = 435    # bottom of the service-line table header
ROW = 109.33          # height of one service line row
ROWS = 6
FOOTER = 1107         # top of box 25 (tax id / total charge / signature)


def render(page):
    pix = page.get_pixmap(dpi=DPI, colorspace=pymupdf.csGRAY)
    return np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w).copy()


def deskew(img):
    bw = ((img < 160) * 255).astype(np.uint8)
    lines = cv2.HoughLinesP(bw, 1, np.pi / 1800, 400, minLineLength=1200, maxLineGap=20)
    angles = []
    if lines is not None:
        for x1, y1, x2, y2 in lines.reshape(-1, 4):
            a = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            if abs(a) < 5:
                angles.append(a)
    angle = float(np.median(angles)) if angles else 0.0
    h, w = img.shape
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1)
    return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_LINEAR, borderValue=255), angle


def form_box(img):
    """Return (top, left, right) of the form's outer ruled box."""
    bw = (img < 170).astype(np.uint8)
    h = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (150, 1)))
    rows = np.where(h.sum(1) > 1500)[0]
    top = int(rows[0])
    xs = np.where(h[top:top + 4].max(0) > 0)[0]
    return top, int(xs[0]), int(xs[-1])


def clean(crop):
    """Remove scanner speckle and binarise for OCR."""
    crop = cv2.medianBlur(crop, 3)
    _, bw = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # drop ruled lines that leak into the crop (a divider spans most of the strip height)
    inv = 255 - bw
    for k in [(80, 1), (1, max(15, int(crop.shape[0] * 0.7)))]:
        lines = cv2.morphologyEx(inv, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, k))
        inv = cv2.subtract(inv, lines)
    # drop tiny specks that survive the blur
    n, lab, stats, _ = cv2.connectedComponentsWithStats(inv, 8)
    keep = np.zeros(n, bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= 12
    inv = np.where(keep[lab], 255, 0).astype(np.uint8)
    return cv2.copyMakeBorder(255 - inv, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)


def tesseract(crop, psm=6, whitelist=None):
    ok, png = cv2.imencode(".png", clean(crop))
    cmd = ["tesseract", "stdin", "stdout", "--psm", str(psm)]
    if whitelist:
        cmd += ["-c", f"tessedit_char_whitelist={whitelist}", "-c", "preserve_interword_spaces=1"]
    out = subprocess.run(cmd, input=png.tobytes(), capture_output=True, check=True)
    return out.stdout.decode("utf-8", "replace").strip()


UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
WL_ROW = "0123456789" + UPPER + ". "
MONTHS = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}


def _date(mm, dd, yy):
    yy = int(yy)
    if yy < 100:
        yy += 2000
    return f"{yy:04d}-{int(mm):02d}-{int(dd):02d}"


ROW_RE = re.compile(
    r"(\d\d) ?(\d\d) ?(\d\d)\s+(?:\S{1,2}\s+)?((?:PX\d{3})|(?:[A-Z]\d{4}))(?: ([A-Z]{2}))?\s+A\s+"
    r"(\d+\.\d\d)\s+(\d{1,2})\s+(\d{10})\b"
)


def parse_row(text):
    """Parse the main text line of one service row by content pattern.

    Place of service is not used by any rule, so it is allowed to be misread.
    """
    t = re.sub(r"\s+", " ", text.upper()).strip()
    m = ROW_RE.search(t)
    if not m:
        return None
    mm, dd, yy, code, mod, charge, units, npi = m.groups()
    return {
        "date_of_service": _date(mm, dd, yy),
        "procedure_code": code,
        "modifier": mod or "",
        "billed_charge": charge,
        "units": units,
        "rendering_npi": npi,
    }


def _digits(s):
    """Map letters Tesseract commonly confuses with digits in numeric fields."""
    return s.translate(str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "|": " ", "'": " ",
                                      "‘": " ", "’": " ", ",": " ", ";": " ", "(": " ", ")": " ",
                                      "{": " ", "}": " ", "[": " ", "]": " "}))


def read_stamp(head):
    """Read the mailroom stamp (a small rotated box) as RECEIVED MON DD YYYY."""
    bw = ((cv2.medianBlur(head, 3) < 150) * 255).astype(np.uint8)
    contours, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    texts = []
    if contours:
        box = max(contours, key=cv2.contourArea)
        (cx, cy), (w, h), a = cv2.minAreaRect(box)
        if w < h:
            w, h, a = h, w, a - 90
        for angle in (a, -a):
            m = cv2.getRotationMatrix2D((cx, cy), angle, 1)
            rot = cv2.warpAffine(head, m, head.shape[::-1], borderValue=255)
            crop = rot[int(cy - h / 2) + 8:int(cy + h / 2) - 8, int(cx - w / 2) + 8:int(cx + w / 2) - 8]
            texts.append(tesseract(crop, psm=7))
    texts.append(tesseract(head, psm=11))
    for t in texts:
        m = re.search(r"(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s*(\d\d)\s*(\d{4})",
                      _digits(t.upper()).replace("0CT", "OCT"))
        if m:
            return _date(MONTHS[m.group(1)], m.group(2), m.group(3)), t
    return "", " / ".join(texts)


def dividers(img, y0, y1, x0, x1, frac=0.9):
    """x positions of the vertical ruled lines that cross rows y0..y1."""
    sub = cv2.medianBlur(img[y0:y1, max(0, x0):x1], 3)
    cols = np.where((sub < 200).sum(0) >= frac * (y1 - y0))[0]
    groups = []
    for x in cols:
        if groups and x - groups[-1][-1] <= 4:
            groups[-1].append(x)
        else:
            groups.append([x])
    return [max(0, x0) + int(np.mean(g)) for g in groups]


def cells(img, y0, y1, x0, x1, expected):
    """Split a ruled band into its boxes; None when the rule count is not as expected."""
    for frac in (0.9, 0.8, 0.7):
        xs = dividers(img, y0, y1, x0 - 12, x1 + 12, frac)
        if len(xs) == expected + 1:
            return list(zip(xs[:-1], xs[1:]))
    return None


def ocr_cell(img, y0, y1, xa, xb, whitelist=None):
    return tesseract(img[y0:y1, xa + 8:xb - 6], psm=7, whitelist=whitelist)


DIGITS = "0123456789"


def _num(s):
    """Like _digits, for fields that hold only digits (dates): S/B/Z are 5/8/2."""
    return _digits(s).translate(str.maketrans({"S": "5", "s": "5", "B": "8", "Z": "2"}))


def _money(s):
    """'2.875.00' or '2,875.00' -> '2875.00'."""
    s = re.sub(r"[^\d.,]", "", s).replace(",", ".")
    if s.count(".") > 1:
        head, tail = s.rsplit(".", 1)
        s = head.replace(".", "") + "." + tail
    return s if re.fullmatch(r"\d+\.\d\d", s) else ""


def read_page(page):
    img, angle = deskew(render(page))
    top, left, right = form_box(img)
    fields = {"skew_degrees": round(angle, 2)}
    raw = {}

    head = img[max(0, top - 420):top - 150, left:right]
    raw["header"] = tesseract(head, psm=11)
    m = re.search(r"HB\s?(\d{7})", _digits(raw["header"].upper()).replace("H8", "HB"))
    fields["bill_id"] = f"HB{m.group(1)}" if m else ""
    fields["received_date"], raw["stamp"] = read_stamp(head)

    def band(i, n_boxes):
        """Value text of each box in header band i (the label sits in the top 36 px)."""
        y = top + SECTION * i
        boxes = cells(img, y + 8, y + SECTION - 8, left, right, n_boxes)
        if boxes is None:  # fall back to the whole band as one strip
            return [tesseract(img[y + 36:y + SECTION - 3, left + 6:right - 6], psm=7)]
        return [ocr_cell(img, y + 36, y + SECTION - 3, a, b) for a, b in boxes]

    b1 = band(0, 2)
    raw["band1"] = " | ".join(b1)
    m = re.search(r"WC\s?(\d\d)\s?[-~—]+\s?(\d{5})", _digits(b1[-1].upper()))
    fields["claim_number"] = f"WC{m.group(1)}-{m.group(2)}" if m else ""

    b2 = band(1, 3)
    raw["band2"] = " | ".join(b2)
    if len(b2) == 3:
        fields["claimant_name"] = re.sub(r"[^A-Z,' -]", "", b2[0].upper()).strip(" ,")
        dob_text = b2[1]
    else:
        m = re.search(r"([A-Z][A-Z' -]*,\s*[A-Z][A-Z' -]*)", b2[0].upper())
        fields["claimant_name"] = m.group(1).strip() if m else ""
        dob_text = b2[0][m.end():] if m else b2[0]
    # a column rule next to the date is sometimes read as a leading 1 ("104 15 1969")
    m = re.search(r"(?<!\d)1?(\d\d) (\d\d) (\d{4})", re.sub(r"\s+", " ", _num(dob_text)))
    fields["claimant_dob"] = _date(*m.groups()) if m else ""

    b3 = band(2, 3)
    raw["band3"] = " | ".join(b3)
    doi_text = b3[1] if len(b3) == 3 else b3[0]
    m = re.search(r"(?<!\d)(\d\d) ?(\d\d) ?(\d{4})", re.sub(r"\s+", " ", _num(doi_text)))
    fields["date_of_injury"] = _date(*m.groups()) if m else ""

    y = top + SECTION * 3
    raw["band4"] = tesseract(img[y + 36:y + SECTION - 3, left + 6:right - 6], psm=7)
    m = re.search(r"\bA\W*([A-Z$5]|S\$)\s?(\d{2})\s?[.,]\s?([0-9A-Z]{1,4})", raw["band4"].upper())
    if m:
        letter = {"$": "S", "5": "S", "S$": "S"}.get(m.group(1), m.group(1))
        fields["diagnosis_code"] = f"{letter}{m.group(2)}.{m.group(3).replace('O', '0')}"
    else:
        fields["diagnosis_code"] = ""

    yf = top + FOOTER
    fboxes = cells(img, yf + 8, yf + SECTION - 8, left, right, 3)
    if fboxes:
        tin_text = ocr_cell(img, yf + 36, yf + 91, *fboxes[0], whitelist=DIGITS + "-")
        tot_text = ocr_cell(img, yf + 36, yf + 91, *fboxes[1], whitelist=DIGITS + ".$ ")
    else:
        tin_text = tot_text = tesseract(img[yf + 36:yf + 91, left + 6:right - 6], psm=7)
    raw["footer"] = f"{tin_text} | {tot_text}"
    m = re.search(r"(\d\d)\s?-\s?(\d{7})", _digits(tin_text))
    fields["billing_tin"] = f"{m.group(1)}-{m.group(2)}" if m else ""
    m = re.search(r"\$?\s*([\d][\d.,]*\.\d\d)", tot_text)
    fields["total_charge"] = _money(m.group(1)) if m else ""

    prov = img[yf + SECTION + 32:yf + SECTION + 80, left + 6:right - 6]
    raw["billing_provider"] = tesseract(prov, psm=7)

    # service-line table: row number | date | place | procedure | pointer | charges | units | NPI
    t0, t1 = int(top + TABLE_HEADER), int(top + TABLE_HEADER + ROW * ROWS)
    cols = cells(img, t0 - 40, int(top + FOOTER - 20), left, right, 8)
    fields["table_rows_aligned"] = table_rows_aligned(img, top, left, right)
    lines = []
    for r in range(ROWS):
        y0 = int(t0 + ROW * r)
        ya, yb = y0 + 6, y0 + 58  # upper text line of the row; the lower one is the rendering name
        if cols:
            c = [ocr_cell(img, ya, yb, a, b, wl) for (a, b), wl in zip(cols[1:], [
                DIGITS + " ", None, UPPER + DIGITS + " ", None, DIGITS + ".", DIGITS, DIGITS])]
            text = " ".join(x for x in c if x)
            if not re.search(r"\d{3}", c[0] + c[4] + c[6]):
                continue  # blank row (scanner speckle only)
            parsed = _parse_cells(c)
        else:
            text = tesseract(img[ya:yb, left + 4:right - 4], psm=7, whitelist=WL_ROW)
            parsed = parse_row(text)
            if parsed is None and not re.search(r"\d{3}", text):
                continue
        lines.append({"row": r + 1, "raw": text, "parsed": parsed,
                      "crop_box": [left, y0, right, int(y0 + ROW)]})
    return fields, lines, raw, img


def table_rows_aligned(img, top, left, right, tol=8):
    """True when a ruled line sits at every expected service-row boundary.

    Rows are located by fixed geometry from the form's top line; if a form is scaled or laid out
    differently the rows would be read from the wrong place, so this is reported for review.
    """
    bw = (cv2.medianBlur(img, 3) < 200).astype(np.uint8)
    h = cv2.morphologyEx(bw[:, left:right], cv2.MORPH_OPEN,
                         cv2.getStructuringElement(cv2.MORPH_RECT, (150, 1)))
    ys = np.where(h.sum(1) > 0.6 * (right - left))[0]
    for k in range(ROWS + 1):
        y = top + TABLE_HEADER + ROW * k
        if not np.any(np.abs(ys - y) <= tol):
            return False
    return True


def _parse_cells(c):
    date, _pos, proc, _ptr, charge, units, npi = c
    m_date = re.fullmatch(r"(\d\d) ?(\d\d) ?(\d\d)", re.sub(r"\s+", " ", date.strip()))
    m_proc = re.fullmatch(r"((?:PX\d{3})|(?:[A-Z]\d{4}))(?:[ -]?([A-Z]{2}))?", proc.strip())
    m_charge = re.fullmatch(r"\d+\.\d\d", charge.strip())
    m_units = re.fullmatch(r"\d{1,2}", units.strip())
    m_npi = re.fullmatch(r"\d{10}", npi.strip())
    if not all([m_date, m_proc, m_charge, m_units, m_npi]):
        return None
    return {
        "date_of_service": _date(*m_date.groups()),
        "procedure_code": m_proc.group(1),
        "modifier": m_proc.group(2) or "",
        "billed_charge": charge.strip(),
        "units": units.strip(),
        "rendering_npi": npi.strip(),
    }


def read_pdf(path):
    doc = pymupdf.open(path)
    for i, page in enumerate(doc):
        fields, lines, raw, img = read_page(page)
        yield i + 1, fields, lines, raw, img
