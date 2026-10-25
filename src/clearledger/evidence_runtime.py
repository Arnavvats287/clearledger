"""Bounded per-operation snapshot of hash-verified immutable originals, never a global cache."""

from pathlib import Path
from uuid import UUID

from clearledger.case_domain import CaseError
from clearledger.document_runtime import LocalOriginals


class EvidenceOriginals(LocalOriginals):
    MAX_BYTES = 16 * 1024 * 1024
    MAX_DOCUMENTS = 100

    def __init__(self, root: Path):
        super().__init__(root)
        self._verified: dict[tuple[UUID, str], bytes] = {}
        self._bytes = 0

    def get(self, organization_id: UUID, sha: str) -> bytes:
        key = (organization_id, sha)
        if key not in self._verified:
            if len(self._verified) >= self.MAX_DOCUMENTS:
                raise CaseError("EVIDENCE_ORIGINAL_DOCUMENT_BUDGET")
            raw = super().get(organization_id, sha)
            if self._bytes + len(raw) > self.MAX_BYTES:
                raise CaseError("EVIDENCE_ORIGINAL_BYTE_BUDGET")
            self._verified[key] = raw
            self._bytes += len(raw)
        return self._verified[key]
