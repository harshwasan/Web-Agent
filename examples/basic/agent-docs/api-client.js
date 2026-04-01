export class DemoCatalogApi {
  constructor(baseUrl) {
    this.baseUrl = baseUrl || "/demo-api";
  }

  async listProducts(filters) {
    return {
      endpoint: this.baseUrl + "/products",
      method: "GET",
      query: filters || {},
      description: "Returns seeded storefront products for the host page."
    };
  }

  async compareProducts(productIds) {
    return {
      endpoint: this.baseUrl + "/compare",
      method: "POST",
      body: { product_ids: productIds || [] },
      description: "Builds a comparison payload for multiple products."
    };
  }

  async getProduct(productId) {
    return {
      endpoint: this.baseUrl + "/products/" + encodeURIComponent(productId),
      method: "GET",
      description: "Fetches a single product record for detail rendering."
    };
  }

  async listAlternatives(productId) {
    return {
      endpoint: this.baseUrl + "/products/" + encodeURIComponent(productId) + "/alternatives",
      method: "GET",
      description: "Returns products from other brands that can be compared against the seed product."
    };
  }
}
