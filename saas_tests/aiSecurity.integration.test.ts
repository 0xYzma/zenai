import assert from "node:assert/strict";
import { describe, it, before, after } from "node:test";
import jwt from "jsonwebtoken";
import type { Server } from "node:http";
import app from "../src/app";
import { pool } from "../src/config/db";

// Assuming SaaS env variables are loaded (e.g. via cross-env or tsx in package.json)
const SERVICE_SECRET = process.env.AI_INTERNAL_SERVICE_KEY || "dummy-secret-key-for-tests-must-be-long-enough";

describe("AI Security and Tenant Isolation Integration", () => {
  let server: Server;
  let port: number;

  before(async () => {
    await new Promise<void>((resolve) => {
      server = app.listen(0, () => {
        const address = server.address();
        port = typeof address === "string" ? 0 : address?.port || 0;
        resolve();
      });
    });
  });

  after(async () => {
    server.close();
    await pool.end(); // close DB connections to let process exit
  });

  const getBaseUrl = () => `http://localhost:${port}/api/v1/ai`;

  // Helper to generate a token with specific claims
  const generateToken = (overrides: Record<string, any> = {}, secret = SERVICE_SECRET, algorithm: jwt.Algorithm = "RS256") => {
    const payload = {
      iss: "nexdokandar-ai",
      aud: "nexdokandar-backend",
      sub: "user-123",
      org_id: "org-123",
      role: "admin",
      allowed_location_ids: ["loc-123"],
      selected_location_id: "loc-123",
      permissions: ["insights", "reports"],
      features: ["ai_features"],
      ...overrides,
    };
    
    // In a real test environment, RS256 requires a private key. 
    // If the system under test verifies RS256, we must sign with an RS256 private key.
    // For test simplicity, we simulate the algorithms here.
    try {
      return jwt.sign(payload, secret, { algorithm, expiresIn: "5m" });
    } catch (e) {
      return "invalid-token";
    }
  };

  describe("Delegation and Service Authentication", () => {
    it("rejects request with missing token", async () => {
      const res = await fetch(`${getBaseUrl()}/tools/sales_summary`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ arguments: {} }),
      });
      assert.equal(res.status, 401);
    });

    it("rejects request with wrong service key", async () => {
      const res = await fetch(`${getBaseUrl()}/tools/sales_summary`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${generateToken({}, "wrong-secret", "HS256")}`
        },
        body: JSON.stringify({ arguments: {} }),
      });
      assert.equal(res.status, 401);
    });

    it("rejects request with wrong issuer or audience", async () => {
      // Typically verified by passport or jwt middleware
      // We assume the test infra would have a valid RS256 key pair if it natively uses RS256.
      // If this throws 401, it passes.
      const res = await fetch(`${getBaseUrl()}/tools/sales_summary`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${generateToken({ iss: "wrong-issuer" }, SERVICE_SECRET, "HS256")}`
        },
        body: JSON.stringify({ arguments: {} }),
      });
      assert.equal(res.status, 401);
    });
  });

  describe("Authorization and Tenant Scope", () => {
    // Note: To make these tests deterministic without mocking the DB entirely, 
    // the system expects DB-backed HTTP tests. 
    // We expect 401/403 for missing claims.

    it("rejects if user lacks insights permission", async () => {
      const res = await fetch(`${getBaseUrl()}/tools/sales_summary`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${generateToken({ permissions: [] }, SERVICE_SECRET, "HS256")}`
        },
        body: JSON.stringify({ arguments: {} }),
      });
      assert.equal(res.status, 403);
    });

    it("rejects if org lacks ai_features plan feature", async () => {
      const res = await fetch(`${getBaseUrl()}/tools/sales_summary`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${generateToken({ features: [] }, SERVICE_SECRET, "HS256")}`
        },
        body: JSON.stringify({ arguments: {} }),
      });
      assert.equal(res.status, 403);
    });

    it("rejects selected location outside allowed locations", async () => {
      const res = await fetch(`${getBaseUrl()}/tools/sales_summary`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${generateToken({ 
            allowed_location_ids: ["loc-1"], 
            selected_location_id: "loc-999" 
          }, SERVICE_SECRET, "HS256")}`
        },
        body: JSON.stringify({ arguments: {} }),
      });
      assert.equal(res.status, 403); // Or 401 depending on middleware
    });
  });

  describe("Curated Tools and Leakage Prevention", () => {
    it("fails closed on unknown tools", async () => {
      const res = await fetch(`${getBaseUrl()}/tools/delete_database`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${generateToken({}, SERVICE_SECRET, "HS256")}`
        },
        body: JSON.stringify({ arguments: {} }),
      });
      // Should not expose stack traces, should be 404 or 400
      assert.equal(res.status, 404);
      const data = await res.json();
      assert.equal(data.success, false);
      assert.ok(!JSON.stringify(data).includes("SELECT")); // No SQL leakage
    });
  });
});
