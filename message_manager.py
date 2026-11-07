"""
Tactical Datalink & Inter-Agent Messaging Framework (MUM-T).
Provides decentralized message passing, pub-sub broadcasting, and simulated
tactical networking (latency, packet drop under electronic warfare / jamming).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional, Union, Callable
from random import uniform


class MessageTopic(str, Enum):
    """Standardized tactical datalink communication topics."""
    FORMATION_COMMAND = "FORMATION_COMMAND"    # Leader broadcast: formation type, slots, leader pose
    TARGET_ASSIGNMENT = "TARGET_ASSIGNMENT"    # Tactical coordinator: Hungarian threat lock & role
    THREAT_ALERT = "THREAT_ALERT"              # Scout/Wingman alert: hostile contact detected
    STATUS_REPORT = "STATUS_REPORT"            # Wingman report: ammo count, fuel, damage state
    WEAPON_RELEASE = "WEAPON_RELEASE"          # Fire notification: shooter, target_id, weapon, eta
    CASUALTY_ALERT = "CASUALTY_ALERT"          # Wingman/Leader destroyed alert
    HEARTBEAT = "HEARTBEAT"                    # Periodic presence / datalink sync ping


@dataclass
class TacticalMessage:
    """
    Standardized datalink message transmitted over the tactical bus.
    """
    sender_id: Union[str, int]
    recipient_id: Union[str, int]  # Specific agent ID, or 'BROADCAST', 'SWARM', 'ALL'
    topic: Union[MessageTopic, str]
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0
    delivery_time: float = 0.0

    def is_broadcast(self) -> bool:
        """Determines if the message is intended for all network subscribers."""
        return str(self.recipient_id).upper() in ("BROADCAST", "SWARM", "ALL")


class MessageManager(object):
    """
    Central Tactical Datalink Bus mediating inter-agent communications.
    Supports point-to-point dispatch, topic broadcasting, mailboxes (inboxes),
    and optional network degradation modeling (latency and EW packet loss).
    """
    def __init__(self,
                 latency: float = 0.0,
                 packet_loss_rate: float = 0.0,
                 max_history: int = 1000):
        self.latency = latency
        self.packet_loss_rate = packet_loss_rate
        self.max_history = max_history

        # Inboxes indexed by agent_id
        self.inboxes: Dict[Union[str, int], List[TacticalMessage]] = {}
        # Pending messages in transit (for latency simulation)
        self.pending_queue: List[TacticalMessage] = []
        # Audit log of sent messages
        self.history: List[TacticalMessage] = []

    def register_agent(self, agent_id: Union[str, int]):
        """Registers an agent into the tactical datalink network."""
        if agent_id not in self.inboxes:
            self.inboxes[agent_id] = []

    def unregister_agent(self, agent_id: Union[str, int]):
        """Removes an agent from the datalink network."""
        if agent_id in self.inboxes:
            del self.inboxes[agent_id]

    def send_message(self,
                     sender_id: Union[str, int],
                     recipient_id: Union[str, int],
                     topic: Union[MessageTopic, str],
                     payload: Dict[str, Any],
                     current_time: float = 0.0) -> bool:
        """
        Dispatches a message across the datalink bus.
        Subject to packet loss probability under electronic warfare (EW).
        """
        # 1. Check electronic warfare / jamming packet drop
        if self.packet_loss_rate > 0.0 and uniform(0.0, 1.0) < self.packet_loss_rate:
            return False

        topic_str = topic.value if isinstance(topic, MessageTopic) else str(topic)
        msg = TacticalMessage(
            sender_id=sender_id,
            recipient_id=recipient_id,
            topic=topic_str,
            payload=payload,
            timestamp=current_time,
            delivery_time=current_time + self.latency
        )

        # 2. Record telemetry
        self.history.append(msg)
        if len(self.history) > self.max_history:
            self.history.pop(0)

        # 3. Route or queue based on latency
        if self.latency <= 0.0:
            self._route_message(msg)
        else:
            self.pending_queue.append(msg)

        return True

    def broadcast(self,
                  sender_id: Union[str, int],
                  topic: Union[MessageTopic, str],
                  payload: Dict[str, Any],
                  current_time: float = 0.0) -> bool:
        """Helper to broadcast a tactical message to the entire swarm."""
        return self.send_message(
            sender_id=sender_id,
            recipient_id="SWARM",
            topic=topic,
            payload=payload,
            current_time=current_time
        )

    def _route_message(self, msg: TacticalMessage):
        """Routes a message to recipient inbox(es)."""
        if msg.is_broadcast():
            # Deliver to all agents except sender
            for agent_id, inbox in self.inboxes.items():
                if agent_id != msg.sender_id:
                    inbox.append(msg)
        else:
            # Deliver to targeted recipient
            if msg.recipient_id in self.inboxes:
                self.inboxes[msg.recipient_id].append(msg)

    def update(self, current_time: float):
        """
        Processes delayed messages whose delivery time has elapsed.
        Called once per simulation tick.
        """
        if not self.pending_queue:
            return

        ready_indices = []
        for idx, msg in enumerate(self.pending_queue):
            if current_time >= msg.delivery_time:
                self._route_message(msg)
                ready_indices.append(idx)

        # Remove delivered messages in reverse order
        for idx in reversed(ready_indices):
            self.pending_queue.pop(idx)

    def receive_messages(self, agent_id: Union[str, int]) -> List[TacticalMessage]:
        """
        Retrieves and clears all pending messages from an agent's inbox.
        """
        if agent_id not in self.inboxes:
            return []
        msgs = self.inboxes[agent_id]
        self.inboxes[agent_id] = []
        return msgs

    def peek_messages(self, agent_id: Union[str, int]) -> List[TacticalMessage]:
        """Inspects messages without removing them from the inbox."""
        return self.inboxes.get(agent_id, [])

    def clear(self):
        """Resets all inboxes and queues."""
        for inbox in self.inboxes.values():
            inbox.clear()
        self.pending_queue.clear()
        self.history.clear()
