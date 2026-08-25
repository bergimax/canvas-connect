import { beforeEach, describe, expect, it } from "vitest";

import { clearToken, getParticipantId, getToken, setParticipantId, setToken } from "./auth";

beforeEach(() => {
  localStorage.clear();
});

describe("token storage", () => {
  it("returns null when nothing is stored", () => {
    expect(getToken()).toBeNull();
    expect(getParticipantId()).toBeNull();
  });

  it("round-trips a token", () => {
    setToken("abc123");
    expect(getToken()).toBe("abc123");
  });

  it("round-trips a participant id", () => {
    setParticipantId("participant-1");
    expect(getParticipantId()).toBe("participant-1");
  });

  it("clears both the token and the participant id", () => {
    setToken("abc123");
    setParticipantId("participant-1");
    clearToken();
    expect(getToken()).toBeNull();
    expect(getParticipantId()).toBeNull();
  });
});
