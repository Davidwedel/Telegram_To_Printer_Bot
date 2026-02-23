"""Send a 'Hello World' test page directly to the printer."""

import socket

IP = "192.168.0.227"
PORT = 9100

PJL_RESET = b"\x1b%-12345X@PJL\r\n@PJL RESET\r\n\x1b%-12345X"

pdf = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj
4 0 obj<</Length 44>>
stream
BT /F1 24 Tf 200 400 Td (Hello World) Tj ET
endstream
endobj
5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000266 00000 n
0000000360 00000 n
trailer<</Size 6/Root 1 0 R>>
startxref
434
%%EOF"""

print(f"Connecting to {IP}:{PORT}...")
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.settimeout(10)
    s.connect((IP, PORT))
    print("Connected. Sending PJL reset...")
    s.sendall(PJL_RESET)
    print("Sending PDF...")
    s.sendall(pdf)
print("Done! Check the printer.")
