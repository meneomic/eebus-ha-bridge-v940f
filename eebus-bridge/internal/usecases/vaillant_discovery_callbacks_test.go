package usecases

import (
	"bytes"
	"log"
	"strings"
	"testing"

	eebusapi "github.com/enbility/eebus-go/api"
	spineapi "github.com/enbility/spine-go/api"
	spinemocks "github.com/enbility/spine-go/mocks"
	"github.com/enbility/spine-go/model"
)

// The Vaillant ecoTEC/VR940f provides room-heating SPINE but no MPC. Verify
// that a heating callback can produce the diagnostic inventory on its own,
// that all heat-related wrappers share one device-level dump, and that
// disabling debugging suppresses the dump.
func TestVaillantHeatingCallbacksDumpDiscoveryWithoutMPC(t *testing.T) {
	const ski = "1234567890abcdef1234567890abcdefaabbccdd"

	device := spinemocks.NewDeviceRemoteInterface(t)
	device.EXPECT().Ski().Return(ski).Maybe()
	device.EXPECT().DeviceType().Return((*model.DeviceTypeType)(nil)).Maybe()
	device.EXPECT().Entities().Return([]spineapi.EntityRemoteInterface(nil)).Maybe()
	device.EXPECT().UseCases().Return([]model.UseCaseInformationDataType(nil)).Maybe()

	old := log.Writer()
	var logs bytes.Buffer
	log.SetOutput(&logs)
	t.Cleanup(func() { log.SetOutput(old) })

	(&CRHTConfigurationFacade{debug: true}).HandleEvent(
		ski, device, nil, eebusapi.EventType("unknown"),
	)
	(&RoomHeatingSystemFunctionMonitoring{debug: true}).HandleEvent(
		ski, device, nil, eebusapi.EventType("unknown"),
	)
	(&TemperatureMonitoringWrapper{debug: true}).HandleEvent(
		ski, device, nil, eebusapi.EventType("unknown"),
	)
	output := logs.String()
	if got := strings.Count(output, "[DISCOVERY] device ski="); got != 1 {
		t.Fatalf("discovery dump count = %d, want 1; logs:\n%s", got, output)
	}
	if !strings.Contains(output, "(no use cases advertised yet)") {
		t.Fatalf("unexpected discovery inventory:\n%s", output)
	}

	logs.Reset()
	const otherSki = "1234567890abcdef1234567890abcdefaabbccee"
	(&CRHTConfigurationFacade{debug: false}).HandleEvent(
		otherSki, device, nil, eebusapi.EventType("unknown"),
	)
	(&RoomHeatingSystemFunctionMonitoring{debug: false}).HandleEvent(
		otherSki, device, nil, eebusapi.EventType("unknown"),
	)
	(&TemperatureMonitoringWrapper{debug: false}).HandleEvent(
		otherSki, device, nil, eebusapi.EventType("unknown"),
	)
	if strings.Contains(logs.String(), "[DISCOVERY]") {
		t.Fatalf("discovery logged with diagnostics disabled: %s", logs.String())
	}
}
