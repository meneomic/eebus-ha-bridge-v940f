package grpc

import (
	"strings"
	"testing"

	"github.com/enbility/spine-go/model"
)

func TestSpineInventoryAllowlistAndRedaction(t *testing.T) {
	zone := model.LabelType("Rdc")
	label := &model.DeviceClassificationUserDataType{UserLabel: &zone}
	payload, allowed := safeSpineCachedPayload("HeatingZone", "DeviceClassification", model.FunctionTypeDeviceClassificationUserData, label)
	if !allowed {
		t.Fatal("HeatingZone label unexpectedly filtered")
	}
	got := payload.(map[string]string)
	if got["user_label"] != "Rdc" || len(got) != 1 {
		t.Fatalf("unexpected non-minimal label payload: %+v", payload)
	}
	for _, test := range []struct{ entity, feature string; function model.FunctionType }{
		{"DeviceInformation", "DeviceClassification", model.FunctionTypeDeviceClassificationManufacturerData},
		{"HeatingZone", "DeviceClassification", model.FunctionTypeDeviceClassificationManufacturerData},
		{"DeviceInformation", "NodeManagement", model.FunctionTypeNodeManagementDetailedDiscoveryData},
		{"Generic", "Generic", model.FunctionTypeDeviceClassificationUserData},
	} {
		if _, ok := safeSpineCachedPayload(test.entity, test.feature, test.function, map[string]string{"secret":"private"}); ok {
			t.Fatalf("sensitive payload not filtered: %+v", test)
		}
	}
}

func TestSpineInventoryReadOnlyCategories(t *testing.T) {
	allowed := []struct{ feature string; function model.FunctionType }{
		{"Measurement", model.FunctionTypeMeasurementDescriptionListData},
		{"Measurement", model.FunctionTypeMeasurementListData},
		{"Measurement", model.FunctionTypeMeasurementConstraintsListData},
		{"Setpoint", model.FunctionTypeSetpointListData},
		{"HVAC", model.FunctionTypeHvacSystemFunctionSetPointRelationListData},
	}
	for _, item := range allowed {
		data := map[string]any{"id": 7, "unit": "degC", "value": 19.0}
		payload, ok := safeSpineCachedPayload("HVACRoom", item.feature, item.function, data)
		if !ok || payload == nil {
			t.Fatalf("allowlisted cache rejected: %s/%s", item.feature, item.function)
		}
	}
}

func TestSpineAddressNilIsSafe(t *testing.T) {
	if got := spineEntityAddress(nil); got != "?" {
		t.Fatalf("missing entity address: %q", got)
	}
	if got := spineFeatureAddress(nil); got != "?" {
		t.Fatalf("missing feature address: %q", got)
	}
	if strings.Contains(spineFeatureAddress(nil), "SKI") {
		t.Fatal("identity leak")
	}
}
