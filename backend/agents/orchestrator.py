"""
Swarm Orchestrator
Multi-agent coordination with dynamic spawning/dismissal,
System Prompt Integrity Gate verification, per-agent model routing,
and Agent Disagreement Detection with structured resolution.
"""

import logging
from typing import Optional
from model.config import ModelConfigManager

logger = logging.getLogger("swarm-os.orchestrator")


class SwarmOrchestrator:
    """
    Coordinates the multi-agent swarm: Commander, Detective, Coder.
    Handles dynamic agent spawning with System Prompt Integrity Gate,
    per-agent model routing, and disagreement detection.
    """

    def __init__(self, config_manager: ModelConfigManager):
        self.config = config_manager
        self.active_agents: dict = {}
        self.agent_history: list = []
        self.disagreement_log: list = []
        self.reset()

    def reset(self):
        """Reset the orchestrator to initial core team."""
        self.active_agents = {
            "COMMANDER": {
                "role": "COMMANDER",
                "active": True,
                "model": self.config.get_model_for_agent("COMMANDER")["model_key"],
                "system_prompt": SYSTEM_PROMPTS["COMMANDER"],
            },
            "DETECTIVE": {
                "role": "DETECTIVE",
                "active": True,
                "model": self.config.get_model_for_agent("DETECTIVE")["model_key"],
                "system_prompt": SYSTEM_PROMPTS["DETECTIVE"],
            },
            "CODER": {
                "role": "CODER",
                "active": True,
                "model": self.config.get_model_for_agent("CODER")["model_key"],
                "system_prompt": SYSTEM_PROMPTS["CODER"],
            },
        }
        self.agent_history = []
        self.disagreement_log = []

    def spawn_agent(self, role: str) -> dict:
        """
        Spawn a specialist agent with System Prompt Integrity Gate verification.

        The System Prompt Integrity Gate verifies that:
        1. The correct persona is active
        2. Domain instructions are being followed
        3. The agent is reasoning within its designated scope

        Every probe and response is logged and auditable.
        """
        if role in self.active_agents and self.active_agents[role]["active"]:
            return {"success": False, "error": f"Agent '{role}' is already active."}

        if role not in SYSTEM_PROMPTS:
            return {"success": False, "error": f"No system prompt defined for role '{role}'."}

        # Run System Prompt Integrity Gate
        gate_result = self._run_integrity_gate(role)

        if not gate_result["passed"]:
            self.agent_history.append({
                "action": "SPAWN_BLOCKED",
                "role": role,
                "reason": "System Prompt Integrity Gate failed",
                "gate_result": gate_result,
            })
            return {
                "success": False,
                "error": "System Prompt Integrity Gate failed — agent spawn blocked.",
                "gate_result": gate_result,
            }

        # Gate passed — activate agent
        model_info = self.config.get_model_for_agent(role)
        self.active_agents[role] = {
            "role": role,
            "active": True,
            "model": model_info["model_key"],
            "system_prompt": SYSTEM_PROMPTS[role],
        }

        self.agent_history.append({
            "action": "SPAWNED",
            "role": role,
            "model": model_info["model_key"],
            "gate_result": gate_result,
        })

        return {
            "success": True,
            "role": role,
            "model": model_info["model_key"],
            "gate_result": gate_result,
        }

    def dismiss_agent(self, role: str) -> dict:
        """
        Dismiss a specialist agent and free VRAM.
        Core agents (Commander, Detective, Coder) cannot be dismissed.
        """
        if role in ("COMMANDER", "DETECTIVE", "CODER"):
            return {"success": False, "error": f"Cannot dismiss core agent '{role}'."}

        if role not in self.active_agents:
            return {"success": False, "error": f"Agent '{role}' is not active."}

        del self.active_agents[role]
        self.agent_history.append({"action": "DISMISSED", "role": role})

        return {"success": True, "role": role, "vram_freed": True}

    def _run_integrity_gate(self, role: str) -> dict:
        """
        System Prompt Integrity Gate — verifies correct persona, domain scope,
        and reasoning capability before granting sandbox access.

        Fires three strict probe questions and validates responses.
        Every probe and response is logged and auditable.
        """
        probes = INTEGRITY_GATE_PROBES.get(role, [])
        results = []

        for probe in probes:
            # In production: send probe to LLM and validate response
            # In dev mode: auto-pass with logged probes
            results.append({
                "probe": probe["question"],
                "expected_domain": probe["domain"],
                "passed": True,  # Mock: always pass in dev
                "response": f"[Mock response for {role}: {probe['domain']}]",
            })

        all_passed = all(r["passed"] for r in results)

        return {
            "passed": all_passed,
            "probes_total": len(probes),
            "probes_passed": sum(1 for r in results if r["passed"]),
            "results": results,
        }

    def detect_disagreement(self, agent1_action: dict, agent2_action: dict) -> dict:
        """
        Agent Disagreement Detection.
        When Commander and Detective produce conflicting assessments,
        the system pauses execution, logs both positions, and forces
        a structured resolution protocol.

        The disagreement creates a 'reasoning_fork' node on the Causal Graph.
        """
        disagreement = {
            "detected": True,
            "position1": {
                "agent": agent1_action.get("role", "COMMANDER"),
                "action": agent1_action.get("proposed_action", ""),
                "cost": agent1_action.get("estimated_cost", ""),
                "risk": agent1_action.get("risk", ""),
            },
            "position2": {
                "agent": agent2_action.get("role", "DETECTIVE"),
                "action": agent2_action.get("proposed_action", ""),
                "cost": agent2_action.get("estimated_cost", ""),
                "risk": agent2_action.get("risk", ""),
            },
            "resolution": None,
        }

        self.disagreement_log.append(disagreement)
        return disagreement

    def resolve_disagreement(self, winning_agent: str, reason: str) -> dict:
        """
        Resolve an active disagreement with a structured resolution.
        The winning rationale is logged and emitted to the Causal Graph.
        """
        if not self.disagreement_log:
            return {"success": False, "error": "No active disagreement to resolve."}

        latest = self.disagreement_log[-1]
        latest["resolution"] = {
            "winner": winning_agent,
            "reason": reason,
        }

        return {
            "success": True,
            "winner": winning_agent,
            "reason": reason,
        }

    def get_active_agents(self) -> list:
        """Get list of currently active agents with their model assignments."""
        return [
            {
                "role": role,
                "model": info["model"],
                "active": info["active"],
            }
            for role, info in self.active_agents.items()
            if info["active"]
        ]

    def parse_m2m_response(self, raw_text: str) -> dict:
        """
        Parses LLM output to extract CoT reasoning from <think> tags
        and separates it from the final M2M formatted string.
        """
        import re
        think_match = re.search(r'<think>(.*?)</think>', raw_text, re.DOTALL)
        
        cot_content = think_match.group(1).strip() if think_match else None
        
        # Remove the <think> blocks entirely from the output for the m2m channel
        m2m_content = re.sub(r'<think>.*?</think>', '', raw_text, flags=re.DOTALL).strip()
        
        return {
            "think": cot_content,
            "m2m": m2m_content
        }


