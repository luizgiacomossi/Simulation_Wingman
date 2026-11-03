import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
os.environ['SDL_VIDEODRIVER'] = 'dummy'

import time
import pytest
import pygame as pg
from pygame.math import Vector2
from message_manager import MessageManager, TacticalMessage, MessageTopic
from swarm_manager import SwarmManager

def test_registration_and_direct_messaging():
    print("=== [TEST 1] Testing Agent Registration & Point-to-Point Messaging ===")
    bus = MessageManager()
    bus.register_agent("LEADER")
    bus.register_agent("WINGMAN_0")
    bus.register_agent("WINGMAN_1")

    assert "LEADER" in bus.inboxes
    assert "WINGMAN_0" in bus.inboxes

    # Send point-to-point message
    payload = {"role": "INTERCEPTOR", "threat_id": 42}
    success = bus.send_message(
        sender_id="LEADER",
        recipient_id="WINGMAN_0",
        topic=MessageTopic.TARGET_ASSIGNMENT,
        payload=payload,
        current_time=1.5
    )
    assert success is True

    # Check recipient inbox
    inbox_w0 = bus.receive_messages("WINGMAN_0")
    assert len(inbox_w0) == 1
    assert inbox_w0[0].sender_id == "LEADER"
    assert inbox_w0[0].topic == MessageTopic.TARGET_ASSIGNMENT
    assert inbox_w0[0].payload["threat_id"] == 42
    assert inbox_w0[0].timestamp == 1.5

    # Check other inboxes are clean
    assert len(bus.receive_messages("WINGMAN_1")) == 0
    assert len(bus.receive_messages("LEADER")) == 0
    # Inbox should now be empty after receive
    assert len(bus.receive_messages("WINGMAN_0")) == 0
    print("✓ Point-to-point message routing, inbox delivery, and mailbox clearing verified.")

def test_broadcast_messaging():
    print("=== [TEST 2] Testing Datalink Broadcast (SWARM) ===")
    bus = MessageManager()
    bus.register_agent("LEADER")
    bus.register_agent("WINGMAN_0")
    bus.register_agent("WINGMAN_1")
    bus.register_agent("WINGMAN_2")

    formation_payload = {
        "formation_type": "WEDGE",
        "slots": {
            "WINGMAN_0": (500, 300),
            "WINGMAN_1": (450, 350),
            "WINGMAN_2": (450, 250)
        }
    }

    # Leader broadcasts formation command
    bus.broadcast(sender_id="LEADER", topic=MessageTopic.FORMATION_COMMAND, payload=formation_payload, current_time=2.0)

    # Sender must not receive its own broadcast
    assert len(bus.receive_messages("LEADER")) == 0

    # All wingmen must receive the broadcast
    for wid in ["WINGMAN_0", "WINGMAN_1", "WINGMAN_2"]:
        inbox = bus.receive_messages(wid)
        assert len(inbox) == 1
        assert inbox[0].topic == MessageTopic.FORMATION_COMMAND
        assert inbox[0].payload["formation_type"] == "WEDGE"
        assert inbox[0].payload["slots"][wid] is not None
    print("✓ Datalink broadcast delivers simultaneously to all wingmen without self-reflection.")

def test_latency_and_delayed_delivery():
    print("=== [TEST 3] Testing Network Latency Simulation ===")
    bus = MessageManager(latency=0.2)  # 200ms latency
    bus.register_agent("A")
    bus.register_agent("B")

    bus.send_message(sender_id="A", recipient_id="B", topic="PING", payload={"val": 1}, current_time=1.0)

    # At t=1.1s (100ms later), message must still be in transit
    bus.update(current_time=1.1)
    assert len(bus.receive_messages("B")) == 0
    assert len(bus.pending_queue) == 1

    # At t=1.2s (200ms later), message is ready and delivered
    bus.update(current_time=1.2)
    inbox_b = bus.receive_messages("B")
    assert len(inbox_b) == 1
    assert inbox_b[0].payload["val"] == 1
    assert len(bus.pending_queue) == 0
    print("✓ Configurable network latency queue correctly buffers and delivers at target timestamp.")

def test_electronic_warfare_packet_loss():
    print("=== [TEST 4] Testing Electronic Warfare (EW) Jamming Packet Loss ===")
    jammed_bus = MessageManager(packet_loss_rate=1.0)  # 100% jammed
    jammed_bus.register_agent("LEADER")
    jammed_bus.register_agent("WINGMAN_0")

    result = jammed_bus.send_message(
        sender_id="LEADER",
        recipient_id="WINGMAN_0",
        topic="CMD",
        payload={}
    )
    assert result is False
    assert len(jammed_bus.receive_messages("WINGMAN_0")) == 0
    print("✓ Electronic warfare packet loss drops messages under jamming conditions.")

def test_swarm_manager_full_datalink_integration():
    print("=== [TEST 5] Testing Full SwarmManager Datalink Integration (120 frames) ===")
    sm = SwarmManager(window=None)
    sm.create_swarm(num_loyal=6, num_kamikazes=3)

    # Verify datalink registration
    assert sm.message_manager is not None
    assert "LEADER" in sm.message_manager.inboxes
    for i in range(6):
        assert f"WINGMAN_{i}" in sm.message_manager.inboxes

    # Run 120 frames
    t0 = time.time()
    for frame in range(120):
        sm.update([])
    elapsed = time.time() - t0

    # Ensure wingmen received formation coordinates over the datalink bus
    for drone in sm.swarm:
        assert drone.target is not None
        assert getattr(drone, 'message_bus', None) is not None

    print(f"✓ 120 frames executed with full tactical datalink messaging in {elapsed*1000:.1f}ms ({120/elapsed:.0f} FPS).")
    print(f"✓ Total datalink messages transmitted: {len(sm.message_manager.history)}")

if __name__ == "__main__":
    test_registration_and_direct_messaging()
    test_broadcast_messaging()
    test_latency_and_delayed_delivery()
    test_electronic_warfare_packet_loss()
    test_swarm_manager_full_datalink_integration()
    print("\n★★★ ALL TACTICAL DATALINK & MESSAGE BUS TESTS PASSED! ★★★")
