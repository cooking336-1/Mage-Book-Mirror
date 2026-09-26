"""In-Memory Vector QR SVG Code Generator for Ghana Revenue Authority (GRA) Verification.

Generates pure vector SVG QR codes in memory (RAM) without writing temporary files to disk,
satisfying high-throughput and security isolation invariants.
"""

from reportlab.graphics import renderSVG
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing


class QRGeneratorService:
    """Compiles vector SVG QR codes in-memory."""

    @classmethod
    def generate_vector_svg(cls, payload: str, size: int = 100) -> str:
        """Generates an in-memory vector SVG QR code string.

        Args:
            payload: Verification URL or cryptographic payload string.
            size: Width and height dimension in points.

        Returns:
            str: Full XML SVG document string.
        """
        drawing = Drawing(size, size)
        qr_widget = QrCodeWidget(payload)
        qr_widget.barWidth = size
        qr_widget.barHeight = size
        drawing.add(qr_widget)

        return renderSVG.drawToString(drawing)
