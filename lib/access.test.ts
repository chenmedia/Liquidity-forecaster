import { describe, expect, it } from "vitest";
import { isAllowedEmail } from "./access";

describe("isAllowedEmail", () => {
  it("allows the configured domain (case-insensitive)", () => {
    expect(isAllowedEmail("kai@chenmedia.no")).toBe(true);
    expect(isAllowedEmail("Kai@ChenMedia.NO")).toBe(true);
  });

  it("rejects other domains", () => {
    expect(isAllowedEmail("kai@gmail.com")).toBe(false);
    expect(isAllowedEmail("kai@notchenmedia.no")).toBe(false);
    expect(isAllowedEmail("kai@chenmedia.no.evil.com")).toBe(false);
  });

  it("rejects missing or malformed emails", () => {
    expect(isAllowedEmail(null)).toBe(false);
    expect(isAllowedEmail(undefined)).toBe(false);
    expect(isAllowedEmail("not-an-email")).toBe(false);
    expect(isAllowedEmail("")).toBe(false);
  });

  it("honours an explicit domain argument", () => {
    expect(isAllowedEmail("a@example.com", "example.com")).toBe(true);
    expect(isAllowedEmail("a@chenmedia.no", "example.com")).toBe(false);
  });
});
