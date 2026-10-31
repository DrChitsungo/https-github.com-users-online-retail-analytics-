"""Create deck/qr_dashboard.png for the dashboard URL and prove it decodes back to the same URL. Usage: python scripts/make_qr.py [URL]"""
import sys
from pathlib import Path
import qrcode, cv2
URL = sys.argv[1] if len(sys.argv) > 1 else "https://huggingface.co/spaces/Bezzel/retail-churn-dashboard"
out = Path(__file__).resolve().parents[1] / "deck" / "qr_dashboard.png"
qrcode.make(URL, box_size=12, border=4, error_correction=qrcode.constants.ERROR_CORRECT_M).save(out)
dec, _, _ = cv2.QRCodeDetector().detectAndDecode(cv2.imread(str(out)))
assert dec == URL, f"QR decodes to {dec!r}, expected {URL!r}"; print("QR ok:", dec, "->", out)
