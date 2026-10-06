"""The Brief: the agent's structured output, validated with pydantic."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

AlertLevel = Literal["routine", "heads_up", "caution"]
RelationshipStatus = Literal[
    "net_new",
    "healthy_department",
    "at_risk_department",
    "closed_lost_history",
    "job_changer",
    "conflict",
]
FlagType = Literal[
    "renewal_risk",
    "champion_change",
    "closed_lost_history",
    "open_opp_conflict",
    "stale_contact",
    "warm_reference",
    "job_changer",
]

# crm:account/ACC-017, crm:contact/CON-102, crm:opp/OPP-031, crm:lead/L-001, usage:ACC-017, transcript:T-0042
SourceId = Annotated[
    str,
    StringConstraints(pattern=r"^(crm:(account/ACC|contact/CON|opp/OPP|lead/L)-\d+|usage:ACC-\d+|transcript:T-\d+)$"),
]
AccountId = Annotated[str, StringConstraints(pattern=r"^ACC-\d+$")]


class Flag(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: FlagType
    claim: str = Field(description="One sentence the rep can act on, stating the fact and its date.")
    source_ids: list[SourceId] = Field(
        min_length=1, description="Source IDs that support the claim, copied exactly from tool results."
    )


class Brief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alert_level: AlertLevel
    relationship_status: RelationshipStatus
    related_account_ids: list[AccountId] = Field(
        description="Bare account IDs (e.g. ACC-017) of accounts truly related to the lead's company. Empty if none."
    )
    headline: str = Field(description="The one line the rep must see first.")
    flags: list[Flag] = Field(description="Empty on routine leads.")
    summary: str = Field(description="Two to four sentences on the relationship, with dates.")
    call_context_note: str = Field(
        description="One or two sentences on the lead themself and their inbound request: who they are, what they asked for, when."
    )
    recommended_action: str = Field(description="What the rep should do next, naming people where relevant.")

    def render(self) -> str:
        """Plain-text view for the rep."""
        accounts = f" (accounts: {', '.join(self.related_account_ids)})" if self.related_account_ids else ""
        lines = [
            f"[{self.alert_level.upper()}] {self.headline}",
            f"Relationship: {self.relationship_status}{accounts}",
            "",
            self.summary,
        ]
        if self.flags:
            lines += ["", "Flags:"]
            lines += [f"  - {f.type}: {f.claim} [{', '.join(f.source_ids)}]" for f in self.flags]
        lines += ["", f"Call context: {self.call_context_note}", f"Recommended action: {self.recommended_action}"]
        return "\n".join(lines)
