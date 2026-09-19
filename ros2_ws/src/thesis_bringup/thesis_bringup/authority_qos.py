"""QoS contracts at the TIM-MARS controller-authority boundary."""

from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)


AUTHORITY_QOS_DEPTH = 10


def target_state_qos() -> QoSProfile:
    """Return the high-rate controller-target state profile."""
    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=AUTHORITY_QOS_DEPTH,
        reliability=ReliabilityPolicy.BEST_EFFORT,
        durability=DurabilityPolicy.VOLATILE,
    )


def authority_status_qos() -> QoSProfile:
    """Return the reliable, non-latched authority-status profile."""
    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=AUTHORITY_QOS_DEPTH,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.VOLATILE,
    )
