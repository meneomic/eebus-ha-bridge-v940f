package eebus_test

import (
	"fmt"
	"testing"
	"time"

	"github.com/volschin/eebus-bridge/internal/eebus"
)

func newRoomHeatingOnlyRegistry() (*eebus.DeviceRegistry, *fakeClock) {
	clock := &fakeClock{now: time.Date(2026, 11, 15, 11, 0, 0, 0, time.UTC)}
	registry := eebus.NewDeviceRegistryWithClock(clock)
	const ski = "AA11"
	registry.MarkConnected(ski)
	registry.RecordCapabilitySupport(ski, eebus.CapabilityMonitoring, false)
	registry.RecordCapabilitySupport(ski, eebus.CapabilityRoomHeating, true)
	registry.RecordCapabilityRead(ski, eebus.CapabilityRoomHeating, nil)
	return registry, clock
}

func TestRoomHeatingOnlyDeviceDoesNotTriggerMPCRecovery(t *testing.T) {
	registry, clock := newRoomHeatingOnlyRegistry()
	clock.now = clock.now.Add(12 * time.Minute)

	if got := registry.StaleDevices(10*time.Minute, 2*time.Minute); len(got) != 0 {
		t.Fatalf("unsupported MPC triggered stale recovery despite room heating: %v", got)
	}
	health, ok := registry.DeviceHealth("AA11")
	if !ok || !health.MonitoringNotRequired {
		t.Fatalf("room heating only device should not require MPC monitoring: %+v", health)
	}
	controller := eebus.NewRecoverySupervisor(registry, nil, eebus.RecoveryConfig{
		StaleThreshold: 10 * time.Minute, GracePeriod: 2 * time.Minute,
		BaseBackoff: 2 * time.Minute, MaxBackoff: 8 * time.Minute, MaxAttempts: 3,
	})
	if result := controller.Tick(clock.now); result.RestartRequired {
		t.Fatalf("room-heating-only device caused restart: %+v", result)
	}
	if state := controller.Snapshot("AA11", clock.now).State; state != eebus.RecoveryStateHealthy {
		t.Fatalf("room-heating-only device state = %s, want healthy", state)
	}
}

func TestMPCWatchdogStillAppliesWhenRemoteReAdvertisesMonitoring(t *testing.T) {
	registry, clock := newRoomHeatingOnlyRegistry()
	clock.now = clock.now.Add(12 * time.Minute)
	registry.RecordCapabilitySupport("AA11", eebus.CapabilityMonitoring, true)

	if got := registry.StaleDevices(10*time.Minute, 2*time.Minute); len(got) != 1 || got[0] != "AA11" {
		t.Fatalf("MPC advertised without monitoring success must be stale: %v", got)
	}
	if health, _ := registry.DeviceHealth("AA11"); health.MonitoringNotRequired {
		t.Fatalf("MPC advertised but watchdog exemption remains: %+v", health)
	}
}

func TestMPCWatchdogNotSkippedWithoutUsableRoomHeating(t *testing.T) {
	registry, clock := newRoomHeatingOnlyRegistry()
	clock.now = clock.now.Add(12 * time.Minute)
	registry.RecordCapabilityRead("AA11", eebus.CapabilityRoomHeating, fmt.Errorf("temporary heating read failure"))
	if got := registry.StaleDevices(10*time.Minute, 2*time.Minute); len(got) != 1 || got[0] != "AA11" {
		t.Fatalf("room-heating capability unavailable must not disable watchdog: %v", got)
	}
}

func TestRequiredHeartbeatOverridesRoomHeatingOnlyExemption(t *testing.T) {
	registry, clock := newRoomHeatingOnlyRegistry()
	registry.RecordCapabilitySupport("AA11", eebus.CapabilityHeartbeat, true)
	clock.now = clock.now.Add(12 * time.Minute)

	if got := registry.StaleDevices(10*time.Minute, 2*time.Minute); len(got) != 1 || got[0] != "AA11" {
		t.Fatalf("required EEBUS heartbeat must stay monitored: %v", got)
	}
	if health, _ := registry.DeviceHealth("AA11"); health.MonitoringNotRequired {
		t.Fatalf("heartbeat-required device incorrectly exempted: %+v", health)
	}
}

func TestRoomHeatingOnlyCapabilityCanResolvePriorRecovery(t *testing.T) {
	clock := &fakeClock{now: time.Date(2026, 11, 15, 11, 0, 0, 0, time.UTC)}
	registry := eebus.NewDeviceRegistryWithClock(clock)
	registry.MarkConnected("AA11")
	controller := eebus.NewRecoverySupervisor(registry, nil, eebus.RecoveryConfig{
		StaleThreshold: 10 * time.Minute, GracePeriod: 2 * time.Minute,
		BaseBackoff: 2 * time.Minute, MaxBackoff: 8 * time.Minute, MaxAttempts: 3,
	})
	clock.now = clock.now.Add(3 * time.Minute)
	controller.Tick(clock.now)
	if state := controller.Snapshot("AA11", clock.now).State; state != eebus.RecoveryStateGracePeriod {
		t.Fatalf("initial recovery state = %s, want grace", state)
	}
	registry.RecordCapabilitySupport("AA11", eebus.CapabilityMonitoring, false)
	registry.RecordCapabilitySupport("AA11", eebus.CapabilityRoomHeating, true)
	registry.RecordCapabilityRead("AA11", eebus.CapabilityRoomHeating, nil)
	controller.Tick(clock.now)
	snapshot := controller.Snapshot("AA11", clock.now)
	if snapshot.State != eebus.RecoveryStateHealthy || snapshot.Attempts != 0 {
		t.Fatalf("confirmed room-heating-only device was not restored to healthy: %+v", snapshot)
	}
}
