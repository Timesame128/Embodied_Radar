from __future__ import annotations

import re


CONFERENCES = {
    "CoRL": {
        "name": "Conference on Robot Learning",
        "aliases": ("Conference on Robot Learning", "CoRL"),
    },
    "ICRA": {
        "name": "IEEE International Conference on Robotics and Automation",
        "aliases": (
            "IEEE International Conference on Robotics and Automation",
            "International Conference on Robotics and Automation",
            "ICRA",
        ),
    },
    "RSS": {
        "name": "Robotics: Science and Systems",
        "aliases": ("Robotics: Science and Systems", "Robotics Science and Systems"),
    },
    "IROS": {
        "name": "IEEE/RSJ International Conference on Intelligent Robots and Systems",
        "aliases": (
            "IEEE/RSJ International Conference on Intelligent Robots and Systems",
            "International Conference on Intelligent Robots and Systems",
            "IROS",
        ),
    },
    "CVPR": {
        "name": "Conference on Computer Vision and Pattern Recognition",
        "aliases": (
            "IEEE/CVF Conference on Computer Vision and Pattern Recognition",
            "Conference on Computer Vision and Pattern Recognition",
            "CVPR",
        ),
    },
    "ICLR": {
        "name": "International Conference on Learning Representations",
        "aliases": ("International Conference on Learning Representations", "ICLR"),
    },
    "NeurIPS": {
        "name": "Conference on Neural Information Processing Systems",
        "aliases": (
            "Conference on Neural Information Processing Systems",
            "Neural Information Processing Systems",
            "Advances in Neural Information Processing Systems",
            "NeurIPS",
            "NIPS",
        ),
    },
    "ICML": {
        "name": "International Conference on Machine Learning",
        "aliases": ("International Conference on Machine Learning", "ICML"),
    },
    "ICCV": {
        "name": "International Conference on Computer Vision",
        "aliases": (
            "IEEE/CVF International Conference on Computer Vision",
            "International Conference on Computer Vision",
            "ICCV",
        ),
    },
}

CONFERENCE_PATTERNS = {
    "CoRL": (
        r"\bcorl\b",
        r"\bconference on robot learning\b",
    ),
    "ICRA": (
        r"\bicra\b",
        r"\binternational conference on robotics and automation\b",
    ),
    "RSS": (
        r"\brobotics:\s*science and systems\b",
        r"\brobotics science and systems\b",
        r"\brss(?:\s+conference)?\s*[\'’]?\d{2,4}\b",
    ),
    "IROS": (
        r"\biros\b",
        r"\binternational conference on intelligent robots and systems\b",
    ),
    "CVPR": (
        r"\bcvpr\b",
        r"\bconference on computer vision and pattern recognition\b",
    ),
    "ICLR": (
        r"\biclr\b",
        r"\binternational conference on learning representations\b",
    ),
    "NeurIPS": (
        r"\bneurips\b",
        r"\bnips(?:\s+conference)?\s*[\'’]?\d{2,4}\b",
        r"\bneural information processing systems\b",
    ),
    "ICML": (
        r"\bicml\b",
        r"\binternational conference on machine learning\b",
    ),
    "ICCV": (
        r"\biccv\b",
        r"\binternational conference on computer vision\b",
    ),
}

SUPPORTED_CONFERENCES = tuple(CONFERENCES)


def detect_conferences(*values: str) -> list[str]:
    text = " ".join(value for value in values if value).lower()
    return [
        conference
        for conference, patterns in CONFERENCE_PATTERNS.items()
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)
    ]
