from __future__ import annotations

import re


CATEGORY_RULES = {
    "视觉-语言-动作": [
        "vision-language-action",
        "vision language action",
        "vla model",
        "multimodal action",
        "language-conditioned robot",
        "robot foundation model",
        "generalist robot",
    ],
    "操作与抓取": [
        "robot manipulation",
        "dexterous manipulation",
        "grasping",
        "grasp planning",
        "bimanual",
        "tool use",
        "object manipulation",
        "mobile manipulation",
    ],
    "导航与探索": [
        "embodied navigation",
        "visual navigation",
        "vision-language navigation",
        "robot navigation",
        "object navigation",
        "nav2",
        "slam",
        "exploration",
    ],
    "运动与控制": [
        "robot locomotion",
        "legged robot",
        "humanoid",
        "whole-body control",
        "quadruped",
        "motion imitation",
    ],
    "电机与驱动控制": [
        "motor control",
        "electric motor",
        "motor drive",
        "servo motor",
        "servo drive",
        "field-oriented control",
        "field oriented control",
        "direct torque control",
        "torque control",
        "current control",
        "sensorless control",
        "permanent magnet synchronous motor",
        "pmsm",
        "brushless dc motor",
        "bldc",
    ],
    "具身感知": [
        "embodied perception",
        "robot perception",
        "active perception",
        "tactile sensing",
        "visuotactile",
        "3d scene understanding",
        "spatial reasoning",
        "affordance",
    ],
    "具身智能体": [
        "embodied agent",
        "embodied ai",
        "embodied intelligence",
        "robot agent",
        "interactive agent",
        "physical agent",
        "agentic robot",
    ],
    "世界模型与仿真": [
        "world model",
        "robot simulation",
        "sim-to-real",
        "digital twin",
        "generative simulation",
        "physics-based simulation",
        "robot learning environment",
    ],
    "人机交互": [
        "human-robot interaction",
        "human robot interaction",
        "robot collaboration",
        "social robot",
        "teleoperation",
        "human demonstration",
        "learning from demonstration",
    ],
}

CORE_TERMS = {
    "robot",
    "robotic",
    "embodied",
    "manipulation",
    "navigation",
    "locomotion",
    "humanoid",
    "grasping",
    "physical agent",
    "motor control",
    "electric motor",
    "motor drive",
    "servo motor",
    "servo drive",
    "field-oriented control",
    "field oriented control",
    "direct torque control",
    "permanent magnet synchronous motor",
    "pmsm",
    "brushless dc motor",
    "bldc",
}

NEGATIVE_CONTEXTS = {
    "financial agent",
    "software engineering agent",
    "web agent",
    "recommendation system",
    "molecular",
}


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower().replace("_", " ")).strip()


def classify(title: str, summary: str) -> tuple[list[str], list[str]]:
    text = normalize_text(f"{title} {summary}")
    if any(term in text for term in NEGATIVE_CONTEXTS):
        return [], []

    matched_core = [term for term in CORE_TERMS if term in text]
    categories: list[str] = []
    evidence: list[str] = []
    for category, terms in CATEGORY_RULES.items():
        hits = [term for term in terms if term in text]
        if hits:
            categories.append(category)
            evidence.extend(hits[:2])

    # Category membership alone is too broad; require physical/robotic context.
    if not matched_core or not categories:
        return [], []
    return categories, sorted(set(evidence + matched_core))[:8]


def core_evidence(title: str, summary: str) -> list[str]:
    text = normalize_text(f"{title} {summary}")
    if any(term in text for term in NEGATIVE_CONTEXTS):
        return []
    return sorted(term for term in CORE_TERMS if term in text)
