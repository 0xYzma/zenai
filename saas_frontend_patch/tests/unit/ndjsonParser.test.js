import { describe, it, expect, vi } from "vitest";
// Assuming the parser logic can be tested by mocking fetch.
// For the sake of the unit test, we will re-implement the stream parser logic here
// to test its chunking ability, or we can mock fetch and call streamAiChat directly.

import { streamAiChat } from "../../src/services/aiInsightsService";

describe("NDJSON Parser (streamAiChat)", () => {
  it("successfully parses chunks split across arbitrary boundaries", async () => {
    // 1. Setup mock readable stream that yields chunks split artificially
    const events = [];
    const encoder = new TextEncoder();
    
    // Original JSONs:
    // {"type":"status","message":"Loading..."}\n
    // {"type":"answer","answer":"Hello world"}\n
    // We split them awkwardly to test the buffer logic.
    const chunks = [
      '{"type":"status"',
      ',"message":"Load',
      'ing..."}\n{"type":"a',
      'nswer","answer":"Hello world"}\n',
      '{"type":"done"}'
    ].map(text => encoder.encode(text));

    let currentChunk = 0;
    const mockReader = {
      read: async () => {
        if (currentChunk < chunks.length) {
          return { done: false, value: chunks[currentChunk++] };
        }
        return { done: true, value: undefined };
      }
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      body: {
        getReader: () => mockReader
      }
    });

    const mockOnEvent = vi.fn((event) => events.push(event));
    
    // 2. Execute
    await streamAiChat({ question: "Test" }, { signal: null, onEvent: mockOnEvent });

    // 3. Verify
    expect(mockOnEvent).toHaveBeenCalledTimes(3);
    expect(events[0]).toEqual({ type: "status", message: "Loading..." });
    expect(events[1]).toEqual({ type: "answer", answer: "Hello world" });
    expect(events[2]).toEqual({ type: "done" });
  });

  it("ignores malformed JSON without throwing or breaking stream", async () => {
    const events = [];
    const encoder = new TextEncoder();
    
    const chunks = [
      '{"type":"status","message":"Ok"}\n',
      '{"badjson: true}\n', // Malformed line
      '{"type":"done"}\n'
    ].map(text => encoder.encode(text));

    let currentChunk = 0;
    const mockReader = {
      read: async () => {
        if (currentChunk < chunks.length) {
          return { done: false, value: chunks[currentChunk++] };
        }
        return { done: true, value: undefined };
      }
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      body: { getReader: () => mockReader }
    });

    await streamAiChat({ question: "Test" }, { signal: null, onEvent: (e) => events.push(e) });

    expect(events).toHaveLength(2);
    expect(events[0].type).toBe("status");
    expect(events[1].type).toBe("done");
  });
});
