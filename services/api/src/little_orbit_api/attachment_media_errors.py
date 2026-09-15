"""Error types shared by the isolated attachment worker modules."""


class ScanUnavailable(RuntimeError):
    """Raised when scanning or sanitization cannot safely finish."""


class AttachmentRejected(ValueError):
    """Raised when attachment bytes permanently violate the accepted media policy."""
