from embodied_arxiv.classifier import classify


def test_classifies_vla_manipulation():
    categories, evidence = classify(
        "A Vision-Language-Action Model for Robot Manipulation",
        "We train a generalist robot policy for dexterous manipulation.",
    )
    assert "视觉-语言-动作" in categories
    assert "操作与抓取" in categories
    assert evidence


def test_rejects_non_embodied_agent():
    categories, _ = classify(
        "An Agent for Software Engineering",
        "A web agent improves repository issue resolution.",
    )
    assert categories == []


def test_requires_specific_embodied_subcategory():
    categories, _ = classify(
        "Generic Robotics Benchmark",
        "This paper discusses robot datasets without a physical task.",
    )
    assert categories == []


def test_classifies_motor_drive_control_as_its_own_direction():
    categories, evidence = classify(
        "Sensorless Field-Oriented Control of a PMSM Drive",
        "A torque controller improves permanent magnet synchronous motor efficiency.",
    )

    assert "电机与驱动控制" in categories
    assert "运动与控制" not in categories
    assert "pmsm" in evidence


def test_classifies_robot_motor_control_without_locomotion_overlap():
    categories, _ = classify(
        "High-Bandwidth Motor Control for Robotic Actuators",
        "The electric motor drive improves torque tracking for a robot joint.",
    )

    assert "电机与驱动控制" in categories
    assert "运动与控制" not in categories
