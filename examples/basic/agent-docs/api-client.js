export class DemoInventoryApi {
  constructor(baseUrl) {
    this.baseUrl = baseUrl || "/demo-api";
  }

  async listInventory(filters) {
    return {
      endpoint: this.baseUrl + "/inventory",
      method: "GET",
      query: filters || {},
      description: "Returns demo inventory rows for the host page."
    };
  }

  async getSupportSummary() {
    return {
      endpoint: this.baseUrl + "/support/summary",
      method: "GET",
      description: "Returns ticket counts, current alerts, and support notes."
    };
  }

  async openVehicleRecord(vehicleId) {
    return {
      endpoint: this.baseUrl + "/inventory/" + encodeURIComponent(vehicleId),
      method: "GET",
      description: "Fetches a single vehicle record for detail rendering."
    };
  }
}
