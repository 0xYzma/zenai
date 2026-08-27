import { test, expect } from '@playwright/test';

test.describe('AI Insights E2E Tests', () => {
  // Assuming the user logs in before these tests, or we bypass auth using a setup state
  test.beforeEach(async ({ page }) => {
    // Navigate to the insights page.
    await page.goto('/admin/insights');
    
    // We mock the API responses for predictability
    await page.route('**/api/v1/ai/scope', async (route) => {
      await route.fulfill({ json: { selected_location_id: "loc-123", all_branches_allowed: true, locations: [{ id: "loc-123", name: "Main Branch" }] } });
    });
    await page.route('**/api/v1/ai/usage', async (route) => {
      await route.fulfill({ json: { used: 5, limit: 100 } });
    });
    await page.route('**/api/v1/ai/conversations', async (route) => {
      await route.fulfill({ json: { items: [{ id: "conv-1", title: "Sales Analysis" }] } });
    });
    await page.route('**/api/v1/ai/proactive', async (route) => {
      await route.fulfill({ json: { cards: [] } });
    });
  });

  test('opens the chat interface and displays quota indicator', async ({ page }) => {
    // Verify header exists
    await expect(page.getByRole('heading', { name: /AI Business Insights/i })).toBeVisible();
    
    // Verify quota indicator
    const quota = page.getByRole('status', { name: 'AI usage quota' });
    await expect(quota).toBeVisible();
    await expect(quota).toContainText('5 / 100');
    
    // Verify suggested prompts
    await expect(page.getByRole('group', { name: 'Suggested prompts' })).toBeVisible();
  });

  test('sends a message and waits for the streamed result', async ({ page }) => {
    // Mock the streaming response
    await page.route('**/api/v1/ai/chat', async (route) => {
      // Mocking a readable stream in Playwright can be done by fulfilling with a body string 
      // containing NDJSON lines.
      const body = `{"type":"status","message":"Analyzing..."}\n{"type":"answer","answer":"Here is the sales data."}\n`;
      await route.fulfill({
        status: 200,
        contentType: 'application/x-ndjson',
        body: body
      });
    });

    // Type a question
    const input = page.getByRole('textbox', { name: 'Your message' });
    await input.fill('What are my sales?');
    
    // Send it
    await page.getByRole('button', { name: 'Send' }).click();

    // Verify the user message is rendered
    await expect(page.getByText('What are my sales?')).toBeVisible();

    // Verify the AI response is rendered
    await expect(page.getByText('Here is the sales data.')).toBeVisible();
  });

  test('opens history and switches conversations', async ({ page }) => {
    // Mock getting a specific conversation
    await page.route('**/api/v1/ai/conversations/conv-1', async (route) => {
      await route.fulfill({ 
        json: { 
          id: "conv-1", 
          messages: [
            { role: "user", content: "Previous question" },
            { role: "assistant", content: "Previous answer" }
          ] 
        } 
      });
    });

    // Click the history item
    const historyItem = page.getByRole('option', { name: 'Sales Analysis' });
    await expect(historyItem).toBeVisible();
    await historyItem.click();

    // Verify the conversation loaded
    await expect(page.getByText('Previous question')).toBeVisible();
    await expect(page.getByText('Previous answer')).toBeVisible();
    
    // Start a new chat
    await page.getByRole('button', { name: 'Start new chat' }).click();
    await expect(page.getByText('What would you like to know?')).toBeVisible();
  });
});
