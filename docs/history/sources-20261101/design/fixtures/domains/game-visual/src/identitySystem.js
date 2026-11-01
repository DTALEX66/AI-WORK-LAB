export function verifyPassengerIdentity(passenger = {}, observation = {}) {
  const conflicts = [];
  if (passenger.badge != null && observation.badge !== passenger.badge) conflicts.push('badge');
  if (Array.isArray(passenger.allowedFloors)
    && !passenger.allowedFloors.map(String).includes(String(observation.requestedFloor))) {
    conflicts.push('floor');
  }
  return {
    valid: conflicts.length === 0,
    conflicts,
    passengerId: passenger.id ?? null,
    verificationPaths: ['cam01', 'protocol'],
  };
}

export function countPassengersForPanel(passengers = []) {
  return passengers.filter(passenger => passenger.countMode !== 'ignore').length;
}
