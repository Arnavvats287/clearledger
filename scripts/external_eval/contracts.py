"""Strict source/prediction DTOs; deliberately independent of AR domain models."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Key = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")]
Text = Annotated[str, Field(min_length=1, max_length=250_000)]
Label = Literal["Entailment", "Contradiction", "NotMentioned", "Abstain", "ProviderFailure"]
Unit = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)


class Hypothesis(Strict):
    hypothesis_id: Key
    text: Text


class ContractPacket(Strict):
    document_id: Key
    text: Text
    hypotheses: Annotated[list[Hypothesis], Field(min_length=1, max_length=17)]

    @model_validator(mode="after")
    def unique_ids(self) -> "ContractPacket":
        if len({h.hypothesis_id for h in self.hypotheses}) != len(self.hypotheses):
            raise ValueError("DUPLICATE_HYPOTHESIS")
        return self


class Quote(Strict):
    text: Annotated[str, Field(min_length=1, max_length=8000)]
    start: Annotated[int, Field(ge=0)] | None = None
    end: Annotated[int, Field(gt=0)] | None = None

    @model_validator(mode="after")
    def paired_range(self) -> "Quote":
        if (self.start is None) != (self.end is None):
            raise ValueError("INCOMPLETE_RANGE")
        if self.start is not None and self.end is not None and self.start >= self.end:
            raise ValueError("INVALID_RANGE")
        return self


class ProviderMetadata(Strict):
    provider: Annotated[str, Field(min_length=1, max_length=80)]
    model: Annotated[str, Field(min_length=1, max_length=100)] | None = None
    fallback: bool = False
    failure: Literal["NONE", "PROVIDER", "POLICY", "PARSE", "SCHEMA", "MISSING_OUTPUT"] = "NONE"
    latency_ms: Annotated[int, Field(ge=0)] | None = None


class Answer(Strict):
    hypothesis_id: Key
    predicted_label: Label
    evidence_quotes: Annotated[list[Quote], Field(max_length=100)] = []
    confidence: Unit | None = None
    uncertainty: Literal["none", "review", "unknown"] = "unknown"


class ContractOutput(Strict):
    document_id: Key
    answers: Annotated[list[Answer], Field(max_length=17)]
    metadata: ProviderMetadata

    @model_validator(mode="after")
    def unique_ids(self) -> "ContractOutput":
        if len({a.hypothesis_id for a in self.answers}) != len(self.answers):
            raise ValueError("DUPLICATE_ANSWER")
        return self


class Box(Strict):
    left: Unit
    top: Unit
    right: Unit
    bottom: Unit

    @model_validator(mode="after")
    def ordered(self) -> "Box":
        if self.left > self.right or self.top > self.bottom:
            raise ValueError("INVALID_GEOMETRY")
        return self


class Word(Strict):
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    box: Box


class Page(Strict):
    page: Annotated[int, Field(ge=0)]  # DocILE native zero-based page convention.
    text: Text
    words: Annotated[list[Word], Field(max_length=30_000)]

    @model_validator(mode="after")
    def valid_offsets(self) -> "Page":
        previous = 0
        for word in self.words:
            if not previous <= word.start < word.end <= len(self.text):
                raise ValueError("INVALID_WORD_OFFSETS")
            previous = word.end
        return self


class DocilePacket(Strict):
    document_id: Key
    pages: Annotated[list[Page], Field(min_length=1, max_length=200)]

    @model_validator(mode="after")
    def unique_pages(self) -> "DocilePacket":
        if [p.page for p in self.pages] != list(range(len(self.pages))):
            raise ValueError("INVALID_PAGE_SEQUENCE")
        return self


class InvoiceReference(Strict):
    value: Annotated[str, Field(min_length=1, max_length=200)]
    quote: Quote
    page: Annotated[int, Field(ge=0)] | None = None
    confidence: Unit | None = None


class DocileOutput(Strict):
    document_id: Key
    invoice_references: Annotated[list[InvoiceReference], Field(max_length=100)]
    metadata: ProviderMetadata


class Edge(Strict):
    txn_id: Key
    line_id: Key