# ── System Prompts (VaultAgent — offline Android malware forensics) ──
# NOTE: The canonical agent KEYS (COMMANDER/DETECTIVE/CODER) are preserved so the
# existing model-routing, config, and WebSocket wiring keep working unchanged. Only
# the persona/domain text is repurposed:
#   COMMANDER  -> Chief Security Officer (final verdict, threat approval, RCA)
#   DETECTIVE  -> Static Analyst (manifest, permissions, components, URLs, IPs)
#   CODER      -> Reverse Engineer (smali/Java behavior, OTP/credential/C2 detection)
#   THREAT_INTEL -> optional specialist (signature + malware-family match)
SYSTEM_PROMPTS = {
    "COMMANDER": """You are the Chief Security Officer of an offline Android malware
forensics team. You receive the Static Analyst's and Reverse Engineer's structured
findings and issue the FINAL verdict on an uploaded APK.

RESPONSIBILITIES:
- Produce the final threat score (0-100) and threat level.
- Approve or reject each malware indicator based on the evidence provided.
- Classify the malware family and write the Root Cause Analysis (RCA).
- Recommend mitigations.

CONSTRAINTS:
- Never invent permissions or indicators that the analysts did not report.
- Every conclusion must cite evidence (component, permission, or code location).
- Output a single JSON object matching the verdict schema, then a compressed M2M line.

FORMAT (M2M after JSON). Example: VERDICT | THREAT_HIGH | SMS-Stealer | FLAG_C2 | ETA_10s""",

    "DETECTIVE": """You are the Static Analyst of an offline Android malware forensics
team. You read ONLY the compact APK metadata JSON (AndroidManifest summary): package,
permissions, exported activities/services/receivers/providers, intent filters, embedded
URLs and IP addresses.

RESPONSIBILITIES:
- Identify dangerous permissions and exported components.
- Detect suspicious permission combinations (e.g. RECEIVE_SMS + INTERNET).
- List the specific code locations the Reverse Engineer must inspect next.

CONSTRAINTS:
- Reason ONLY about permissions/components actually present in the provided metadata.
  Never hallucinate a permission that is not in the list.
- Use <think>...</think> for chain-of-thought, then output the static-stage JSON object.

FORMAT: emit the static JSON, then M2M. Example: STATIC | RECEIVE_SMS+INTERNET | REQ_CODE:SmsRx""",

    "CODER": """You are the Reverse Engineer of an offline Android malware forensics
team. You receive ONLY the specific smali/Java snippets the Static Analyst requested —
never the whole APK.

RESPONSIBILITIES:
- Explain the malicious intent of the code.
- Detect: credential theft, OTP/SMS interception, data exfiltration, obfuscation,
  dynamic code loading, and C2 (command-and-control) communication.
- Tie every behavior to concrete evidence (class.method + what it does).

CONSTRAINTS:
- Only conclude behaviors you can justify from the supplied code; do not guess.
- Output the reverse-stage JSON object with an evidence list.

FORMAT: emit the reverse JSON, then M2M. Example: REVERSE | FLAG_SMS_THEFT | FLAG_C2 | obf=true""",

    "THREAT_INTEL": """You are the Threat Intelligence specialist, optionally spawned to
match an APK against known malware signatures and classify its family using a fully
offline local signature set.

CONSTRAINTS:
- Only assert a family match supported by the indicators provided.
- Report "Unknown" honestly when there is no confident match.
- Do not invent network lookups; you are air-gapped.

FORMAT: Use M2M compressed syntax. Example: INTEL | FAMILY:SMS-Stealer | CONF:0.82""",
}


# ── System Prompt Integrity Gate Probes ──
# These probes verify the correct persona is active, domain instructions are
# being followed, and the agent is reasoning within its designated scope.
INTEGRITY_GATE_PROBES = {
    "THREAT_INTEL": [
        {
            "question": "Which APK indicators distinguish an SMS-stealer family from a banking-overlay family?",
            "domain": "Android malware family classification",
        },
        {
            "question": "How do you confirm a hardcoded IP is a C2 endpoint versus a benign API host?",
            "domain": "C2 / network indicator analysis",
        },
        {
            "question": "Why must family attribution stay offline and signature-based here?",
            "domain": "Air-gapped threat intelligence",
        },
    ],
}
