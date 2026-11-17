package grpc

import (
	"encoding/json"
	"fmt"
	"sort"
	"strings"

	spineapi "github.com/enbility/spine-go/api"
	"github.com/enbility/spine-go/model"
	pb "github.com/volschin/eebus-bridge/gen/proto/eebus/v1"
	"github.com/volschin/eebus-bridge/internal/eebus"
)

// The diagnostic endpoint only inspects copies of already-cached SPINE data:
// it never requests a new subscription, sends a write, or changes pairing.
// A missing cache entry is explicitly distinguished from unsupported SPINE.
const maxSpineInventoryEntities = 32
const maxSpineInventoryFunctions = 256
const maxSpinePayloadBytes = 32768

func spineInventoryDiagnostics(registry *eebus.DeviceRegistry, ski string) *pb.SpineInventoryDiagnostics {
	if registry == nil {
		return nil
	}
	device, ok := registry.GetDevice(ski)
	if !ok {
		return nil
	}
	connected, _, _ := registry.DeviceConnection(ski)
	result := &pb.SpineInventoryDiagnostics{
		Connected: connected,
		ZoneLabel: registry.ZoneLabel(ski),
	}
	// Observation callbacks may be scoped to one use case and leave the
	// registry's entity list incomplete. The remote device, when present,
	// carries the full detailed-discovery list (including HeatingCircuit).
	var entities []spineapi.EntityRemoteInterface
	if device.RemoteDevice != nil {
		entities = device.RemoteDevice.Entities()
	} else {
		for _, observed := range registry.Entities(ski) {
			if observed.Entity != nil {
				entities = append(entities, observed.Entity)
			}
		}
	}
	functionCount := 0
	for _, entity := range entities {
		if entity == nil || len(result.Entities) >= maxSpineInventoryEntities ||
			functionCount >= maxSpineInventoryFunctions {
			break
		}
		entry := &pb.SpineEntityDiagnostics{
			Address: spineEntityAddress(entity.Address()),
			EntityType: string(entity.EntityType()),
		}
		for _, feature := range entity.Features() {
			if feature == nil || functionCount >= maxSpineInventoryFunctions {
				break
			}
			funcs := feature.Operations()
			names := make([]model.FunctionType, 0, len(funcs))
			for name := range funcs {
				names = append(names, name)
			}
			sort.Slice(names, func(i, j int) bool { return names[i] < names[j] })
			for _, name := range names {
				if functionCount >= maxSpineInventoryFunctions {
					break
				}
				op := funcs[name]
				if op == nil {
					continue
				}
				record := &pb.SpineFunctionDiagnostics{
					FeatureAddress: spineFeatureAddress(feature.Address()),
					FeatureType: string(feature.Type()),
					FunctionName: string(name),
					Readable: op.Read(),
					ReadPartial: op.ReadPartial(),
					Writable: op.Write(),
					WritePartial: op.WritePartial(),
				}
				record.CacheState, record.CachedJson = spineCachedFunction(
					entry.EntityType, record.FeatureType, name, record.Readable || record.ReadPartial,
					feature,
				)
				entry.Functions = append(entry.Functions, record)
				functionCount++
			}
		}
		sort.Slice(entry.Functions, func(i, j int) bool {
			a, b := entry.Functions[i], entry.Functions[j]
			if a.FeatureAddress != b.FeatureAddress {
				return a.FeatureAddress < b.FeatureAddress
			}
			return a.FunctionName < b.FunctionName
		})
		result.Entities = append(result.Entities, entry)
	}
	sort.Slice(result.Entities, func(i, j int) bool {
		return result.Entities[i].Address < result.Entities[j].Address
	})
	return result
}

func spineEntityAddress(addr *model.EntityAddressType) string {
	if addr == nil || len(addr.Entity) == 0 {
		return "?"
	}
	parts := make([]string, 0, len(addr.Entity))
	for _, item := range addr.Entity {
		parts = append(parts, fmt.Sprintf("%d", uint(item)))
	}
	return strings.Join(parts, ":")
}

func spineFeatureAddress(addr *model.FeatureAddressType) string {
	if addr == nil {
		return "?"
	}
	parts := make([]string, 0, len(addr.Entity)+1)
	for _, item := range addr.Entity {
		parts = append(parts, fmt.Sprintf("%d", uint(item)))
	}
	if addr.Feature != nil {
		parts = append(parts, fmt.Sprintf("%d", uint(*addr.Feature)))
	}
	if len(parts) == 0 {
		return "?"
	}
	return strings.Join(parts, ":")
}

// Only measurement, setpoint, and HVAC caches contain metadata/data relevant to
// this opt-in diagnostic. Never serialize NodeManagement, ManufacturerData,
// arbitrary vendor features or other possibly identifying/private payloads.
func safeSpineCachedPayload(entityType, featureType string, name model.FunctionType, data any) (any, bool) {
	switch featureType {
	case string(model.FeatureTypeTypeMeasurement):
		return data, strings.HasPrefix(string(name), "measurement")
	case string(model.FeatureTypeTypeSetpoint):
		return data, strings.HasPrefix(string(name), "setpoint")
	case string(model.FeatureTypeTypeHVAC):
		return data, strings.HasPrefix(string(name), "hvac")
	case string(model.FeatureTypeTypeDeviceClassification):
		if name != model.FunctionTypeDeviceClassificationUserData {
			return nil, false
		}
		// The remote may publish user node IDs, descriptions, or serial-like
		// values alongside labels. Extract ONLY the heating-area name.
		if entityType != string(model.EntityTypeTypeHeatingZone) &&
			entityType != string(model.EntityTypeTypeHeatingCircuit) &&
			entityType != string(model.EntityTypeTypeHVACRoom) {
			return nil, false
		}
		value, ok := data.(*model.DeviceClassificationUserDataType)
		if !ok || value.UserLabel == nil {
			return map[string]string{}, true
		}
		return map[string]string{"user_label": string(*value.UserLabel)}, true
	default:
		return nil, false
	}
}

func spineCachedFunction(
	entityType, featureType string, name model.FunctionType, readable bool,
	feature spineapi.FeatureRemoteInterface,
) (string, string) {
	if !readable {
		return "not_readable", ""
	}
	// Check the allowlist BEFORE touching the cache to keep secret-bearing
	// feature data entirely out of the inspection path.
	if _, safe := safeSpineCachedPayload(entityType, featureType, name, nil); !safe {
		// The classification reader still needs data to check the type, so
		// its allowlisting is evaluated by function and entity below.
		return "skipped_sensitive", ""
	}
	data := feature.DataCopy(name)
	if data == nil {
		return "not_cached", ""
	}
	payload, safe := safeSpineCachedPayload(entityType, featureType, name, data)
	if !safe {
		return "skipped_sensitive", ""
	}
	serialized, err := json.Marshal(payload)
	if err != nil {
		return "invalid_cache_data", ""
	}
	if len(serialized) > maxSpinePayloadBytes {
		return "oversized", ""
	}
	return "cached", string(serialized)
}
